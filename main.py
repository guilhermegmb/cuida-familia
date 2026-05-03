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
import re
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo

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
# CONFIGURAÇÃO
# ============================================================

app = FastAPI(title="CuidaFamília API", version="3.0")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
TIMEZONE = ZoneInfo("America/Sao_Paulo")

# ============================================================
# ÂNCORA TEMPORAL (Camada 1)
# ============================================================

def get_now_brazil() -> datetime:
    """Retorna datetime atual no fuso de São Paulo."""
    return datetime.now(TIMEZONE)

def get_today_brazil() -> date:
    return get_now_brazil().date()

def get_temporal_anchor() -> str:
    """
    Gera bloco de contexto temporal para injetar nos prompts.
    Impede que a IA invente datas ou use datas do passado.
    """
    now = get_now_brazil()
    weekdays_pt = ["segunda-feira", "terça-feira", "quarta-feira",
                   "quinta-feira", "sexta-feira", "sábado", "domingo"]
    weekday_name = weekdays_pt[now.weekday()]
    tomorrow = now + timedelta(days=1)
    day_after = now + timedelta(days=2)

    # Próximos dias da semana
    next_days = {}
    for i in range(1, 8):
        d = now + timedelta(days=i)
        next_days[weekdays_pt[d.weekday()]] = d.strftime("%Y-%m-%d")

    return f"""
=== ÂNCORA TEMPORAL (USE SEMPRE) ===
Hoje é {weekday_name}, {now.strftime("%d/%m/%Y")}.
Hora atual: {now.strftime("%H:%M")} (horário de Brasília).
Data ISO hoje: {now.strftime("%Y-%m-%d")}
Amanhã: {tomorrow.strftime("%Y-%m-%d")} ({weekdays_pt[tomorrow.weekday()]})
Depois de amanhã: {day_after.strftime("%Y-%m-%d")} ({weekdays_pt[day_after.weekday()]})

Próximos dias da semana:
- Próxima segunda: {next_days.get("segunda-feira", "N/A")}
- Próxima terça: {next_days.get("terça-feira", "N/A")}
- Próxima quarta: {next_days.get("quarta-feira", "N/A")}
- Próxima quinta: {next_days.get("quinta-feira", "N/A")}
- Próxima sexta: {next_days.get("sexta-feira", "N/A")}
- Próximo sábado: {next_days.get("sábado", "N/A")}
- Próximo domingo: {next_days.get("domingo", "N/A")}

REGRA CRÍTICA: Toda data que você calcular DEVE ser >= {now.strftime("%Y-%m-%d")}.
Se a data calculada for anterior a hoje, PARE e peça esclarecimento ao usuário.
=====================================
"""

# ============================================================
# VALIDAÇÃO DE DATA (Camada 1 — backend determinístico)
# ============================================================

def validate_event_date(event_date_str: str) -> tuple[bool, str]:
    """
    Valida se a data do evento é válida e não está no passado.
    Retorna (is_valid, mensagem_de_erro_ou_vazio).
    """
    try:
        event_date = datetime.strptime(event_date_str, "%Y-%m-%d").date()
        today = get_today_brazil()
        if event_date < today:
            return False, f"A data {event_date.strftime('%d/%m/%Y')} já passou. Hoje é {today.strftime('%d/%m/%Y')}."
        return True, ""
    except ValueError:
        return False, f"Formato de data inválido: {event_date_str}. Use YYYY-MM-DD."

# ============================================================
# TOOLS EXPOSTAS À IA (Camada 4 — sem schedule_event direto)
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
                    "birthdate": {"type": "string", "description": "Formato YYYY-MM-DD"},
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
                "Solicita confirmação do usuário antes de agendar uma consulta, exame ou compromisso pontual. "
                "NUNCA agenda diretamente. Sempre use esta função para eventos pontuais."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Título do evento"},
                    "event_date": {"type": "string", "description": "Data no formato YYYY-MM-DD"},
                    "event_time": {"type": "string", "description": "Horário no formato HH:MM (opcional)"},
                    "event_type": {
                        "type": "string",
                        "enum": ["consulta", "exame", "compromisso", "lembrete", "outro"],
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
                "Use para medicamentos que devem ser tomados diariamente ou em horários fixos."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "medication_name": {"type": "string"},
                    "dosage": {"type": "string", "description": "Ex: 50mg"},
                    "frequency": {"type": "string", "description": "Ex: diário, 2x ao dia, semanal"},
                    "times": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Lista de horários, ex: ['08:00', '20:00']",
                    },
                    "notes": {"type": "string"},
                },
                "required": ["medication_name", "frequency"],
            },
        },
    },
]

