"""
DEBUG COMPLETO - CuidaFamília
Testa cada etapa da integração Twilio + Supabase + OpenRouter
"""

import os
import logging
from fastapi import FastAPI, Request, Response
from supabase import create_client, Client
import requests
from twilio.twiml.messaging_response import MessagingResponse

# ============================================================================
# CONFIGURAÇÃO DE LOGS - MÁXIMO DETALHE
# ============================================================================

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="CuidaFamília DEBUG", version="DEBUG")

# ============================================================================
# PASSO 1: VERIFICAR VARIÁVEIS DE AMBIENTE
# ============================================================================

logger.info("=" * 80)
logger.info("PASSO 1: VERIFICANDO VARIÁVEIS DE AMBIENTE")
logger.info("=" * 80)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")

logger.info(f"✓ SUPABASE_URL: {SUPABASE_URL[:50]}..." if SUPABASE_URL else "✗ SUPABASE_URL: NÃO DEFINIDA")
logger.info(f"✓ SUPABASE_KEY: {SUPABASE_KEY[:20]}..." if SUPABASE_KEY else "✗ SUPABASE_KEY: NÃO DEFINIDA")
logger.info(f"✓ OPENROUTER_API_KEY: {OPENROUTER_API_KEY[:20]}..." if OPENROUTER_API_KEY else "✗ OPENROUTER_API_KEY: NÃO DEFINIDA")
logger.info(f"✓ OPENROUTER_MODEL: {OPENROUTER_MODEL}")

# ============================================================================
# PASSO 2: TENTAR CONECTAR NO SUPABASE
# ============================================================================

logger.info("=" * 80)
logger.info("PASSO 2: CONECTANDO NO SUPABASE")
logger.info("=" * 80)

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    logger.info("✓ Cliente Supabase criado com sucesso")
except Exception as e:
    logger.error(f"✗ ERRO ao criar cliente Supabase: {e}")
    supabase = None

# ============================================================================
# PASSO 3: TESTAR LEITURA DA TABELA FAMILIES
# ============================================================================

logger.info("=" * 80)
logger.info("PASSO 3: TESTANDO LEITURA DA TABELA FAMILIES")
logger.info("=" * 80)

if supabase:
    try:
        response = supabase.table("families").select("*").execute()
        families = response.data
        logger.info(f"✓ Conexão com tabela 'families' bem-sucedida")
        logger.info(f"✓ Total de famílias no banco: {len(families)}")
        for family in families:
            logger.info(f"  - ID: {family.get('id')}, Nome: {family.get('family_name')}, WhatsApp: {family.get('main_whatsapp')}")
    except Exception as e:
        logger.error(f"✗ ERRO ao ler tabela families: {e}")
else:
    logger.error("✗ Supabase não foi inicializado, pulando teste")

# ============================================================================
# ENDPOINTS DE DEBUG
# ============================================================================

@app.get("/")
async def root():
    """Health check com informações de debug."""
    return {
        "status": "CuidaFamília DEBUG Online",
        "supabase_url": "✓ Configurada" if SUPABASE_URL else "✗ Não configurada",
        "supabase_key": "✓ Configurada" if SUPABASE_KEY else "✗ Não configurada",
        "openrouter_key": "✓ Configurada" if OPENROUTER_API_KEY else "✗ Não configurada",
    }

