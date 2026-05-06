"""
CuidaFamília — Executor de Tools

Responsabilidade única: receber a decisão do LLM sobre qual tool chamar
e executar a operação correspondente no banco de dados.

Padrão: Command Pattern — cada tool é um handler isolado e testável.
"""

import json
from datetime import datetime, timedelta, timezone
from src.services import supabase_service as db
from src.utils.logger import get_logger, log_erro

logger = get_logger("tools.executor")


async def executar_tool(
    nome_tool: str,
    argumentos: dict,
    cuidador_id: str,
    pessoa_cuidada_id: str | None = None,
) -> dict:
    """
    Dispatcher central. Recebe o nome da tool e seus argumentos,
    delega para o handler correto e retorna o resultado.

    Retorna: {"sucesso": bool, "resultado": str, "dados": dict}
    """
    handlers = {
        "log_event": _handler_log_event,
        "schedule_checkin": _handler_schedule_checkin,
        "get_recent_events": _handler_get_recent_events,
    }

    handler = handlers.get(nome_tool)
    if not handler:
        log_erro("tool_desconhecida", {"nome": nome_tool}, cuidador_id)
        return {
            "sucesso": False,
            "resultado": f"Tool '{nome_tool}' não reconhecida.",
            "dados": {},
        }

    try:
        resultado = await handler(argumentos, cuidador_id, pessoa_cuidada_id)
        logger.info(f"Tool '{nome_tool}' executada com sucesso → {cuidador_id[:8]}...")
        return resultado

    except Exception as e:
        log_erro(f"tool_falhou_{nome_tool}", {"erro": str(e), "args": argumentos}, cuidador_id)
        return {
            "sucesso": False,
            "resultado": f"Erro ao executar '{nome_tool}': {str(e)}",
            "dados": {},
        }


# ── Handler: log_event ───────────────────────────────────────────────────────

async def _handler_log_event(
    args: dict,
    cuidador_id: str,
    pessoa_cuidada_id: str | None,
) -> dict:
    """Registra um evento de saúde no banco."""
    tipo = args["tipo"]
    descricao = args["descricao"]
    severidade = args.get("severidade", "normal")
    dados_estruturados = args.get("dados_estruturados", {})

    sb = db.get_supabase()
    resultado = sb.table("eventos_saude").insert({
        "cuidador_id": cuidador_id,
        "pessoa_cuidada_id": pessoa_cuidada_id,
        "tipo": tipo,
        "severidade": severidade,
        "descricao": descricao,
        "dados_estruturados": dados_estruturados,
        "origem": "conversa",
        "registrado_automaticamente": True,
    }).execute()

    evento_id = resultado.data[0]["id"] if resultado.data else None

    # Se severidade for "atencao" ou "urgente", salva também na memória
    if severidade in ("atencao", "urgente"):
        db.salvar_memoria(
            cuidador_id,
            f"ultimo_evento_{severidade}",
            f"{descricao} ({datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M')})"
        )

    mensagem_confirmacao = {
        "sintoma": f"📋 Sintoma registrado: {descricao}",
        "medicao": f"📊 Medição registrada: {descricao}",
        "crise": f"⚠️ Crise registrada: {descricao}",
        "bem_estar": f"💙 Bem-estar registrado: {descricao}",
        "outro": f"📝 Evento registrado: {descricao}",
    }.get(tipo, f"✅ Evento registrado: {descricao}")

    return {
        "sucesso": True,
        "resultado": mensagem_confirmacao,
        "dados": {"evento_id": evento_id, "tipo": tipo, "severidade": severidade},
    }


# ── Handler: schedule_checkin ────────────────────────────────────────────────

