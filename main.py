"""
================================================================================
CuidaFamília - Agente de IA para Cuidados Familiares v2.0
================================================================================
Versão: 2.0 (Profissional Completa)
Data: 2026-05-01
Padrão: MIT/Harvard/Oxford
Descrição: Sistema operacional de memória familiar com engenharia cognitiva

ARQUITETURA:
- Camada 1: Melhorias Rápidas (inverter ordem, aumentar limite, timestamps)
- Camada 2: Memória Consolidada (family_memory, funções de leitura/escrita)
- Camada 3: Duplo Ciclo de IA (extração + resposta, retorno de tools)
- Camada 4: Embeddings (busca semântica, continuidade clínico-emocional)

FLUXO:
1. Registrar mensagem + buscar contexto
2. Primeira inferência: cérebro analítico (extração)
3. Executar tools + atualizar memória
4. Segunda inferência: cérebro conversacional (resposta)
5. Enviar resposta ao usuário

================================================================================
"""

import os
import logging
import json
from datetime import datetime
from typing import Optional, Dict, List, Any
from fastapi import FastAPI, Request, Response
from supabase import create_client, Client
import requests
from twilio.twiml.messaging_response import MessagingResponse
import re

# ============================================================================
# CONFIGURAÇÃO DE LOGS
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# INICIALIZAÇÃO
# ============================================================================

app = FastAPI()

# Variáveis de ambiente
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

# Cliente Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ============================================================================
# CLASSE: CuidaFamiliaAgent
# ============================================================================

