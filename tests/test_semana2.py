"""
CuidaFamília — Testes Semana 2

Cobre:
  - Definições das tools (estrutura válida)
  - Executor de tools (handlers isolados)
  - Scheduler (lógica de cálculo de horários)
  - Agente (orquestração com tool_calls)
  - Regras de risco (severidade)

Execute com:
    pytest tests/test_semana2.py -v
"""

import pytest
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test_key")
os.environ.setdefault("TWILIO_ACCOUNT_SID", "ACtest")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "test_token")
os.environ.setdefault("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
os.environ.setdefault("OPENROUTER_API_KEY", "sk-or-test")
os.environ.setdefault("APP_ENV", "test")


# ══════════════════════════════════════════════════════════════
# TESTE 1: Definições das tools têm estrutura válida
# ══════════════════════════════════════════════════════════════
def test_tools_estrutura_valida():
    from src.services.tools.definitions import ALL_TOOLS, LOG_EVENT, SCHEDULE_CHECKIN, GET_RECENT_EVENTS

    assert len(ALL_TOOLS) == 3

    for tool in ALL_TOOLS:
        assert tool["type"] == "function"
        assert "function" in tool
        assert "name" in tool["function"]
        assert "description" in tool["function"]
        assert "parameters" in tool["function"]
        params = tool["function"]["parameters"]
        assert "required" in params
        assert "properties" in params

    # Verifica campos obrigatórios de cada tool
    log_params = LOG_EVENT["function"]["parameters"]
    assert "tipo" in log_params["required"]
    assert "descricao" in log_params["required"]
    assert "severidade" in log_params["required"]

    sched_params = SCHEDULE_CHECKIN["function"]["parameters"]
    assert "tipo" in sched_params["required"]
    assert "descricao" in sched_params["required"]
    assert "horario" in sched_params["required"]

    events_params = GET_RECENT_EVENTS["function"]["parameters"]
    assert "janela_dias" in events_params["required"]

    print("✅ Estrutura das tools válida")


# ══════════════════════════════════════════════════════════════
# TESTE 2: Executor — log_event registra evento no banco
# ══════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_executor_log_event():
    from src.services.tools.executor import executar_tool

    mock_sb = MagicMock()
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "evt-uuid-123"}
    ]

    with patch("src.services.tools.executor.db") as mock_db:
        mock_db.get_supabase.return_value = mock_sb
        mock_db.salvar_memoria = MagicMock()

        resultado = await executar_tool(
            nome_tool="log_event",
            argumentos={
                "tipo": "sintoma",
                "descricao": "Dor de cabeça intensa desde a manhã",
                "severidade": "atencao",
                "dados_estruturados": {},
            },
            cuidador_id="cuidador-uuid-123",
            pessoa_cuidada_id="pessoa-uuid-456",
        )

    assert resultado["sucesso"] is True
    assert "registrado" in resultado["resultado"].lower() or "sintoma" in resultado["resultado"].lower()
    assert resultado["dados"]["tipo"] == "sintoma"
    assert resultado["dados"]["severidade"] == "atencao"
    print("✅ log_event registra evento corretamente")


# ══════════════════════════════════════════════════════════════
# TESTE 3: Executor — schedule_checkin cria rotina
# ══════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_executor_schedule_checkin():
    from src.services.tools.executor import executar_tool

    mock_sb = MagicMock()
    # Simula que não existe rotina duplicada
    mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value \
        .eq.return_value.eq.return_value.execute.return_value.data = []
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "rotina-uuid-789"}
    ]

    with patch("src.services.tools.executor.db") as mock_db:
        mock_db.get_supabase.return_value = mock_sb

        resultado = await executar_tool(
            nome_tool="schedule_checkin",
            argumentos={
                "tipo": "medicamento",
                "descricao": "Tomar Rivaroxabana 15mg",
                "horario": "15:00",
                "dias_semana": "todos",
            },
            cuidador_id="cuidador-uuid-123",
        )

    assert resultado["sucesso"] is True
    assert "15:00" in resultado["resultado"]
    assert "lembrete" in resultado["resultado"].lower() or "rivaroxabana" in resultado["resultado"].lower()
    print("✅ schedule_checkin cria rotina corretamente")


# ══════════════════════════════════════════════════════════════
# TESTE 4: Executor — get_recent_events retorna eventos
# ══════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_executor_get_recent_events():
    from src.services.tools.executor import executar_tool

    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value \
        .gte.return_value.order.return_value.limit.return_value.execute.return_value.data = [
        {
            "tipo": "sintoma",
            "severidade": "normal",
            "descricao": "Dor de cabeça leve",
            "created_at": "2026-05-05T14:00:00+00:00",
        },
        {
            "tipo": "medicao",
            "severidade": "atencao",
            "descricao": "Pressão 15x10",
            "created_at": "2026-05-05T09:00:00+00:00",
        },
    ]

    with patch("src.services.tools.executor.db") as mock_db:
        mock_db.get_supabase.return_value = mock_sb

        resultado = await executar_tool(
            nome_tool="get_recent_events",
            argumentos={"janela_dias": 7, "tipo_filtro": "todos"},
            cuidador_id="cuidador-uuid-123",
        )

    assert resultado["sucesso"] is True
    assert resultado["dados"]["total"] == 2
    assert "Dor de cabeça" in resultado["resultado"]
    assert "Pressão" in resultado["resultado"]
    print("✅ get_recent_events retorna histórico corretamente")


