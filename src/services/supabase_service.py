from supabase import create_client, Client
from src.core.config import get_settings
from src.utils.logger import get_logger, log_erro

logger = get_logger("supabase")
_client: Client | None = None


def get_supabase() -> Client:
    global _client
    if _client is None:
        settings = get_settings()
        _client = create_client(settings.supabase_url, settings.supabase_service_key)
    return _client


# ── Cuidadores ──────────────────────────────────────────────

def buscar_ou_criar_cuidador(telefone: str) -> dict:
    """Retorna o cuidador existente ou cria um novo registro."""
    try:
        sb = get_supabase()
        resultado = sb.table("cuidadores").select("*").eq("telefone", telefone).execute()

        if resultado.data:
            return resultado.data[0]

        novo = sb.table("cuidadores").insert({
            "telefone": telefone,
            "onboarding_completo": False,
            "etapa_onboarding": "inicio"
        }).execute()

        logger.info(f"Novo cuidador criado: {telefone}")
        return novo.data[0]

    except Exception as e:
        log_erro("buscar_ou_criar_cuidador", {"erro": str(e)}, telefone)
        raise


def atualizar_cuidador(telefone: str, dados: dict) -> dict:
    """Atualiza campos do cuidador."""
    try:
        sb = get_supabase()
        resultado = sb.table("cuidadores").update(dados).eq("telefone", telefone).execute()
        return resultado.data[0] if resultado.data else {}
    except Exception as e:
        log_erro("atualizar_cuidador", {"erro": str(e), "dados": dados}, telefone)
        raise


# ── Pessoas Cuidadas ─────────────────────────────────────────

def criar_pessoa_cuidada(cuidador_id: str, nome: str, relacao: str = None) -> dict:
    """Registra a pessoa que está sendo cuidada."""
    try:
        sb = get_supabase()
        resultado = sb.table("pessoas_cuidadas").insert({
            "cuidador_id": cuidador_id,
            "nome": nome,
            "relacao": relacao,
        }).execute()
        logger.info(f"Pessoa cuidada registrada: {nome}")
        return resultado.data[0]
    except Exception as e:
        log_erro("criar_pessoa_cuidada", {"erro": str(e)}, cuidador_id)
        raise


def buscar_pessoa_cuidada(cuidador_id: str) -> dict | None:
    """Retorna a primeira pessoa cuidada do cuidador."""
    try:
        sb = get_supabase()
        resultado = sb.table("pessoas_cuidadas") \
            .select("*") \
            .eq("cuidador_id", cuidador_id) \
            .limit(1) \
            .execute()
        return resultado.data[0] if resultado.data else None
    except Exception as e:
        log_erro("buscar_pessoa_cuidada", {"erro": str(e)}, cuidador_id)
        return None


# ── Interações ───────────────────────────────────────────────

def salvar_interacao(cuidador_id: str, papel: str, mensagem: str, tokens: int = 0) -> dict:
    """Persiste uma mensagem no histórico."""
    try:
        sb = get_supabase()
        resultado = sb.table("interacoes").insert({
            "cuidador_id": cuidador_id,
            "papel": papel,
            "mensagem": mensagem,
            "tokens_usados": tokens,
        }).execute()
        return resultado.data[0]
    except Exception as e:
        log_erro("salvar_interacao", {"erro": str(e)}, cuidador_id)
        return {}


def buscar_historico(cuidador_id: str, limite: int = 10) -> list[dict]:
    """Retorna as últimas N interações para contexto do LLM."""
    try:
        sb = get_supabase()
        resultado = sb.table("interacoes") \
            .select("papel, mensagem") \
            .eq("cuidador_id", cuidador_id) \
            .order("created_at", desc=True) \
            .limit(limite) \
            .execute()
        # Inverte para ordem cronológica
        return list(reversed(resultado.data)) if resultado.data else []
    except Exception as e:
        log_erro("buscar_historico", {"erro": str(e)}, cuidador_id)
        return []


# ── Memória do Agente ────────────────────────────────────────

def salvar_memoria(cuidador_id: str, chave: str, valor: str):
    """Salva ou atualiza um item de memória do agente."""
    try:
        sb = get_supabase()
        sb.table("memoria_agente").upsert({
            "cuidador_id": cuidador_id,
            "chave": chave,
            "valor": valor,
        }, on_conflict="cuidador_id,chave").execute()
    except Exception as e:
        log_erro("salvar_memoria", {"erro": str(e), "chave": chave}, cuidador_id)


def buscar_memoria(cuidador_id: str) -> dict:
    """Retorna toda a memória do agente para um cuidador."""
    try:
        sb = get_supabase()
        resultado = sb.table("memoria_agente") \
            .select("chave, valor") \
            .eq("cuidador_id", cuidador_id) \
            .execute()
        return {item["chave"]: item["valor"] for item in resultado.data} if resultado.data else {}
    except Exception as e:
        log_erro("buscar_memoria", {"erro": str(e)}, cuidador_id)
        return {}


# ── Logs ─────────────────────────────────────────────────────

def registrar_log(nivel: str, evento: str, detalhes: dict = None, telefone: str = None):
    """Persiste um log de sistema no Supabase."""
    try:
        sb = get_supabase()
        sb.table("logs_sistema").insert({
            "nivel": nivel,
            "evento": evento,
            "detalhes": detalhes or {},
            "telefone": telefone,
        }).execute()
    except Exception:
        pass  # Silencia erros de log para não causar loops