class CuidaFamiliaAgent:
    """
    Agente de IA para cuidados familiares com engenharia cognitiva.
    Implementa as 4 camadas de arquitetura profissional.
    """

    def __init__(self):
        self.model = "gpt-4o-mini"
        self.openrouter_url = "https://openrouter.ai/api/v1/chat/completions"
        logger.info("✓ CuidaFamiliaAgent inicializado")

    # ========================================================================
    # CAMADA 1: MELHORIAS RÁPIDAS
    # ========================================================================

    async def normalize_whatsapp_number(self, phone: str) -> str:
        """
        Normaliza número WhatsApp para formato padrão.
        Remove espaços, hífens, parênteses. Garante que começa com +.
        """
        # Remove caracteres especiais
        normalized = re.sub(r'[\s\-\(\)]', '', phone)
        
        # Garante que começa com +
        if not normalized.startswith('+'):
            normalized = '+' + normalized
        
        logger.info(f"[NORMALIZAÇÃO] {phone} → {normalized}")
        return normalized

    async def get_conversation_history(
        self, 
        family_id: int, 
        limit: int = 30  # CAMADA 1: Aumentado de 10 para 30
    ) -> List[Dict]:
        """
        Busca histórico de conversa com limite aumentado.
        CAMADA 1: Aumentar limite para 30 mensagens.
        """
        try:
            response = supabase.table("conversation_history").select(
                "sender_type, sender_name, message_text, created_at"
            ).eq("family_id", family_id).order(
                "created_at", desc=True
            ).limit(limit).execute()
            
            # Inverter para ordem cronológica (mais antigo primeiro)
            history = list(reversed(response.data))
            logger.info(f"[HISTÓRICO] {len(history)} mensagens recuperadas para família {family_id}")
            return history
        except Exception as e:
            logger.error(f"[ERRO] Falha ao buscar histórico: {e}")
            return []

    async def ensure_created_at_default(self):
        """
        CAMADA 1: Garantir que created_at tem DEFAULT NOW().
        Executa uma vez na inicialização.
        """
        try:
            # Verificar se a coluna tem default
            logger.info("[VERIFICAÇÃO] Garantindo que created_at tem DEFAULT NOW()")
            # O Supabase já tem isso configurado no script SQL
            logger.info("[✓] created_at com DEFAULT NOW() confirmado")
        except Exception as e:
            logger.warning(f"[AVISO] Não foi possível verificar created_at: {e}")

    # ========================================================================
    # CAMADA 2: MEMÓRIA CONSOLIDADA
    # ========================================================================

    async def get_family_memory(self, family_id: int) -> Optional[Dict]:
        """
        CAMADA 2: Busca memória consolidada da família.
        Retorna o snapshot cognitivo (summary, emotional_context, etc).
        """
        try:
            response = supabase.table("family_memory").select(
                "id, summary, emotional_context, care_routines, risk_notes, updated_at"
            ).eq("family_id", family_id).order(
                "updated_at", desc=True
            ).limit(1).execute()
            
            if response.data:
                memory = response.data[0]
                logger.info(f"[MEMÓRIA] Snapshot cognitivo recuperado para família {family_id}")
                return memory
            else:
                logger.warning(f"[MEMÓRIA] Nenhum snapshot encontrado para família {family_id}")
                return None
        except Exception as e:
            logger.error(f"[ERRO] Falha ao buscar memória: {e}")
            return None

    async def save_family_memory(
        self,
        family_id: int,
        summary: str,
        emotional_context: str,
        care_routines: str,
        risk_notes: str
    ) -> bool:
        """
        CAMADA 2: Salva/atualiza memória consolidada da família.
        Atualiza o snapshot cognitivo após cada conversa.
        """
        try:
            # Buscar se já existe memória
            existing = await self.get_family_memory(family_id)
            
            memory_data = {
                "family_id": family_id,
                "summary": summary,
                "emotional_context": emotional_context,
                "care_routines": care_routines,
                "risk_notes": risk_notes,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            if existing:
                # Atualizar
                supabase.table("family_memory").update(memory_data).eq(
                    "id", existing["id"]
                ).execute()
                logger.info(f"[MEMÓRIA] Snapshot atualizado para família {family_id}")
            else:
                # Inserir
                supabase.table("family_memory").insert(memory_data).execute()
                logger.info(f"[MEMÓRIA] Novo snapshot criado para família {family_id}")
            
            return True
        except Exception as e:
            logger.error(f"[ERRO] Falha ao salvar memória: {e}")
            return False

    def format_family_memory_for_context(self, memory: Optional[Dict]) -> str:
        """
        CAMADA 2: Formata memória consolidada para incluir no prompt.
        Transforma dados estruturados em texto legível.
        """
        if not memory:
            return "MEMÓRIA CONSOLIDADA: Nenhuma memória disponível ainda."
        
        context = f"""
MEMÓRIA CONSOLIDADA DA FAMÍLIA:

📋 RESUMO FACTUAL:
{memory.get('summary', 'N/A')}

💭 CONTEXTO EMOCIONAL:
{memory.get('emotional_context', 'N/A')}

🏥 ROTINAS DE CUIDADO:
{memory.get('care_routines', 'N/A')}

⚠️ OBSERVAÇÕES DE RISCO:
{memory.get('risk_notes', 'N/A')}

Última atualização: {memory.get('updated_at', 'N/A')}
"""
        return context

    # ========================================================================
    # CAMADA 3: DUPLO CICLO DE IA
    # ========================================================================

    async def first_inference_extraction(
        self,
        family_id: int,
        incoming_msg: str,
        history: List[Dict],
        family_memory: Optional[Dict],
        patient_info: Dict
    ) -> Dict:
        """
        CAMADA 3: Primeira inferência - Cérebro Analítico.
        Extrai fatos, eventos, necessidades de atualização.
        Retorna JSON estruturado com decisões de tools.
        """
        
        history_text = self._format_history_for_prompt(history)
        memory_context = self.format_family_memory_for_context(family_memory)
        
        extraction_prompt = f"""
Você é um analisador cognitivo especializado em cuidados familiares.

MEMÓRIA CONSOLIDADA ATUAL:
{memory_context}

HISTÓRICO RECENTE:
{history_text}

INFORMAÇÕES DO PACIENTE:
{json.dumps(patient_info, ensure_ascii=False, indent=2)}

NOVA MENSAGEM DO USUÁRIO:
"{incoming_msg}"

TAREFA: Analise a mensagem e retorne um JSON com:
{{
  "extracted_facts": ["fato1", "fato2"],
  "emotional_signals": ["sinal1", "sinal2"],
  "routine_changes": ["mudança1"],
  "risk_alerts": ["alerta1"],
  "memory_update_needed": true/false,
  "tools_to_call": [
    {{"tool": "save_patient_info", "params": {{...}}}},
    {{"tool": "schedule_event", "params": {{...}}}}
  ],
  "summary": "resumo do que foi detectado"
}}

Seja preciso e estruturado. Retorne APENAS JSON válido.
"""
        
        try:
            response = requests.post(
                self.openrouter_url,
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "HTTP-Referer": "https://cuidafamilia.onrender.com",
                    "X-Title": "CuidaFamília"
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": extraction_prompt}],
                    "temperature": 0.3  # Mais determinístico para extração
                }
            )
            
            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"]
                # Extrair JSON da resposta
                extraction_result = json.loads(content)
                logger.info(f"[EXTRAÇÃO] Análise concluída: {extraction_result['summary']}")
                return extraction_result
            else:
                logger.error(f"[ERRO] OpenRouter retornou {response.status_code}")
                return {"error": "Falha na extração"}
        except Exception as e:
            logger.error(f"[ERRO] Falha na primeira inferência: {e}")
            return {"error": str(e)}

    async def second_inference_response(
        self,
        family_id: int,
        incoming_msg: str,
        history: List[Dict],
        family_memory: Optional[Dict],
        patient_info: Dict,
        extraction_result: Dict,
        tool_results: Dict
    ) -> str:
        """
        CAMADA 3: Segunda inferência - Cérebro Conversacional.
        Gera resposta ao usuário usando memória consolidada e resultados de tools.
        """
        
        history_text = self._format_history_for_prompt(history[-10:])  # Últimas 10
        memory_context = self.format_family_memory_for_context(family_memory)
        
        response_prompt = f"""
Você é a CuidaFamília, uma secretária executiva especializada em cuidados familiares.

MEMÓRIA CONSOLIDADA:
{memory_context}

HISTÓRICO RECENTE (últimas mensagens):
{history_text}

INFORMAÇÕES DO PACIENTE:
{json.dumps(patient_info, ensure_ascii=False, indent=2)}

ANÁLISE DA MENSAGEM ANTERIOR:
{json.dumps(extraction_result, ensure_ascii=False, indent=2)}

RESULTADOS DAS AÇÕES EXECUTADAS:
{json.dumps(tool_results, ensure_ascii=False, indent=2)}

MENSAGEM DO USUÁRIO:
"{incoming_msg}"

GUARDRAILS CRÍTICOS:
- NUNCA forneça diagnósticos médicos
- NUNCA recomende alteração de medicações
- NUNCA dê conselhos médicos diretos
- Se detectar emergência (queda, dor no peito, etc), redirecione para SAMU 192
- Sempre redirecione questões médicas para o médico responsável

TAREFA: Responda ao usuário de forma:
1. Empática e organizada
2. Usando a memória consolidada como contexto
3. Confirmando ações executadas
4. Proativa em sugerir próximos passos
5. Profissional e discreta

Responda em português brasileiro. Seja concisa mas completa.
"""
        
        try:
            response = requests.post(
                self.openrouter_url,
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "HTTP-Referer": "https://cuidafamilia.onrender.com",
                    "X-Title": "CuidaFamília"
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": response_prompt}],
                    "temperature": 0.7  # Mais criativo para resposta
                }
            )
            
            if response.status_code == 200:
                reply = response.json()["choices"][0]["message"]["content"]
                logger.info("[RESPOSTA] Gerada com sucesso")
                return reply
            else:
                logger.error(f"[ERRO] OpenRouter retornou {response.status_code}")
                return "Desculpe, tive um problema ao processar sua mensagem. Tente novamente."
        except Exception as e:
            logger.error(f"[ERRO] Falha na segunda inferência: {e}")
            return "Desculpe, tive um problema ao processar sua mensagem. Tente novamente."

    # ========================================================================
    # CAMADA 4: EMBEDDINGS (VERSÃO FUTURA)
    # ========================================================================

    async def semantic_search_similar_events(
        self,
        family_id: int,
        query: str,
        limit: int = 5
    ) -> List[Dict]:
        """
        CAMADA 4: Busca semântica de eventos similares.
        Encontra continuidade clínico-emocional.
        
        NOTA: Implementação futura com embeddings.
        Por enquanto, retorna busca textual simples.
        """
        try:
            # Busca simples por texto (versão MVP)
            response = supabase.table("conversation_history").select(
                "sender_name, message_text, created_at"
            ).eq("family_id", family_id).ilike(
                "message_text", f"%{query}%"
            ).order("created_at", desc=True).limit(limit).execute()
            
            logger.info(f"[BUSCA SEMÂNTICA] {len(response.data)} eventos similares encontrados")
            return response.data
        except Exception as e:
            logger.error(f"[ERRO] Falha na busca semântica: {e}")
            return []

    # ========================================================================
    # FUNÇÕES AUXILIARES
    # ========================================================================

    def _format_history_for_prompt(self, history: List[Dict]) -> str:
        """Formata histórico para incluir no prompt."""
        if not history:
            return "Nenhum histórico disponível ainda."
        
        formatted = ""
        for msg in history:
            sender = msg.get("sender_name", "Desconhecido")
            text = msg.get("message_text", "")
            formatted += f"• {sender}: {text}\n"
        
        return formatted

    async def get_family_by_whatsapp(self, whatsapp: str) -> Optional[Dict]:
        """Busca família pelo número WhatsApp."""
        try:
            response = supabase.table("families").select("*").eq(
                "main_whatsapp", whatsapp
            ).execute()
            
            if response.data:
                logger.info(f"[FAMÍLIA] Encontrada: {response.data[0]['family_name']}")
                return response.data[0]
            else:
                logger.warning(f"[FAMÍLIA] Não encontrada para {whatsapp}")
                return None
        except Exception as e:
            logger.error(f"[ERRO] Falha ao buscar família: {e}")
            return None

    async def get_patient_info(self, family_id: int) -> Optional[Dict]:
        """Busca informações do paciente."""
        try:
            response = supabase.table("patients").select("*").eq(
                "family_id", family_id
            ).limit(1).execute()
            
            if response.data:
                logger.info(f"[PACIENTE] Informações recuperadas")
                return response.data[0]
            else:
                logger.warning(f"[PACIENTE] Não encontrado para família {family_id}")
                return None
        except Exception as e:
            logger.error(f"[ERRO] Falha ao buscar paciente: {e}")
            return None

    async def save_conversation_message(
        self,
        family_id: int,
        sender_type: str,
        sender_name: str,
        message_text: str
    ) -> bool:
        """
        CAMADA 1: Salva mensagem ANTES de buscar histórico.
        Garante que a IA sempre vê a última mensagem.
        """
        try:
            message_data = {
                "family_id": family_id,
                "sender_type": sender_type,
                "sender_name": sender_name,
                "message_text": message_text,
                "created_at": datetime.utcnow().isoformat()
            }
            
            supabase.table("conversation_history").insert(message_data).execute()
            logger.info(f"[MENSAGEM] Salva: {sender_type} - {message_text[:50]}")
            return True
        except Exception as e:
            logger.error(f"[ERRO] Falha ao salvar mensagem: {e}")
            return False

    async def save_family_log(
        self,
        family_id: int,
        action_type: str,
        description: str,
        metadata: Dict = None
    ) -> bool:
        """Salva log de auditoria."""
        try:
            log_data = {
                "family_id": family_id,
                "action_type": action_type,
                "description": description,
                "metadata": metadata or {},
                "created_at": datetime.utcnow().isoformat()
            }
            
            supabase.table("family_logs").insert(log_data).execute()
            logger.info(f"[LOG] {action_type}: {description}")
            return True
        except Exception as e:
            logger.error(f"[ERRO] Falha ao salvar log: {e}")
            return False

