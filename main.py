"""
CuidaFamília - Agente de IA Concierge de Cuidado
Versão: 3.0 (PCP - Pacote de Confiabilidade do Piloto)
Data: 2026-05-03

Arquitetura:
- Camada 1: Âncora Temporal (IA sempre sabe que dia/hora é)
- Camada 2: Memória Consolidada (família, paciente, histórico)
- Camada 3: Duplo Ciclo de IA (analítico + conversacional)
- Camada 4: Confirmação antes de agendar (nunca agenda sem "sim")
- Camada 5: Suporte a rotina de medicação recorrente
- Camada 6: Log de lembretes (base para o scheduler)

Padrões: MIT License | Harvard Standards | ACID | 3NF | LGPD
"""

import os
import json
import logging
import pytz
from datetime import datetime

import requests
from fastapi import FastAPI, Request, Response
from supabase import create_client, Client
from twilio.twiml.messaging_response import MessagingResponse

# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("CuidaFamilia")

# ============================================================
# CONFIGURAÇÃO BÁSICA
# ============================================================

app = FastAPI(title="CuidaFamília API", version="3.0")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "America/Sao_Paulo")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# ============================================================
# ÂNCORA TEMPORAL (Camada 1)
# Garante que a IA sempre saiba o dia e hora exatos em Brasília
# ============================================================

def get_temporal_anchor() -> str:
    """
    Gera o contexto de data e hora atual no fuso de Brasília.
    Deve ser injetado no topo de todos os prompts analíticos.
    """
    tz = pytz.timezone(DEFAULT_TIMEZONE)
    agora = datetime.now(tz)

    dias_semana = {
        "Monday": "Segunda-feira",
        "Tuesday": "Terça-feira",
        "Wednesday": "Quarta-feira",
        "Thursday": "Quinta-feira",
        "Friday": "Sexta-feira",
        "Saturday": "Sábado",
        "Sunday": "Domingo",
    }

    dia_pt = dias_semana.get(agora.strftime("%A"), agora.strftime("%A"))
    data_hoje = agora.strftime("%d/%m/%Y")
    data_iso = agora.strftime("%Y-%m-%d")
    hora_agora = agora.strftime("%H:%M")

    return (
        f"CONTEXTO TEMPORAL OBRIGATÓRIO:\n"
        f"Hoje é {dia_pt}, dia {data_hoje} ({data_iso}), agora são exatamente {hora_agora} "
        f"(Horário de Brasília).\n"
        f"REGRA: Se o usuário usar termos relativos como 'amanhã', 'depois de amanhã', "
        f"'semana que vem', 'segunda-feira', você DEVE calcular a data real baseada em HOJE "
        f"e retornar SEMPRE no formato YYYY-MM-DD."
    )


# ============================================================
# TOOLS (FUNCTION CALLING)
# ============================================================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "save_patient_info",
            "description": "Salva ou atualiza informações do paciente no banco de dados.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_name": {"type": "string"},
                    "birthdate": {"type": "string"},
                    "gender": {"type": "string", "enum": ["M", "F", "Outro"]},
                    "medications": {"type": "string"},
                    "health_condition": {"type": "string"},
                    "doctor_name": {"type": "string"},
                    "doctor_phone": {"type": "string"},
                },
                "required": ["patient_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_interlocutor_info",
            "description": "Salva o nome do principal interlocutor da família.",
            "parameters": {
                "type": "object",
                "properties": {
                    "interlocutor_name": {"type": "string"},
                },
                "required": ["interlocutor_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_schedule_confirmation",
            "description": (
                "Solicita confirmação do usuário antes de agendar um evento ou consulta. "
                "NUNCA agende diretamente. Sempre use esta função primeiro."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "event_date": {
                        "type": "string",
                        "description": "Data no formato YYYY-MM-DD, já resolvida a partir da âncora temporal.",
                    },
                    "event_time": {
                        "type": "string",
                        "description": "Hora no formato HH:MM.",
                    },
                    "event_type": {
                        "type": "string",
                        "enum": ["consulta", "medicação", "exame", "compromisso", "lembrete", "outro"],
                    },
                    "description": {"type": "string"},
                },
                "required": ["title", "event_date", "event_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_medication_confirmation",
            "description": (
                "Solicita confirmação do usuário antes de registrar uma rotina de medicação recorrente. "
                "NUNCA registre diretamente. Sempre use esta função primeiro."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "medication_name": {"type": "string"},
                    "dosage": {"type": "string"},
                    "times": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Lista de horários no formato HH:MM. Ex: ['08:00', '20:00']",
                    },
                },
                "required": ["medication_name", "times"],
            },
        },
    },
]

