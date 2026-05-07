"""
CuidaFamília — Serviço de Plano de Cuidado

Responsabilidade única: todas as operações relacionadas ao plano de cuidado.
Separado do supabase_service para manter coesão e facilitar testes.

Padrão: Service Layer — lógica de negócio isolada da camada de dados.
"""

import json
from datetime import datetime, timedelta, timezone
from src.services.supabase_service import get_supabase, salvar_memoria
from src.utils.logger import get_logger, log_erro

logger = get_logger("plan_service")


# ── Leitura ──────────────────────────────────────────────────────────────────

def buscar_plano_ativo(cuidador_id: str) -> dict | None:
    """
    Retorna o plano de cuidado ativo do cuidador.
    Retorna None se não existir plano.
    """
    try:
        sb = get_supabase()
        resultado = sb.table("planos_cuidado") \
            .select("*") \
            .eq("cuidador_id", cuidador_id) \
            .eq("status", "ativo") \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()
        return resultado.data[0] if resultado.data else None
    except Exception as e:
        log_erro("buscar_plano_ativo", {"erro": str(e)}, cuidador_id)
        return None


def cuidador_tem_plano(cuidador_id: str) -> bool:
    """Verifica rapidamente se o cuidador já tem um plano ativo."""
    return buscar_plano_ativo(cuidador_id) is not None


def buscar_rotinas_ativas(cuidador_id: str) -> list[dict]:
    """Retorna todas as rotinas ativas do cuidador para contexto."""
    try:
        sb = get_supabase()
        resultado = sb.table("rotinas_checkin") \
            .select("tipo, descricao, horario, dias_semana") \
            .eq("cuidador_id", cuidador_id) \
            .eq("ativa", True) \
            .order("horario") \
            .execute()
        return resultado.data or []
    except Exception as e:
        log_erro("buscar_rotinas_ativas", {"erro": str(e)}, cuidador_id)
        return []


# ── Criação ──────────────────────────────────────────────────────────────────

def criar_plano(
    cuidador_id: str,
    pessoa_cuidada_id: str | None,
    objetivo_primario: str,
    objetivos_secundarios: list[str],
    rotinas_recomendadas: list[dict],
    alertas_relevantes: list[str],
    contexto_clinico: dict,
) -> dict:
    """
    Cria um novo plano de cuidado.
    Arquiva planos anteriores antes de criar o novo.
    Retorna o plano criado.
    """
    try:
        sb = get_supabase()

        # Arquiva plano anterior se existir
        sb.table("planos_cuidado") \
            .update({"status": "arquivado"}) \
            .eq("cuidador_id", cuidador_id) \
            .eq("status", "ativo") \
            .execute()

        resultado = sb.table("planos_cuidado").insert({
            "cuidador_id": cuidador_id,
            "pessoa_cuidada_id": pessoa_cuidada_id,
            "status": "ativo",
            "objetivo_primario": objetivo_primario,
            "objetivos_secundarios": objetivos_secundarios,
            "rotinas_recomendadas": rotinas_recomendadas,
            "alertas_relevantes": alertas_relevantes or [],
            "contexto_clinico": contexto_clinico,
            "versao": 1,
        }).execute()

        plano = resultado.data[0]
        logger.info(f"Plano de cuidado criado → {cuidador_id[:8]}... | ID: {plano['id'][:8]}...")

        # Salva referência na memória para contexto rápido
        salvar_memoria(cuidador_id, "plano_objetivo_primario", objetivo_primario)
        salvar_memoria(cuidador_id, "plano_id", plano["id"])

        return plano

    except Exception as e:
        log_erro("criar_plano", {"erro": str(e)}, cuidador_id)
        raise


# ── Atualização ──────────────────────────────────────────────────────────────

def atualizar_plano(
    cuidador_id: str,
    plano_id: str,
    campo: str,
    novo_valor,
    motivo: str,
) -> dict:
    """
    Atualiza um campo do plano e registra a adaptação no histórico.
    Retorna o plano atualizado.
    """
    try:
        sb = get_supabase()

        # Busca estado atual para registrar antes/depois
        plano_atual = buscar_plano_ativo(cuidador_id)
        valor_antes = plano_atual.get(campo) if plano_atual else None

        # Incrementa versão
        versao_nova = (plano_atual.get("versao") or 1) + 1

        # Atualiza o plano
        sb.table("planos_cuidado").update({
            campo: novo_valor,
            "versao": versao_nova,
            "ultima_adaptacao": datetime.now(timezone.utc).isoformat(),
            "motivo_ultima_adaptacao": motivo,
            # Cooldown: próxima sugestão de adaptação em 7 dias
            "proxima_sugestao_adaptacao": (
                datetime.now(timezone.utc) + timedelta(days=7)
            ).isoformat(),
        }).eq("id", plano_id).execute()

        # Registra no histórico de adaptações
        sb.table("adaptacoes_plano").insert({
            "plano_id": plano_id,
            "cuidador_id": cuidador_id,
            "tipo_adaptacao": _inferir_tipo_adaptacao(campo),
            "descricao": f"Campo '{campo}' atualizado",
            "motivo": motivo,
            "decisao": "aceito",
            "decidido_em": datetime.now(timezone.utc).isoformat(),
            "dados_antes": {"valor": valor_antes},
            "dados_depois": {"valor": novo_valor},
        }).execute()

        logger.info(f"Plano atualizado: campo={campo} | motivo={motivo[:50]} | v{versao_nova}")

        # Atualiza memória se for objetivo primário
        if campo == "objetivo_primario":
            salvar_memoria(cuidador_id, "plano_objetivo_primario", str(novo_valor))

        return buscar_plano_ativo(cuidador_id) or {}

    except Exception as e:
        log_erro("atualizar_plano", {"erro": str(e), "campo": campo}, cuidador_id)
        raise


