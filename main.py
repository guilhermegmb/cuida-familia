import os
import json
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, Request, Response, BackgroundTasks
from pydantic import BaseModel
from supabase import create_client, Client
import requests

# Configuração de Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# --- CONFIGURAÇÕES (Variáveis de Ambiente) ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_NUMBER") # Ex: "whatsapp:+14155238886"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- CLASSES E MODELOS ---

class WhatsAppMessage(BaseModel):
    From: str
    Body: str
    To: str

# --- CAMADA 1: UTILITÁRIOS E NORMALIZAÇÃO ---

def normalize_whatsapp_number(number: str) -> str:
    """Remove o prefixo 'whatsapp:' do número."""
    if number.startswith("whatsapp:"):
        return number.replace("whatsapp:", "")
    return number

def send_whatsapp_message(to: str, message: str):
    """Envia mensagem via Twilio API."""
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    data = {
        "From": TWILIO_PHONE_NUMBER,
        "To": f"whatsapp:{to}",
        "Body": message
    }
    response = requests.post(url, data=data, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
    if response.status_code != 201:
        logger.error(f"Erro ao enviar WhatsApp: {response.text}")
    return response

# --- CAMADA 2: BANCO DE DADOS (SUPABASE) ---

def get_family_by_phone(phone: str):
    """Busca a família pelo número de telefone do canal principal."""
    normalized_phone = normalize_whatsapp_number(phone)
    res = supabase.table("families").select("*").eq("channel_id", normalized_phone).execute()
    return res.data[0] if res.data else None

def get_conversation_history(family_id: int, limit: int = 30):
    """Busca o histórico recente de mensagens."""
    res = supabase.table("conversation_history")\
        .select("*")\
        .eq("family_id", family_id)\
        .order("created_at", desc=True)\
        .limit(limit)\
        .execute()
    history = res.data[::-1] # Inverte para ordem cronológica
    return history

def save_message_history(family_id: int, sender: str, content: str):
    """Salva mensagem no histórico."""
    supabase.table("conversation_history").insert({
        "family_id": family_id,
        "sender": sender,
        "content": content
    }).execute()

def get_family_memory(family_id: int):
    """Busca a memória consolidada da família."""
    res = supabase.table("family_memory").select("*").eq("family_id", family_id).execute()
    return res.data[0] if res.data else None

def save_family_memory(family_id: int, summary: str, emotional_context: str, care_routines: str, risk_notes: str):
    """Atualiza ou insere a memória da família."""
    memory_data = {
        "family_id": family_id,
        "summary": summary,
        "emotional_context": emotional_context,
        "care_routines": care_routines,
        "risk_notes": risk_notes,
        "updated_at": datetime.utcnow().isoformat()
    }
    existing = get_family_memory(family_id)
    if existing:
        supabase.table("family_memory").update(memory_data).eq("family_id", family_id).execute()
    else:
        supabase.table("family_memory").insert(memory_data).execute()

# --- FASE 1: ROTEAMENTO DE MEDICAÇÃO RECORRENTE ---

def save_medication_schedule_db(family_id: int, medication_data: Dict):
    """Salva medicação recorrente na tabela específica."""
    try:
        data = {
            "family_id": family_id,
            "medication_name": medication_data.get("med_name"),
            "dosage": medication_data.get("dosage"),
            "frequency": medication_data.get("frequency"),
            "start_date": medication_data.get("start_date", datetime.utcnow().date().isoformat()),
            "status": "active",
            "notes": medication_data.get("notes")
        }
        supabase.table("medication_schedules").insert(data).execute()
        return True
    except Exception as e:
        logger.error(f"Erro ao salvar medicação: {e}")
        return False

# --- FASE 2: PERSISTÊNCIA DE CONFIRMAÇÕES ---

def save_pending_confirmation(family_id: int, payload: Dict, confirmation_text: str):
    """Salva confirmação pendente no banco para evitar perda em reinícios do Render."""
    supabase.table("pending_confirmations").insert({
        "family_id": family_id,
        "payload": json.dumps(payload),
        "confirmation_text": confirmation_text,
        "status": "pending"
    }).execute()

def get_pending_confirmation(family_id: int):
    """Busca confirmação pendente ativa para a família."""
    res = supabase.table("pending_confirmations")\
        .select("*")\
        .eq("family_id", family_id)\
        .eq("status", "pending")\
        .order("created_at", desc=True)\
        .limit(1)\
        .execute()
    return res.data[0] if res.data else None

def resolve_pending_confirmation(confirmation_id: int, status: str = "resolved"):
    """Marca confirmação como resolvida ou cancelada."""
    supabase.table("pending_confirmations").update({"status": status}).eq("id", confirmation_id).execute()

# --- CAMADA 3: CÉREBRO DE IA (DOUBLE CYCLE) ---

def call_openrouter(messages: List[Dict], temperature: float = 0.5):
    """Chama a API do OpenRouter (Gemini ou GPT-4)."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://abacus.ai/",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "google/gemini-2.0-flash-001", # Recomendado por custo/velocidade
        "messages": messages,
        "temperature": temperature
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        return response.json()['choices'][0]['message']['content']
    else:
        logger.error(f"Erro OpenRouter: {response.text}")
        return None

# --- PROMPT ANALÍTICO (EXTRAÇÃO E CLARIFICAÇÃO) ---

SYSTEM_PROMPT_ANALYTICAL = """
Você é o Analista do CuidaFamília. Sua missão é ler as mensagens e extrair dados estruturados.

REGRAS CRÍTICAS (FASE 3 - CLARIFICAÇÃO):
1. Se o usuário quiser agendar algo (consulta, exame) mas não informar DATA, HORÁRIO ou MÉDICO, você DEVE usar a ferramenta 'request_clarification'.
2. Se o usuário quiser registrar um remédio mas não informar NOME ou HORÁRIO, você DEVE usar 'request_clarification'.
3. Nunca infira dados obrigatórios que não foram ditos.

REGRAS DE ROTEAMENTO (FASE 1):
- Eventos ÚNICOS (consulta amanhã) -> use 'schedule_event'.
- Medicações RECORRENTES (todo dia, 8h em 8h) -> use 'save_medication_schedule'.

FERRAMENTAS DISPONÍVEIS:
- request_clarification(missing_info_message): Use quando faltar dados básicos.
- schedule_event(event_type, description, date, time): Somente para eventos pontuais.
- save_medication_schedule(med_name, dosage, frequency, notes): Somente para uso recorrente de remédios.
- update_memory(summary_update, emotional_signal, risk_alert): Sempre que houver fato novo.
- answer_user(text): Resposta final se nenhuma ação for necessária.

Responda SEMPRE em JSON puro no formato:
{
  "actions": [{"tool": "nome_da_tool", "params": {...}}],
  "internal_summary": "resumo do que entendeu",
  "confirmation_required": true/false,
  "confirmation_text": "Texto amigável pedindo confirmação (se necessário)"
}
"""

SYSTEM_PROMPT_RESPONSE = """
Você é o Concierge CuidaFamília. Sua personalidade: Empático, Organizado e Vigilante.
Você fala no WhatsApp com famílias que cuidam de entes queridos. Use um tom de 'filha/filho dedicado'.

CONTEXTO ATUAL:
Memória: {family_memory}
Ação realizada pela IA: {action_result}

Responda de forma curta, direta e acolhedora. Se for uma confirmação, apresente os dados claramente.
"""

# --- FLUXO PRINCIPAL ---

@app.post("/whatsapp")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    form_data = await request.form()
    phone = normalize_whatsapp_number(form_data.get("From"))
    user_msg = form_data.get("Body").strip()

    family = get_family_by_phone(phone)
    if not family:
        return Response(content="Família não cadastrada.", status_code=200)

    family_id = family['id']
    save_message_history(family_id, "user", user_msg)

    # --- VERIFICAÇÃO DE CONFIRMAÇÃO PENDENTE (FASE 2) ---
    pending = get_pending_confirmation(family_id)

    if pending and user_msg.lower() in ["sim", "pode", "ok", "confirmar", "com certeza", "s"]:
        # Usuário confirmou
        payload = json.loads(pending['payload'])
        logger.info(f"Confirmando ação para família {family_id}: {payload}")

        # Executar ação efetiva baseada no payload
        for action in payload.get("actions", []):
            if action['tool'] == "schedule_event":
                supabase.table("family_agenda").insert({
                    "family_id": family_id,
                    "event_type": action['params']['event_type'],
                    "description": action['params']['description'],
                    "event_date": action['params']['date'],
                    "event_time": action['params']['time']
                }).execute()
            elif action['tool'] == "save_medication_schedule":
                save_medication_schedule_db(family_id, action['params'])

        resolve_pending_confirmation(pending['id'], "confirmed")
        send_whatsapp_message(phone, "Feito! Já anotei aqui e vou te lembrar na hora certa. Mais alguma coisa?")
        return Response(status_code=200)

    elif pending and user_msg.lower() in ["não", "nao", "cancela", "parar", "n"]:
        resolve_pending_confirmation(pending['id'], "cancelled")
        send_whatsapp_message(phone, "Sem problemas, operação cancelada. Se precisar de outra coisa, é só chamar.")
        return Response(status_code=200)

    # --- CICLO 1: INFERÊNCIA ANALÍTICA ---
    history = get_conversation_history(family_id)
    memory = get_family_memory(family_id)

    history_context = "\n".join([f"{m['sender']}: {m['content']}" for m in history])

    messages_analytical = [
        {"role": "system", "content": SYSTEM_PROMPT_ANALYTICAL},
        {"role": "user", "content": f"HISTÓRICO:\n{history_context}\n\nMEMÓRIA ATUAL: {memory}\n\nMENSAGEM NOVA: {user_msg}"}
    ]

    ai_raw = call_openrouter(messages_analytical, temperature=0.2)
    try:
        ai_analysis = json.loads(ai_raw)
    except:
        logger.error(f"Erro ao parsear JSON da IA: {ai_raw}")
        send_whatsapp_message(phone, "Desculpe, tive um probleminha técnico. Pode repetir o que você disse?")
        return Response(status_code=200)

    # --- PROCESSAMENTO DE AÇÕES ---
    actions = ai_analysis.get("actions", [])

    # Verificação de Clarificação (Fase 3)
    for action in actions:
        if action['tool'] == "request_clarification":
            save_message_history(family_id, "assistant", action['params']['missing_info_message'])
            send_whatsapp_message(phone, action['params']['missing_info_message'])
            return Response(status_code=200)

    # Se precisar de confirmação, salva no banco (Fase 2)
    if ai_analysis.get("confirmation_required"):
        save_pending_confirmation(family_id, {"actions": actions}, ai_analysis['confirmation_text'])
        send_whatsapp_message(phone, ai_analysis['confirmation_text'])
        return Response(status_code=200)

    # Execução de ações que não precisam de confirmação (ex: update_memory)
    for action in actions:
        if action['tool'] == "update_memory":
            save_family_memory(
                family_id,
                action['params'].get("summary_update", ""),
                action['params'].get("emotional_signal", ""),
                action['params'].get("care_routines", ""),
                action['params'].get("risk_alert", "")
            )

    # --- CICLO 2: RESPOSTA FINAL ---
    messages_response = [
        {"role": "system", "content": SYSTEM_PROMPT_RESPONSE.format(
            family_memory=memory, 
            action_result=ai_analysis.get("internal_summary", "Processado com sucesso.")
        )},
        {"role": "user", "content": user_msg}
    ]

    final_response = call_openrouter(messages_response)
    save_message_history(family_id, "assistant", final_response)
    send_whatsapp_message(phone, final_response)

    return Response(status_code=200)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
