"""
CuidaFamília - Agente de IA Concierge de Cuidado
Versão: 3.1 (Melhorias sem quebrar nada)

CORREÇÕES ANTERIORES (v3.0):
  [FASE 1] Medicação recorrente vai para medication_schedules (não mais family_agenda)
  [FASE 2] Confirmações pendentes persistidas no banco (pending_confirmations)
  [FASE 3] Regra de clarificação para mensagens vagas antes de registrar qualquer coisa

MELHORIAS v3.1:
  [FIX 1] upsert_family_memory: merge inteligente — não sobrescreve campos existentes com vazio
  [FIX 2] Clarificação acumulada: IA recebe dados já coletados no histórico para não repetir perguntas
  [FIX 3] Segundo ciclo condicional: não chama OpenRouter duas vezes quando resposta já está definida
  [FIX 4] Log de ação enriquecido: registra tipo de ação executada para melhor rastreabilidade
"""

import os
import json
import logging
from datetime import datetime

import requests
from fastapi import FastAPI, Request, Response
from supabase import create_client, Client
from twilio.twiml.messaging_response import MessagingResponse

# ====
# LOGGING
# ====

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("CuidaFamilia")

# ====
# CONFIGURAÇÃO BÁSICA
# ====

app = FastAPI(title="CuidaFamília API", version="3.0")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# ====
# TOOLS (FUNCTION CALLING)
# ====

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
            "description": "Agenda um evento pontual: consulta, exame, compromisso ou lembrete com data específica. NÃO usar para medicações recorrentes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "event_date": {"type": "string"},
                    "event_time": {"type": "string"},
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
    # [FASE 1] Nova tool separada para medicação recorrente
    {
        "type": "function",
        "function": {
            "name": "save_medication_schedule",
            "description": "Registra uma rotina de medicação recorrente (diária, semanal, etc.). Usar APENAS para medicações com frequência contínua, não para eventos pontuais.",
            "parameters": {
                "type": "object",
                "properties": {
                    "medication_name": {"type": "string", "description": "Nome do medicamento"},
                    "dosage": {"type": "string", "description": "Dosagem ex: 50mg, 1 comprimido"},
                    "times": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista de horários ex: ['08:00', '20:00']",
                    },
                    "frequency": {
                    "type": "string",
                    "description": "Frequência: diário, semanal, etc.",
                    },
                    "notes": {"type": "string", "description": "Observações adicionais"},
                },
                "required": ["medication_name", "dosage", "times", "frequency"],
            },
        },
    },
    # [FASE 3] Tool para sinalizar que a mensagem está incompleta
    {
        "type": "function",
        "function": {
            "name": "request_clarification",
            "description": "Usar quando a mensagem do usuário tem intenção de registrar algo, mas falta pelo menos um campo obrigatório (nome do medicamento, data, horário, médico, etc.). Nunca inferir campos obrigatórios sem avisar o usuário.",
            "parameters": {
                "type": "object",
                "properties": {
                    "intent": {
                    "type": "string",
                    "description": "O que o usuário parece querer registrar: medicação, consulta, exame, etc.",
                    },
                    "missing_fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista dos campos que estão faltando para completar o registro.",
                    },
                },
                "required": ["intent", "missing_fields"],
            },
        },
    },
]

# ====
# SUPABASE HELPERS
# ====


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
    """[FASE 1] Apenas eventos pontuais vão para family_agenda."""
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