# ============================================================
# SUPABASE HELPERS
# ============================================================

async def get_family_by_whatsapp(whatsapp_number: str):
    try:
        res = supabase.table("families").select("*").eq("main_whatsapp", whatsapp_number).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Erro ao buscar família: {e}")
        return None


async def get_patient_by_family_id(family_id: int):
    try:
        res = supabase.table("patients").select("*").eq("family_id", family_id).execute()
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


async def save_conversation_message(family_id: int, sender_type: str, sender_name: str, message_text: str):
    try:
        supabase.table("conversation_history").insert({
            "family_id": family_id,
            "sender_type": sender_type,
            "sender_name": sender_name,
            "message_text": message_text,
        }).execute()
    except Exception as e:
        logger.error(f"Erro ao salvar mensagem: {e}")


async def log_action(family_id: int, log_type: str, message: str, created_by: str = "IA", metadata: dict = None):
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
        logger.error(f"Erro ao buscar memória: {e}")
        return None


async def upsert_family_memory(family_id: int, summary: str = None, emotional_context: str = None,
                                care_routines: str = None, risk_notes: str = None):
    try:
        data = {
            "family_id": family_id,
            "summary": summary or "",
            "emotional_context": emotional_context or "",
            "care_routines": care_routines or "",
            "risk_notes": risk_notes or "",
            "updated_at": get_now_brazil().isoformat(),
        }
        existing = await get_family_memory(family_id)
        if existing:
            supabase.table("family_memory").update(data).eq("id", existing["id"]).execute()
        else:
            supabase.table("family_memory").insert(data).execute()
    except Exception as e:
        logger.error(f"Erro ao atualizar memória: {e}")


async def save_patient_info_db(family_id: int, patient_name: str, **kwargs):
    try:
        data = {"family_id": family_id, "patient_name": patient_name}
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
        supabase.table("families").update({"main_interlocutor_name": interlocutor_name}).eq("id", family_id).execute()
    except Exception as e:
        logger.error(f"Erro ao salvar interlocutor: {e}")


async def schedule_event_db(family_id: int, title: str, event_date: str,
                             event_time: str = None, event_type: str = "outro", description: str = None):
    """Grava evento na agenda. Só chamado após confirmação explícita do usuário."""
    try:
        supabase.table("family_agenda").insert({
            "family_id": family_id,
            "title": title,
            "event_date": event_date,
            "event_time": event_time,
            "event_type": event_type,
            "description": description,
            "status": "ativo",
        }).execute()
        logger.info(f"[AGENDA] Evento gravado: {title} em {event_date}")
    except Exception as e:
        logger.error(f"Erro ao agendar evento: {e}")


async def save_medication_routine_db(family_id: int, medication_name: str, dosage: str = None,
                                      frequency: str = None, times: list = None, notes: str = None):
    """
    Grava rotina de medicação recorrente.
    Usa family_agenda com event_type='medicação' e description com detalhes.
    Só chamado após confirmação explícita do usuário.
    """
    try:
        times_str = ", ".join(times) if times else "horário não especificado"
        desc = f"Dosagem: {dosage or 'N/A'} | Frequência: {frequency} | Horários: {times_str}"
        if notes:
            desc += f" | Obs: {notes}"

        # Para medicação recorrente, event_date = hoje (data de início da rotina)
        today_str = get_today_brazil().isoformat()

        if times:
            for t in times:
                supabase.table("family_agenda").insert({
                    "family_id": family_id,
                    "title": f"{medication_name} - {dosage or ''}".strip(" -"),
                    "event_date": today_str,
                    "event_time": t,
                    "event_type": "medicação",
                    "description": desc,
                    "status": "ativo",
                }).execute()
        else:
            supabase.table("family_agenda").insert({
                "family_id": family_id,
                "title": medication_name,
                "event_date": today_str,
                "event_time": None,
                "event_type": "medicação",
                "description": desc,
                "status": "ativo",
            }).execute()

        logger.info(f"[MEDICAÇÃO] Rotina gravada: {medication_name} | {frequency} | {times_str}")
    except Exception as e:
        logger.error(f"Erro ao salvar rotina de medicação: {e}")


