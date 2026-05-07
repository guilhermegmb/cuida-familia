"""
CuidaFamília — Agente Principal (Cérebro) — Fase 3 / Semana 2

Arquitetura do fluxo de conversa com tools:

  Mensagem do usuário
        │
        ▼
  [LLM Principal] ──── tool_calls? ────► [Executor de Tools]
        │                                        │
    não (texto)                          resultado da tool
        │                                        │
        ▼                                        ▼
   Resposta final                    [LLM pós-tool] → Resposta final
        │
        ▼
  [Background] → extrair_entidades → salvar_memoria_lote
"""

import asyncio
import json
from src.services import supabase_service as db
from src.services import llm_service
from src.services.tools.definitions import ALL_TOOLS
from src.services.tools.executor import executar_tool
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

        cuidador = db.buscar_ou_criar_cuidador(telefone)
        cuidador_id = cuidador["id"]

        db.salvar_interacao(cuidador_id, "user", mensagem)

        if not cuidador.get("onboarding_completo"):
            resposta = await _fluxo_onboarding(cuidador, mensagem)
        else:
            resposta = await _fluxo_conversa(cuidador, mensagem)

        db.salvar_interacao(cuidador_id, "assistant", resposta)
        log_interacao(telefone, "assistant", resposta)

        return resposta

    except Exception as e:
        log_erro("processar_mensagem", {"erro": str(e)}, telefone)
        return PROMPT_FALLBACK_GERAL


