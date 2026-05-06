"""
CuidaFamília — Definições das Tools para o LLM (OpenAI Function Calling format)

Estas definições são enviadas ao LLM para que ele possa decidir
autonomamente quando e como chamar cada ferramenta.

Padrão: OpenAI / OpenRouter tool_choice format.
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
                        "Classificação do evento: "
                        "'sintoma' para dores, desconfortos, mal-estar; "
                        "'medicao' para valores mensuráveis (pressão, glicose, temperatura); "
                        "'crise' para eventos agudos (queda, convulsão, falta de ar intensa); "
                        "'bem_estar' para relatos positivos; "
                        "'outro' para demais."
                    ),
                },
                "descricao": {
                    "type": "string",
                    "description": (
                        "Descrição clara do evento em linguagem natural. "
                        "Ex: 'Dor de cabeça intensa desde a manhã' ou "
                        "'Pressão arterial 15x10 medida às 9h'."
                    ),
                },
                "severidade": {
                    "type": "string",
                    "enum": ["normal", "atencao", "urgente"],
                    "description": (
                        "'normal' para eventos rotineiros; "
                        "'atencao' para repetição de sintomas ou piora gradual; "
                        "'urgente' para crises ou situações que exigem ação imediata."
                    ),
                },
                "dados_estruturados": {
                    "type": "object",
                    "description": (
                        "Dados numéricos ou estruturados quando disponíveis. "
                        "Ex: {\"pressao_sistolica\": 150, \"pressao_diastolica\": 100} ou "
                        "{\"temperatura\": 38.5, \"unidade\": \"C\"}. "
                        "Deixe vazio {} se não houver dados estruturados."
                    ),
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
            "Use quando o cuidador mencionar que quer ser lembrado de algo de forma recorrente, "
            "como tomar um medicamento, medir a pressão, ou fazer um acompanhamento diário. "
            "Também use proativamente ao perceber padrões: se um medicamento é mencionado "
            "com frequência, sugira criar um lembrete."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "tipo": {
                    "type": "string",
                    "enum": [
                        "bem_estar_diario",
                        "medicamento",
                        "medicao_pressao",
                        "medicao_glicose",
                        "hidratacao",
                        "consulta",
                        "outro",
                    ],
                    "description": "Categoria do check-in.",
                },
                "descricao": {
                    "type": "string",
                    "description": (
                        "Descrição específica do check-in. "
                        "Ex: 'Tomar Rivaroxabana 15mg' ou 'Medir pressão arterial'."
                    ),
                },
                "horario": {
                    "type": "string",
                    "description": (
                        "Horário do check-in no formato HH:MM (24h). "
                        "Ex: '08:00', '15:00', '21:30'."
                    ),
                },
                "dias_semana": {
                    "type": "string",
                    "description": (
                        "Recorrência: 'todos' para todos os dias; "
                        "'seg-sex' para dias úteis; "
                        "'sab-dom' para fins de semana. "
                        "Padrão: 'todos'."
                    ),
                    "enum": ["todos", "seg-sex", "sab-dom"],
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
            "Recupera eventos de saúde recentes registrados para a pessoa cuidada. "
            "Use quando o cuidador perguntar sobre o histórico ('o que aconteceu essa semana?', "
            "'quais sintomas ela teve?'), ou quando precisar de contexto histórico para "
            "responder com mais precisão. Também use para verificar se um sintoma atual "
            "é recorrente."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "janela_dias": {
                    "type": "integer",
                    "description": (
                        "Quantos dias para trás buscar. "
                        "Use 1 para 'hoje', 7 para 'essa semana', 30 para 'esse mês'. "
                        "Padrão: 7."
                    ),
                    "minimum": 1,
                    "maximum": 90,
                },
                "tipo_filtro": {
                    "type": "string",
                    "enum": ["todos", "sintoma", "medicao", "crise", "bem_estar"],
                    "description": (
                        "Filtrar por tipo específico de evento. "
                        "Use 'todos' para buscar todos os tipos."
                    ),
                },
            },
            "required": ["janela_dias"],
        },
    },
}

# ── Lista completa exportada ─────────────────────────────────────────────────
ALL_TOOLS = [LOG_EVENT, SCHEDULE_CHECKIN, GET_RECENT_EVENTS]