# ══════════════════════════════════════════════════════════════
# TESTE 5: Executor — tool desconhecida retorna erro gracioso
# ══════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_executor_tool_desconhecida():
    from src.services.tools.executor import executar_tool

    resultado = await executar_tool(
        nome_tool="tool_inexistente",
        argumentos={},
        cuidador_id="cuidador-uuid-123",
    )

    assert resultado["sucesso"] is False
    assert "não reconhecida" in resultado["resultado"]
    print("✅ Tool desconhecida tratada graciosamente")


# ══════════════════════════════════════════════════════════════
# TESTE 6: Scheduler — cálculo de próximo envio
# ══════════════════════════════════════════════════════════════
def test_scheduler_calculo_proximo_envio():
    from src.services.tools.executor import _calcular_proximo_envio

    proximo = _calcular_proximo_envio("08:00", "todos")
    agora = datetime.now(timezone.utc)

    # O próximo envio deve ser no futuro
    assert proximo > agora

    # E dentro das próximas 25h
    from datetime import timedelta
    assert proximo < agora + timedelta(hours=25)
    print("✅ Cálculo de próximo envio correto")


# ══════════════════════════════════════════════════════════════
# TESTE 7: Regra de risco — severidade "urgente" ativa emergência
# ══════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_regra_risco_urgente():
    from src.services.tools.executor import executar_tool

    mock_sb = MagicMock()
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "evt-crise-123"}
    ]

    with patch("src.services.tools.executor.db") as mock_db:
        mock_db.get_supabase.return_value = mock_sb
        mock_db.salvar_memoria = MagicMock()

        resultado = await executar_tool(
            nome_tool="log_event",
            argumentos={
                "tipo": "crise",
                "descricao": "Queda no banheiro, possível fratura",
                "severidade": "urgente",
            },
            cuidador_id="cuidador-uuid-123",
        )

    assert resultado["sucesso"] is True
    # Evento urgente deve salvar na memória também
    mock_db.salvar_memoria.assert_called_once()
    call_args = mock_db.salvar_memoria.call_args[0]
    assert "urgente" in call_args[1]
    print("✅ Evento urgente salvo na memória como alerta")


# ══════════════════════════════════════════════════════════════
# TESTE 8: Agente — fluxo com tool_call do LLM
# ══════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_agente_fluxo_com_tool():
    from src.core.agent import processar_mensagem

    with patch("src.core.agent.db") as mock_db, \
         patch("src.core.agent.llm_service") as mock_llm, \
         patch("src.core.agent.executar_tool") as mock_executor:

        # Simula cuidador com onboarding completo
        mock_db.buscar_ou_criar_cuidador.return_value = {
            "id": "cuidador-uuid-123",
            "telefone": "+5511999999999",
            "onboarding_completo": True,
            "etapa_onboarding": "completo",
            "nome": "Guilherme",
        }
        mock_db.buscar_pessoa_cuidada.return_value = {"id": "pessoa-uuid-456"}
        mock_db.buscar_historico.return_value = []
        mock_db.buscar_memoria.return_value = {"pessoa_cuidada": "Dona Antonina"}
        mock_db.salvar_interacao.return_value = {}

        # Simula LLM decidindo usar log_event
        mock_llm.chamar_llm = AsyncMock(return_value=(
            "",  # texto vazio (LLM vai usar tool)
            50,
            [{
                "id": "call_abc123",
                "function": {
                    "name": "log_event",
                    "arguments": '{"tipo": "sintoma", "descricao": "Dor de cabeca", "severidade": "normal"}',
                },
            }],
        ))

        # Simula execução da tool
        mock_executor.return_value = {
            "sucesso": True,
            "resultado": "📋 Sintoma registrado: Dor de cabeca",
            "dados": {"evento_id": "evt-123"},
        }

        # Simula resposta final do LLM após tool
        mock_llm.chamar_llm_com_resultado_tool = AsyncMock(
            return_value=("Anotei a dor de cabeça no histórico dela. ✅ Como ela está agora?", 80)
        )

        resposta = await processar_mensagem("+5511999999999", "ela está com dor de cabeça")

    assert "anotei" in resposta.lower() or "histórico" in resposta.lower()
    mock_executor.assert_called_once()
    print("✅ Agente orquestra tool_call corretamente")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
