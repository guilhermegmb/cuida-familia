"""
CuidaFamília - Agente de IA Concierge de Cuidado
Versão: 2.0 (Arquitetura Cognitiva com Memória Consolidada)
Data: 2026-05-01
"""

import os
import json
import logging
from datetime import datetime

import requests
from fastapi import FastAPI, Request, Response
from supabase import create_client, Client
from twilio.twiml.messaging_response import MessagingResponse

# ============================================================================
# LOGGING
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("CuidaFamilia")

# ============================================================================
# CONFIGURAÇÃO BÁSICA
# ============================================================================

app = FastAPI(title="CuidaFamília API", version="2.0")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# ============================================================================
# TOOLS (FUNCTION CALLING)
# ============================================================================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "save_patient_info",
            "description": "Salva ou atualiza informações do paciente idoso no banco de dados.",
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
            "name": "schedule_event",
            "description": "Agenda um evento, consulta, medicação ou lembrete.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "event_date": {"type": "string"},
                    "event_time": {"type": "string"},
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
]

# ============================================================================
# SUPABASE HELPERS
# ============================================================================


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
        data = {
            "family_id": family_id,
            "sender_type": sender_type,
            "sender_name": sender_name,
            "message_text": message_text,
        }
        supabase.table("conversation_history").insert(data).execute()
    except Exception as e:
        logger.error(f"Erro ao salvar mensagem: {e}")


async def log_action(family_id: int, log_type: str, message: str, created_by: str = "IA", metadata: dict | None = None):
    try:
        data = {
            "family_id": family_id,
            "log_type": log_type,
            "message": message,
            "created_by": created_by,
            "metadata": metadata,
        }
        supabase.table("family_logs").insert(data).execute()
    except Exception as e:
        logger.error(f"Erro ao registrar log: {e}")


async def save_patient_info_db(
    family_id: int,
    patient_name: str,
    birthdate: str | None = None,
    gender: str | None = None,
    medications: str | None = None,
    health_condition: str | None = None,
    doctor_name: str | None = None,
    doctor_phone: str | None = None,
):
    try:
        patient_data = {
            "family_id": family_id,
            "patient_name": patient_name,
            "birthdate": birthdate,
            "gender": gender,
            "medications": medications,
            "health_condition": health_condition,
            "doctor_name": doctor_name,
            "doctor_phone": doctor_phone,
        }
        patient_data = {k: v for k, v in patient_data.items() if v is not None}
        existing = await get_patient_by_family_id(family_id)
        if existing:
            supabase.table("patients").update(patient_data).eq("family_id", family_id).execute()
        else:
            supabase.table("patients").insert(patient_data).execute()
    except Exception as e:
        logger.error(f"Erro ao salvar paciente: {e}")


async def save_interlocutor_info_db(family_id: int, interlocutor_name: str):
    try:
        supabase.table("families").update({"main_interlocutor_name": interlocutor_name}).eq("id", family_id).execute()
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
    try:
        data = {
            "family_id": family_id,
            "title": title,
            "event_date": event_date,
            "event_time": event_time,
            "event_type": event_type,
            "description": description,
            "status": "ativo",
        }
        supabase.table("family_agenda").insert(data).execute()
    except Exception as e:
        logger.error(f"Erro ao agendar evento: {e}")


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

# ============================================================================
# CONTEXTO PARA PROMPTS
# ============================================================================


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

# ============================================================================
# OPENROUTER HELPER
# ============================================================================


def call_openrouter(payload: dict) -> dict:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=40)
    resp.raise_for_status()
    return resp.json()

# ============================================================================
# HEALTH CHECK
# ============================================================================


@app.get("/")
async def root():
    return {
        "status": "CuidaFamília Online",
        "version": "2.0",
        "timestamp": datetime.utcnow().isoformat(),
    }

# ============================================================================
# WEBHOOK WHATSAPP (ORQUESTRAÇÃO COGNITIVA)
# ============================================================================