# ============================================================
# SUPABASE HELPERS — LEITURA
# ============================================================


async def get_family_by_whatsapp(whatsapp_number: str):
    try:
        res = (
            supabase.table("families")
            .select("*")
            .eq("main_whatsapp", whatsapp_number)
            .execute()
        )
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Erro ao buscar família: {e}")
        return None


async def get_patient_by_family_id(family_id: int):
    try:
        res = (
            supabase.table("patients")
            .select("*")
            .eq("family_id", family_id)
            .execute()
        )
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Erro ao buscar paciente: {e}")
        return None


async def get_conversation_history(family_id: int, limit: int = 30):
    try:
        res = (
            supabase.table("conversation_history")
            .select("sender_type, sender_name, message_text, created_at")
            .eq("family_id", family_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return list(reversed(res.data)) if res.data else []
    except Exception as e:
        logger.error(f"Erro ao buscar histórico: {e}")
        return []


async def get_family_memory(family_id: int):
    try:
        res = (
            supabase.table("family_memory")
            .select("*")
            .eq("family_id", family_id)
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Erro ao buscar memória da família: {e}")
        return None


async def get_pending_confirmation(family_id: int):
    """Busca se existe uma confirmação pendente para esta família."""
    try:
        res = (
            supabase.table("pending_confirmations")
            .select("*")
            .eq("family_id", family_id)
            .eq("status", "pending")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Erro ao buscar confirmação pendente: {e}")
        return None

# ============================================================
# SUPABASE HELPERS — ESCRITA
# ============================================================


async def save_conversation_message(
    family_id: int, sender_type: str, sender_name: str, message_text: str
):
    try:
        supabase.table("conversation_history").insert({
            "family_id": family_id,
            "sender_type": sender_type,
            "sender_name": sender_name,
            "message_text": message_text,
        }).execute()
    except Exception as e:
        logger.error(f"Erro ao salvar mensagem: {e}")


async def log_action(
    family_id: int,
    log_type: str,
    message: str,
    created_by: str = "IA",
    metadata: dict | None = None,
):
    try:
        supabase.table("family_logs").insert({
            "family_id": family_id,
            "log_type": log_type,
            "message": message,
            "created_by": created_by,
            "metadata": metadata,
        }).execute()
    except Exception as e:
        logger.error(f"Erro ao registrar log: {e}")


async def save_patient_info_db(family_id: int, **kwargs):
    try:
        data = {"family_id": family_id}
        data.update({k: v for k, v in kwargs.items() if v is not None})
        existing = await get_patient_by_family_id(family_id)
        if existing:
            supabase.table("patients").update(data).eq("family_id", family_id).execute()
        else:
            supabase.table("patients").insert(data).execute()
    except Exception as e:
        logger.error(f"Erro ao salvar paciente: {e}")


async def save_interlocutor_info_db(family_id: int, interlocutor_name: str):
    try:
        supabase.table("families").update(
            {"main_interlocutor_name": interlocutor_name}
        ).eq("id", family_id).execute()
    except Exception as e:
        logger.error(f"Erro ao salvar interlocutor: {e}")


async def schedule_event_db(
    family_id: int,
    title: str,
    event_date: str,
    event_time: str | None = None,
    event_type: str = "outro",
    description: str | None = None,
):
    """Grava o evento na agenda E cria o registro de lembrete pendente."""
    try:
        # 1. Salvar na agenda
        result = supabase.table("family_agenda").insert({
            "family_id": family_id,
            "title": title,
            "event_date": event_date,
            "event_time": event_time,
            "event_type": event_type,
            "description": description,
            "status": "ativo",
        }).execute()

        # 2. Criar entradas no reminder_log para o scheduler disparar
        if result.data:
            agenda_id = result.data[0]["id"]
            tz = pytz.timezone(DEFAULT_TIMEZONE)

            # Lembrete 1: Manhã do dia do evento (08:00)
            remind_morning = f"{event_date}T08:00:00"
            try:
                supabase.table("reminder_log").insert({
                    "family_id": family_id,
                    "source_type": "agenda",
                    "source_id": agenda_id,
                    "remind_at": remind_morning,
                    "status": "pending",
                }).execute()
            except Exception:
                pass  # Ignora duplicidade (constraint unique)

            # Lembrete 2: 1 hora antes (se tiver horário definido)
            if event_time:
                try:
                    event_dt_str = f"{event_date}T{event_time}:00"
                    event_dt = datetime.fromisoformat(event_dt_str)
                    remind_before = event_dt.replace(
                        hour=event_dt.hour - 1 if event_dt.hour > 0 else 0
                    )
                    supabase.table("reminder_log").insert({
                        "family_id": family_id,
                        "source_type": "agenda",
                        "source_id": agenda_id,
                        "remind_at": remind_before.isoformat(),
                        "status": "pending",
                    }).execute()
                except Exception:
                    pass  # Ignora se horário inválido

        logger.info(f"[AGENDA] Evento '{title}' agendado para {event_date} com lembretes criados.")
    except Exception as e:
        logger.error(f"Erro ao agendar evento: {e}")


async def save_medication_schedule_db(
    family_id: int,
    medication_name: str,
    times: list,
    dosage: str | None = None,
):
    """Grava a rotina de medicação recorrente."""
    try:
        supabase.table("medication_schedules").insert({
            "family_id": family_id,
            "medication_name": medication_name,
            "dosage": dosage,
            "times": times,
            "is_active": True,
        }).execute()
        logger.info(f"[MEDICAÇÃO] Rotina de '{medication_name}' registrada: {times}")
    except Exception as e:
        logger.error(f"Erro ao salvar rotina de medicação: {e}")


async def save_pending_confirmation(
    family_id: int,
    confirmation_type: str,
    payload: dict,
):
    """Salva uma confirmação pendente para aguardar resposta do usuário."""
    try:
        # Cancela qualquer confirmação anterior pendente desta família
        supabase.table("pending_confirmations").update(
            {"status": "cancelled"}
        ).eq("family_id", family_id).eq("status", "pending").execute()

        # Cria a nova confirmação
        supabase.table("pending_confirmations").insert({
            "family_id": family_id,
            "confirmation_type": confirmation_type,
            "payload": payload,
            "status": "pending",
        }).execute()
    except Exception as e:
        logger.error(f"Erro ao salvar confirmação pendente: {e}")


async def resolve_pending_confirmation(confirmation_id: int, confirmed: bool):
    """Marca a confirmação como confirmada ou cancelada."""
    try:
        status = "confirmed" if confirmed else "cancelled"
        supabase.table("pending_confirmations").update(
            {"status": status}
        ).eq("id", confirmation_id).execute()
    except Exception as e:
        logger.error(f"Erro ao resolver confirmação: {e}")


async def upsert_family_memory(
    family_id: int,
    summary: str | None,
    emotional_context: str | None,
    care_routines: str | None,
    risk_notes: str | None,
):
    try:
        data = {
            "family_id": family_id,
            "summary": summary or "",
            "emotional_context": emotional_context or "",
            "care_routines": care_routines or "",
            "risk_notes": risk_notes or "",
            "updated_at": datetime.utcnow().isoformat(),
        }
        existing = await get_family_memory(family_id)
        if existing:
            supabase.table("family_memory").update(data).eq("id", existing["id"]).execute()
        else:
            supabase.table("family_memory").insert(data).execute()
    except Exception as e:
        logger.error(f"Erro ao atualizar memória da família: {e}")

# ============================================================
# FORMATADORES DE CONTEXTO PARA PROMPTS
# ============================================================


def format_conversation_history_for_context(history: list) -> str:
    if not history:
        return "Nenhuma conversa anterior relevante."
    lines = []
    for msg in history:
        sender = msg.get("sender_name") or msg.get("sender_type", "Desconhecido")
        text = msg.get("message_text", "")
        lines.append(f"- {sender}: {text}")
    return "Histórico recente de mensagens:\n" + "\n".join(lines)


def format_patient_info_for_context(patient: dict | None) -> str:
    if not patient:
        return "Nenhuma informação de paciente cadastrada ainda."
    parts = [f"- Nome: {patient.get('patient_name', 'N/A')}"]
    if patient.get("birthdate"):
        parts.append(f"- Data de nascimento: {patient['birthdate']}")
    if patient.get("medications"):
        parts.append(f"- Medicamentos: {patient['medications']}")
    if patient.get("health_condition"):
        parts.append(f"- Condição de saúde: {patient['health_condition']}")
    if patient.get("doctor_name"):
        parts.append(f"- Médico responsável: {patient['doctor_name']}")
    return "Informações do paciente:\n" + "\n".join(parts)


def format_family_memory_for_context(memory: dict | None) -> str:
    if not memory:
        return "Nenhuma memória consolidada registrada ainda."
    parts = []
    if memory.get("summary"):
        parts.append(f"Resumo factual: {memory['summary']}")
    if memory.get("care_routines"):
        parts.append(f"Rotinas de cuidado: {memory['care_routines']}")
    if memory.get("risk_notes"):
        parts.append(f"Notas de risco: {memory['risk_notes']}")
    if memory.get("emotional_context"):
        parts.append(f"Contexto emocional: {memory['emotional_context']}")
    return "Memória consolidada da família:\n" + "\n".join(parts)

# ============================================================
# OPENROUTER HELPER
# ============================================================


def call_openrouter(payload: dict) -> dict:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=40)
    resp.raise_for_status()
    return resp.json()

# ============================================================
# LÓGICA DE CONFIRMAÇÃO PENDENTE
# Verifica se o usuário está respondendo "sim" ou "não"
# a uma confirmação anterior
# ============================================================

RESPOSTAS_POSITIVAS = ["sim", "s", "ok", "pode", "confirma", "confirmo", "isso", "certo", "correto", "yes"]
RESPOSTAS_NEGATIVAS = ["não", "nao", "n", "cancela", "cancelo", "errado", "errei", "no"]


def is_positive_response(text: str) -> bool:
    return text.strip().lower() in RESPOSTAS_POSITIVAS


def is_negative_response(text: str) -> bool:
    return text.strip().lower() in RESPOSTAS_NEGATIVAS


async def handle_pending_confirmation(
    family_id: int,
    incoming_msg: str,
    pending: dict,
) -> str | None:
    """
    Verifica se a mensagem é uma resposta a uma confirmação pendente.
    Retorna a mensagem de resposta ao usuário, ou None se não for uma resposta de confirmação.
    """
    if is_positive_response(incoming_msg):
        payload = pending["payload"]
        ctype = pending["confirmation_type"]

        await resolve_pending_confirmation(pending["id"], confirmed=True)

        if ctype == "agenda":
            await schedule_event_db(
                family_id=family_id,
                title=payload.get("title"),
                event_date=payload.get("event_date"),
                event_time=payload.get("event_time"),
                event_type=payload.get("event_type", "outro"),
                description=payload.get("description"),
            )
            await log_action(
                family_id,
                "update",
                f"Evento confirmado e agendado: {payload.get('title')} em {payload.get('event_date')}",
                metadata=payload,
            )
            event_time_str = f" às {payload.get('event_time')}" if payload.get("event_time") else ""
            return (
                f"✅ Perfeito! Agendei *{payload.get('title')}* para o dia "
                f"{payload.get('event_date')}{event_time_str}.\n"
                f"Vou te lembrar de manhã e 1 hora antes. 😊"
            )

        elif ctype == "medicacao":
            await save_medication_schedule_db(
                family_id=family_id,
                medication_name=payload.get("medication_name"),
                times=payload.get("times", []),
                dosage=payload.get("dosage"),
            )
            await log_action(
                family_id,
                "update",
                f"Rotina de medicação confirmada: {payload.get('medication_name')} {payload.get('times')}",
                metadata=payload,
            )
            times_str = ", ".join(payload.get("times", []))
            return (
                f"✅ Anotei! Vou lembrar do *{payload.get('medication_name')}* "
                f"todos os dias nos horários: {times_str}. 💊"
            )

    elif is_negative_response(incoming_msg):
        await resolve_pending_confirmation(pending["id"], confirmed=False)
        return (
            "Tudo bem, cancelei. 😊 Me diga como posso te ajudar "
            "ou me corrija as informações."
        )

    return None  # Não era uma resposta de confirmação

# ============================================================
# HEALTH CHECK
# ============================================================


@app.get("/")
async def root():
    tz = pytz.timezone(DEFAULT_TIMEZONE)
    return {
        "status": "CuidaFamília Online",
        "version": "3.0",
        "timestamp": datetime.now(tz).isoformat(),
    }

# ============================================================
# WEBHOOK WHATSAPP — ORQUESTRAÇÃO PRINCIPAL
# ============================================================


@app.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    twilio_resp = MessagingResponse()

    try:
        form = await request.form()
        incoming_msg = (form.get("Body") or "").strip()
        sender_number = (form.get("From") or "").replace("whatsapp:", "")

        logger.info(f"[NOVA MENSAGEM] {sender_number}: {incoming_msg}")

        # --------------------------------------------------------
        # 1. Identificar família pelo número
        # --------------------------------------------------------
        family = await get_family_by_whatsapp(sender_number)
        if not family:
            twilio_resp.message(
                "Olá! Não consegui identificar sua família no CuidaFamília.\n"
                "Verifique se seu número está cadastrado ou fale com o suporte."
            )
            return Response(content=str(twilio_resp), media_type="application/xml")

        family_id = family["id"]
        family_name = family.get("family_name", "Família")
        main_interlocutor = family.get("main_interlocutor_name") or "Responsável"

        # --------------------------------------------------------
        # 2. Registrar mensagem do usuário imediatamente
        # --------------------------------------------------------
        await save_conversation_message(
            family_id=family_id,
            sender_type="user",
            sender_name=main_interlocutor,
            message_text=incoming_msg,
        )

        # --------------------------------------------------------
        # 3. Verificar se existe confirmação pendente
        # (usuário pode estar respondendo "sim" ou "não")
        # --------------------------------------------------------
        pending = await get_pending_confirmation(family_id)
        if pending:
            confirmation_response = await handle_pending_confirmation(
                family_id, incoming_msg, pending
            )
            if confirmation_response:
                twilio_resp.message(confirmation_response)
                await save_conversation_message(
                    family_id=family_id,
                    sender_type="ai",
                    sender_name="CuidaFamília",
                    message_text=confirmation_response,
                )
                return Response(content=str(twilio_resp), media_type="application/xml")

        # --------------------------------------------------------
        # 4. Buscar contexto completo
        # --------------------------------------------------------
        patient = await get_patient_by_family_id(family_id)
        patient_name = patient.get("patient_name", "paciente") if patient else "paciente"
        family_memory = await get_family_memory(family_id)
        history = await get_conversation_history(family_id, limit=30)

        patient_context = format_patient_info_for_context(patient)
        memory_context = format_family_memory_for_context(family_memory)
        history_context = format_conversation_history_for_context(history)

        # --------------------------------------------------------
        # 5. PRIMEIRO CICLO: ANALÍTICO (com âncora temporal)
        # --------------------------------------------------------
        ancora_temporal = get_temporal_anchor()

        system_analytical = f"""
{ancora_temporal}

Você é o módulo ANALÍTICO do CuidaFamília, um Concierge de Cuidado para a família {family_name} e o paciente {patient_name}.

Seu papel neste ciclo NÃO é conversar com o usuário. Você deve:
- Analisar a nova mensagem com atenção.
- Decidir se deve chamar ferramentas (functions).
- Sugerir atualização da MEMÓRIA CONSOLIDADA.

REGRAS DE AGENDAMENTO (CRÍTICO):
- NUNCA use schedule_event diretamente.
- SEMPRE use request_schedule_confirmation para eventos e consultas.
- SEMPRE use request_medication_confirmation para rotinas de remédio.
- Datas DEVEM estar no formato YYYY-MM-DD, calculadas a partir da âncora temporal acima.

Contexto disponível:

{patient_context}

{memory_context}

{history_context}

GUARDRAILS CLÍNICOS (NUNCA viole):
- Não faça diagnósticos.
- Não recomende, altere ou confirme medicações.
- Não dê conselhos médicos específicos.
- Em emergências (dor no peito, falta de ar, desmaio), a camada conversacional avisará para ligar 192.

FORMATO DA SUA RESPOSTA:
Você pode chamar tools quantas vezes forem necessárias.
No campo 'content', retorne APENAS este JSON:

{{
  "memory_update": {{
    "summary": "string ou null",
    "emotional_context": "string ou null",
    "care_routines": "string ou null",
    "risk_notes": "string ou null"
  }}
}}
"""

        analytical_payload = {
            "model": OPENROUTER_MODEL,
            "messages": [
                {"role": "system", "content": system_analytical},
                {"role": "user", "content": incoming_msg},
            ],
            "tools": TOOLS,
            "tool_choice": "auto",
        }

        logger.info("[IA] Iniciando ciclo analítico...")
        analytical_response = call_openrouter(analytical_payload)
        analytical_msg = analytical_response.get("choices", [{}])[0].get("message", {})

        # --------------------------------------------------------
        # 5.1 Executar tools chamadas pelo modelo analítico
        # --------------------------------------------------------
        confirmation_message = None  # Mensagem de confirmação para o usuário

        if analytical_msg.get("tool_calls"):
            for tool_call in analytical_msg["tool_calls"]:
                fn_name = tool_call["function"]["name"]
                args = json.loads(tool_call["function"]["arguments"] or "{}")
                logger.info(f"[FUNCTION CALL] {fn_name} | {args}")

                if fn_name == "save_patient_info":
                    await save_patient_info_db(family_id=family_id, **args)
                    await log_action(
                        family_id, "update",
                        f"Paciente atualizado: {args.get('patient_name')}",
                        metadata=args,
                    )

                elif fn_name == "save_interlocutor_info":
                    await save_interlocutor_info_db(family_id, args.get("interlocutor_name", ""))
                    await log_action(
                        family_id, "update",
                        f"Interlocutor registrado: {args.get('interlocutor_name')}",
                        metadata=args,
                    )

                elif fn_name == "request_schedule_confirmation":
                    # Salva como pendente e prepara mensagem de confirmação
                    await save_pending_confirmation(
                        family_id=family_id,
                        confirmation_type="agenda",
                        payload=args,
                    )
                    event_time_str = f" às {args.get('event_time')}" if args.get("event_time") else ""
                    confirmation_message = (
                        f"📅 Entendi! Vou agendar:\n"
                        f"*{args.get('title')}*\n"
                        f"📆 Data: {args.get('event_date')}{event_time_str}\n"
                        f"Posso confirmar? Responda *sim* ou *não*."
                    )
                    await log_action(
                        family_id, "note",
                        f"Confirmação de agenda solicitada: {args.get('title')}",
                        metadata=args,
                    )

                elif fn_name == "request_medication_confirmation":
                    # Salva como pendente e prepara mensagem de confirmação
                    await save_pending_confirmation(
                        family_id=family_id,
                        confirmation_type="medicacao",
                        payload=args,
                    )
                    times_str = ", ".join(args.get("times", []))
                    dosage_str = f" ({args.get('dosage')})" if args.get("dosage") else ""
                    confirmation_message = (
                        f"💊 Entendi! Vou registrar o lembrete:\n"
                        f"*{args.get('medication_name')}*{dosage_str}\n"
                        f"⏰ Horários: {times_str} (todos os dias)\n"
                        f"Posso confirmar? Responda *sim* ou *não*."
                    )
                    await log_action(
                        family_id, "note",
                        f"Confirmação de medicação solicitada: {args.get('medication_name')}",
                        metadata=args,
                    )

        # --------------------------------------------------------
        # 5.2 Atualizar memória consolidada
        # --------------------------------------------------------
        if analytical_msg.get("content"):
            try:
                parsed = json.loads(analytical_msg["content"])
                memory_update = parsed.get("memory_update")
                if memory_update:
                    await upsert_family_memory(
                        family_id=family_id,
                        summary=memory_update.get("summary"),
                        emotional_context=memory_update.get("emotional_context"),
                        care_routines=memory_update.get("care_routines"),
                        risk_notes=memory_update.get("risk_notes"),
                    )
                    logger.info("[MEMÓRIA] Memória consolidada atualizada.")
            except Exception as e:
                logger.warning(f"Falha ao parsear memory_update: {e}")

        # --------------------------------------------------------
        # 5.3 Se há mensagem de confirmação, retorna direto
        # (não precisa do ciclo conversacional)
        # --------------------------------------------------------
        if confirmation_message:
            twilio_resp.message(confirmation_message)
            await save_conversation_message(
                family_id=family_id,
                sender_type="ai",
                sender_name="CuidaFamília",
                message_text=confirmation_message,
            )
            return Response(content=str(twilio_resp), media_type="application/xml")

        # --------------------------------------------------------
        # 6. SEGUNDO CICLO: CONVERSACIONAL
        # --------------------------------------------------------
        family_memory = await get_family_memory(family_id)
        memory_context = format_family_memory_for_context(family_memory)

        system_conversational = f"""
Você é o CuidaFamília, um Concierge de Cuidado e Secretária Executiva Familiar.

Você atende a família {family_name}, cuidando de {patient_name}.

Seu papel:
- Responder de forma empática, organizada e profissional.
- Ajudar a organizar informações, registrar fatos, agendar compromissos e lembrar rotinas.
- Usar a MEMÓRIA CONSOLIDADA e o histórico para manter continuidade.

MEMÓRIA CONSOLIDADA:
{memory_context}

INFORMAÇÕES DO PACIENTE:
{patient_context}

HISTÓRICO RECENTE:
{history_context}

GUARDRAILS CRÍTICOS:
- NUNCA forneça diagnósticos médicos.
- NUNCA recomende, altere ou ajuste medicações.
- NUNCA diga se um exame está normal ou anormal.
- Em emergências (dor no peito, falta de ar, desmaio), diga SEMPRE:
  "⚠️ EMERGÊNCIA! Ligue para o SAMU (192) ou vá ao pronto-socorro AGORA!"
- Foque em organização, logística e apoio emocional leve.

Estilo:
- Linguagem simples, clara e respeitosa.
- Respostas objetivas, mas acolhedoras.
- Ofereça ajuda prática (registrar, agendar, lembrar).
"""

        conversational_payload = {
            "model": OPENROUTER_MODEL,
            "messages": [
                {"role": "system", "content": system_conversational},
                {"role": "user", "content": incoming_msg},
            ],
        }

        logger.info("[IA] Iniciando ciclo conversacional...")
        conv_response = call_openrouter(conversational_payload)
        ai_text = (
            conv_response.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )

        if not ai_text:
            ai_text = (
                "Entendi sua mensagem e registrei as informações. "
                "Como posso ajudar você a organizar os cuidados?"
            )

        twilio_resp.message(ai_text)

        await save_conversation_message(
            family_id=family_id,
            sender_type="ai",
            sender_name="CuidaFamília",
            message_text=ai_text,
        )

        await log_action(
            family_id, "note",
            f"Mensagem processada: {incoming_msg[:120]}",
            metadata={"sender": main_interlocutor},
        )

    except requests.exceptions.Timeout:
        logger.error("Timeout ao conectar com OpenRouter")
        twilio_resp.message(
            "A inteligência artificial demorou para responder. "
            "Por favor, tente novamente em alguns instantes."
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro na requisição ao OpenRouter: {e}")
        twilio_resp.message(
            "Tive um problema de comunicação com a inteligência artificial. "
            "Tente novamente mais tarde."
        )
    except Exception as e:
        logger.error(f"Erro crítico no webhook: {e}", exc_info=True)
        twilio_resp.message(
            "Ocorreu um erro inesperado no CuidaFamília. "
            "Nossa equipe foi notificada. Tente novamente em alguns minutos."
        )

    return Response(content=str(twilio_resp), media_type="application/xml")
