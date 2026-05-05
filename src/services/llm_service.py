import httpx
import json
from src.core.config import get_settings
from src.core.prompts import PROMPT_SISTEMA, PROMPT_FALLBACK_LLM
from src.utils.logger import get_logger, log_erro

logger = get_logger("llm")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
TIMEOUT_SEGUNDOS = 30


async def chamar_llm(
    mensagem_usuario: str,
    historico: list[dict] = None,
    contexto_extra: str = "",
) -> tuple[str, int]:
    """
    Envia mensagem ao LLM via OpenRouter.
    Retorna: (resposta_texto, tokens_usados)
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

    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json; charset=utf-8",
        "HTTP-Referer": "https://cuidafamilia.app",
        "X-Title": "CuidaFamilia",
    }

    payload = {
        "model": settings.openrouter_model,
        "messages": mensagens,
        "max_tokens": 500,
        "temperature": 0.7,
    }

    # Serializa com ensure_ascii=False para preservar acentos e caracteres especiais
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SEGUNDOS) as client:
            response = await client.post(OPENROUTER_URL, content=body, headers=headers)
            response.raise_for_status()
            data = response.json()

            texto = data["choices"][0]["message"]["content"].strip()
            tokens = data.get("usage", {}).get("total_tokens", 0)

            logger.info(f"LLM respondeu — tokens: {tokens}")
            return texto, tokens

    except httpx.TimeoutException:
        log_erro("llm_timeout", {"model": settings.openrouter_model})
        return PROMPT_FALLBACK_LLM, 0

    except httpx.HTTPStatusError as e:
        log_erro("llm_http_error", {"status": e.response.status_code, "body": e.response.text[:200]})
        return PROMPT_FALLBACK_LLM, 0

    except Exception as e:
        log_erro("llm_erro_generico", {"erro": str(e)})
        return PROMPT_FALLBACK_LLM, 0