# [FASE 1] Nova função: medicação recorrente vai para medication_schedules
async def save_medication_schedule_db(
    family_id: int,
    medication_name: str,
    dosage: str,
    times: list,
    frequency: str,
    notes: str | None = None,
):
    """[FASE 1] Medicações recorrentes vão para medication_schedules, não para family_agenda."""
    try:
        data = {
            "family_id": family_id,
            "medication_name": medication_name,
            "dosage": dosage,
            "times": times,  # array de strings ex: ["08:00", "20:00"]
            "is_active": True,
        }
        # Verificar se já existe essa medicação para essa família (evitar duplicata)
        existing = (
            supabase.table("medication_schedules")
            .select("id")
            .eq("family_id", family_id)
            .eq("medication_name", medication_name)
            .execute()
        )
        if existing.data:
            supabase.table("medication_schedules").update(data).eq("id", existing.data[0]["id"]).execute()
            logger.info(f"[FASE 1] Medicação atualizada em medication_schedules: {medication_name}")
        else:
            supabase.table("medication_schedules").insert(data).execute()
            logger.info(f"[FASE 1] Medicação inserida em medication_schedules: {medication_name}")
    except Exception as e:
        logger.error(f"Erro ao salvar medicação recorrente: {e}")


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
    """[FIX 1] Merge inteligente: só atualiza campos que a IA enviou, preserva os demais."""
    try:
        existing = await get_family_memory(family_id)

        # Monta apenas os campos que a IA realmente enviou (não None e não vazio)
        updates = {"updated_at": datetime.utcnow().isoformat()}
        if summary:
            updates["summary"] = summary
        if emotional_context:
            updates["emotional_context"] = emotional_context
        if care_routines:
            updates["care_routines"] = care_routines
        if risk_notes:
            updates["risk_notes"] = risk_notes

        if existing:
            # Atualiza apenas os campos enviados — preserva o restante
            supabase.table("family_memory").update(updates).eq("id", existing["id"]).execute()
        else:
            # Primeiro registro: insere com todos os campos (vazios onde não há dado)
            data = {
                "family_id": family_id,
                "summary": summary or "",
                "emotional_context": emotional_context or "",
                "care_routines": care_routines or "",
                "risk_notes": risk_notes or "",
                "updated_at": datetime.utcnow().isoformat(),
            }
            supabase.table("family_memory").insert(data).execute()
    except Exception as e:
        logger.error(f"Erro ao atualizar memória da família: {e}")


# ====
# [FASE 2] PENDING CONFIRMATIONS — PERSISTÊNCIA NO BANCO
# ====

async def save_pending_confirmation(family_id: int, payload: dict, confirmation_text: str):
    """[FASE 2] Persiste a confirmação pendente no banco para sobreviver a reinícios do Render."""
    try:
        data = {
            "family_id": family_id,
            "payload": json.dumps(payload),
            "confirmation_text": confirmation_text,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
        }
        supabase.table("pending_confirmations").insert(data).execute()
        logger.info(f"[FASE 2] Confirmação pendente salva no banco para família {family_id}")
    except Exception as e:
        logger.error(f"Erro ao salvar confirmação pendente: {e}")


async def get_pending_confirmation(family_id: int):
    """[FASE 2] Busca a confirmação pendente mais recente da família no banco."""
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


async def resolve_pending_confirmation(confirmation_id: int, status: str = "confirmed"):
    """[FASE 2] Marca a confirmação como resolvida (confirmed ou cancelled)."""
    try:
        supabase.table("pending_confirmations").update({"status": status}).eq("id", confirmation_id).execute()
        logger.info(f"[FASE 2] Confirmação {confirmation_id} marcada como {status}")
    except Exception as e:
        logger.error(f"Erro ao resolver confirmação pendente: {e}")


def is_affirmative(text: str) -> bool:
    """Verifica se a mensagem é uma confirmação positiva."""
    normalized = text.strip().lower()
    return normalized in ["sim", "s", "yes", "y", "confirmar", "confirmo", "ok", "pode", "pode ser", "tá", "ta", "certo"]


def is_negative(text: str) -> bool:
    """Verifica se a mensagem é uma negação."""
    normalized = text.strip().lower()
    return normalized in ["não", "nao", "n", "no", "cancelar", "cancela", "cancelo", "negativo"]


# ====
# CONTEXTO PARA PROMPTS
# ====


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


# ====
# OPENROUTER HELPER
# ====


def call_openrouter(payload: dict) -> dict:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=40)
    resp.raise_for_status()
    return resp.json()


# ====
# HEALTH CHECK
# ====


