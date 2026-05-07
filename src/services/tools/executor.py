"""
CuidaFamília — Executor de Tools

Semana 1+2: log_event, schedule_checkin, get_recent_events
Semana 3:   create_care_plan, get_care_plan, update_care_plan, update_routine

Padrão: Command Pattern — cada tool é um handler isolado e testável.
"""

import json
from datetime import datetime, timedelta, timezone
from src.services import supabase_service as db
from src.services import plan_service
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
        # Semana 1+2
        "log_event": _handler_log_event,
        "schedule_checkin": _handler_schedule_checkin,
        "get_recent_events": _handler_get_recent_events,
        # Semana 3
        "create_care_plan": _handler_create_care_plan,
        "get_care_plan": _handler_get_care_plan,
        "update_care_plan": _handler_update_care_plan,
        "update_routine": _handler_update_routine,
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
        logger.info(f"Tool '{nome_tool}' executada → {cuidador_id[:8]}...")
        return resultado
    except Exception as e:
        log_erro(f"tool_falhou_{nome_tool}", {"erro": str(e), "args": argumentos}, cuidador_id)
        return {
            "sucesso": False,
            "resultado": f"Erro ao executar '{nome_tool}': {str(e)}",
            "dados": {},
        }


# ── Handler: log_event ───────────────────────────────────────────────────────

async def _handler_log_event(args, cuidador_id, pessoa_cuidada_id):
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

    if severidade in ("atencao", "urgente"):
        db.salvar_memoria(
            cuidador_id,
            f"ultimo_evento_{severidade}",
            f"{descricao} ({datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M')})"
        )

    confirmacao = {
        "sintoma": f"📋 Sintoma registrado: {descricao}",
        "medicao": f"📊 Medição registrada: {descricao}",
        "crise": f"⚠️ Crise registrada: {descricao}",
        "bem_estar": f"💙 Bem-estar registrado: {descricao}",
        "outro": f"📝 Evento registrado: {descricao}",
    }.get(tipo, f"✅ Evento registrado: {descricao}")

    return {
        "sucesso": True,
        "resultado": confirmacao,
        "dados": {"evento_id": evento_id, "tipo": tipo, "severidade": severidade},
    }


# ── Handler: schedule_checkin ────────────────────────────────────────────────

async def _handler_schedule_checkin(args, cuidador_id, pessoa_cuidada_id):
    tipo = args["tipo"]
    descricao = args["descricao"]
    horario_str = args["horario"]
    dias_semana = args.get("dias_semana", "todos")

    try:
        hora, minuto = horario_str.split(":")
        horario_time = f"{int(hora):02d}:{int(minuto):02d}:00"
    except (ValueError, AttributeError):
        return {
            "sucesso": False,
            "resultado": "Horário inválido. Use o formato HH:MM (ex: 08:00).",
            "dados": {},
        }

    proximo_envio = _calcular_proximo_envio(horario_str, dias_semana)

    # Verifica se é horário passado de hoje → informa claramente
    agora_br = datetime.now(timezone.utc) - timedelta(hours=3)
    horario_hoje = agora_br.replace(
        hour=int(hora), minute=int(minuto), second=0, microsecond=0
    )
    primeiro_disparo_amanha = horario_hoje < agora_br

    sb = db.get_supabase()
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
            "resultado": f"✅ Já existe um lembrete de '{descricao}' às {horario_str}. Está ativo!",
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

    # Mensagem clara sobre quando será o primeiro disparo
    aviso_primeiro = (
        f" O primeiro lembrete será *amanhã* às {horario_str}."
        if primeiro_disparo_amanha else ""
    )

    return {
        "sucesso": True,
        "resultado": (
            f"⏰ Lembrete criado! Vou te avisar sobre '{descricao}' "
            f"às {horario_str} {dias_label}.{aviso_primeiro}"
        ),
        "dados": {
            "rotina_id": rotina_id,
            "proximo_envio": proximo_envio.isoformat(),
            "primeiro_disparo_amanha": primeiro_disparo_amanha,
        },
    }