async def _handler_schedule_checkin(
    args: dict,
    cuidador_id: str,
    pessoa_cuidada_id: str | None,
) -> dict:
    """Cria uma rotina de check-in automático."""
    tipo = args["tipo"]
    descricao = args["descricao"]
    horario_str = args["horario"]  # "HH:MM"
    dias_semana = args.get("dias_semana", "todos")

    # Valida e converte horário
    try:
        hora, minuto = horario_str.split(":")
        horario_time = f"{int(hora):02d}:{int(minuto):02d}:00"
    except (ValueError, AttributeError):
        return {
            "sucesso": False,
            "resultado": "Horário inválido. Use o formato HH:MM (ex: 08:00).",
            "dados": {},
        }

    # Calcula o próximo envio
    proximo_envio = _calcular_proximo_envio(horario_str, dias_semana)

    sb = db.get_supabase()

    # Verifica se já existe rotina igual para não duplicar
    existente = sb.table("rotinas_checkin") \
        .select("id") \
        .eq("cuidador_id", cuidador_id) \
        .eq("tipo", tipo) \
        .eq("horario", horario_time) \
        .eq("ativa", True) \
        .execute()

    if existente.data:
        return {
            "sucesso": True,
            "resultado": f"✅ Já existe um lembrete de {descricao} às {horario_str}. Está ativo!",
            "dados": {"rotina_id": existente.data[0]["id"], "duplicado": True},
        }

    resultado = sb.table("rotinas_checkin").insert({
        "cuidador_id": cuidador_id,
        "pessoa_cuidada_id": pessoa_cuidada_id,
        "tipo": tipo,
        "descricao": descricao,
        "horario": horario_time,
        "dias_semana": dias_semana,
        "ativa": True,
        "proximo_envio": proximo_envio.isoformat(),
    }).execute()

    rotina_id = resultado.data[0]["id"] if resultado.data else None

    dias_label = {
        "todos": "todos os dias",
        "seg-sex": "de segunda a sexta",
        "sab-dom": "nos fins de semana",
    }.get(dias_semana, dias_semana)

    return {
        "sucesso": True,
        "resultado": (
            f"⏰ Lembrete criado! Vou te avisar sobre '{descricao}' "
            f"às {horario_str} {dias_label}."
        ),
        "dados": {
            "rotina_id": rotina_id,
            "proximo_envio": proximo_envio.isoformat(),
        },
    }


# ── Handler: get_recent_events ───────────────────────────────────────────────

async def _handler_get_recent_events(
    args: dict,
    cuidador_id: str,
    pessoa_cuidada_id: str | None,
) -> dict:
    """Recupera eventos recentes para contexto do LLM."""
    janela_dias = min(int(args.get("janela_dias", 7)), 90)
    tipo_filtro = args.get("tipo_filtro", "todos")

    desde = datetime.now(timezone.utc) - timedelta(days=janela_dias)

    sb = db.get_supabase()
    query = sb.table("eventos_saude") \
        .select("tipo, severidade, descricao, created_at") \
        .eq("cuidador_id", cuidador_id) \
        .gte("created_at", desde.isoformat()) \
        .order("created_at", desc=False)

    if tipo_filtro != "todos":
        query = query.eq("tipo", tipo_filtro)

    resultado = query.limit(20).execute()
    eventos = resultado.data or []

    if not eventos:
        label_dias = "hoje" if janela_dias == 1 else f"nos últimos {janela_dias} dias"
        return {
            "sucesso": True,
            "resultado": f"Nenhum evento registrado {label_dias}.",
            "dados": {"eventos": [], "total": 0},
        }

    # Formata para o LLM consumir
    linhas = []
    for ev in eventos:
        data_br = _formatar_data_br(ev["created_at"])
        emoji = {"sintoma": "🤒", "medicao": "📊", "crise": "⚠️", "bem_estar": "💙"}.get(ev["tipo"], "📋")
        severidade_label = {"atencao": " ⚠️", "urgente": " 🚨"}.get(ev["severidade"], "")
        linhas.append(f"{emoji} [{data_br}] {ev['descricao']}{severidade_label}")

    resumo = "\n".join(linhas)
    label_dias = "hoje" if janela_dias == 1 else f"nos últimos {janela_dias} dias"

    return {
        "sucesso": True,
        "resultado": f"Eventos registrados {label_dias}:\n{resumo}",
        "dados": {"eventos": eventos, "total": len(eventos)},
    }


# ── Utilitários ──────────────────────────────────────────────────────────────

def _calcular_proximo_envio(horario_str: str, dias_semana: str) -> datetime:
    """Calcula o próximo datetime de envio baseado no horário e recorrência."""
    hora, minuto = map(int, horario_str.split(":"))
    agora = datetime.now(timezone.utc)

    # Ajusta para horário de Brasília (UTC-3)
    agora_br = agora - timedelta(hours=3)

    candidato = agora_br.replace(hour=hora, minute=minuto, second=0, microsecond=0)
    if candidato <= agora_br:
        candidato += timedelta(days=1)

    # Ajusta para dias da semana se necessário
    if dias_semana == "seg-sex":
        while candidato.weekday() >= 5:  # 5=sab, 6=dom
            candidato += timedelta(days=1)
    elif dias_semana == "sab-dom":
        while candidato.weekday() < 5:
            candidato += timedelta(days=1)

    # Reconverte para UTC
    return candidato + timedelta(hours=3)


def _formatar_data_br(iso_str: str) -> str:
    """Converte ISO datetime para formato brasileiro legível."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        dt_br = dt - timedelta(hours=3)
        return dt_br.strftime("%d/%m %H:%M")
    except Exception:
        return iso_str[:10]
