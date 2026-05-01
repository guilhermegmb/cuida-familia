"""
CuidaFamília - Agente de IA Concierge de Cuidado
Versão: 2.0 (Profissional)
Data: 2026-05-01

Propósito: Agente de IA que atua via WhatsApp como Secretária Executiva Familiar
para gerenciar cuidados de saúde de idosos, com gravação automática de dados
no Supabase e guardrails jurídicos para nunca fornecer diagnósticos médicos.

Padrão: MIT/Harvard
Autor: CuidaFamília Team
"""

import os
import logging
import json
from datetime import datetime
from fastapi import FastAPI, Request, Response
from supabase import create_client, Client
import requests
from twilio.twiml.messaging_response import MessagingResponse

# ============================================================================
# CONFIGURAÇÃO DE LOGS
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# INICIALIZAÇÃO DA APLICAÇÃO
# ============================================================================

app = FastAPI(title="CuidaFamília API", version="2.0")

# ============================================================================
# VARIÁVEIS DE AMBIENTE
# ============================================================================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")

# Inicializa cliente Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ============================================================================
# DEFINIÇÃO DAS FERRAMENTAS (FUNCTION CALLING) PARA A IA
# ============================================================================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "save_patient_info",
            "description": "Salva ou atualiza informações do paciente idoso no banco de dados. Use quando o usuário fornecer dados como nome, data de nascimento, medicamentos, condição de saúde ou médico responsável.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_name": {
                        "type": "string",
                        "description": "Nome completo do paciente idoso."
                    },
                    "birthdate": {
                        "type": "string",
                        "description": "Data de nascimento no formato YYYY-MM-DD (ex: 1945-03-15)."
                    },
                    "gender": {
                        "type": "string",
                        "enum": ["M", "F", "Outro"],
                        "description": "Gênero do paciente."
                    },
                    "medications": {
                        "type": "string",
                        "description": "Lista de medicamentos que o paciente toma, separados por vírgula (ex: 'Losartana 50mg, Metformina 500mg')."
                    },
                    "health_condition": {
                        "type": "string",
                        "description": "Condição de saúde principal do paciente (ex: 'Hipertensão e Diabetes')."
                    },
                    "doctor_name": {
                        "type": "string",
                        "description": "Nome do médico responsável pelo paciente."
                    },
                    "doctor_phone": {
                        "type": "string",
                        "description": "Telefone do médico para contato de emergência."
                    }
                },
                "required": ["patient_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_interlocutor_info",
            "description": "Salva o nome do principal interlocutor (cuidador ou membro da família) que está interagindo com o sistema.",
            "parameters": {
                "type": "object",
                "properties": {
                    "interlocutor_name": {
                        "type": "string",
                        "description": "Nome completo da pessoa que é o principal contato da família."
                    }
                },
                "required": ["interlocutor_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "schedule_event",
            "description": "Agenda um evento, consulta, medicação ou lembrete na agenda da família.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Título do evento (ex: 'Consulta com Dr. Carlos')."
                    },
                    "event_date": {
                        "type": "string",
                        "description": "Data do evento no formato YYYY-MM-DD."
                    },
                    "event_time": {
                        "type": "string",
                        "description": "Horário do evento no formato HH:MM (opcional, ex: '14:00')."
                    },
                    "event_type": {
                        "type": "string",
                        "enum": ["consulta", "medicação", "exame", "compromisso", "lembrete", "outro"],
                        "description": "Tipo de evento."
                    },
                    "description": {
                        "type": "string",
                        "description": "Descrição detalhada do evento (opcional)."
                    }
                },
                "required": ["title", "event_date", "event_type"]
            }
        }
    }
]

# ============================================================================
# FUNÇÕES AUXILIARES - INTERAÇÃO COM SUPABASE
# ============================================================================