# ============================================================
# GERENCIAMENTO DE CONFIRMAÇÕES PENDENTES (Camada 4)
# ============================================================

# Dicionário em memória: {whatsapp_number: {pending_data}}
# Em produção futura, migrar para Redis ou tabela Supabase
pending_confirmations: dict = {}


def store_pending_confirmation(whatsapp_number: str, confirmation_type: str, data: dict):
    pending_confirmations[whatsapp_number] = {
        "type": confirmation_type,
        "data": data,
        "created_at": get_now_brazil().isoformat(),
    }
    logger.info(f"[PENDENTE] Confirmação armazenada para {whatsapp_number}: {confirmation_type}")


def get_pending_confirmation(whatsapp_number: str) -> dict | None:
    return pending_confirmations.get(whatsapp_number)


def clear_pending_confirmation(whatsapp_number: str):
    if whatsapp_number in pending_confirmations:
        del pending_confirmations[whatsapp_number]
        logger.info(f"[PENDENTE] Confirmação limpa para {whatsapp_number}")


def is_affirmative(text: str) -> bool:
    """Detecta resposta afirmativa do usuário."""
    text_lower = text.lower().strip()
    affirmatives = ["sim", "s", "yes", "y", "ok", "pode", "confirmo", "confirmar",
                    "certo", "correto", "isso", "exato", "pode ser", "tá", "ta", "vai",
                    "pode registrar", "registra", "salva", "salvar", "agenda", "agendar"]
    return any(text_lower == a or text_lower.startswith(a) for a in affirmatives)


def is_negative(text: str) -> bool:
    """Detecta resposta negativa do usuário."""
    text_lower = text.lower().strip()
    negatives = ["não", "nao", "no", "n", "cancela", "cancelar", "errado", "errei",
                 "não é isso", "nao e isso", "para", "pare", "desiste", "desistir"]
    return any(text_lower == n or text_lower.startswith(n) for n in negatives)


# ============================================================
# FORMATADORES DE CONTEXTO
# ============================================================

def format_conversation_history(history: list) -> str:
    if not history:
        return "Nenhuma conversa anterior."
    lines = [f"- {msg.get('sender_name', 'Desconhecido')}: {msg.get('message_text', '')}" for msg in history]
    return "Histórico recente:\n" + "\n".join(lines)


def format_patient_info(patient: dict | None) -> str:
    if not patient:
        return "Nenhuma informação de paciente cadastrada ainda."
    parts = [f"- Nome: {patient.get('patient_name', 'N/A')}"]
    if patient.get("birthdate"):
        parts.append(f"- Nascimento: {patient['birthdate']}")
    if patient.get("medications"):
        parts.append(f"- Medicamentos: {patient['medications']}")
    if patient.get("health_condition"):
        parts.append(f"- Condição: {patient['health_condition']}")
    if patient.get("doctor_name"):
        parts.append(f"- Médico: {patient['doctor_name']}")
    return "Paciente:\n" + "\n".join(parts)


def format_family_memory(memory: dict | None) -> str:
    if not memory:
        return "Nenhuma memória consolidada ainda."
    parts = []
    if memory.get("summary"):
        parts.append(f"Resumo: {memory['summary']}")
    if memory.get("care_routines"):
        parts.append(f"Rotinas: {memory['care_routines']}")
    if memory.get("risk_notes"):
        parts.append(f"Riscos: {memory['risk_notes']}")
    if memory.get("emotional_context"):
        parts.append(f"Contexto emocional: {memory['emotional_context']}")
    return "Memória consolidada:\n" + "\n".join(parts)


# ============================================================
# OPENROUTER HELPER
# ============================================================

def call_openrouter(payload: dict) -> dict:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=45)
    resp.raise_for_status()
    return resp.json()


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/")
async def root():
    now = get_now_brazil()
    return {
        "status": "CuidaFamília Online",
        "version": "3.0-PCP",
        "timestamp_brasilia": now.isoformat(),
        "date_brasilia": now.strftime("%d/%m/%Y"),
    }


# ============================================================
# WEBHOOK PRINCIPAL
# ============================================================