@app.get("/debug/families")
async def debug_families():
    """Retorna todas as famílias no banco."""
    try:
        if not supabase:
            return {"error": "Supabase não inicializado"}
        
        response = supabase.table("families").select("*").execute()
        return {
            "status": "sucesso",
            "total": len(response.data),
            "families": response.data
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/debug/test-whatsapp/{whatsapp_number}")
async def debug_test_whatsapp(whatsapp_number: str):
    """Testa busca de uma família por número WhatsApp."""
    logger.info(f"[DEBUG] Testando busca por: {whatsapp_number}")
    
    try:
        if not supabase:
            return {"error": "Supabase não inicializado"}
        
        # Normalizar número
        normalized = whatsapp_number.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        if not normalized.startswith("+"):
            normalized = "+" + normalized
        
        logger.info(f"[DEBUG] Número normalizado: {normalized}")
        
        response = supabase.table("families").select("*").eq("main_whatsapp", normalized).execute()
        
        if response.data:
            logger.info(f"[DEBUG] Família encontrada: {response.data[0].get('family_name')}")
            return {
                "status": "encontrada",
                "family": response.data[0]
            }
        else:
            logger.warning(f"[DEBUG] Nenhuma família encontrada para {normalized}")
            return {
                "status": "não encontrada",
                "numero_procurado": normalized
            }
    except Exception as e:
        logger.error(f"[DEBUG] ERRO: {e}")
        return {"error": str(e)}

@app.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    """Webhook do Twilio com debug completo."""
    logger.info("=" * 80)
    logger.info("NOVA MENSAGEM RECEBIDA DO TWILIO")
    logger.info("=" * 80)
    
    try:
        # PASSO 1: Extrair dados
        form_data = await request.form()
        incoming_msg = form_data.get("Body", "").strip()
        sender_number = form_data.get("From", "").replace("whatsapp:", "").strip()
        
        logger.info(f"[TWILIO] De: {sender_number}")
        logger.info(f"[TWILIO] Mensagem: {incoming_msg}")
        
        # PASSO 2: Normalizar número
        normalized_number = sender_number.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        if not normalized_number.startswith("+"):
            normalized_number = "+" + normalized_number
        logger.info(f"[NORMALIZAÇÃO] Número normalizado: {normalized_number}")
        
        # PASSO 3: Buscar família
        logger.info("[SUPABASE] Buscando família...")
        if not supabase:
            logger.error("[SUPABASE] Cliente não inicializado!")
            resp = MessagingResponse()
            resp.message("Erro: Supabase não inicializado")
            return Response(content=str(resp), media_type="application/xml")
        
        family_response = supabase.table("families").select("*").eq("main_whatsapp", normalized_number).execute()
        
        if family_response.data:
            family = family_response.data[0]
            logger.info(f"[SUPABASE] ✓ Família encontrada: {family.get('family_name')}")
        else:
            logger.warning(f"[SUPABASE] ✗ Nenhuma família encontrada para {normalized_number}")
            logger.info("[SUPABASE] Listando todas as famílias para debug:")
            all_families = supabase.table("families").select("id, family_name, main_whatsapp").execute()
            for f in all_families.data:
                logger.info(f"  - {f}")
            
            resp = MessagingResponse()
            resp.message(f"Erro: Família não encontrada para {normalized_number}")
            return Response(content=str(resp), media_type="application/xml")
        
        # PASSO 4: Chamar OpenRouter
        logger.info("[OPENROUTER] Chamando IA...")
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }
        
        prompt = f"Você é o Concierge de Cuidado da {family.get('family_name')}. Responda de forma curta e profissional: {incoming_msg}"
        
        payload = {
            "model": OPENROUTER_MODEL,
            "messages": [{"role": "user", "content": prompt}]
        }
        
        ai_response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=10
        )
        
        if ai_response.status_code == 200:
            ai_text = ai_response.json()['choices'][0]['message']['content']
            logger.info(f"[OPENROUTER] ✓ Resposta recebida: {ai_text[:100]}...")
        else:
            logger.error(f"[OPENROUTER] ✗ Erro {ai_response.status_code}: {ai_response.text}")
            ai_text = "Desculpe, tive um erro técnico ao processar sua mensagem."
        
        # PASSO 5: Responder
        resp = MessagingResponse()
        resp.message(ai_text)
        logger.info("[RESPOSTA] Enviando resposta ao Twilio")
        
        return Response(content=str(resp), media_type="application/xml")
        
    except Exception as e:
        logger.error(f"[ERRO CRÍTICO] {str(e)}", exc_info=True)
        resp = MessagingResponse()
        resp.message("Ocorreu um erro interno no servidor do CuidaFamília.")
        return Response(content=str(resp), media_type="application/xml")

if __name__ == "__main__":
    logger.info("=" * 80)
    logger.info("SERVIDOR DEBUG INICIADO")
    logger.info("=" * 80)
    logger.info("Endpoints disponíveis:")
    logger.info("  GET  /                          - Health check")
    logger.info("  GET  /debug/families            - Lista todas as famílias")
    logger.info("  GET  /debug/test-whatsapp/{num} - Testa busca por número")
    logger.info("  POST /whatsapp                  - Webhook do Twilio")
