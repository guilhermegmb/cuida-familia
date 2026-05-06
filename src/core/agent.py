"""
CuidaFamília — Agente Principal (Cérebro) — Fase 1 revisada

Melhorias desta versão:
  - Memória completa: toda a memoria_agente é injetada no contexto
  - Extração automática de entidades após cada resposta
  - Histórico expandido para 20 mensagens
  - Contexto enriquecido com seções organizadas por categoria
"""

import asyncio
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

    if etapa == "inicio":
        db.atualizar_cuidador(telefone, {"etapa_onboarding": "aguardando_nome"})
        return PROMPT_ONBOARDING_BOAS_VINDAS

    if etapa == "aguardando_nome":
        nome = mensagem.strip().split()[0].capitalize()
        db.atualizar_cuidador(telefone, {
            "nome": nome,
            "etapa_onboarding": "aguardando_pessoa_cuidada",
        })
        db.salvar_memoria(cuidador_id, "nome_cuidador", nome)
        return PROMPT_ONBOARDING_QUEM_CUIDA.format(nome=nome)

    if etapa == "aguardando_pessoa_cuidada":
        nome_cuidador = cuidador.get("nome", "amigo(a)")
        pessoa_texto = mensagem.strip()

        db.criar_pessoa_cuidada(cuidador_id, nome=pessoa_texto, relacao=pessoa_texto)
        db.salvar_memoria(cuidador_id, "pessoa_cuidada", pessoa_texto)

        db.atualizar_cuidador(telefone, {
            "onboarding_completo": True,
            "etapa_onboarding": "completo",
        })

        return PROMPT_ONBOARDING_CONFIRMACAO.format(
            nome=nome_cuidador,
            pessoa_cuidada=pessoa_texto,
        )

    db.atualizar_cuidador(telefone, {"etapa_onboarding": "inicio"})
    return PROMPT_ONBOARDING_BOAS_VINDAS


async def _fluxo_conversa(cuidador: dict, mensagem: str) -> str:
    """
    Conversa normal pós-onboarding com contexto completo e memória persistente.

    Fluxo:
      1. Carrega memória completa + histórico expandido
      2. Monta contexto enriquecido
      3. Chama LLM principal → gera resposta
      4. Em paralelo (asyncio): extrai entidades da mensagem e salva na memória
         (não bloqueia nem atrasa a resposta ao usuário)
    """
    cuidador_id = cuidador["id"]

    # Carrega histórico expandido (20 msgs) e memória completa
    historico = db.buscar_historico(cuidador_id, limite=20)
    memoria = db.buscar_memoria(cuidador_id)

    # Monta contexto enriquecido com TODA a memória disponível
    contexto_extra = _formatar_contexto_completo(memoria, cuidador)

    # Chama o LLM principal
    resposta, tokens = await llm_service.chamar_llm(
        mensagem_usuario=mensagem,
        historico=historico[:-1],  # Exclui a msg atual que já vai no payload
        contexto_extra=contexto_extra,
    )

    # Extração de entidades em background — não bloqueia a resposta
    asyncio.create_task(
        _extrair_e_salvar_entidades(cuidador_id, mensagem, memoria)
    )

    return resposta


async def _extrair_e_salvar_entidades(
    cuidador_id: str,
    mensagem: str,
    contexto_atual: dict
):
    """
    Chamada silenciosa e assíncrona ao LLM extrator.
    Roda em background após a resposta já ter sido enviada ao usuário.
    Qualquer falha aqui é silenciosa — nunca impacta a conversa.
    """
    try:
        entidades = await llm_service.extrair_entidades(mensagem, contexto_atual)

        if entidades:
            db.salvar_memorias_lote(cuidador_id, entidades)
            logger.info(f"Memória atualizada: {list(entidades.keys())} → {cuidador_id[:8]}...")

    except Exception as e:
        # Falha completamente silenciosa
        log_erro("extracao_background_falhou", {"erro": str(e)}, cuidador_id)


def _formatar_contexto_completo(memoria: dict, cuidador: dict) -> str:
    """
    Formata TODA a memória disponível como contexto estruturado para o LLM.

    Diferença da versão anterior:
    - Antes: só 4 chaves hard-coded eram injetadas
    - Agora: TODA a memoria_agente é injetada, organizada por seções
    """
    secoes = []

    # ── Seção 1: Identidade do cuidador ──
    nome = cuidador.get("nome") or memoria.get("nome_cuidador")
    pessoa = memoria.get("pessoa_cuidada")
    if nome or pessoa:
        id_partes = []
        if nome:
            id_partes.append(f"Cuidador: {nome}")
        if pessoa:
            id_partes.append(f"Pessoa cuidada: {pessoa}")
        secoes.append("### Identificação\n" + "\n".join(f"- {p}" for p in id_partes))

    # ── Seção 2: Saúde — informações clínicas conhecidas ──
    saude_chaves = {
        "medicamentos": "Medicamentos em uso",
        "condicoes_saude": "Condições de saúde",
        "alergias": "Alergias",
        "medico_responsavel": "Médico responsável",
    }
    saude_partes = []
    for chave, label in saude_chaves.items():
        if chave in memoria and memoria[chave]:
            saude_partes.append(f"- {label}: {memoria[chave]}")
    if saude_partes:
        secoes.append("### Saúde\n" + "\n".join(saude_partes))

    # ── Seção 3: Agenda e compromissos ──
    agenda_chaves = {
        "ultima_consulta": "Última consulta",
        "proximo_compromisso": "Próximo compromisso",
    }
    agenda_partes = []
    for chave, label in agenda_chaves.items():
        if chave in memoria and memoria[chave]:
            agenda_partes.append(f"- {label}: {memoria[chave]}")
    if agenda_partes:
        secoes.append("### Agenda\n" + "\n".join(agenda_partes))

    # ── Seção 4: Demais memórias (chaves não categorizadas) ──
    chaves_categorizadas = set(saude_chaves) | set(agenda_chaves) | {
        "nome_cuidador", "pessoa_cuidada"
    }
    extras = {
        k: v for k, v in memoria.items()
        if k not in chaves_categorizadas and v
    }
    if extras:
        extras_partes = [
            f"- {k.replace('_', ' ').capitalize()}: {v}"
            for k, v in extras.items()
        ]
        secoes.append("### Outras informações\n" + "\n".join(extras_partes))

    if not secoes:
        return ""

    return "\n\n".join(secoes)
