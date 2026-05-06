import httpx
import json
from src.core.config import get_settings
from src.core.prompts import PROMPT_SISTEMA, PROMPT_FALLBACK_LLM
from src.utils.logger import get_logger, log_erro

logger = get_logger("llm")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
TIMEOUT_SEGUNDOS = 30
TIMEOUT_EXTRACAO = 15  # Extração é rápida, timeout menor


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


async def extrair_entidades(mensagem: str, contexto_atual: dict) -> dict:
    """
    Chamada silenciosa e secundária ao LLM para extrair entidades
    estruturadas da mensagem do usuário.

    Retorna dict com chaves prontas para salvar na memoria_agente.
    Nunca lança exceção — falha silenciosa para não impactar a conversa.

    Entidades extraídas:
    - medicamentos        → lista de remédios mencionados
    - condicoes_saude     → condições/diagnósticos mencionados
    - ultima_consulta     → data de consulta mencionada
    - proximo_compromisso → próximo agendamento mencionado
    - alergias            → alergias mencionadas
    - medico_responsavel  → nome do médico mencionado
    """
    settings = get_settings()

    # Monta contexto resumido para guiar a extração
    contexto_str = ""
    if contexto_atual:
        partes = []
        if contexto_atual.get("pessoa_cuidada"):
            partes.append(f"Pessoa cuidada: {contexto_atual['pessoa_cuidada']}")
        if contexto_atual.get("medicamentos"):
            partes.append(f"Medicamentos já conhecidos: {contexto_atual['medicamentos']}")
        contexto_str = "\n".join(partes)

    prompt_sistema = """Você é um extrator silencioso de informações de saúde.
Analise a mensagem do cuidador e extraia SOMENTE informações factuais mencionadas explicitamente.

Retorne APENAS um JSON válido, sem nenhum texto antes ou depois, sem markdown, sem explicações.
Se não houver informação relevante para uma chave, retorne null para ela.

Formato obrigatório:
{
  "medicamentos": "lista separada por vírgula ou null",
  "condicoes_saude": "lista separada por vírgula ou null",
  "ultima_consulta": "data ou descrição ou null",
  "proximo_compromisso": "data/hora ou descrição ou null",
  "alergias": "lista separada por vírgula ou null",
  "medico_responsavel": "nome do médico ou null"
}

Regras:
- Para medicamentos: inclua nome + dosagem se informada (ex: "Atenolol 25mg, Losartana 50mg")
- Se a mensagem atualizar medicamentos já conhecidos, retorne a lista COMPLETA atualizada
- Não invente informações que não estejam na mensagem
- Não faça diagnósticos ou interpretações clínicas"""

    mensagens = [
        {"role": "system", "content": prompt_sistema},
        {"role": "user", "content": f"Contexto:\n{contexto_str}\n\nMensagem do cuidador:\n{mensagem}"}
    ]

    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json; charset=utf-8",
        "HTTP-Referer": "https://cuidafamilia.app",
        "X-Title": "CuidaFamilia",
    }

    payload = {
        "model": settings.openrouter_model,
        "messages": mensagens,
        "max_tokens": 200,
        "temperature": 0.0,  # Zero: queremos extração determinística
    }

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_EXTRACAO) as client:
            response = await client.post(OPENROUTER_URL, content=body, headers=headers)
            response.raise_for_status()
            data = response.json()

            texto = data["choices"][0]["message"]["content"].strip()

            # Remove possíveis marcadores de código que o LLM possa ter adicionado
            texto = texto.replace("```json", "").replace("```", "").strip()

            entidades = json.loads(texto)

            # Filtra apenas valores não-nulos e converte para string
            resultado = {
                k: str(v)
                for k, v in entidades.items()
                if v is not None and str(v).strip() not in ("", "null", "None")
            }

            if resultado:
                logger.info(f"Entidades extraídas: {list(resultado.keys())}")

            return resultado

    except json.JSONDecodeError as e:
        log_erro("extracao_json_invalido", {"erro": str(e), "texto": texto[:100] if 'texto' in dir() else "N/A"})
        return {}

    except Exception as e:
        # Falha silenciosa — extração nunca deve derrubar a conversa principal
        log_erro("extracao_entidades_falhou", {"erro": str(e)})
        return {}