@app.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    twilio_resp = MessagingResponse()

    try:
        form = await request.form()
        incoming_msg = (form.get("Body") or "").strip()
        raw_number = (form.get("From") or "").replace("whatsapp:", "").strip()

        # Normalizar número
        sender_number = re.sub(r"[\s\-\(\)]", "", raw_number)
        if not sender_number.startswith("+"):
            sender_number = "+" + sender_number

        logger.info(f"[MENSAGEM] {sender_number}: {incoming_msg}")

        # ----------------------------------------------------------
        # 1. Identificar família
        # ----------------------------------------------------------
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

        # ----------------------------------------------------------
        # 2. Verificar se há confirmação pendente (Camada 4)
        # ----------------------------------------------------------
        pending = get_pending_confirmation(sender_number)

        if pending:
            if is_affirmative(incoming_msg):
                # Usuário confirmou — executar a ação pendente
                ptype = pending["type"]
                pdata = pending["data"]
                clear_pending_confirmation(sender_number)

                if ptype == "schedule_event":
                    await schedule_event_db(family_id=family_id, **pdata)
                    await log_action(family_id, "agenda", f"Evento confirmado e agendado: {pdata.get('title')} em {pdata.get('event_date')}", metadata=pdata)
                    reply = (
                        f"✅ Agendado com sucesso!\n"
                        f"📅 *{pdata.get('title')}*\n"
                        f"📆 Data: {datetime.strptime(pdata['event_date'], '%Y-%m-%d').strftime('%d/%m/%Y')}"
                        + (f"\n⏰ Horário: {pdata['event_time']}" if pdata.get("event_time") else "")
                        + "\n\nPosso ajudar com mais alguma coisa?"
                    )

                elif ptype == "medication_routine":
                    await save_medication_routine_db(family_id=family_id, **pdata)
                    await log_action(family_id, "medicação", f"Rotina confirmada: {pdata.get('medication_name')}", metadata=pdata)
                    times_str = ", ".join(pdata.get("times", [])) if pdata.get("times") else "horário a definir"
                    reply = (
                        f"✅ Rotina de medicação registrada!\n"
                        f"💊 *{pdata.get('medication_name')}* {pdata.get('dosage', '')}\n"
                        f"🔁 Frequência: {pdata.get('frequency', 'N/A')}\n"
                        f"⏰ Horários: {times_str}\n\n"
                        f"Posso ajudar com mais alguma coisa?"
                    )
                else:
                    reply = "✅ Ação confirmada e registrada!"

                await save_conversation_message(family_id, "user", main_interlocutor, incoming_msg)
                await save_conversation_message(family_id, "ai", "CuidaFamília", reply)
                twilio_resp.message(reply)
                return Response(content=str(twilio_resp), media_type="application/xml")

            elif is_negative(incoming_msg):
                # Usuário cancelou
                pdata = pending.get("data", {})
                clear_pending_confirmation(sender_number)
                reply = (
                    f"Ok, cancelei o registro de *{pdata.get('title') or pdata.get('medication_name', 'item')}*. "
                    f"Se quiser ajustar alguma informação, é só me dizer!"
                )
                await save_conversation_message(family_id, "user", main_interlocutor, incoming_msg)
                await save_conversation_message(family_id, "ai", "CuidaFamília", reply)
                twilio_resp.message(reply)
                return Response(content=str(twilio_resp), media_type="application/xml")

            # Se não for sim nem não, limpa pendência e processa normalmente
            clear_pending_confirmation(sender_number)

        # ----------------------------------------------------------
        # 3. Registrar mensagem do usuário
        # ----------------------------------------------------------
        await save_conversation_message(family_id, "user", main_interlocutor, incoming_msg)

        # ----------------------------------------------------------
        # 4. Buscar contexto
        # ----------------------------------------------------------
        patient = await get_patient_by_family_id(family_id)
        patient_name = patient.get("patient_name", "paciente") if patient else "paciente"
        family_memory = await get_family_memory(family_id)
        history = await get_conversation_history(family_id, limit=30)

        patient_ctx = format_patient_info(patient)
        memory_ctx = format_family_memory(family_memory)
        history_ctx = format_conversation_history(history)
        temporal_anchor = get_temporal_anchor()

        # ----------------------------------------------------------
        # 5. CICLO ANALÍTICO (Camada 3 + Camada 1)
        # ----------------------------------------------------------
        system_analytical = f"""
Você é o módulo ANALÍTICO do CuidaFamília para a família {family_name} / paciente {patient_name}.

{temporal_anchor}

Seu papel:
- Analisar a mensagem recebida
- Chamar tools quando necessário (save_patient_info, save_interlocutor_info, request_schedule_confirmation, request_medication_confirmation)
- NUNCA agendar diretamente — use SEMPRE request_schedule_confirmation ou request_medication_confirmation
- Retornar JSON com memory_update

Contexto:
{patient_ctx}

{memory_ctx}

{history_ctx}

GUARDRAILS CLÍNICOS:
- Não diagnostique
- Não recomende medicações
- Não altere prescrições
- Em emergência (dor no peito, falta de ar, desmaio): a camada conversacional alertará para ligar 192

REGRAS DE DATA (CRÍTICO):
- Use SEMPRE a Âncora Temporal acima para calcular datas
- "amanhã" = {(get_now_brazil() + timedelta(days=1)).strftime("%Y-%m-%d")}
- "depois de amanhã" = {(get_now_brazil() + timedelta(days=2)).strftime("%Y-%m-%d")}
- NUNCA use datas anteriores a hoje ({get_today_brazil().isoformat()})
- Se não souber a data exata, peça confirmação

REGRAS DE MEDICAÇÃO:
- Medicação recorrente (diária, semanal, etc.) → use request_medication_confirmation
- Consulta/exame/compromisso pontual → use request_schedule_confirmation

FORMATO DO CAMPO 'content':
Retorne APENAS este JSON (sem texto fora dele):
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

        logger.info("[IA] Ciclo analítico iniciado...")
        analytical_response = call_openrouter(analytical_payload)
        analytical_msg = analytical_response.get("choices", [{}])[0].get("message", {})

        # ----------------------------------------------------------
        # 6. Processar tool calls (Camada 4)
        # ----------------------------------------------------------
        pending_action_reply = None  # Mensagem de confirmação a enviar ao usuário

        if analytical_msg.get("tool_calls"):
            for tool_call in analytical_msg["tool_calls"]:
                fn_name = tool_call["function"]["name"]
                args = json.loads(tool_call["function"]["arguments"] or "{}")
                logger.info(f"[TOOL] {fn_name} | {args}")

                if fn_name == "save_patient_info":
                    await save_patient_info_db(family_id=family_id, **args)
                    await log_action(family_id, "update", f"Paciente atualizado: {args.get('patient_name')}", metadata=args)

                elif fn_name == "save_interlocutor_info":
                    await save_interlocutor_info_db(family_id, args.get("interlocutor_name", ""))
                    await log_action(family_id, "update", f"Interlocutor: {args.get('interlocutor_name')}", metadata=args)

                elif fn_name == "request_schedule_confirmation":
                    # Validar data antes de pedir confirmação
                    event_date = args.get("event_date", "")
                    is_valid, date_error = validate_event_date(event_date)

                    if not is_valid:
                        pending_action_reply = (
                            f"⚠️ Percebi uma inconsistência na data: {date_error}\n"
                            f"Pode me confirmar a data correta do evento *{args.get('title')}*?"
                        )
                    else:
                        store_pending_confirmation(sender_number, "schedule_event", args)
                        date_fmt = datetime.strptime(event_date, "%Y-%m-%d").strftime("%d/%m/%Y")
                        time_str = f" às {args['event_time']}" if args.get("event_time") else ""
                        pending_action_reply = (
                            f"📅 Posso registrar o seguinte?\n\n"
                            f"*{args.get('title')}*\n"
                            f"📆 Data: {date_fmt}{time_str}\n"
                            f"📋 Tipo: {args.get('event_type', 'N/A')}\n"
                            + (f"📝 {args['description']}\n" if args.get("description") else "")
                            + f"\nResponda *SIM* para confirmar ou *NÃO* para cancelar."
                        )

                elif fn_name == "request_medication_confirmation":
                    store_pending_confirmation(sender_number, "medication_routine", args)
                    times_str = ", ".join(args.get("times", [])) if args.get("times") else "horário a definir"
                    pending_action_reply = (
                        f"💊 Posso registrar a seguinte rotina de medicação?\n\n"
                        f"*{args.get('medication_name')}* {args.get('dosage', '')}\n"
                        f"🔁 Frequência: {args.get('frequency', 'N/A')}\n"
                        f"⏰ Horários: {times_str}\n"
                        + (f"📝 {args['notes']}\n" if args.get("notes") else "")
                        + f"\nResponda *SIM* para confirmar ou *NÃO* para cancelar."
                    )

        # ----------------------------------------------------------
        # 7. Atualizar memória consolidada
        # ----------------------------------------------------------
        if analytical_msg.get("content"):
            try:
                parsed = json.loads(analytical_msg["content"])
                mu = parsed.get("memory_update", {})
                if any(mu.get(k) for k in ["summary", "emotional_context", "care_routines", "risk_notes"]):
                    await upsert_family_memory(
                        family_id=family_id,
                        summary=mu.get("summary"),
                        emotional_context=mu.get("emotional_context"),
                        care_routines=mu.get("care_routines"),
                        risk_notes=mu.get("risk_notes"),
                    )
                    logger.info("[MEMÓRIA] Atualizada.")
            except Exception as e:
                logger.warning(f"Falha ao parsear memory_update: {e}")

        # Se há uma ação pendente de confirmação, enviar e encerrar
        if pending_action_reply:
            await save_conversation_message(family_id, "ai", "CuidaFamília", pending_action_reply)
            await log_action(family_id, "note", f"Confirmação solicitada para: {pending_action_reply[:80]}")
            twilio_resp.message(pending_action_reply)
            return Response(content=str(twilio_resp), media_type="application/xml")

        # ----------------------------------------------------------
        # 8. CICLO CONVERSACIONAL (Camada 3)
        # ----------------------------------------------------------
        # Recarregar memória após possível atualização
        family_memory = await get_family_memory(family_id)
        memory_ctx = format_family_memory(family_memory)

        system_conversational = f"""
