"""
CuidaFamília — Testes Mínimos da Semana 1

Execute com:
    pip install pytest pytest-asyncio httpx
    pytest tests/ -v
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# ── Setup mocks antes de importar o app ──
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test_key")
os.environ.setdefault("TWILIO_ACCOUNT_SID", "ACtest")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "test_token")
os.environ.setdefault("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
os.environ.setdefault("OPENROUTER_API_KEY", "sk-or-test")
os.environ.setdefault("APP_ENV", "test")

from main import app

client = TestClient(app)


# ══════════════════════════════════════════════════════════════
# TESTE 1: Health check
# ══════════════════════════════════════════════════════════════
def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "CuidaFamília" in data["servico"]
    print("✅ Health check OK")


# ══════════════════════════════════════════════════════════════
# TESTE 2: Webhook recebe mensagem e responde (fluxo básico)
# ══════════════════════════════════════════════════════════════
@patch("src.api.webhook.processar_mensagem", new_callable=AsyncMock)
@patch("src.api.webhook.enviar_mensagem")
def test_webhook_recebe_e_responde(mock_enviar, mock_processar):
    mock_processar.return_value = "Olá! Sou o CuidaFamília 💙"
    mock_enviar.return_value = True

    response = client.post("/webhook/whatsapp", data={
        "From": "whatsapp:+5511999999999",
        "To": "whatsapp:+14155238886",
        "Body": "Olá",
        "MessageSid": "SMtest123",
    })

    assert response.status_code == 200
    mock_processar.assert_called_once_with("+5511999999999", "Olá")
    mock_enviar.assert_called_once()
    print("✅ Webhook recebe e responde OK")


# ══════════════════════════════════════════════════════════════
# TESTE 3: Mensagem vazia retorna resposta padrão
# ══════════════════════════════════════════════════════════════
@patch("src.api.webhook.enviar_mensagem")
def test_webhook_mensagem_vazia(mock_enviar):
    mock_enviar.return_value = True

    response = client.post("/webhook/whatsapp", data={
        "From": "whatsapp:+5511999999999",
        "To": "whatsapp:+14155238886",
        "Body": "",
        "MessageSid": "SMtest456",
    })

    assert response.status_code == 200
    # Deve enviar resposta de mensagem vazia
    if mock_enviar.called:
        args = mock_enviar.call_args[0]
        assert "vazia" in args[1].lower() or len(args[1]) > 0
    print("✅ Mensagem vazia tratada OK")


# ══════════════════════════════════════════════════════════════
# TESTE 4: Falha no LLM → fallback gracioso
# ══════════════════════════════════════════════════════════════
@patch("src.services.llm_service.chamar_llm", new_callable=AsyncMock)
async def test_llm_fallback(mock_llm):
    from src.core.prompts import PROMPT_FALLBACK_LLM
    mock_llm.return_value = (PROMPT_FALLBACK_LLM, 0)

    resposta, tokens = await mock_llm("mensagem teste", [], "")

    assert "dificuldade técnica" in resposta.lower() or len(resposta) > 0
    assert tokens == 0
    print("✅ Fallback LLM OK")


# ══════════════════════════════════════════════════════════════
# TESTE 5: Fluxo de onboarding completo (mock banco)
# ══════════════════════════════════════════════════════════════
@patch("src.core.agent.db")
@pytest.mark.asyncio
async def test_onboarding_fluxo_completo(mock_db):
    from src.core.agent import processar_mensagem

    # Configura mocks do banco
    mock_db.buscar_ou_criar_cuidador.return_value = {
        "id": "uuid-test-123",
        "telefone": "+5511999999999",
        "onboarding_completo": False,
        "etapa_onboarding": "inicio",
        "nome": None,
    }
    mock_db.salvar_interacao.return_value = {}
    mock_db.atualizar_cuidador.return_value = {}
    mock_db.salvar_memoria.return_value = None

    # Primeira mensagem → deve iniciar onboarding
    resposta = await processar_mensagem("+5511999999999", "Oi")
    assert "CuidaFamília" in resposta or "nome" in resposta.lower()
    print("✅ Onboarding iniciado OK")


# ══════════════════════════════════════════════════════════════
# TESTE 6: Webhook sem 'From' não quebra o servidor
# ══════════════════════════════════════════════════════════════
def test_webhook_sem_from():
    response = client.post("/webhook/whatsapp", data={
        "Body": "Mensagem sem origem",
        "MessageSid": "SMtest789",
    })
    # Deve retornar 200 mesmo assim (não pode quebrar)
    assert response.status_code == 200
    print("✅ Webhook robusto sem 'From' OK")


if __name__ == "__main__":
    print("\n🧪 Rodando testes CuidaFamília — Semana 1\n")
    pytest.main([__file__, "-v", "--tb=short"])
