import os
import logging
import json
from fastapi import FastAPI, Request, Response
from supabase import create_client, Client
import requests
from twilio.twiml.messaging_response import MessagingResponse

# Configuração de Logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Variáveis de Ambiente
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")

# Inicializa Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Definição das Ferramentas (Functions) para a IA --- #
# A IA vai "saber" que pode chamar essas funções para interagir com o Supabase
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "save_patient_info",
            "description": "Salva ou atualiza informações de um paciente no banco de dados. Use esta função quando o usuário fornecer dados sobre o paciente, como nome, idade, remédios, condição de saúde ou médico responsável.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_name": {"type": "string", "description": "Nome completo do paciente."},
                    "age": {"type": "integer", "description": "Idade do paciente."},
                    "medications": {"type": "string", "description": "Lista de remédios que o paciente toma, separados por vírgula."},
                    "health_condition": {"type": "string", "description": "Condição de saúde principal do paciente."},
                    "doctor_name": {"type": "string", "description": "Nome do médico responsável pelo paciente."}
                },
                "required": ["patient_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_interlocutor_info",
            "description": "Salva ou atualiza o nome do principal interlocutor da família. Use esta função quando o usuário se identificar ou indicar quem é o principal contato para o paciente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "interlocutor_name": {"type": "string", "description": "Nome completo do principal interlocutor da família."}
                },
                "required": ["interlocutor_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "log_care_event",
            "description": "Registra um evento de cuidado ou uma interação importante no histórico da família. Use para anotar compromissos, lembretes, ou qualquer informação relevante sobre o cuidado do paciente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_description": {"type": "string", "description": "Descrição detalhada do evento de cuidado."},
                    "event_date": {"type": "string", "description": "Data do evento (formato YYYY-MM-DD)."}
                },
                "required": ["event_description"]
            }
        }
    }
]

# --- Funções para Interagir com o Supabase --- #
async def _get_family_by_whatsapp(whatsapp_number: str):
    response = supabase.table("families").select("id, family_name").eq("main_whatsapp", whatsapp_number).execute()
    return response.data[0] if response.data else None

async def _get_patient_by_family_id(family_id: int):
    response = supabase.table("patients").select("*").eq("family_id", family_id).execute()
    return response.data[0] if response.data else None

async def _save_patient_info_db(family_id: int, patient_name: str, age: int = None, medications: str = None, health_condition: str = None, doctor_name: str = None):
    patient_data = {
        "family_id": family_id,
        "patient_name": patient_name,
        "age": age,
        "medications": medications,
        "health_condition": health_condition,
        "doctor_name": doctor_name
    }
    # Remove None values to avoid overwriting existing data with nulls if not provided
    patient_data = {k: v for k, v in patient_data.items() if v is not None}

    # Tenta atualizar, se não existir, insere
    existing_patient = await _get_patient_by_family_id(family_id)
    if existing_patient:
        response = supabase.table("patients").update(patient_data).eq("family_id", family_id).execute()
    else:
        response = supabase.table("patients").insert(patient_data).execute()
    return response.data

async def _save_interlocutor_info_db(family_id: int, interlocutor_name: str):
    # Assumindo que o interlocutor principal pode ser salvo na tabela family_members
    # ou diretamente na tabela families se for um campo único.
    # Por simplicidade, vamos atualizar o family_name na tabela families por enquanto.
    response = supabase.table("families").update({"main_interlocutor_name": interlocutor_name}).eq("id", family_id).execute()
    return response.data

async def _log_care_event_db(family_id: int, event_description: str, event_date: str = None):
    event_data = {
        "family_id": family_id,
        "event_description": event_description,
        "event_date": event_date if event_date else str(os.getenv("CURRENT_DATE", "2026-05-01")) # Usar data atual se não fornecida
    }
    response = supabase.table("family_logs").insert(event_data).execute()
    return response.data

# --- Roteamento da API --- #
@app.get("/")
async def root():
    return {"status": "CuidaFamília Online e Operante (v3)"}

