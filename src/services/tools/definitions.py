"""
CuidaFamília — Definições das Tools para o LLM (OpenAI Function Calling format)

Semana 1+2: log_event, schedule_checkin, get_recent_events
Semana 3:   create_care_plan, get_care_plan, update_care_plan, update_routine
"""

# ── Tool 1: log_event ────────────────────────────────────────────────────────
LOG_EVENT = {
    "type": "function",
    "function": {
        "name": "log_event",
        "description": (
            "Registra um evento de saúde no histórico da pessoa cuidada. "
            "Use quando o cuidador relatar sintomas, medições (pressão, glicose, temperatura), "
            "crises, quedas, mal-estar, ou qualquer ocorrência de saúde relevante. "
            "Sempre registre mesmo que o evento pareça leve — o histórico é valioso."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "tipo": {
                    "type": "string",
                    "enum": ["sintoma", "medicao", "crise", "bem_estar", "outro"],
                    "description": (
                        "'sintoma' para dores, desconfortos, mal-estar; "
                        "'medicao' para valores mensuráveis; "
                        "'crise' para eventos agudos; "
                        "'bem_estar' para relatos positivos; "
                        "'outro' para demais."
                    ),
                },
                "descricao": {
                    "type": "string",
                    "description": "Descrição clara do evento em linguagem natural.",
                },
                "severidade": {
                    "type": "string",
                    "enum": ["normal", "atencao", "urgente"],
                    "description": (
                        "'normal' para eventos rotineiros; "
                        "'atencao' para repetição ou piora gradual; "
                        "'urgente' para crises que exigem ação imediata."
                    ),
                },
                "dados_estruturados": {
                    "type": "object",
                    "description": "Dados numéricos quando disponíveis. Ex: {\"pressao_sistolica\": 150}.",
                },
            },
            "required": ["tipo", "descricao", "severidade"],
        },
    },
}

# ── Tool 2: schedule_checkin ─────────────────────────────────────────────────
SCHEDULE_CHECKIN = {
    "type": "function",
    "function": {
        "name": "schedule_checkin",
        "description": (
            "Cria uma rotina de check-in automático para o cuidador. "
            "Use quando o cuidador pedir para ser lembrado de algo recorrente. "
            "IMPORTANTE: se o horário informado já passou hoje, informe que o primeiro "
            "disparo será amanhã e confirme antes de criar."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "tipo": {
                    "type": "string",
                    "enum": ["bem_estar_diario", "medicamento", "medicao_pressao",
                             "medicao_glicose", "hidratacao", "consulta", "outro"],
                    "description": "Categoria do check-in.",
                },
                "descricao": {
                    "type": "string",
                    "description": "Descrição específica. Ex: 'Tomar Rivaroxabana 15mg'.",
                },
                "horario": {
                    "type": "string",
                    "description": "Horário no formato HH:MM (24h). Ex: '08:00', '15:00'.",
                },
                "dias_semana": {
                    "type": "string",
                    "enum": ["todos", "seg-sex", "sab-dom"],
                    "description": "Recorrência. Padrão: 'todos'.",
                },
            },
            "required": ["tipo", "descricao", "horario"],
        },
    },
}

# ── Tool 3: get_recent_events ────────────────────────────────────────────────
GET_RECENT_EVENTS = {
    "type": "function",
    "function": {
        "name": "get_recent_events",
        "description": (
            "Recupera eventos de saúde recentes. Use quando o cuidador perguntar sobre "
            "o histórico ou quando precisar verificar se um sintoma é recorrente."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "janela_dias": {
                    "type": "integer",
                    "description": "Dias para trás. 1=hoje, 7=semana, 30=mês.",
                    "minimum": 1,
                    "maximum": 90,
                },
                "tipo_filtro": {
                    "type": "string",
                    "enum": ["todos", "sintoma", "medicao", "crise", "bem_estar"],
                    "description": "Filtrar por tipo. Use 'todos' para todos.",
                },
            },
            "required": ["janela_dias"],
        },
    },
}

