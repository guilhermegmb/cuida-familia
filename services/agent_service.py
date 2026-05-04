from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Callable, Awaitable

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.enums import PapelInteracaoEnum
from src.services.alert_service import AlertService
from src.services.care_plan_service import CarePlanService
from src.services.memory_service import MemoryService
from src.services.openrouter_service import OpenRouterService
from src.services.reminder_service import ReminderService
from src.utils.constants import AGENT_PERSONALITY_PROMPT
from src.utils.helpers import parse_iso_datetime


class AgentService:
    def __init__(self) -> None:
        self.openrouter = OpenRouterService()
        self.memory = MemoryService()
        self.care_plans = CarePlanService()
        self.reminders = ReminderService()
        self.alerts = AlertService()

    async def process_incoming_message(self, db: AsyncSession, from_phone: str, message_text: str) -> str:
        caregiver = await self.care_plans.get_or_create_caregiver_by_phone(db, from_phone)
        person = await self.care_plans.get_primary_person(db, caregiver.id)

        await self.memory.save_interaction(
            db=db,
            cuidador_id=caregiver.id,
            pessoa_cuidada_id=person.id if person else None,
            papel_origem=PapelInteracaoEnum.cuidador,
            conteudo=message_text,
        )

        risk = self.alerts.analyze_text_for_risk(message_text)
        if risk and person:
            await self.alerts.create_alert(
                db=db,
                cuidador_id=caregiver.id,
                pessoa_cuidada_id=person.id,
                tipo=risk["tipo"],
                prioridade=risk["prioridade"],
                titulo=risk["titulo"],
                descricao=risk["descricao"],
                acao_recomendada="Se os sinais persistirem ou piorarem, procure atendimento de urgência imediatamente.",
            )

        history = await self.memory.fetch_recent_context(db, caregiver.id, limit=20)
        messages = [{"role": "system", "content": AGENT_PERSONALITY_PROMPT}]

        for interaction in history:
            role = "assistant" if interaction.papel_origem == PapelInteracaoEnum.agente else "user"
            messages.append({"role": role, "content": interaction.conteudo})

        if not history or history[-1].conteudo != message_text:
            messages.append({"role": "user", "content": message_text})

        tool_schemas = self._get_tool_schemas()

        final_response = "Desculpe, tive uma instabilidade agora. Pode tentar novamente em alguns instantes?"
        for _ in range(4):
            llm_payload = await self.openrouter.chat_completion(messages=messages, tools=tool_schemas)
            choice = llm_payload["choices"][0]["message"]
            assistant_content = choice.get("content") or ""
            tool_calls = choice.get("tool_calls") or []

            if tool_calls:
                messages.append({"role": "assistant", "content": assistant_content, "tool_calls": tool_calls})
                for call in tool_calls:
                    tool_name = call["function"]["name"]
                    raw_args = call["function"].get("arguments") or "{}"
                    args = json.loads(raw_args)
                    result = await self._execute_tool(
                        db=db,
                        tool_name=tool_name,
                        args=args,
                        caregiver_id=caregiver.id,
                        caregiver_phone=caregiver.telefone_whatsapp,
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call["id"],
                            "name": tool_name,
                            "content": json.dumps(result, ensure_ascii=False, default=str),
                        }
                    )
                continue

            final_response = assistant_content.strip() or final_response
            break

        await self.memory.save_interaction(
            db=db,
            cuidador_id=caregiver.id,
            pessoa_cuidada_id=person.id if person else None,
            papel_origem=PapelInteracaoEnum.agente,
            conteudo=final_response,
        )
        return final_response

    def _get_tool_schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_context",
                    "description": "Busca dados resumidos do cuidador, pessoa cuidada principal, alertas e lembretes.",
                    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "upsert_caregiver_profile",
                    "description": "Cria ou atualiza dados do cuidador principal.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "nome_completo": {"type": "string"},
                            "parentesco": {"type": "string"},
                            "email": {"type": "string"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "upsert_cared_person_profile",
                    "description": "Cria ou atualiza perfil da pessoa cuidada.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "nome_completo": {"type": "string"},
                            "grau_dependencia": {"type": "integer", "minimum": 1, "maximum": 5},
                            "condicoes_clinicas": {"type": "string"},
                        },
                        "required": ["nome_completo"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "create_medication_reminder",
                    "description": "Cria lembrete de medicação e cadastro de medicamento.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "nome_medicamento": {"type": "string"},
                            "dosagem": {"type": "string"},
                            "agendado_para": {"type": "string", "description": "ISO datetime"},
                            "mensagem": {"type": "string"},
                        },
                        "required": ["nome_medicamento", "dosagem", "agendado_para"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_medication_reminders",
                    "description": "Lista lembretes de medicação do cuidador.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "confirm_medication_taken",
                    "description": "Confirma que uma medicação foi tomada.",
                    "parameters": {
                        "type": "object",
                        "properties": {"reminder_id": {"type": "string"}},
                        "required": ["reminder_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "create_appointment",
                    "description": "Agenda consulta/exame e cria lembrete associado.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "agendada_para": {"type": "string", "description": "ISO datetime"},
                            "especialidade": {"type": "string"},
                            "profissional_saude": {"type": "string"},
                            "local_consulta": {"type": "string"},
                            "tipo": {"type": "string"},
                        },
                        "required": ["agendada_para"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_upcoming_appointments",
                    "description": "Lista consultas/exames futuros.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "create_care_plan",
                    "description": "Cria um plano de cuidado personalizado.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "titulo": {"type": "string"},
                            "objetivo_geral": {"type": "string"},
                            "detalhes": {"type": "string"},
                        },
                        "required": ["titulo", "objetivo_geral"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "register_health_event",
                    "description": "Registra um evento/sintoma de saúde.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "titulo": {"type": "string"},
                            "descricao": {"type": "string"},
                            "tipo": {"type": "string"},
                            "gravidade": {"type": "string"},
                        },
                        "required": ["titulo", "descricao"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "create_alert",
                    "description": "Cria um alerta manual de risco para a pessoa cuidada.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tipo": {"type": "string"},
                            "prioridade": {"type": "string"},
                            "titulo": {"type": "string"},
                            "descricao": {"type": "string"},
                            "acao_recomendada": {"type": "string"},
                        },
                        "required": ["tipo", "prioridade", "titulo", "descricao"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_active_alerts",
                    "description": "Lista alertas ativos (novo/em_analise).",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
        ]

    async def _execute_tool(
        self,
        db: AsyncSession,
        tool_name: str,
        args: dict[str, Any],
        caregiver_id: uuid.UUID,
        caregiver_phone: str,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        person = await self.care_plans.get_primary_person(db, caregiver_id)

        tools: dict[str, Callable[[], Awaitable[Any]]] = {
            "get_context": lambda: self._tool_get_context(db, caregiver_id),
            "upsert_caregiver_profile": lambda: self.care_plans.upsert_caregiver_profile(
                db=db,
                telefone_whatsapp=caregiver_phone,
                nome_completo=args.get("nome_completo"),
                parentesco=args.get("parentesco"),
                email=args.get("email"),
            ),
            "upsert_cared_person_profile": lambda: self.care_plans.upsert_cared_person(
                db=db,
                cuidador_id=caregiver_id,
                nome_completo=args["nome_completo"],
                grau_dependencia=args.get("grau_dependencia", 3),
                condicoes_clinicas=args.get("condicoes_clinicas"),
            ),
            "list_medication_reminders": lambda: self.reminders.list_medication_reminders(db, caregiver_id),
            "confirm_medication_taken": lambda: self.reminders.confirm_medication_taken(
                db, uuid.UUID(args["reminder_id"])
            ),
            "list_upcoming_appointments": lambda: self.reminders.list_upcoming_appointments(db, caregiver_id),
            "list_active_alerts": lambda: self.alerts.list_active_alerts(db, caregiver_id),
        }

        if person:
            tools.update(
                {
                    "create_medication_reminder": lambda: self.reminders.create_medication_reminder(
                        db=db,
                        cuidador_id=caregiver_id,
                        pessoa_cuidada_id=person.id,
                        nome_medicamento=args["nome_medicamento"],
                        dosagem=args["dosagem"],
                        agendado_para=parse_iso_datetime(args["agendado_para"]),
                        mensagem=args.get("mensagem"),
                    ),
                    "create_appointment": lambda: self.reminders.create_appointment(
                        db=db,
                        cuidador_id=caregiver_id,
                        pessoa_cuidada_id=person.id,
                        agendada_para=parse_iso_datetime(args["agendada_para"]),
                        especialidade=args.get("especialidade"),
                        profissional_saude=args.get("profissional_saude"),
                        local_consulta=args.get("local_consulta"),
                    ),
                    "create_care_plan": lambda: self.care_plans.create_care_plan(
                        db=db,
                        cuidador_id=caregiver_id,
                        pessoa_cuidada_id=person.id,
                        titulo=args["titulo"],
                        objetivo_geral=args["objetivo_geral"],
                        detalhes=args.get("detalhes"),
                    ),
                    "register_health_event": lambda: self.alerts.register_health_event(
                        db=db,
                        pessoa_cuidada_id=person.id,
                        cuidador_id=caregiver_id,
                        titulo=args["titulo"],
                        descricao=args["descricao"],
                    ),
                    "create_alert": lambda: self.alerts.create_alert(
                        db=db,
                        cuidador_id=caregiver_id,
                        pessoa_cuidada_id=person.id,
                        tipo=args["tipo"],
                        prioridade=args["prioridade"],
                        titulo=args["titulo"],
                        descricao=args["descricao"],
                        acao_recomendada=args.get("acao_recomendada"),
                    ),
                }
            )

        tool_callable = tools.get(tool_name)
        if tool_callable is None:
            return {"ok": False, "erro": f"Ferramenta não suportada: {tool_name}"}

        try:
            result = await tool_callable()
            return result
        except Exception as exc:
            return {"ok": False, "erro": f"Falha ao executar tool {tool_name}", "detalhes": str(exc)}

    async def _tool_get_context(self, db: AsyncSession, caregiver_id: uuid.UUID) -> dict[str, Any]:
        person = await self.care_plans.get_primary_person(db, caregiver_id)
        reminders = await self.reminders.list_medication_reminders(db, caregiver_id, limit=5)
        alerts = await self.alerts.list_active_alerts(db, caregiver_id, limit=5)
        return {
            "cuidador_id": str(caregiver_id),
            "pessoa_cuidada": (
                {
                    "id": str(person.id),
                    "nome": person.nome_completo,
                    "grau_dependencia": person.grau_dependencia,
                    "condicoes_clinicas": person.condicoes_clinicas,
                }
                if person
                else None
            ),
            "lembretes": reminders,
            "alertas": alerts,
            "timestamp": datetime.utcnow().isoformat(),
        }