@app.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    resp = MessagingResponse()
    try:
        form_data = await request.form()
        incoming_msg = form_data.get("Body", "").strip()
        sender_number = form_data.get("From", "").replace("whatsapp:", "")

        logger.info(f"--- MENSAGEM RECEBIDA (v3) ---")
        logger.info(f"De: {sender_number}")
        logger.info(f"Mensagem: {incoming_msg}")

        family = await _get_family_by_whatsapp(sender_number)
        if not family:
            resp.message("Olá! Não consegui identificar sua família. Por favor, certifique-se de que seu número está cadastrado corretamente no nosso sistema.")
            return Response(content=str(resp), media_type="application/xml")

        family_id = family["id"]
        family_name = family["family_name"]
        patient = await _get_patient_by_family_id(family_id)
        patient_name = patient["patient_name"] if patient else "o paciente"

        # --- Prompt de Elite com Guardrails e Function Calling --- #
        messages = [
            {"role": "system", "content": f"Você é o Concierge de Cuidado da {family_name}. Sua função é ser uma secretária executiva altamente eficiente, discreta e empática para famílias que cuidam de idosos. Seu objetivo é organizar informações, agendar compromissos e registrar dados importantes. NUNCA forneça diagnósticos médicos, conselhos de saúde, ou altere medicações. Se o usuário mencionar uma emergência médica (dor no peito, falta de ar, desmaio, etc.), instrua-o IMEDIATAMENTE a ligar para o SAMU (192) ou procurar um pronto-socorro. Você pode usar as ferramentas disponíveis para salvar informações sobre o paciente e eventos de cuidado. O paciente principal da família é {patient_name}."},
            {"role": "user", "content": incoming_msg}
        ]

        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": OPENROUTER_MODEL,
            "messages": messages,
            "tools": TOOLS, # Inclui as ferramentas para a IA usar
            "tool_choice": "auto" # Permite que a IA decida se usa uma ferramenta
        }

        logger.info("Enviando mensagem para OpenRouter com Function Calling...")
        openrouter_response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
        openrouter_response.raise_for_status() # Levanta exceção para erros HTTP
        
        ai_choice = openrouter_response.json()["choices"][0]

        # --- Processa a resposta da IA (Pode ser texto ou chamada de função) ---
        if ai_choice.get("message") and ai_choice["message"].get("tool_calls"):
            tool_calls = ai_choice["message"]["tool_calls"]
            for tool_call in tool_calls:
                function_name = tool_call["function"]["name"]
                function_args = json.loads(tool_call["function"]["arguments"])
                logger.info(f"IA solicitou chamada de função: {function_name} com args: {function_args}")

                # Executa a função solicitada pela IA
                if function_name == "save_patient_info":
                    await _save_patient_info_db(family_id=family_id, **function_args)
                    resp.message(f"Entendido! As informações sobre o paciente {function_args.get("patient_name", "")} foram atualizadas com sucesso.")
                elif function_name == "save_interlocutor_info":
                    await _save_interlocutor_info_db(family_id=family_id, **function_args)
                    resp.message(f"Certo! Registrei {function_args.get("interlocutor_name", "")} como principal interlocutor da família.")
                elif function_name == "log_care_event":
                    await _log_care_event_db(family_id=family_id, **function_args)
                    resp.message(f"Registrei o evento: {function_args.get("event_description", "")}. Acompanharei de perto.")
                else:
                    resp.message("Desculpe, a IA tentou usar uma função desconhecida.")
        else:
            # Se não houver chamada de função, a IA responde com texto
            ai_text_response = ai_choice["message"]["content"]
            resp.message(ai_text_response)

    except requests.exceptions.RequestException as e:
        logger.error(f"Erro na requisição ao OpenRouter: {e}")
        resp.message("Desculpe, tive um problema de comunicação com a inteligência artificial. Por favor, tente novamente mais tarde.")
    except Exception as e:
        logger.error(f"ERRO CRÍTICO no webhook: {str(e)}")
        resp.message("Ocorreu um erro inesperado no sistema CuidaFamília. Nossa equipe já foi notificada.")

    return Response(content=str(resp), media_type="application/xml")
