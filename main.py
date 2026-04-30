import os
from fastapi import FastAPI, Request, Form
from twilio.twiml.messaging_response import MessagingResponse
from supabase import create_client, Client
import httpx
import json
from datetime import datetime

app = FastAPI()

# Configurações do Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Configurações do OpenRouter
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-flash-1.5")

@app.get("/")
async def root():
    return {"status": "Cuida Família Online - Sistema de Gestão de Cuidado"}

@app.post("/whatsapp")
async def whatsapp_webhook(Body: str = Form(...), From: str = Form(...)):
    # 1. Identificação Profissional do Usuário
    whatsapp_number = From.replace("whatsapp:", "")
    family_query = supabase.table("families").select("*").eq("main_whatsapp", whatsapp_number).execute()
    
    if not family_query.data:
        response = MessagingResponse()
        response.message("Olá! Aqui é o Concierge do Cuida Família. Este número ainda não está vinculado a uma família ativa. Para começar a organizar o cuidado dos seus entes queridos, entre em contato com nosso suporte.")
        return str(response)

    family = family_query.data[0]
    family_id = family['id']
    family_name = family['family_name']

    # 2. Busca de Contexto (Pacientes e Histórico)
    patients_query = supabase.table("patients").select("*").eq("family_id", family_id).execute()
    patients_info = ", ".join([p['name'] for p in patients_query.data]) if patients_query.data else "Não cadastrado"
    
    history_query = supabase.table("family_logs").select("*").eq("family_id", family_id).order("created_at", desc=True).limit(5).execute()
    history_text = "\n".join([f"- {log['message']}" for log in reversed(history_query.data)])

    # 3. O Cérebro com Blindagem Jurídica e Tom de Secretária
    prompt_sistema = f"""
    VOCÊ É: O Concierge de Cuidado da {family_name}. Uma secretária executiva inteligente, empática e altamente organizada.
    PACIENTE(S) SOB CUIDADO: {patients_info}
    
    SUA MISSÃO: Organizar a logística de saúde (remédios, consultas, tarefas) e reduzir a carga mental da família.
    
    REGRAS DE OURO (BLINDAGEM JURÍDICA):
    1. Você NUNCA dá diagnósticos ("Isso parece ser gripe").
    2. Você NUNCA interpreta exames ("O valor está normal").
    3. Você NUNCA recomenda ou altera dosagens de remédios.
    4. Se o usuário relatar sintomas graves (dor no peito, falta de ar, desmaio), sua PRIMEIRA frase deve ser: "⚠️ ATENÇÃO: Em caso de emergência, procure imediatamente um hospital ou ligue para o SAMU (192)."
    5. Sempre se posicione como um assistente ADMINISTRATIVO e LOGÍSTICO.
    
    TOM DE VOZ:
    - Profissional, mas acolhedor.
    - Proativo: Se o usuário disser que tem consulta, pergunte se quer que anote na agenda.
    - Conciso: Não escreva textos gigantes.
    
    HISTÓRICO RECENTE:
    {history_text}
    """

    # 4. Processamento da IA
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
        data = {
            "model": OPENROUTER_MODEL,
            "messages": [
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": Body}
            ]
        }
        try:
            res = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data, timeout=30.0)
            ai_response = res.json()['choices'][0]['message']['content'] if res.status_code == 200 else "Estou com uma instabilidade momentânea, mas já estou verificando. Pode repetir em um minuto?"
        except Exception:
            ai_response = "Tive um problema de conexão. Por favor, tente novamente."

    # 5. Registro e Resposta
    # Salva no log para manter a memória do próximo chat
    supabase.table("family_logs").insert({
        "family_id": family_id,
        "log_type": "interaction",
        "message": f"Usuário: {Body} | Concierge: {ai_response}"
    }).execute()

    # Se a mensagem parecer um agendamento, poderíamos salvar na family_agenda (Fase posterior)

    twilio_res = MessagingResponse()
    twilio_res.message(ai_response)
    return str(twilio_res)
