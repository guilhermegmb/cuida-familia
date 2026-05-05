"""
CuidaFamília — Agente Principal (Cérebro)

Orquestra o fluxo completo:
  1. Identifica o cuidador (novo ou existente)
  2. Gerencia o onboarding passo a passo
  3. Constrói contexto com memória e histórico
  4. Chama o LLM
  5. Persiste tudo no banco
"""

from src.services import supabase_service as db
from src.services import llm_service
from src.core.prompts import (
    PROMPT_ONBOARDING_BOAS_VINDAS,
    PROMPT_ONBOARDING_QUEM_CUIDA,
    PROMPT_ONBOARDING_CONFIRMACAO,
    PROMPT_FALLBACK_GERAL,
)
from src.utils.logger import get_logger, log_interacao, log_erro

logger = get_logger("agente")


async def processar_mensagem(telefone: str, mensagem: str) -> str:
    """
    Ponto de entrada principal. Recebe telefone + mensagem,
    retorna o texto de resposta a ser enviado ao WhatsApp.
    """
    try:
        log_interacao(telefone, "user", mensagem)

        # 1. Busca ou cria o cuidador
        cuidador = db.buscar_ou_criar_cuidador(telefone)
        cuidador_id = cuidador["id"]

        # 2. Persiste a mensagem do usuário
        db.salvar_interacao(cuidador_id, "user", mensagem)

        # 3. Verifica se precisa de onboarding
        if not cuidador.get("onboarding_completo"):
            resposta = await _fluxo_onboarding(cuidador, mensagem)
        else:
            resposta = await _fluxo_conversa(cuidador, mensagem)

        # 4. Persiste resposta do agente
        db.salvar_interacao(cuidador_id, "assistant", resposta)
        log_interacao(telefone, "assistant", resposta)

        return resposta

    except Exception as e:
        log_erro("processar_mensagem", {"erro": str(e)}, telefone)
        return PROMPT_FALLBACK_GERAL


async def _fluxo_onboarding(cuidador: dict, mensagem: str) -> str:
    """Gerencia o onboarding em etapas."""
    etapa = cuidador.get("etapa_onboarding", "inicio")
    telefone = cuidador["telefone"]
    cuidador_id = cuidador["id"]

    # ETAPA 1: Novo usuário — pede o nome
    if etapa == "inicio":
        db.atualizar_cuidador(telefone, {"etapa_onboarding": "aguardando_nome"})
        return PROMPT_ONBOARDING_BOAS_VINDAS

    # ETAPA 2: Recebeu o nome — pede quem cuida
    if etapa == "aguardando_nome":
        nome = mensagem.strip().split()[0].capitalize()  # Pega primeiro nome
        db.atualizar_cuidador(telefone, {
            "nome": nome,
            "etapa_onboarding": "aguardando_pessoa_cuidada",
        })
        db.salvar_memoria(cuidador_id, "nome_cuidador", nome)
        return PROMPT_ONBOARDING_QUEM_CUIDA.format(nome=nome)

    # ETAPA 3: Recebeu info da pessoa cuidada — finaliza onboarding
    if etapa == "aguardando_pessoa_cuidada":
        nome_cuidador = cuidador.get("nome", "amigo(a)")
        pessoa_texto = mensagem.strip()

        # Cria registro da pessoa cuidada
        db.criar_pessoa_cuidada(cuidador_id, nome=pessoa_texto, relacao=pessoa_texto)
        db.salvar_memoria(cuidador_id, "pessoa_cuidada", pessoa_texto)

        # Marca onboarding como completo
        db.atualizar_cuidador(telefone, {
            "onboarding_completo": True,
            "etapa_onboarding": "completo",
        })

        return PROMPT_ONBOARDING_CONFIRMACAO.format(
            nome=nome_cuidador,
            pessoa_cuidada=pessoa_texto,
        )

    # Fallback: reinicia onboarding se etapa desconhecida
    db.atualizar_cuidador(telefone, {"etapa_onboarding": "inicio"})
    return PROMPT_ONBOARDING_BOAS_VINDAS


async def _fluxo_conversa(cuidador: dict, mensagem: str) -> str:
    """Conversa normal pós-onboarding com contexto completo."""
    cuidador_id = cuidador["id"]

    # Busca histórico recente (últimas 10 mensagens)
    historico = db.buscar_historico(cuidador_id, limite=10)

    # Busca memória do agente para enriquecer o contexto
    memoria = db.buscar_memoria(cuidador_id)
    contexto_extra = _formatar_contexto(memoria, cuidador)

    # Chama o LLM
    resposta, tokens = await llm_service.chamar_llm(
        mensagem_usuario=mensagem,
        historico=historico[:-1],  # Exclui a mensagem atual (já está no payload)
        contexto_extra=contexto_extra,
    )

    # Atualiza tokens na última interação (best effort)
    try:
        if tokens > 0:
            db.salvar_interacao(cuidador_id, "assistant", resposta, tokens)
    except Exception:
        pass

    return resposta


def _formatar_contexto(memoria: dict, cuidador: dict) -> str:
    """Formata memória e dados do cuidador como contexto para o LLM."""
    partes = []

    nome = cuidador.get("nome") or memoria.get("nome_cuidador")
    if nome:
        partes.append(f"- Cuidador: {nome}")

    pessoa = memoria.get("pessoa_cuidada")
    if pessoa:
        partes.append(f"- Pessoa cuidada: {pessoa}")

    # Adiciona outras memórias relevantes
    chaves_relevantes = ["ultima_consulta", "medicamento_principal", "condicao_saude", "proximo_compromisso"]
    for chave in chaves_relevantes:
        if chave in memoria:
            partes.append(f"- {chave.replace('_', ' ').capitalize()}: {memoria[chave]}")

    return "\n".join(partes) if partes else ""