@app.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    twilio_resp = MessagingResponse()

    try:
        form = await request.form()
        incoming_msg = (form.get("Body") or "").strip()
        sender_number = (form.get("From") or "").replace("whatsapp:", "")

        logger.info(f"[NOVA MENSAGEM] {sender_number}: {incoming_msg}")

        # --------------------------------------------------------------------
        # 1. Identificar família
        # --------------------------------------------------------------------
        family = await get_family_by_whatsapp(sender_number)
        if not family:
            msg = (
                "Olá! Não consegui identificar sua família no CuidaFamília.\n"
                "Verifique se seu número está cadastrado ou fale com o suporte."
            )
            twilio_resp.message(msg)
            return Response(content=str(twilio_resp), media_type="application/xml")

        family_id = family["id"]
        family_name = family.get("family_name", "Família")
        main_interlocutor = family.get("main_interlocutor_name") or "Responsável"

        # --------------------------------------------------------------------
        # 2. Registrar mensagem do usuário imediatamente
        # --------------------------------------------------------------------
        await save_conversation_message(
            family_id=family_id,
            sender_type="user",
            sender_name=main_interlocutor,
            message_text=incoming_msg,
        )

        # --------------------------------------------------------------------
        # 3. Buscar contexto: paciente, memória consolidada, histórico
        # --------------------------------------------------------------------
        patient = await get_patient_by_family_id(family_id)
        patient_name = patient.get("patient_name", "paciente") if patient else "paciente"

        family_memory = await get_family_memory(family_id)
        history = await get_conversation_history(family_id, limit=30)

        patient_context = format_patient_info_for_context(patient)
        memory_context = format_family_memory_for_context(family_memory)
        history_context = format_conversation_history_for_context(history)

        # --------------------------------------------------------------------
        # 4. PRIMEIRO CICLO: ANÁLISE + TOOLS + ATUALIZAÇÃO DE MEMÓRIA
        # --------------------------------------------------------------------
        system_analytical = f"""
Você é o módulo ANALÍTICO do CuidaFamília, um Concierge de Cuidado para a família {family_name} e o paciente {patient_name}.

Seu papel neste ciclo NÃO é conversar com o usuário, e sim:
- analisar a nova mensagem;
- decidir se deve chamar ferramentas (functions) para:
  - salvar informações do paciente;
  - salvar interlocutor;
  - agendar eventos;
- sugerir atualização da MEMÓRIA CONSOLIDADA da família.

Contexto disponível:

{patient_context}

{memory_context}

{history_context}

GUARDRAILS CLÍNICOS (NUNCA viole):
- Não faça diagnósticos.
- Não recomende, altere ou confirme medicações.
- Não dê conselhos médicos específicos.
- Em caso de emergência (dor no peito, falta de ar, desmaio, etc.), a camada conversacional avisará para ligar 192.

FORMATO DA SUA RESPOSTA:
1) Você pode chamar tools quantas vezes forem necessárias.
2) No campo 'content', você DEVE retornar um JSON com a seguinte estrutura:

{{
  "memory_update": {{
    "summary": "string (ou null)",
    "emotional_context": "string (ou null)",
    "care_routines": "string (ou null)",
    "risk_notes": "string (ou null)"
  }}
}}

Se não houver nada para atualizar, use null nos campos.
Não escreva texto fora de JSON no 'content'.
"""

        analytical_messages = [
            {"role": "system", "content": system_analytical},
            {"role": "user", "content": incoming_msg},
        ]

        analytical_payload = {
            "model": OPENROUTER_MODEL,
            "messages": analytical_messages,
            "tools": TOOLS,
            "tool_choice": "auto",
        }

        logger.info("[IA] Iniciando ciclo analítico com tools...")
        analytical_response = call_openrouter(analytical_payload)
        analytical_choice = analytical_response.get("choices", [{}])[0]
        analytical_msg = analytical_choice.get("message", {})

        # --------------------------------------------------------------------
        # 4.1 Executar tools chamadas pelo modelo
        # --------------------------------------------------------------------
        if analytical_msg.get("tool_calls"):
            for tool_call in analytical_msg["tool_calls"]:
                fn_name = tool_call["function"]["name"]
                args = json.loads(tool_call["function"]["arguments"] or "{}")
                logger.info(f"[FUNCTION CALL] {fn_name} | {args}")

                if fn_name == "save_patient_info":
                    await save_patient_info_db(family_id=family_id, **args)
                    await log_action(
                        family_id,
                        "update",
                        f"Informações do paciente atualizadas: {args.get('patient_name')}",
                        metadata=args,
                    )

                elif fn_name == "save_interlocutor_info":
                    await save_interlocutor_info_db(family_id, args.get("interlocutor_name", ""))
                    await log_action(
                        family_id,
                        "update",
                        f"Interlocutor principal registrado: {args.get('interlocutor_name')}",
                        metadata=args,
                    )

                elif fn_name == "schedule_event":
                    await schedule_event_db(family_id=family_id, **args)
                    await log_action(
                        family_id,
                        "update",
                        f"Evento agendado: {args.get('title')} em {args.get('event_date')}",
                        metadata=args,
                    )

        # --------------------------------------------------------------------
        # 4.2 Atualizar memória consolidada com base no JSON retornado
        # --------------------------------------------------------------------
        memory_update = None
        if analytical_msg.get("content"):
            try:
                parsed = json.loads(analytical_msg["content"])
                memory_update = parsed.get("memory_update")
            except Exception as e:
                logger.warning(f"Falha ao parsear JSON de memory_update: {e}")

        if memory_update:
            await upsert_family_memory(
                family_id=family_id,
                summary=memory_update.get("summary"),
                emotional_context=memory_update.get("emotional_context"),
                care_routines=memory_update.get("care_routines"),
                risk_notes=memory_update.get("risk_notes"),
            )
            logger.info("[MEMÓRIA] Memória consolidada atualizada pelo ciclo analítico.")

        # Recarregar memória após possível atualização
        family_memory = await get_family_memory(family_id)
        memory_context = format_family_memory_for_context(family_memory)

        # --------------------------------------------------------------------
        # 5. SEGUNDO CICLO: RESPOSTA CONVERSACIONAL
        # --------------------------------------------------------------------
        system_conversational = f"""
Você é o CuidaFamília, um Concierge de Cuidado e Secretária Executiva Familiar.

Você atende a família {family_name}, cuidando de {patient_name}.

Seu papel:
- responder de forma empática, organizada e profissional;
- ajudar a organizar informações, registrar fatos, agendar compromissos e lembrar rotinas;
- usar a MEMÓRIA CONSOLIDADA e o histórico para manter continuidade.

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
- Sempre que a mensagem indicar emergência (dor no peito, falta de ar, desmaio, etc.), diga:
  "EMERGÊNCIA DETECTADA! Ligue para o SAMU (192) ou procure o pronto-socorro mais próximo AGORA!"
- Foque em organização, logística, comunicação com o médico e apoio emocional leve.

Estilo:
- linguagem simples, clara, respeitosa;
- respostas objetivas, mas acolhedoras;
- ofereça ajuda prática (ex: registrar, agendar, lembrar).
"""

        conversational_messages = [
            {"role": "system", "content": system_conversational},
            {"role": "user", "content": incoming_msg},
        ]

        conversational_payload = {
            "model": OPENROUTER_MODEL,
            "messages": conversational_messages,
        }

        logger.info("[IA] Iniciando ciclo conversacional...")
        conv_response = call_openrouter(conversational_payload)
        conv_choice = conv_response.get("choices", [{}])[0]
        ai_text = conv_choice.get("message", {}).get("content", "").strip()

        if not ai_text:
            ai_text = (
                "Entendi sua mensagem e registrei as informações. "
                "Como posso ajudar você a organizar os cuidados a partir disso?"
            )

        twilio_resp.message(ai_text)

        await save_conversation_message(
            family_id=family_id,
            sender_type="ai",
            sender_name="CuidaFamília",
            message_text=ai_text,
        )

        await log_action(
            family_id,
            "note",
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
            "Ocorreu um erro inesperado no sistema CuidaFamília. "
            "Nossa equipe foi notificada. Tente novamente em alguns minutos."
        )

    return Response(content=str(twilio_resp), media_type="application/xml")