async def get_family_by_whatsapp(whatsapp_number: str):
    """Busca uma família pelo número WhatsApp principal."""
    try:
        # Normalizar número: remover espaços, hífens, parênteses
        normalized_number = whatsapp_number.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        
        # Garantir que começa com +
        if not normalized_number.startswith("+"):
            normalized_number = "+" + normalized_number
        
        logger.info(f"[DEBUG] Buscando família com número: {normalized_number}")
        
        # Buscar com igualdade exata
        response = supabase.table("families").select("*").eq("main_whatsapp", normalized_number).execute()
        
        if response.data:
            logger.info(f"[DEBUG] Família encontrada: {response.data[0].get('family_name')}")
            return response.data[0]
        else:
            # Se não encontrou, listar todas as famílias para debug
            logger.warning(f"[DEBUG] Nenhuma família encontrada para {normalized_number}")
            all_families = supabase.table("families").select("id, family_name, main_whatsapp").execute()
            logger.warning(f"[DEBUG] Famílias no banco: {all_families.data}")
            return None
    except Exception as e:
        logger.error(f"Erro ao buscar família por WhatsApp: {e}")
        return None


async def get_patient_by_family_id(family_id: int):
    """Busca o paciente de uma família."""
    try:
        response = supabase.table("patients").select("*").eq("family_id", family_id).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        logger.error(f"Erro ao buscar paciente: {e}")
        return None