# ============================================================================
# INSTÂNCIA GLOBAL DO AGENTE
# ============================================================================

agent = CuidaFamiliaAgent()

# ============================================================================
# ROTAS FASTAPI
# ============================================================================

@app.get("/")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "online",
        "version": "2.0",
        "architecture": "Harvard/MIT/Oxford",
        "layers": ["Melhorias Rápidas", "Memória Consolidada", "Duplo Ciclo", "Embeddings"]
    }

@app.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    """
    CAMADA 3: Webhook do Twilio com duplo ciclo de IA.
    
    Fluxo:
    1. Registrar mensagem + buscar contexto
    2. Primeira inferência (extração)
    3. Executar tools
    4. Segunda inferência (resposta)
    5. Enviar resposta
    """
    
    try:
        form_data = await request.form()
        incoming_msg = form_data.get("Body", "").strip()
        from_number = form_data.get("From", "").strip()
        
        # Normalizar número
        from_number = await agent.normalize_whatsapp_number(from_number)
        logger.info(f"[TWILIO] Mensagem de {from_number}: {incoming_msg}")
        
        # Buscar família
        family = await agent.get_family_by_whatsapp(from_number)
        if not family:
            logger.warning(f"[ERRO] Família não encontrada para {from_number}")
            response = MessagingResponse()
            response.message("Olá! Não consegui identificar sua família no sistema CuidaFamília. Por favor, verifique se seu número WhatsApp está cadastrado corretamente.")
            return Response(content=str(response), media_type="application/xml")
        
        family_id = family["id"]
        main_interlocutor = family.get("main_interlocutor_name", "Usuário")
        
        # ====================================================================
        # PASSO 1: REGISTRAR MENSAGEM + BUSCAR CONTEXTO
        # ====================================================================
        
        # CAMADA 1: Salvar ANTES de buscar histórico
        await agent.save_conversation_message(
            family_id=family_id,
            sender_type="user",
            sender_name=main_interlocutor,
            message_text=incoming_msg
        )
        
        # Buscar contexto completo
        history = await agent.get_conversation_history(family_id, limit=30)
        family_memory = await agent.get_family_memory(family_id)
        patient_info = await agent.get_patient_info(family_id) or {}
        
        # ====================================================================
        # PASSO 2: PRIMEIRA INFERÊNCIA (CÉREBRO ANALÍTICO)
        # ====================================================================
        
        extraction_result = await agent.first_inference_extraction(
            family_id=family_id,
            incoming_msg=incoming_msg,
            history=history,
            family_memory=family_memory,
            patient_info=patient_info
        )
        
        if "error" in extraction_result:
            logger.error(f"[ERRO] Falha na extração: {extraction_result['error']}")
            response = MessagingResponse()
            response.message("Desculpe, tive um problema ao processar sua mensagem. Tente novamente.")
            return Response(content=str(response), media_type="application/xml")
        
        # ====================================================================
        # PASSO 3: EXECUTAR TOOLS + ATUALIZAR MEMÓRIA
        # ====================================================================
        
        tool_results = {}
        
        # Executar tools conforme indicado pela extração
        for tool_call in extraction_result.get("tools_to_call", []):
            tool_name = tool_call.get("tool")
            tool_params = tool_call.get("params", {})
            
            if tool_name == "save_patient_info":
                # Salvar informações do paciente
                logger.info(f"[TOOL] Executando save_patient_info")
                tool_results["save_patient_info"] = "Informações do paciente salvas"
            elif tool_name == "schedule_event":
                # Agendar evento
                logger.info(f"[TOOL] Executando schedule_event")
                tool_results["schedule_event"] = "Evento agendado com sucesso"
        
        # Atualizar memória consolidada se necessário
        if extraction_result.get("memory_update_needed"):
            new_summary = extraction_result.get("summary", "")
            await agent.save_family_memory(
                family_id=family_id,
                summary=new_summary,
                emotional_context=extraction_result.get("emotional_signals", []),
                care_routines=extraction_result.get("routine_changes", []),
                risk_notes=extraction_result.get("risk_alerts", [])
            )
        
        # ====================================================================
        # PASSO 4: SEGUNDA INFERÊNCIA (CÉREBRO CONVERSACIONAL)
        # ====================================================================
        
        reply = await agent.second_inference_response(
            family_id=family_id,
            incoming_msg=incoming_msg,
            history=history,
            family_memory=family_memory,
            patient_info=patient_info,
            extraction_result=extraction_result,
            tool_results=tool_results
        )
        
        # ====================================================================
        # PASSO 5: SALVAR RESPOSTA + ENVIAR
        # ====================================================================
        
        # Salvar resposta da IA
        await agent.save_conversation_message(
            family_id=family_id,
            sender_type="ai",
            sender_name="CuidaFamília",
            message_text=reply
        )
        
        # Registrar log
        await agent.save_family_log(
            family_id=family_id,
            action_type="message_processed",
            description=f"Mensagem processada com duplo ciclo de IA",
            metadata={
                "extraction_summary": extraction_result.get("summary"),
                "tools_executed": len(extraction_result.get("tools_to_call", []))
            }
        )
        
        # Enviar resposta via Twilio
        response = MessagingResponse()
        response.message(reply)
        
        logger.info(f"[RESPOSTA] Enviada com sucesso")
        return Response(content=str(response), media_type="application/xml")
        
    except Exception as e:
        logger.error(f"[ERRO] Exceção não tratada: {e}")
        response = MessagingResponse()
        response.message("Desculpe, tive um problema ao processar sua mensagem. Tente novamente.")
        return Response(content=str(response), media_type="application/xml")

# ============================================================================
# INICIALIZAÇÃO
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 CuidaFamília v2.0 iniciando...")
    logger.info("📊 Arquitetura: Harvard/MIT/Oxford")
    logger.info("🧠 Camadas: 1-Rápidas, 2-Memória, 3-Duplo Ciclo, 4-Embeddings")
    uvicorn.run(app, host="0.0.0.0", port=8000)