async def _fluxo_onboarding(cuidador: dict, mensagem: str) -> str:
    """Gerencia o onboarding em etapas — inalterado da Semana 1."""
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
    Conversa pós-onboarding com tools, memória completa e extração em background.

    Fluxo:
      1. Carrega contexto completo (memória + histórico)
      2. Chama LLM com tools disponíveis
      3a. Se LLM retornar texto → resposta direta
      3b. Se LLM decidir usar tool → executa → chama LLM novamente → resposta final
      4. Background: extrai entidades e atualiza memória
    """
    cuidador_id = cuidador["id"]

    # Busca pessoa cuidada para passar às tools
    pessoa_cuidada = db.buscar_pessoa_cuidada(cuidador_id)
    pessoa_cuidada_id = pessoa_cuidada["id"] if pessoa_cuidada else None

    # Carrega histórico e memória completa
    historico = db.buscar_historico(cuidador_id, limite=20)
    memoria = db.buscar_memoria(cuidador_id)
    contexto_extra = _formatar_contexto_completo(memoria, cuidador)
    contexto_extra = _adicionar_plano_ao_contexto(contexto_extra, cuidador_id)

    # ── Chamada 1: LLM com tools disponíveis ──
    texto, tokens, tool_calls = await llm_service.chamar_llm(
        mensagem_usuario=mensagem,
        historico=historico[:-1],
        contexto_extra=contexto_extra,
        tools=ALL_TOOLS,
    )

    # ── Caminho A: LLM respondeu em texto diretamente ──
    if not tool_calls:
        asyncio.create_task(
            _extrair_e_salvar_entidades(cuidador_id, mensagem, memoria)
        )
        return texto or PROMPT_FALLBACK_GERAL

    # ── Caminho B: LLM decidiu usar tool(s) ──
    resposta_final = await _executar_tool_calls(
        tool_calls=tool_calls,
        cuidador_id=cuidador_id,
        pessoa_cuidada_id=pessoa_cuidada_id,
        mensagem_usuario=mensagem,
        historico=historico[:-1],
        contexto_extra=contexto_extra,
        texto_pre_tool=texto,
    )

    asyncio.create_task(
        _extrair_e_salvar_entidades(cuidador_id, mensagem, memoria)
    )

    return resposta_final


async def _executar_tool_calls(
    tool_calls: list[dict],
    cuidador_id: str,
    pessoa_cuidada_id: str | None,
    mensagem_usuario: str,
    historico: list[dict],
    contexto_extra: str,
    texto_pre_tool: str,
) -> str:
    """
    Executa cada tool_call decidida pelo LLM e monta a resposta final.

    Para múltiplas tools: executa em sequência e concatena resultados.
    Depois chama o LLM novamente com todos os resultados para gerar
    uma resposta coesa ao usuário.
    """
    from src.core.prompts import PROMPT_SISTEMA

    # Reconstrói o histórico de mensagens no formato OpenAI
    # para a segunda chamada ao LLM
    sistema = PROMPT_SISTEMA
    if contexto_extra:
        sistema += f"\n\n## Contexto atual do cuidador\n{contexto_extra}"

    mensagens_para_llm = [{"role": "system", "content": sistema}]
    for item in historico:
        role = "user" if item["papel"] == "user" else "assistant"
        mensagens_para_llm.append({"role": role, "content": item["mensagem"]})
    mensagens_para_llm.append({"role": "user", "content": mensagem_usuario})

    # Adiciona a decisão do LLM (assistant com tool_calls)
    mensagens_para_llm.append({
        "role": "assistant",
        "content": texto_pre_tool or None,
        "tool_calls": tool_calls,
    })

    resultados_tools = []

    for tc in tool_calls:
        tool_id = tc["id"]
        nome_tool = tc["function"]["name"]

        try:
            args_str = tc["function"].get("arguments", "{}")
            argumentos = json.loads(args_str)
        except (json.JSONDecodeError, KeyError) as e:
            log_erro("tool_args_invalidos", {"erro": str(e), "tool": nome_tool}, cuidador_id)
            argumentos = {}

        # Executa a tool
        resultado = await executar_tool(
            nome_tool=nome_tool,
            argumentos=argumentos,
            cuidador_id=cuidador_id,
            pessoa_cuidada_id=pessoa_cuidada_id,
        )

        resultado_texto = resultado.get("resultado", "Operação concluída.")
        resultados_tools.append((tool_id, nome_tool, resultado_texto))

        # Adiciona resultado da tool no histórico para o LLM
        mensagens_para_llm.append({
            "role": "tool",
            "tool_call_id": tool_id,
            "content": resultado_texto,
        })

        logger.info(f"Tool '{nome_tool}' → {resultado.get('sucesso')} | {cuidador_id[:8]}...")

    # ── Chamada 2: LLM gera resposta final com contexto das tools ──
    resposta_final, _ = await llm_service.chamar_llm_com_resultado_tool(
        mensagens_originais=mensagens_para_llm[:-len(resultados_tools)],
        tool_call_id=resultados_tools[-1][0],
        nome_tool=resultados_tools[-1][1],
        resultado_tool=resultados_tools[-1][2],
        tools=ALL_TOOLS,
    )

    return resposta_final or PROMPT_FALLBACK_GERAL


async def _extrair_e_salvar_entidades(cuidador_id: str, mensagem: str, contexto_atual: dict):
    """Extração silenciosa em background. Nunca impacta a conversa."""
    try:
        entidades = await llm_service.extrair_entidades(mensagem, contexto_atual)
        if entidades:
            db.salvar_memorias_lote(cuidador_id, entidades)
            logger.info(f"Memória atualizada: {list(entidades.keys())} → {cuidador_id[:8]}...")
    except Exception as e:
        log_erro("extracao_background_falhou", {"erro": str(e)}, cuidador_id)


def _formatar_contexto_completo(memoria: dict, cuidador: dict) -> str:
    """Formata toda a memória disponível em seções organizadas para o LLM."""
    secoes = []

    nome = cuidador.get("nome") or memoria.get("nome_cuidador")
    pessoa = memoria.get("pessoa_cuidada")
    if nome or pessoa:
        partes = []
        if nome:
            partes.append(f"Cuidador: {nome}")
        if pessoa:
            partes.append(f"Pessoa cuidada: {pessoa}")
        secoes.append("### Identificação\n" + "\n".join(f"- {p}" for p in partes))

    saude_chaves = {
        "medicamentos": "Medicamentos em uso",
        "condicoes_saude": "Condições de saúde",
        "alergias": "Alergias",
        "medico_responsavel": "Médico responsável",
    }
    saude_partes = [
        f"- {label}: {memoria[chave]}"
        for chave, label in saude_chaves.items()
        if memoria.get(chave)
    ]
    if saude_partes:
        secoes.append("### Saúde\n" + "\n".join(saude_partes))

    agenda_chaves = {
        "ultima_consulta": "Última consulta",
        "proximo_compromisso": "Próximo compromisso",
    }
    agenda_partes = [
        f"- {label}: {memoria[chave]}"
        for chave, label in agenda_chaves.items()
        if memoria.get(chave)
    ]
    if agenda_partes:
        secoes.append("### Agenda\n" + "\n".join(agenda_partes))

    chaves_categorizadas = set(saude_chaves) | set(agenda_chaves) | {
        "nome_cuidador", "pessoa_cuidada"
    }
    extras = {
        k: v for k, v in memoria.items()
        if k not in chaves_categorizadas and v
    }
    if extras:
        secoes.append(
            "### Outras informações\n" +
            "\n".join(f"- {k.replace('_', ' ').capitalize()}: {v}" for k, v in extras.items())
        )

    return "\n\n".join(secoes) if secoes else ""


# ── Injeção do Plano de Cuidado no contexto (Semana 3) ───────────────────────
# Patch aplicado ao _formatar_contexto_completo existente
# O import é feito aqui para evitar import circular
def _adicionar_plano_ao_contexto(contexto_base: str, cuidador_id: str) -> str:
    """Adiciona o plano de cuidado ao contexto se existir."""
    try:
        from src.services import plan_service
        plano = plan_service.buscar_plano_ativo(cuidador_id)
        if not plano:
            return contexto_base
        rotinas = plan_service.buscar_rotinas_ativas(cuidador_id)
        plano_str = plan_service.formatar_plano_para_llm(plano, rotinas)
        return f"{contexto_base}\n\n{plano_str}" if contexto_base else plano_str
    except Exception:
        return contexto_base