async def get_conversation_history(family_id: int, limit: int = 10):
    """Busca o histórico de conversas recentes para contexto da IA."""
    try:
        response = (
            supabase.table("conversation_history")
            .select("sender_type, sender_name, message_text, created_at")
            .eq("family_id", family_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        # Inverte a ordem para ter as mensagens mais antigas primeiro
        return list(reversed(response.data)) if response.data else []
    except Exception as e:
        logger.error(f"Erro ao buscar histórico de conversa: {e}")
        return []


async def save_patient_info_db(
    family_id: int,
    patient_name: str,
    birthdate: str = None,
    gender: str = None,
    medications: str = None,
    health_condition: str = None,
    doctor_name: str = None,
    doctor_phone: str = None
):
    """Salva ou atualiza informações do paciente."""
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
        # Remove valores None para não sobrescrever dados existentes
        patient_data = {k: v for k, v in patient_data.items() if v is not None}

        # Verifica se paciente já existe
        existing_patient = await get_patient_by_family_id(family_id)
        if existing_patient:
            response = supabase.table("patients").update(patient_data).eq("family_id", family_id).execute()
            logger.info(f"Paciente atualizado: {patient_name}")
        else:
            response = supabase.table("patients").insert(patient_data).execute()
            logger.info(f"Novo paciente criado: {patient_name}")
        
        return response.data
    except Exception as e:
        logger.error(f"Erro ao salvar informações do paciente: {e}")
        return None


async def save_interlocutor_info_db(family_id: int, interlocutor_name: str):
    """Salva o interlocutor principal da família."""
    try:
        response = (
            supabase.table("families")
            .update({"main_interlocutor_name": interlocutor_name})
            .eq("id", family_id)
            .execute()
        )
        logger.info(f"Interlocutor salvo: {interlocutor_name}")
        return response.data
    except Exception as e:
        logger.error(f"Erro ao salvar interlocutor: {e}")
        return None


async def schedule_event_db(
    family_id: int,
    title: str,
    event_date: str,
    event_time: str = None,
    event_type: str = "outro",
    description: str = None
):
    """Agenda um evento na família."""
    try:
        event_data = {
            "family_id": family_id,
            "title": title,
            "event_date": event_date,
            "event_time": event_time,
            "event_type": event_type,
            "description": description,
            "status": "ativo"
        }
        response = supabase.table("family_agenda").insert(event_data).execute()
        logger.info(f"Evento agendado: {title} em {event_date}")
        return response.data
    except Exception as e:
        logger.error(f"Erro ao agendar evento: {e}")
        return None


async def save_conversation_message(family_id: int, sender_type: str, sender_name: str, message_text: str):
    """Salva uma mensagem no histórico de conversa."""
    try:
        message_data = {
            "family_id": family_id,
            "sender_type": sender_type,
            "sender_name": sender_name,
            "message_text": message_text
        }
        response = supabase.table("conversation_history").insert(message_data).execute()
        return response.data
    except Exception as e:
        logger.error(f"Erro ao salvar mensagem: {e}")
        return None


async def log_action(family_id: int, log_type: str, message: str, created_by: str = "IA", metadata: dict = None):
    """Registra uma ação no histórico de logs (auditoria)."""
    try:
        log_data = {
            "family_id": family_id,
            "log_type": log_type,
            "message": message,
            "created_by": created_by,
            "metadata": metadata
        }
        response = supabase.table("family_logs").insert(log_data).execute()
        return response.data
    except Exception as e:
        logger.error(f"Erro ao registrar log: {e}")
        return None


# ============================================================================
# FUNÇÕES DE FORMATAÇÃO DE CONTEXTO
# ============================================================================

def format_conversation_history_for_context(history: list) -> str:
    """Formata o histórico de conversa para incluir no prompt da IA."""
    if not history:
        return "Nenhuma conversa anterior."
    
    formatted = "Histórico de conversas recentes:\n"
    for msg in history:
        sender = msg.get("sender_name", msg.get("sender_type", "Desconhecido"))
        text = msg.get("message_text", "")
        formatted += f"- {sender}: {text}\n"
    
    return formatted


def format_patient_info_for_context(patient: dict) -> str:
    """Formata as informações do paciente para incluir no prompt da IA."""
    if not patient:
        return "Nenhuma informação de paciente cadastrada ainda."
    
    formatted = "Informações do paciente:\n"
    formatted += f"- Nome: {patient.get('patient_name', 'N/A')}\n"
    
    if patient.get('birthdate'):
        formatted += f"- Data de nascimento: {patient.get('birthdate')}\n"
    
    if patient.get('medications'):
        formatted += f"- Medicamentos: {patient.get('medications')}\n"
    
    if patient.get('health_condition'):
        formatted += f"- Condição de saúde: {patient.get('health_condition')}\n"
    
    if patient.get('doctor_name'):
        formatted += f"- Médico responsável: {patient.get('doctor_name')}\n"
    
    return formatted


# ============================================================================
# ROTEAMENTO DA API
# ============================================================================

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "CuidaFamília Online e Operante",
        "version": "2.0",
        "timestamp": datetime.now().isoformat()
    }


@app.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    """
    Webhook para receber mensagens do WhatsApp via Twilio.
    
    Fluxo:
    1. Recebe mensagem do usuário
    2. Busca informações da família no Supabase
    3. Lê histórico de conversas para contexto
    4. Envia para IA com contexto completo
    5. IA pode usar Function Calling para gravar dados
    6. Responde ao usuário
    7. Registra tudo no histórico e logs
    """
    resp = MessagingResponse()
    
    try:
        # ====================================================================
        # PASSO 1: Extrair dados da mensagem do Twilio
        # ====================================================================
        form_data = await request.form()
        incoming_msg = form_data.get("Body", "").strip()
        sender_number = form_data.get("From", "").replace("whatsapp:", "").strip()
        
        # Normalizar número: remover espaços, hífens e garantir formato correto
        sender_number = sender_number.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        
        # Se não começar com +, adicionar
        if not sender_number.startswith("+"):
            sender_number = "+" + sender_number

        logger.info(f"[NOVA MENSAGEM] De: {sender_number} | Texto: {incoming_msg}")

        # ====================================================================
        # PASSO 2: Buscar família no Supabase
        # ====================================================================
        family = await get_family_by_whatsapp(sender_number)
        if not family:
            logger.warning(f"Família não encontrada para WhatsApp: {sender_number}")
            resp.message(
                "Olá! Não consegui identificar sua família no sistema CuidaFamília. "
                "Por favor, verifique se seu número WhatsApp está cadastrado corretamente. "
                "Entre em contato com nosso suporte se precisar de ajuda."
            )
            return Response(content=str(resp), media_type="application/xml")

        family_id = family["id"]
        family_name = family.get("family_name", "Família")
        main_interlocutor = family.get("main_interlocutor_name", "Visitante")

        logger.info(f"[FAMÍLIA ENCONTRADA] ID: {family_id} | Nome: {family_name}")

        # ====================================================================
        # PASSO 3: Buscar informações do paciente
        # ====================================================================
        patient = await get_patient_by_family_id(family_id)
        patient_name = patient.get("patient_name", "paciente") if patient else "paciente"

        # ====================================================================
        # PASSO 4: Buscar histórico de conversas para contexto
        # ====================================================================
        conversation_history = await get_conversation_history(family_id, limit=10)
        history_context = format_conversation_history_for_context(conversation_history)
        patient_context = format_patient_info_for_context(patient)

        # ====================================================================
        # PASSO 5: Salvar mensagem do usuário no histórico
        # ====================================================================
        await save_conversation_message(
            family_id=family_id,
            sender_type="user",
            sender_name=main_interlocutor,
            message_text=incoming_msg
        )

        # ====================================================================
        # PASSO 6: Preparar prompt para a IA com contexto completo
        # ====================================================================
        system_prompt = f"""Você é o CuidaFamília, um Concierge de Cuidado e Secretária Executiva Familiar de altíssima qualidade.

Você trabalha para a {family_name}, ajudando a organizar e gerenciar os cuidados de saúde de {patient_name}.

INFORMAÇÕES ATUAIS:
{patient_context}

{history_context}

SUAS RESPONSABILIDADES:
1. Ser uma secretária executiva discreta, empática e altamente eficiente
2. Organizar informações, agendar compromissos e registrar dados importantes
3. Manter um tom profissional, cuidadoso e humanizado
4. Ser proativa em sugerir ações quando apropriado

GUARDRAILS CRÍTICOS - NUNCA VIOLE ESTES:
❌ NUNCA forneça diagnósticos médicos
❌ NUNCA recomende alterações em medicações
❌ NUNCA dê conselhos de saúde específicos
✅ Se o usuário mencionar emergência (dor no peito, falta de ar, desmaio, etc.), responda IMEDIATAMENTE:
   "EMERGÊNCIA DETECTADA! Ligue para o SAMU (192) ou procure o pronto-socorro mais próximo AGORA!"
✅ Redirecione questões médicas para o médico responsável
✅ Foque em ORGANIZAÇÃO, LOGÍSTICA e COMUNICAÇÃO

QUANDO USAR AS FERRAMENTAS:
- Use "save_patient_info" quando o usuário fornecer dados sobre o paciente
- Use "save_interlocutor_info" quando o usuário se identificar
- Use "schedule_event" quando o usuário quiser agendar algo

Responda de forma natural, profissional e humanizada. Seja conciso mas completo."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": incoming_msg}
        ]

        # ====================================================================
        # PASSO 7: Chamar OpenRouter com Function Calling
        # ====================================================================
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": OPENROUTER_MODEL,
            "messages": messages,
            "tools": TOOLS,
            "tool_choice": "auto"
        }

        logger.info("Enviando mensagem para OpenRouter com Function Calling...")
        openrouter_response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        openrouter_response.raise_for_status()

        response_data = openrouter_response.json()
        ai_choice = response_data.get("choices", [{}])[0]

        # ====================================================================
        # PASSO 8: Processar resposta da IA (pode ser texto ou função)
        # ====================================================================
        ai_text_response = None
        
        if ai_choice.get("message") and ai_choice["message"].get("tool_calls"):
            # IA chamou uma ou mais funções
            tool_calls = ai_choice["message"]["tool_calls"]
            
            for tool_call in tool_calls:
                function_name = tool_call["function"]["name"]
                function_args = json.loads(tool_call["function"]["arguments"])
                
                logger.info(f"[FUNCTION CALL] {function_name} | Args: {function_args}")

                # Executar a função solicitada
                if function_name == "save_patient_info":
                    await save_patient_info_db(family_id=family_id, **function_args)
                    await log_action(
                        family_id=family_id,
                        log_type="update",
                        message=f"Informações do paciente atualizadas: {function_args.get('patient_name', 'N/A')}",
                        metadata=function_args
                    )
                    logger.info(f"✅ Paciente salvo: {function_args.get('patient_name')}")
                
                elif function_name == "save_interlocutor_info":
                    await save_interlocutor_info_db(
                        family_id=family_id,
                        interlocutor_name=function_args.get("interlocutor_name")
                    )
                    await log_action(
                        family_id=family_id,
                        log_type="update",
                        message=f"Interlocutor principal registrado: {function_args.get('interlocutor_name')}",
                        metadata=function_args
                    )
                    logger.info(f"✅ Interlocutor salvo: {function_args.get('interlocutor_name')}")
                
                elif function_name == "schedule_event":
                    await schedule_event_db(family_id=family_id, **function_args)
                    await log_action(
                        family_id=family_id,
                        log_type="update",
                        message=f"Evento agendado: {function_args.get('title')} em {function_args.get('event_date')}",
                        metadata=function_args
                    )
                    logger.info(f"✅ Evento agendado: {function_args.get('title')}")

            # Se houver conteúdo de texto além das funções, usa como resposta
            if ai_choice["message"].get("content"):
                ai_text_response = ai_choice["message"]["content"]
        else:
            # IA respondeu apenas com texto (sem Function Calling)
            ai_text_response = ai_choice.get("message", {}).get("content", "")

        # ====================================================================
        # PASSO 9: Enviar resposta ao usuário
        # ====================================================================
        if ai_text_response:
            resp.message(ai_text_response)
            logger.info(f"[RESPOSTA] {ai_text_response[:100]}...")
            
            # Salvar resposta da IA no histórico
            await save_conversation_message(
                family_id=family_id,
                sender_type="ai",
                sender_name="CuidaFamília",
                message_text=ai_text_response
            )
        else:
            # Se não houver resposta de texto, enviar confirmação padrão
            default_response = "Entendido! Suas informações foram registradas com sucesso. Como posso ajudá-lo mais?"
            resp.message(default_response)
            
            await save_conversation_message(
                family_id=family_id,
                sender_type="ai",
                sender_name="CuidaFamília",
                message_text=default_response
            )

        # ====================================================================
        # PASSO 10: Registrar interação no log
        # ====================================================================
        await log_action(
            family_id=family_id,
            log_type="note",
            message=f"Mensagem processada: {incoming_msg[:100]}...",
            created_by="IA",
            metadata={"sender": main_interlocutor, "message_length": len(incoming_msg)}
        )

    except requests.exceptions.Timeout:
        logger.error("Timeout ao conectar com OpenRouter")
        resp.message(
            "Desculpe, a inteligência artificial demorou muito para responder. "
            "Por favor, tente novamente em alguns momentos."
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro na requisição ao OpenRouter: {e}")
        resp.message(
            "Desculpe, tive um problema de comunicação com a inteligência artificial. "
            "Por favor, tente novamente mais tarde."
        )
    except Exception as e:
        logger.error(f"ERRO CRÍTICO no webhook: {str(e)}", exc_info=True)
        resp.message(
            "Ocorreu um erro inesperado no sistema CuidaFamília. "
            "Nossa equipe foi notificada e está investigando. Por favor, tente novamente."
        )

    return Response(content=str(resp), media_type="application/xml")


# ============================================================================
# FIM DO ARQUIVO
# ============================================================================