# ── Handler: get_recent_events ───────────────────────────────────────────────

async def _handler_get_recent_events(args, cuidador_id, pessoa_cuidada_id):
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
        label = "hoje" if janela_dias == 1 else f"nos últimos {janela_dias} dias"
        return {"sucesso": True, "resultado": f"Nenhum evento registrado {label}.", "dados": {"eventos": [], "total": 0}}

    linhas = []
    for ev in eventos:
        data_br = _formatar_data_br(ev["created_at"])
        emoji = {"sintoma": "🤒", "medicao": "📊", "crise": "⚠️", "bem_estar": "💙"}.get(ev["tipo"], "📋")
        sev = {"atencao": " ⚠️", "urgente": " 🚨"}.get(ev["severidade"], "")
        linhas.append(f"{emoji} [{data_br}] {ev['descricao']}{sev}")

    label = "hoje" if janela_dias == 1 else f"nos últimos {janela_dias} dias"
    return {
        "sucesso": True,
        "resultado": f"Eventos registrados {label}:\n" + "\n".join(linhas),
        "dados": {"eventos": eventos, "total": len(eventos)},
    }


# ── Handler: create_care_plan ────────────────────────────────────────────────

async def _handler_create_care_plan(args, cuidador_id, pessoa_cuidada_id):
    """Cria o plano de cuidado personalizado."""
    objetivo_primario = args["objetivo_primario"]
    objetivos_secundarios = args.get("objetivos_secundarios", [])
    rotinas_recomendadas = args.get("rotinas_recomendadas", [])
    alertas_relevantes = args.get("alertas_relevantes", [])

    # Monta contexto clínico a partir da memória atual
    memoria = db.buscar_memoria(cuidador_id)
    contexto_clinico = {
        "medicamentos": memoria.get("medicamentos", ""),
        "condicoes_saude": memoria.get("condicoes_saude", ""),
        "alergias": memoria.get("alergias", ""),
        "gerado_em": datetime.now(timezone.utc).isoformat(),
    }

    plano = plan_service.criar_plano(
        cuidador_id=cuidador_id,
        pessoa_cuidada_id=pessoa_cuidada_id,
        objetivo_primario=objetivo_primario,
        objetivos_secundarios=objetivos_secundarios,
        rotinas_recomendadas=rotinas_recomendadas,
        alertas_relevantes=alertas_relevantes,
        contexto_clinico=contexto_clinico,
    )

    # Formata o plano para apresentar ao cuidador
    rotinas_ativas = plan_service.buscar_rotinas_ativas(cuidador_id)
    plano_formatado = plan_service.formatar_plano_para_cuidador(plano, rotinas_ativas)

    # Identifica rotinas sugeridas que ainda não existem
    rotinas_novas = _filtrar_rotinas_novas(rotinas_recomendadas, rotinas_ativas)
    sugestao = ""
    if rotinas_novas:
        nomes = [f"'{r['descricao']}' às {r['horario_sugerido']}" for r in rotinas_novas[:3]]
        sugestao = (
            f"\n\n💡 Posso criar automaticamente os seguintes lembretes:\n"
            + "\n".join(f"  • {n}" for n in nomes)
            + "\n\nQuer que eu ative todos? Responda *sim* para confirmar."
        )

    return {
        "sucesso": True,
        "resultado": plano_formatado + sugestao,
        "dados": {
            "plano_id": plano["id"],
            "rotinas_sugeridas": rotinas_novas,
        },
    }


# ── Handler: get_care_plan ───────────────────────────────────────────────────

