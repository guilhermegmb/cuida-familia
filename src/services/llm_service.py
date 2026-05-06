"""
CuidaFamília — Serviço LLM via OpenRouter

Três responsabilidades:
  1. chamar_llm()          → conversa principal com suporte a tools
  2. processar_tool_calls() → interpreta decisões de tool do LLM
  3. extrair_entidades()    → extração silenciosa de entidades (background)
"""

import httpx
import json
from src.core.config import get_settings
from src.core.prompts import PROMPT_SISTEMA, PROMPT_FALLBACK_LLM
from src.utils.logger import get_logger, log_erro

logger = get_logger("llm")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
TIMEOUT_PRINCIPAL = 30
TIMEOUT_EXTRACAO = 15


def _montar_headers(settings) -> dict:
    return {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json; charset=utf-8",
        "HTTP-Referer": "https://cuidafamilia.app",
        "X-Title": "CuidaFamilia",
    }


def _serializar(payload: dict) -> bytes:
    """Serializa garantindo UTF-8 correto para português."""
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


async def chamar_llm(
    mensagem_usuario: str,
    historico: list[dict] = None,
    contexto_extra: str = "",
    tools: list[dict] = None,
) -> tuple[str, int, list[dict]]:
    """
    Chamada principal ao LLM com suporte opcional a tools.

    Retorna: (resposta_texto, tokens_usados, tool_calls)
    - tool_calls é lista vazia se o LLM não decidiu usar nenhuma tool
    - resposta_texto pode ser vazia se o LLM optou por usar só tools
    """
    settings = get_settings()

    sistema = PROMPT_SISTEMA
    if contexto_extra:
        sistema += f"\n\n## Contexto atual do cuidador\n{contexto_extra}"

    mensagens = [{"role": "system", "content": sistema}]
    if historico:
        for item in historico:
            role = "user" if item["papel"] == "user" else "assistant"
            mensagens.append({"role": role, "content": item["mensagem"]})
    mensagens.append({"role": "user", "content": mensagem_usuario})

    payload: dict = {
        "model": settings.openrouter_model,
        "messages": mensagens,
        "max_tokens": 600,
        "temperature": 0.7,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_PRINCIPAL) as client:
            response = await client.post(
                OPENROUTER_URL,
                content=_serializar(payload),
                headers=_montar_headers(settings),
            )
            response.raise_for_status()
            data = response.json()

        choice = data["choices"][0]
        message = choice["message"]
        tokens = data.get("usage", {}).get("total_tokens", 0)

        # Extrai tool_calls se o LLM decidiu usar alguma tool
        tool_calls = message.get("tool_calls") or []
        texto = (message.get("content") or "").strip()

        if tool_calls:
            logger.info(f"LLM decidiu usar tools: {[tc['function']['name'] for tc in tool_calls]}")
        else:
            logger.info(f"LLM respondeu em texto — tokens: {tokens}")

        return texto, tokens, tool_calls

    except httpx.TimeoutException:
        log_erro("llm_timeout", {"model": settings.openrouter_model})
        return PROMPT_FALLBACK_LLM, 0, []
    except httpx.HTTPStatusError as e:
        log_erro("llm_http_error", {"status": e.response.status_code, "body": e.response.text[:200]})
        return PROMPT_FALLBACK_LLM, 0, []
    except Exception as e:
        log_erro("llm_erro_generico", {"erro": str(e)})
        return PROMPT_FALLBACK_LLM, 0, []


async def chamar_llm_com_resultado_tool(
    mensagens_originais: list[dict],
    tool_call_id: str,
    nome_tool: str,
    resultado_tool: str,
    tools: list[dict] = None,
) -> tuple[str, int]:
    """
    Segunda chamada ao LLM após execução de uma tool.
    Injeta o resultado da tool para o LLM gerar a resposta final ao usuário.

    Retorna: (resposta_texto, tokens_usados)
    """
    settings = get_settings()

    # Adiciona o resultado da tool no histórico de mensagens
    mensagens = list(mensagens_originais) + [
        {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": resultado_tool,
        }
    ]

    payload = {
        "model": settings.openrouter_model,
        "messages": mensagens,
        "max_tokens": 400,
        "temperature": 0.7,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "none"  # Não permitir mais tool_calls nesta rodada

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_PRINCIPAL) as client:
            response = await client.post(
                OPENROUTER_URL,
                content=_serializar(payload),
                headers=_montar_headers(settings),
            )
            response.raise_for_status()
            data = response.json()

        message = data["choices"][0]["message"]
        tokens = data.get("usage", {}).get("total_tokens", 0)
        texto = (message.get("content") or "").strip()

        logger.info(f"LLM pós-tool respondeu — tokens: {tokens}")
        return texto, tokens

    except Exception as e:
        log_erro("llm_pos_tool_falhou", {"erro": str(e)})
        return PROMPT_FALLBACK_LLM, 0


async def extrair_entidades(mensagem: str, contexto_atual: dict) -> dict:
    """
    Chamada silenciosa para extrair entidades estruturadas da mensagem.
    Temperature=0 para máximo determinismo.
    Nunca lança exceção.
    """
    settings = get_settings()

    contexto_str = ""
    partes = []
    if contexto_atual.get("pessoa_cuidada"):
        partes.append(f"Pessoa cuidada: {contexto_atual['pessoa_cuidada']}")
    if contexto_atual.get("medicamentos"):
        partes.append(f"Medicamentos já conhecidos: {contexto_atual['medicamentos']}")
    if partes:
        contexto_str = "\n".join(partes)

    prompt_sistema = """Você é um extrator de informações de saúde.
Analise a mensagem do cuidador e extraia informações factuais mencionadas explicitamente.
Retorne APENAS JSON válido, sem markdown, sem texto adicional.

Formato:
{
  "medicamentos": "lista com dosagens ou null",
  "condicoes_saude": "diagnósticos/condições ou null",
  "ultima_consulta": "data ou null",
  "proximo_compromisso": "data/hora ou null",
  "alergias": "lista ou null",
  "medico_responsavel": "nome do médico ou null"
}

Regras: não invente, não interprete clinicamente, apenas extraia o que está explícito."""

    mensagens = [
        {"role": "system", "content": prompt_sistema},
        {"role": "user", "content": f"Contexto:\n{contexto_str}\n\nMensagem:\n{mensagem}"},
    ]

    payload = {
        "model": settings.openrouter_model,
        "messages": mensagens,
        "max_tokens": 200,
        "temperature": 0.0,
    }

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_EXTRACAO) as client:
            response = await client.post(
                OPENROUTER_URL,
                content=_serializar(payload),
                headers=_montar_headers(settings),
            )
            response.raise_for_status()
            data = response.json()

        texto = data["choices"][0]["message"]["content"].strip()
        texto = texto.replace("```json", "").replace("```", "").strip()
        entidades = json.loads(texto)

        return {
            k: str(v)
            for k, v in entidades.items()
            if v is not None and str(v).strip() not in ("", "null", "None")
        }

    except Exception as e:
        log_erro("extracao_entidades_falhou", {"erro": str(e)})
        return {}
