import os
import logging
from fastapi import FastAPI, Request, Response
from supabase import create_client, Client
import requests

# Configuração de Logs para vermos tudo na Render
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

@app.get("/")
async def root():
    return {"status": "CuidaFamília Online e Operante"}

@app.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    try:
        # 1. Captura os dados do Twilio
        form_data = await request.form()
        incoming_msg = form_data.get('Body', '').strip()
        sender_number = form_data.get('From', '').replace('whatsapp:', '')
        
        logger.info(f"--- NOVA MENSAGEM RECEBIDA ---")
        logger.info(f"De: {sender_number}")
        logger.info(f"Mensagem: {incoming_msg}")

        # 2. Busca Família no Supabase
        logger.info(f"Buscando no Supabase por: {sender_number}")
        family_query = supabase.table("families").select("*").eq("main_whatsapp", sender_number).execute()
        
        family_data = family_query.data
        family_name = "Família"
        
        if family_data:
            family_name = family_data[0].get('family_name', 'Família')
            logger.info(f"Família encontrada: {family_name}")
        else:
            logger.warning(f"AVISO: Número {sender_number} não encontrado na tabela families!")
            # Mesmo sem encontrar, vamos continuar para testar a IA

        # 3. Chamada para a IA (OpenRouter)
        logger.info(f"Chamando OpenRouter ({OPENROUTER_MODEL})...")
        
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }
        
        prompt = f"Você é o Concierge de Cuidado da {family_name}. Responda de forma curta e profissional: {incoming_msg}"
        
        payload = {
            "model": OPENROUTER_MODEL,
            "messages": [{"role": "user", "content": prompt}]
        }
        
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
        
        if response.status_code == 200:
            ai_response = response.json()['choices'][0]['message']['content']
            logger.info(f"IA Respondeu: {ai_response}")
        else:
            ai_response = "Desculpe, tive um erro técnico ao processar sua mensagem."
            logger.error(f"Erro OpenRouter: {response.text}")

        # 4. Resposta TwiML (O formato que o Twilio entende)
        twiml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Message>{ai_response}</Message>
        </Response>"""
        
        return Response(content=twiml_response, media_type="application/xml")

    except Exception as e:
        logger.error(f"ERRO CRÍTICO: {str(e)}")
        twiml_error = """<?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Message>Ocorreu um erro interno no servidor do CuidaFamília.</Message>
        </Response>"""
        return Response(content=twiml_error, media_type="application/xml")