async def _handler_get_care_plan(args, cuidador_id, pessoa_cuidada_id):
    """Recupera e formata o plano de cuidado atual."""
    incluir_rotinas = args.get("incluir_rotinas", True)

    plano = plan_service.buscar_plano_ativo(cuidador_id)

    if not plano:
        return {
            "sucesso": True,
            "resultado": (
                "Ainda não criamos um Plano de Cuidado para a sua familiar. "
                "Com base nas informações que já tenho, posso criar um agora. Quer que eu faça isso?"
            ),
            "dados": {"tem_plano": False},
        }

    rotinas_ativas = plan_service.buscar_rotinas_ativas(cuidador_id) if incluir_rotinas else []
    plano_formatado = plan_service.formatar_plano_para_cuidador(plano, rotinas_ativas)

    return {
        "sucesso": True,
        "resultado": plano_formatado,
        "dados": {
            "tem_plano": True,
            "plano_id": plano["id"],
            "versao": plano.get("versao", 1),
        },
    }


# ── Handler: update_care_plan ────────────────────────────────────────────────

async def _handler_update_care_plan(args, cuidador_id, pessoa_cuidada_id):
    """Atualiza um campo do plano de cuidado."""
    campo = args["campo"]
    novo_valor = args["novo_valor"]
    motivo = args["motivo"]

    plano = plan_service.buscar_plano_ativo(cuidador_id)
    if not plano:
        return {
            "sucesso": False,
            "resultado": "Não encontrei um plano de cuidado ativo. Podemos criar um agora, se quiser.",
            "dados": {},
        }

    plan_service.atualizar_plano(
        cuidador_id=cuidador_id,
        plano_id=plano["id"],
        campo=campo,
        novo_valor=novo_valor,
        motivo=motivo,
    )

    campo_label = {
        "objetivo_primario": "objetivo principal",
        "objetivos_secundarios": "objetivos secundários",
        "rotinas_recomendadas": "rotinas recomendadas",
        "alertas_relevantes": "alertas",
    }.get(campo, campo)

    return {
        "sucesso": True,
        "resultado": f"✅ Plano atualizado! O campo '{campo_label}' foi ajustado. Motivo: {motivo}",
        "dados": {"plano_id": plano["id"], "campo_atualizado": campo},
    }


# ── Handler: update_routine ──────────────────────────────────────────────────

async def _handler_update_routine(args, cuidador_id, pessoa_cuidada_id):
    """Atualiza ou desativa uma rotina existente."""
    descricao_busca = args["descricao_rotina"]
    novo_horario = args.get("novo_horario")
    nova_descricao = args.get("nova_descricao")
    ativa = args.get("ativa")
    motivo = args.get("motivo", "Solicitado pelo cuidador")

    return plan_service.atualizar_rotina(
        cuidador_id=cuidador_id,
        descricao_busca=descricao_busca,
        novo_horario=novo_horario,
        nova_descricao=nova_descricao,
        ativa=ativa,
        motivo=motivo,
    )


# ── Utilitários ──────────────────────────────────────────────────────────────

def _filtrar_rotinas_novas(
    rotinas_recomendadas: list[dict],
    rotinas_existentes: list[dict],
) -> list[dict]:
    """Retorna apenas as rotinas recomendadas que ainda não existem."""
    descricoes_existentes = {
        r["descricao"].lower() for r in rotinas_existentes
    }
    return [
        r for r in rotinas_recomendadas
        if r.get("descricao", "").lower() not in descricoes_existentes
    ]


def _calcular_proximo_envio(horario_str: str, dias_semana: str) -> datetime:
    hora, minuto = map(int, horario_str.split(":"))
    agora = datetime.now(timezone.utc)
    agora_br = agora - timedelta(hours=3)
    candidato = agora_br.replace(hour=hora, minute=minuto, second=0, microsecond=0)
    if candidato <= agora_br:
        candidato += timedelta(days=1)
    if dias_semana == "seg-sex":
        while candidato.weekday() >= 5:
            candidato += timedelta(days=1)
    elif dias_semana == "sab-dom":
        while candidato.weekday() < 5:
            candidato += timedelta(days=1)
    return candidato + timedelta(hours=3)


def _formatar_data_br(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        dt_br = dt - timedelta(hours=3)
        return dt_br.strftime("%d/%m %H:%M")
    except Exception:
        return iso_str[:10]