# ── Tool 4: create_care_plan ─────────────────────────────────────────────────
CREATE_CARE_PLAN = {
    "type": "function",
    "function": {
        "name": "create_care_plan",
        "description": (
            "Cria o Plano de Cuidado Personalizado da pessoa cuidada. "
            "Use quando: (1) o cuidador acabou de completar o onboarding, "
            "(2) o cuidador pedir para criar ou ver um plano de cuidado, "
            "(3) você perceber que o cuidador tem informações suficientes mas ainda não tem plano. "
            "O plano organiza objetivos, rotinas recomendadas e alertas relevantes. "
            "Sempre apresente o plano ao cuidador após criá-lo."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "objetivo_primario": {
                    "type": "string",
                    "description": (
                        "Objetivo principal do cuidado, baseado nas condições de saúde conhecidas. "
                        "Ex: 'Controlar pressão arterial e prevenir eventos cardiovasculares'."
                    ),
                },
                "objetivos_secundarios": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Lista de 2 a 4 objetivos secundários. "
                        "Ex: ['Monitorar humor e qualidade do sono', 'Garantir hidratação adequada']."
                    ),
                },
                "rotinas_recomendadas": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "tipo": {"type": "string"},
                            "descricao": {"type": "string"},
                            "horario_sugerido": {"type": "string"},
                            "dias_semana": {"type": "string"},
                            "prioridade": {
                                "type": "string",
                                "enum": ["alta", "media", "baixa"],
                            },
                        },
                        "required": ["tipo", "descricao", "horario_sugerido", "prioridade"],
                    },
                    "description": (
                        "Lista de 3 a 5 rotinas recomendadas para o plano. "
                        "Inclua apenas rotinas que ainda não existem. "
                        "Ex: [{\"tipo\": \"medicao_pressao\", \"descricao\": \"Medir pressão arterial\", "
                        "\"horario_sugerido\": \"09:00\", \"prioridade\": \"alta\"}]."
                    ),
                },
                "alertas_relevantes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Alertas contextuais baseados nas condições de saúde. "
                        "Ex: ['Anticoagulante em uso — atenção a quedas e hematomas', "
                        "'Antidepressivo — observar humor e sono']."
                    ),
                },
            },
            "required": ["objetivo_primario", "objetivos_secundarios", "rotinas_recomendadas"],
        },
    },
}

# ── Tool 5: get_care_plan ────────────────────────────────────────────────────
GET_CARE_PLAN = {
    "type": "function",
    "function": {
        "name": "get_care_plan",
        "description": (
            "Recupera o Plano de Cuidado atual da pessoa cuidada. "
            "Use quando: o cuidador perguntar sobre o plano, pedir um resumo do cuidado, "
            "antes de sugerir adaptações, ou quando precisar de contexto do plano para responder."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "incluir_rotinas": {
                    "type": "boolean",
                    "description": "Se true, inclui as rotinas ativas associadas ao plano. Padrão: true.",
                },
            },
            "required": [],
        },
    },
}

# ── Tool 6: update_care_plan ─────────────────────────────────────────────────
UPDATE_CARE_PLAN = {
    "type": "function",
    "function": {
        "name": "update_care_plan",
        "description": (
            "Atualiza o Plano de Cuidado existente. "
            "Use quando o cuidador informar novas condições de saúde, novos medicamentos, "
            "mudanças nos objetivos, ou quando sugerir adaptações aceitas pelo cuidador. "
            "Registra o motivo da adaptação para rastreabilidade."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "campo": {
                    "type": "string",
                    "enum": [
                        "objetivo_primario",
                        "objetivos_secundarios",
                        "rotinas_recomendadas",
                        "alertas_relevantes",
                    ],
                    "description": "Qual campo do plano será atualizado.",
                },
                "novo_valor": {
                    "description": "Novo valor para o campo. Tipo varia conforme o campo.",
                },
                "motivo": {
                    "type": "string",
                    "description": (
                        "Motivo da adaptação, para rastreabilidade. "
                        "Ex: 'Nova condição informada: diabetes tipo 2' ou "
                        "'Cuidador relatou dificuldade com horário das 09h'."
                    ),
                },
            },
            "required": ["campo", "novo_valor", "motivo"],
        },
    },
}

# ── Tool 7: update_routine ───────────────────────────────────────────────────
UPDATE_ROUTINE = {
    "type": "function",
    "function": {
        "name": "update_routine",
        "description": (
            "Atualiza ou desativa uma rotina existente. "
            "Use quando o cuidador pedir para mudar horário de um lembrete, "
            "pausar ou desativar uma rotina, ou quando uma adaptação do plano "
            "exigir ajuste de rotina existente."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "descricao_rotina": {
                    "type": "string",
                    "description": (
                        "Descrição ou parte do nome da rotina a ser atualizada. "
                        "Ex: 'Rivaroxabana', 'pressão', 'Sertralina'. "
                        "Usado para localizar a rotina correta."
                    ),
                },
                "novo_horario": {
                    "type": "string",
                    "description": "Novo horário no formato HH:MM. Deixe vazio se não mudar.",
                },
                "nova_descricao": {
                    "type": "string",
                    "description": "Nova descrição. Deixe vazio se não mudar.",
                },
                "ativa": {
                    "type": "boolean",
                    "description": "false para desativar a rotina. Omita se não mudar.",
                },
                "motivo": {
                    "type": "string",
                    "description": "Motivo da alteração. Ex: 'Cuidador pediu mudança para 21h'.",
                },
            },
            "required": ["descricao_rotina"],
        },
    },
}

# ── Lista completa exportada ─────────────────────────────────────────────────
ALL_TOOLS = [
    LOG_EVENT,
    SCHEDULE_CHECKIN,
    GET_RECENT_EVENTS,
    CREATE_CARE_PLAN,
    GET_CARE_PLAN,
    UPDATE_CARE_PLAN,
    UPDATE_ROUTINE,
]