@app.get("/")
async def root():
    return {
        "status": "CuidaFamília Online",
        "version": "3.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


# ====
# WEBHOOK WHATSAPP (ORQUESTRAÇÃO COGNITIVA v3.0)
# ====


@app.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    twilio_resp = MessagingResponse()

    try:
        form = await request.form()
        incoming_msg = (form.get("Body") or "").strip()
        sender_number = (form.get("From") or "").replace("whatsapp:", "")

        logger.info(f"[NOVA MENSAGEM] {sender_number}: {incoming_msg}")

        # ----
        # 1. Identificar família
        # ----
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

        # ----
        # [FASE 2] Verificar se há confirmação pendente no banco ANTES de qualquer processamento
        # ----
        pending = await get_pending_confirmation(family_id)

        if pending:
            logger.info(f"[FASE 2] Confirmação pendente encontrada no banco: id={pending['id']}")

            if is_affirmative(incoming_msg):
                # Executar a ação confirmada
                payload = json.loads(pending["payload"])
                action_type = payload.get("action_type")
                action_data = payload.get("data", {})

                await resolve_pending_confirmation(pending["id"], "confirmed")

                if action_type == "schedule_event":
                    await schedule_event_db(family_id=family_id, **action_data)
                    await log_action(family_id, "update", f"Evento confirmado e agendado: {action_data.get('title')}", metadata=action_data)
                    reply = (
                    f"✅ Agendado com sucesso!\n"
                    f"📅 {action_data.get('title')}\n"
                    f"📆 Data: {action_data.get('event_date')}\n"
                    f"⏰ Horário: {action_data.get('event_time', 'não informado')}\n\n"
                    f"Posso ajudar com mais alguma coisa?"
                    )

                elif action_type == "save_medication_schedule":
                    await save_medication_schedule_db(family_id=family_id, **action_data)
                    await log_action(family_id, "update", f"Medicação confirmada e registrada: {action_data.get('medication_name')}", metadata=action_data)
                    times_str = ", ".join(action_data.get("times", []))
                    reply = (
                    f"✅ Rotina de medicação registrada!\n"
                    f"💊 {action_data.get('medication_name')} {action_data.get('dosage')}\n"
                    f"🔁 Frequência: {action_data.get('frequency')}\n"
                    f"⏰ Horários: {times_str}\n\n"
                    f"Posso ajudar com mais alguma coisa?"
                    )

                else:
                    reply = "✅ Ação confirmada e registrada com sucesso!"

                await save_conversation_message(family_id, "user", main_interlocutor, incoming_msg)
                await save_conversation_message(family_id, "ai", "CuidaFamília", reply)
                twilio_resp.message(reply)
                return Response(content=str(twilio_resp), media_type="application/xml")

            elif is_negative(incoming_msg):
                await resolve_pending_confirmation(pending["id"], "cancelled")
                reply = "❌ Cancelado. Nada foi registrado.\n\nPosso ajudar com mais alguma coisa?"
                await save_conversation_message(family_id, "user", main_interlocutor, incoming_msg)
                await save_conversation_message(family_id, "ai", "CuidaFamília", reply)
                twilio_resp.message(reply)
                return Response(content=str(twilio_resp), media_type="application/xml")

            else:
                # Usuário enviou outra mensagem sem responder SIM/NÃO — cancelar pendência e processar normalmente
                logger.info(f"[FASE 2] Usuário enviou nova mensagem sem confirmar. Cancelando pendência {pending['id']}.")
                await resolve_pending_confirmation(pending["id"], "cancelled")

        # ----
        # 2. Registrar mensagem do usuário
        # ----
        await save_conversation_message(
            family_id=family_id,
            sender_type="user",
            sender_name=main_interlocutor,
            message_text=incoming_msg,
        )

        # ----
        # 3. Buscar contexto: paciente, memória consolidada, histórico
        # ----
        patient = await get_patient_by_family_id(family_id)
        patient_name = patient.get("patient_name", "paciente") if patient else "paciente"

        family_memory = await get_family_memory(family_id)
        history = await get_conversation_history(family_id, limit=30)

        patient_context = format_patient_info_for_context(patient)
        memory_context = format_family_memory_for_context(family_memory)
        history_context = format_conversation_history_for_context(history)

        # ----
        # 4. PRIMEIRO CICLO: ANÁLISE + TOOLS + ATUALIZAÇÃO DE MEMÓRIA
        # ----
        today_str = datetime.now().strftime("%d/%m/%Y")
        weekday_str = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"][datetime.now().weekday()]

        system_analytical = f"""
Você é o módulo ANALÍTICO do CuidaFamília, um Concierge de Cuidado para a família {family_name} e o paciente {patient_name}.

Hoje é {weekday_str}, {today_str}.

Seu papel neste ciclo NÃO é conversar com o usuário, e sim:
- analisar a nova mensagem;
- decidir se deve chamar ferramentas (functions);
- sugerir atualização da MEMÓRIA CONSOLIDADA da família.

REGRAS CRÍTICAS PARA CHAMADA DE TOOLS:

[FASE 1 - ROTEAMENTO DE MEDICAÇÃO]
- Se a mensagem menciona medicação RECORRENTE (todo dia, diariamente, toda manhã, etc.):
  → Use EXCLUSIVAMENTE a tool "save_medication_schedule"
  → NUNCA use "schedule_event" para medicações recorrentes
- Se a mensagem menciona evento PONTUAL (consulta, exame com data específica):
  → Use "schedule_event"

[FASE 2 - CONFIRMAÇÃO ANTES DE GRAVAR]
- NUNCA grave diretamente no banco sem confirmação do usuário.
- Para qualquer agendamento ou medicação, você deve:
  1. Preparar os dados completos
  2. Retornar no JSON o campo "pending_action" com os dados para confirmação
  3. NÃO chamar as tools diretamente — a confirmação será feita pelo usuário

[FASE 3 - CLARIFICAÇÃO OBRIGATÓRIA]
- Se a mensagem tem intenção de registrar algo, mas falta campo obrigatório:
  → Use a tool "request_clarification"
  → IMPORTANTE: Verifique o HISTÓRICO RECENTE antes de pedir clarificação.
    Se o usuário já informou o dado em mensagem anterior desta mesma conversa, USE esse dado.
    Só peça clarificação se o dado realmente não foi informado em nenhuma mensagem anterior.
  → Campos obrigatórios por tipo:
    - consulta/exame: título/médico, data, horário
    - medicação recorrente: nome do medicamento, dosagem, horários
    - lembrete: descrição, data
- Exemplos de mensagens vagas que DEVEM acionar clarificação:
  → "ela tem consulta" (falta: médico, data, horário — se não estiverem no histórico)
  → "ela toma remédio todo dia" (falta: nome, dosagem, horário)
  → "precisa de exame" (falta: tipo, data)
  → "tem compromisso amanhã" (falta: descrição, horário)
- Se o usuário já disse "amanhã às 15h" e depois informou o médico, COMBINE os dados e vá para pending_action.

[DATAS PASSADAS]
- Se a data mencionada for anterior a hoje ({today_str}), NÃO agende.
- Retorne no JSON o campo "date_error": true com uma explicação.

Contexto disponível:

{patient_context}

{memory_context}

{history_context}

GUARDRAILS CLÍNICOS (NUNCA viole):
- Não faça diagnósticos.
- Não recomende, altere ou confirme medicações.
- Não dê conselhos médicos específicos.

FORMATO DA SUA RESPOSTA (JSON obrigatório no campo 'content'):

{{
  "pending_action": {{
    "action_type": "schedule_event" | "save_medication_schedule" | null,
    "data": {{ ... campos completos da ação ... }},
    "confirmation_text": "texto formatado para mostrar ao usuário pedindo confirmação"
  }},
  "clarification_needed": {{
    "intent": "string",
    "missing_fields": ["campo1", "campo2"],
    "question": "pergunta clara para o usuário"
  }},
  "date_error": false,
  "date_error_message": null,
  "memory_update": {{
    "summary": "string ou null",
    "emotional_context": "string ou null",
    "care_routines": "string ou null",
    "risk_notes": "string ou null"
  }}
}}

Use null nos campos que não se aplicam.
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

        # ----
        # 4.1 Processar tool calls (apenas save_patient_info e save_interlocutor_info executam direto)
        # ----
        clarification_needed = None
        pending_action = None
        date_error = False
        date_error_message = None
        # [FIX 3] Flag para pular segundo ciclo quando a resposta já está definida pela ação executada
        skip_conversational = False

        if analytical_msg.get("tool_calls"):
            for tool_call in analytical_msg["tool_calls"]:
                fn_name = tool_call["function"]["name"]
                args = json.loads(tool_call["function"]["arguments"] or "{}")
                logger.info(f"[FUNCTION CALL] {fn_name} | {args}")

                if fn_name == "save_patient_info":
                    await save_patient_info_db(family_id=family_id, **args)
                    # [FIX 4] Log enriquecido com tipo de ação
                    await log_action(
                        family_id, "cadastro_paciente",
                        f"Paciente cadastrado/atualizado: {args.get('patient_name')}",
                        metadata={**args, "action": "save_patient_info"}
                    )

                elif fn_name == "save_interlocutor_info":
                    await save_interlocutor_info_db(family_id, args.get("interlocutor_name", ""))
                    # [FIX 4] Log enriquecido com tipo de ação
                    await log_action(
                        family_id, "cadastro_interlocutor",
                        f"Interlocutor principal registrado: {args.get('interlocutor_name')}",
                        metadata={**args, "action": "save_interlocutor_info"}
                    )

                # [FASE 3] Clarificação sinalizada pela IA
                elif fn_name == "request_clarification":
                    clarification_needed = args
                    logger.info(f"[FASE 3] Clarificação necessária: {args}")

                # [FASE 1+2] schedule_event e save_medication_schedule NÃO executam direto — vão para pending
                elif fn_name in ("schedule_event", "save_medication_schedule"):
                    logger.info(f"[FASE 2] Tool {fn_name} interceptada — aguardando confirmação do usuário")

        # ----
        # 4.2 Parsear JSON do content para pending_action, clarification, date_error e memory_update
        # ----
        memory_update = None
        if analytical_msg.get("content"):
            try:
                parsed = json.loads(analytical_msg["content"])
                memory_update = parsed.get("memory_update")
                date_error = parsed.get("date_error", False)
                date_error_message = parsed.get("date_error_message")

                if parsed.get("pending_action") and parsed["pending_action"].get("action_type"):
                    pending_action = parsed["pending_action"]

                if parsed.get("clarification_needed") and parsed["clarification_needed"].get("missing_fields"):
                    clarification_needed = parsed["clarification_needed"]

            except Exception as e:
                logger.warning(f"Falha ao parsear JSON de content analítico: {e}")

        # ----
        # 4.3 Atualizar memória consolidada
        # ----
        if memory_update:
            await upsert_family_memory(
                family_id=family_id,
                summary=memory_update.get("summary"),
                emotional_context=memory_update.get("emotional_context"),
                care_routines=memory_update.get("care_routines"),
                risk_notes=memory_update.get("risk_notes"),
            )
            logger.info("[MEMÓRIA] Memória consolidada atualizada.")

        family_memory = await get_family_memory(family_id)
        memory_context = format_family_memory_for_context(family_memory)

        # ----
        # 4.4 [FASE 3] Se clarificação necessária, responder imediatamente sem segundo ciclo
        # ----
        if clarification_needed:
            question = clarification_needed.get("question") or (
                f"Para registrar {clarification_needed.get('intent', 'isso')}, "
                f"preciso de mais informações: {', '.join(clarification_needed.get('missing_fields', []))}. "
                f"Pode me informar?"
            )
            await save_conversation_message(family_id, "ai", "CuidaFamília", question)
            twilio_resp.message(question)
            # [FIX 3] Log da clarificação solicitada
            await log_action(family_id, "clarificacao", f"Clarificação solicitada: {clarification_needed.get('intent')}", metadata=clarification_needed)
            return Response(content=str(twilio_resp), media_type="application/xml")

        # ----
        # 4.5 [FASE 2] Se há ação pendente, salvar no banco e pedir confirmação
        # ----
        if pending_action:
            action_type = pending_action.get("action_type")
            action_data = pending_action.get("data", {})
            confirmation_text = pending_action.get("confirmation_text", "")

            # Montar texto de confirmação se não veio da IA
            if not confirmation_text:
                if action_type == "schedule_event":
                    confirmation_text = (
                    f"📅 Posso registrar o seguinte?\n\n"
                    f"{action_data.get('title')}\n"
                    f"📆 Data: {action_data.get('event_date')} às {action_data.get('event_time', '?')}\n"
                    f"📋 Tipo: {action_data.get('event_type')}\n\n"
                    f"Responda SIM para confirmar ou NÃO para cancelar."
                    )
                elif action_type == "save_medication_schedule":
                    times_str = ", ".join(action_data.get("times", []))
                    confirmation_text = (
                    f"💊 Posso registrar a seguinte rotina de medicação?\n\n"
                    f"{action_data.get('medication_name')} {action_data.get('dosage')}\n"
                    f"🔁 Frequência: {action_data.get('frequency')}\n"
                    f"⏰ Horários: {times_str}\n\n"
                    f"Responda SIM para confirmar ou NÃO para cancelar."
                    )

            # [FASE 2] Salvar pendência no banco
            await save_pending_confirmation(
                family_id=family_id,
                payload={"action_type": action_type, "data": action_data},
                confirmation_text=confirmation_text,
            )

            await save_conversation_message(family_id, "ai", "CuidaFamília", confirmation_text)
            twilio_resp.message(confirmation_text)
            # [FIX 4] Log da ação pendente criada
            await log_action(family_id, "confirmacao_pendente", f"Aguardando confirmação: {action_type}", metadata={"action_type": action_type, "data": action_data})
            return Response(content=str(twilio_resp), media_type="application/xml")

        # ----
        # 4.6 Erro de data passada
        # ----
        if date_error and date_error_message:
            await save_conversation_message(family_id, "ai", "CuidaFamília", date_error_message)
            twilio_resp.message(date_error_message)
            # [FIX 3] Pula segundo ciclo — resposta já definida
            await log_action(family_id, "erro_data", "Tentativa de agendamento com data passada", metadata={"mensagem": incoming_msg})
            return Response(content=str(twilio_resp), media_type="application/xml")

        # ----
        # 5. SEGUNDO CICLO: RESPOSTA CONVERSACIONAL
        # ----
        system_conversational = f"""
Você é o CuidaFamília, um Concierge de Cuidado e Secretária Executiva Familiar.

Você atende a família {family_name}, cuidando de {patient_name}.

Hoje é {weekday_str}, {today_str}.

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