Você é o CuidaFamília, Concierge de Cuidado e Secretária Executiva Familiar.

Atende a família {family_name}, cuidando de {patient_name}.

{temporal_anchor}

MEMÓRIA CONSOLIDADA:
{memory_ctx}

INFORMAÇÕES DO PACIENTE:
{patient_ctx}

HISTÓRICO RECENTE:
{history_ctx}

GUARDRAILS CRÍTICOS:
- NUNCA forneça diagnósticos médicos
- NUNCA recomende, altere ou ajuste medicações
- NUNCA diga se exame está normal ou anormal
- Em emergência (dor no peito, falta de ar, desmaio, queda grave):
  "⚠️ EMERGÊNCIA! Ligue para o SAMU (192) ou vá ao pronto-socorro AGORA!"
- Foque em organização, logística, comunicação e apoio emocional leve

Estilo:
- Linguagem simples, clara, respeitosa
- Respostas objetivas e acolhedoras
- Ofereça ajuda prática (registrar, agendar, lembrar)
- Use emojis com moderação para facilitar leitura no WhatsApp
"""

        conv_payload = {
            "model": OPENROUTER_MODEL,
            "messages": [
                {"role": "system", "content": system_conversational},
                {"role": "user", "content": incoming_msg},
            ],
        }

        logger.info("[IA] Ciclo conversacional iniciado...")
        conv_response = call_openrouter(conv_payload)
        ai_text = conv_response.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

        if not ai_text:
            ai_text = (
                "Entendi sua mensagem e registrei as informações. "
                "Como posso ajudar a organizar os cuidados?"
            )

        # ----------------------------------------------------------
        # 9. Salvar resposta e enviar
        # ----------------------------------------------------------
        await save_conversation_message(family_id, "ai", "CuidaFamília", ai_text)
        await log_action(family_id, "note", f"Mensagem processada: {incoming_msg[:120]}", metadata={"sender": main_interlocutor})

        twilio_resp.message(ai_text)

    except requests.exceptions.Timeout:
        logger.error("Timeout OpenRouter")
        twilio_resp.message("A IA demorou para responder. Tente novamente em instantes.")
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro OpenRouter: {e}")
        twilio_resp.message("Problema de comunicação com a IA. Tente novamente.")
    except Exception as e:
        logger.error(f"Erro crítico: {e}", exc_info=True)
        twilio_resp.message("Ocorreu um erro inesperado. Tente novamente em alguns minutos.")

    return Response(content=str(twilio_resp), media_type="application/xml")