# ── Rotinas ──────────────────────────────────────────────────────────────────

def atualizar_rotina(
    cuidador_id: str,
    descricao_busca: str,
    novo_horario: str | None = None,
    nova_descricao: str | None = None,
    ativa: bool | None = None,
    motivo: str = "",
) -> dict:
    """
    Localiza uma rotina pelo texto da descrição e aplica as atualizações.
    Retorna resultado da operação.
    """
    try:
        sb = get_supabase()

        # Busca rotinas ativas que contenham o texto
        rotinas = sb.table("rotinas_checkin") \
            .select("*") \
            .eq("cuidador_id", cuidador_id) \
            .eq("ativa", True) \
            .ilike("descricao", f"%{descricao_busca}%") \
            .execute()

        if not rotinas.data:
            return {
                "sucesso": False,
                "resultado": f"Não encontrei nenhuma rotina ativa com '{descricao_busca}'. "
                             f"Verifique o nome e tente novamente.",
                "dados": {},
            }

        rotina = rotinas.data[0]
        rotina_id = rotina["id"]
        atualizacoes = {}

        if novo_horario:
            try:
                hora, minuto = novo_horario.split(":")
                atualizacoes["horario"] = f"{int(hora):02d}:{int(minuto):02d}:00"
                # Recalcula próximo envio
                from src.services.tools.executor import _calcular_proximo_envio
                proximo = _calcular_proximo_envio(novo_horario, rotina.get("dias_semana", "todos"))
                atualizacoes["proximo_envio"] = proximo.isoformat()
            except ValueError:
                return {
                    "sucesso": False,
                    "resultado": "Horário inválido. Use o formato HH:MM.",
                    "dados": {},
                }

        if nova_descricao:
            atualizacoes["descricao"] = nova_descricao

        if ativa is not None:
            atualizacoes["ativa"] = ativa

        if not atualizacoes:
            return {
                "sucesso": False,
                "resultado": "Nenhuma alteração informada.",
                "dados": {},
            }

        sb.table("rotinas_checkin").update(atualizacoes).eq("id", rotina_id).execute()

        # Monta mensagem de confirmação
        partes = []
        if novo_horario:
            partes.append(f"horário alterado para {novo_horario}")
        if nova_descricao:
            partes.append(f"descrição atualizada")
        if ativa is False:
            partes.append("rotina desativada")

        descricao_final = rotina.get("descricao", descricao_busca)
        resumo = ", ".join(partes)

        logger.info(f"Rotina atualizada: '{descricao_final}' | {resumo} | motivo: {motivo[:50]}")

        return {
            "sucesso": True,
            "resultado": f"✅ Rotina '{descricao_final}' atualizada: {resumo}.",
            "dados": {"rotina_id": rotina_id, "atualizacoes": atualizacoes},
        }

    except Exception as e:
        log_erro("atualizar_rotina", {"erro": str(e)}, cuidador_id)
        raise


# ── Formatação ───────────────────────────────────────────────────────────────

def formatar_plano_para_cuidador(plano: dict, rotinas_ativas: list[dict] = None) -> str:
    """
    Formata o plano de cuidado em linguagem clara e amigável para o WhatsApp.
    """
    linhas = ["📋 *Plano de Cuidado*\n"]

    linhas.append(f"*Objetivo principal:*\n{plano['objetivo_primario']}\n")

    objetivos_sec = plano.get("objetivos_secundarios") or []
    if objetivos_sec:
        linhas.append("*Objetivos secundários:*")
        for obj in objetivos_sec:
            linhas.append(f"  • {obj}")
        linhas.append("")

    alertas = plano.get("alertas_relevantes") or []
    if alertas:
        linhas.append("*Pontos de atenção:*")
        for alerta in alertas:
            linhas.append(f"  ⚠️ {alerta}")
        linhas.append("")

    if rotinas_ativas:
        linhas.append("*Rotinas ativas:*")
        for r in rotinas_ativas:
            horario = str(r.get("horario", ""))[:5]
            linhas.append(f"  ⏰ {horario} — {r['descricao']}")
        linhas.append("")

    versao = plano.get("versao", 1)
    linhas.append(f"_Versão {versao} do plano_ 💙")

    return "\n".join(linhas)


def formatar_plano_para_llm(plano: dict, rotinas_ativas: list[dict] = None) -> str:
    """
    Formata o plano como contexto estruturado para injetar no prompt do LLM.
    """
    partes = [f"### Plano de Cuidado (v{plano.get('versao', 1)})"]
    partes.append(f"- Objetivo primário: {plano['objetivo_primario']}")

    objetivos_sec = plano.get("objetivos_secundarios") or []
    if objetivos_sec:
        partes.append(f"- Objetivos secundários: {'; '.join(objetivos_sec)}")

    alertas = plano.get("alertas_relevantes") or []
    if alertas:
        partes.append(f"- Alertas: {'; '.join(alertas)}")

    if rotinas_ativas:
        rotinas_str = ", ".join(
            f"{str(r.get('horario',''))[:5]} ({r['descricao']})"
            for r in rotinas_ativas
        )
        partes.append(f"- Rotinas ativas: {rotinas_str}")

    return "\n".join(partes)


# ── Utilitários internos ─────────────────────────────────────────────────────

def _inferir_tipo_adaptacao(campo: str) -> str:
    mapa = {
        "objetivo_primario": "ajuste_objetivo",
        "objetivos_secundarios": "ajuste_objetivo",
        "rotinas_recomendadas": "nova_rotina",
        "alertas_relevantes": "ajuste_alerta",
    }
    return mapa.get(campo, "outro")
