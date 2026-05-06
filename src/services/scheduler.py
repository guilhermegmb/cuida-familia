"""
CuidaFamília — Scheduler de Check-ins Proativos

Responsabilidade: verificar rotinas ativas e disparar mensagens
no horário correto, sem depender de serviço externo.

Estratégia: APScheduler rodando dentro do processo FastAPI.
- Job principal: a cada 60s verifica rotinas com proximo_envio <= agora
- Idempotente: cada disparo atualiza proximo_envio antes de enviar
- Resiliente: falha em um disparo não afeta os demais
- Limite: máximo 3 check-ins por cuidador por dia (anti-spam)
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timedelta, timezone
from src.services import supabase_service as db
from src.services.twilio_service import enviar_mensagem
from src.utils.logger import get_logger, log_erro

logger = get_logger("scheduler")

_scheduler: AsyncIOScheduler | None = None

# Limite de check-ins automáticos por cuidador por dia
MAX_CHECKINS_DIA = 3


def iniciar_scheduler():
    """Inicializa o APScheduler e registra o job de check-ins."""
    global _scheduler
    if _scheduler and _scheduler.running:
        logger.warning("Scheduler já está rodando.")
        return

    _scheduler = AsyncIOScheduler(timezone="America/Sao_Paulo")
    _scheduler.add_job(
        _verificar_e_disparar_checkins,
        trigger=IntervalTrigger(seconds=60),
        id="checkins_job",
        name="Verificar e disparar check-ins",
        replace_existing=True,
        max_instances=1,  # Garante que só roda uma instância por vez
    )
    _scheduler.start()
    logger.info("✅ Scheduler iniciado — verificando check-ins a cada 60s")


def parar_scheduler():
    """Para o scheduler graciosamente."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler parado.")


async def _verificar_e_disparar_checkins():
    """
    Job principal — executado a cada 60 segundos.

    Fluxo:
      1. Busca rotinas com proximo_envio <= agora
      2. Para cada rotina: verifica limite diário
      3. Atualiza proximo_envio ANTES de enviar (idempotência)
      4. Monta mensagem personalizada
      5. Envia via Twilio
      6. Registra no histórico
    """
    agora = datetime.now(timezone.utc)

    try:
        sb = db.get_supabase()
        rotinas = sb.table("rotinas_checkin") \
            .select("*, cuidadores(telefone, nome)") \
            .eq("ativa", True) \
            .lte("proximo_envio", agora.isoformat()) \
            .execute()

        if not rotinas.data:
            return

        logger.info(f"🔔 {len(rotinas.data)} check-in(s) para disparar")

        for rotina in rotinas.data:
            await _processar_rotina(rotina, agora, sb)

    except Exception as e:
        log_erro("scheduler_verificacao_falhou", {"erro": str(e)})


async def _processar_rotina(rotina: dict, agora: datetime, sb):
    """Processa e dispara um único check-in."""
    rotina_id = rotina["id"]
    cuidador_id = rotina["cuidador_id"]
    cuidador_info = rotina.get("cuidadores", {})
    telefone = cuidador_info.get("telefone") if cuidador_info else None
    nome_cuidador = cuidador_info.get("nome", "")

    if not telefone:
        log_erro("rotina_sem_telefone", {"rotina_id": rotina_id}, cuidador_id)
        return

    try:
        # ── 1. Verifica limite diário (anti-spam) ──
        inicio_dia = agora.replace(hour=0, minute=0, second=0, microsecond=0)
        enviados_hoje = sb.table("historico_checkins") \
            .select("id", count="exact") \
            .eq("cuidador_id", cuidador_id) \
            .gte("enviado_em", inicio_dia.isoformat()) \
            .execute()

        total_hoje = enviados_hoje.count or 0
        if total_hoje >= MAX_CHECKINS_DIA:
            logger.info(f"Limite diário atingido para {cuidador_id[:8]}... — pulando")
            # Atualiza proximo_envio para amanhã mesmo assim
            _atualizar_proximo_envio(sb, rotina, agora)
            return

        # ── 2. Atualiza proximo_envio ANTES de enviar (idempotência) ──
        _atualizar_proximo_envio(sb, rotina, agora)

        # ── 3. Monta mensagem personalizada ──
        mensagem = _montar_mensagem_checkin(rotina, nome_cuidador)

        # ── 4. Envia via Twilio ──
        destino = f"whatsapp:{telefone}"
        enviado = enviar_mensagem(destino, mensagem)

        # ── 5. Registra no histórico ──
        status = "enviado" if enviado else "sem_resposta"
        sb.table("historico_checkins").insert({
            "rotina_id": rotina_id,
            "cuidador_id": cuidador_id,
            "mensagem_enviada": mensagem,
            "status": status,
        }).execute()

        if enviado:
            logger.info(f"✅ Check-in enviado → {telefone} | {rotina['descricao']}")
        else:
            log_erro("checkin_envio_falhou", {"rotina_id": rotina_id}, cuidador_id)

    except Exception as e:
        log_erro("processar_rotina_falhou", {"erro": str(e), "rotina_id": rotina_id}, cuidador_id)


def _atualizar_proximo_envio(sb, rotina: dict, agora: datetime):
    """Calcula e persiste o próximo datetime de envio."""
    from src.services.tools.executor import _calcular_proximo_envio

    horario_str = str(rotina["horario"])[:5]  # "HH:MM:SS" → "HH:MM"
    dias_semana = rotina.get("dias_semana", "todos")

    proximo = _calcular_proximo_envio(horario_str, dias_semana)

    sb.table("rotinas_checkin").update({
        "ultimo_envio": agora.isoformat(),
        "proximo_envio": proximo.isoformat(),
    }).eq("id", rotina["id"]).execute()


def _montar_mensagem_checkin(rotina: dict, nome_cuidador: str) -> str:
    """Monta a mensagem de check-in baseada no tipo da rotina."""
    descricao = rotina.get("descricao", "")
    tipo = rotina.get("tipo", "outro")
    nome = nome_cuidador or "cuidador(a)"

    templates = {
        "medicamento": (
            f"⏰ Olá, {nome}! Lembrete: é hora de *{descricao}*.\n\n"
            "Já foi administrado? 💙"
        ),
        "medicao_pressao": (
            f"📊 Olá, {nome}! Hora de medir a pressão arterial.\n\n"
            "Quando tiver o resultado, pode me contar! 💙"
        ),
        "medicao_glicose": (
            f"📊 Olá, {nome}! Hora de verificar a glicose.\n\n"
            "Pode me informar o resultado? 💙"
        ),
        "bem_estar_diario": (
            f"💙 Bom dia, {nome}! Como está sua mãe/familiar hoje?\n\n"
            "Algo de diferente para relatar?"
        ),
        "hidratacao": (
            f"💧 Olá, {nome}! Lembrete de hidratação — "
            f"{descricao or 'ofereça água para quem você cuida'}. 💙"
        ),
        "consulta": (
            f"📅 Olá, {nome}! Lembrete: *{descricao}*.\n\n"
            "Tudo certo com o agendamento? 💙"
        ),
        "outro": (
            f"🔔 Olá, {nome}! Lembrete: *{descricao}*. 💙"
        ),
    }

    return templates.get(tipo, templates["outro"])
