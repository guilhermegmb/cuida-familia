from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.entities import Consulta, Lembrete, Medicamento
from src.models.enums import (
    StatusConsultaEnum,
    StatusLembreteEnum,
    StatusMedicamentoEnum,
    TipoConsultaEnum,
    TipoLembreteEnum,
    ViaAdministracaoEnum,
    ViaAgendamentoEnum,
)


class ReminderService:
    async def create_medication_reminder(
        self,
        db: AsyncSession,
        cuidador_id: uuid.UUID,
        pessoa_cuidada_id: uuid.UUID,
        nome_medicamento: str,
        dosagem: str,
        agendado_para: datetime,
        mensagem: str | None = None,
    ) -> dict[str, Any]:
        medication = Medicamento(
            pessoa_cuidada_id=pessoa_cuidada_id,
            nome=nome_medicamento,
            dosagem=dosagem,
            via_administracao=ViaAdministracaoEnum.oral,
            inicio_em=agendado_para.date(),
            status=StatusMedicamentoEnum.ativo,
        )
        db.add(medication)
        await db.flush()

        reminder = Lembrete(
            pessoa_cuidada_id=pessoa_cuidada_id,
            cuidador_id=cuidador_id,
            medicamento_id=medication.id,
            tipo=TipoLembreteEnum.medicamento,
            status=StatusLembreteEnum.agendado,
            titulo=f"Tomar {nome_medicamento}",
            mensagem=mensagem or f"Hora de administrar {nome_medicamento} ({dosagem}).",
            agendado_para=agendado_para,
            canais=["whatsapp"],
        )
        db.add(reminder)
        await db.commit()
        await db.refresh(reminder)
        return {
            "id": str(reminder.id),
            "titulo": reminder.titulo,
            "agendado_para": reminder.agendado_para.isoformat(),
            "status": reminder.status.value,
        }

    async def list_medication_reminders(self, db: AsyncSession, cuidador_id: uuid.UUID, limit: int = 10) -> list[dict[str, Any]]:
        stmt = (
            select(Lembrete)
            .where(Lembrete.cuidador_id == cuidador_id, Lembrete.tipo == TipoLembreteEnum.medicamento)
            .order_by(Lembrete.agendado_para.asc())
            .limit(limit)
        )
        reminders = (await db.execute(stmt)).scalars().all()
        return [
            {
                "id": str(r.id),
                "titulo": r.titulo,
                "mensagem": r.mensagem,
                "status": r.status.value,
                "agendado_para": r.agendado_para.isoformat(),
            }
            for r in reminders
        ]

    async def confirm_medication_taken(self, db: AsyncSession, reminder_id: uuid.UUID) -> dict[str, Any]:
        reminder = await db.get(Lembrete, reminder_id)
        if not reminder:
            return {"ok": False, "erro": "Lembrete não encontrado."}
        reminder.status = StatusLembreteEnum.confirmado
        reminder.confirmado_em = datetime.now(timezone.utc)
        await db.commit()
        return {"ok": True, "id": str(reminder.id), "status": reminder.status.value}

    async def create_appointment(
        self,
        db: AsyncSession,
        cuidador_id: uuid.UUID,
        pessoa_cuidada_id: uuid.UUID,
        agendada_para: datetime,
        especialidade: str | None = None,
        profissional_saude: str | None = None,
        local_consulta: str | None = None,
        tipo: TipoConsultaEnum = TipoConsultaEnum.presencial,
    ) -> dict[str, Any]:
        consulta = Consulta(
            cuidador_id=cuidador_id,
            pessoa_cuidada_id=pessoa_cuidada_id,
            tipo=tipo,
            status=StatusConsultaEnum.agendada,
            especialidade=especialidade,
            profissional_saude=profissional_saude,
            local_consulta=local_consulta,
            agendada_para=agendada_para,
            via_agendamento=ViaAgendamentoEnum.agente_ia,
        )
        db.add(consulta)
        await db.flush()

        lembrete = Lembrete(
            pessoa_cuidada_id=pessoa_cuidada_id,
            cuidador_id=cuidador_id,
            consulta_id=consulta.id,
            tipo=TipoLembreteEnum.consulta,
            titulo=f"Consulta: {especialidade or 'acompanhamento'}",
            mensagem=f"Lembrete de consulta em {agendada_para.strftime('%d/%m/%Y %H:%M')}",
            agendado_para=agendada_para,
        )
        db.add(lembrete)
        await db.commit()
        await db.refresh(consulta)
        return {
            "id": str(consulta.id),
            "status": consulta.status.value,
            "agendada_para": consulta.agendada_para.isoformat(),
            "especialidade": consulta.especialidade,
        }

    async def list_upcoming_appointments(self, db: AsyncSession, cuidador_id: uuid.UUID, limit: int = 10) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        stmt = (
            select(Consulta)
            .where(and_(Consulta.cuidador_id == cuidador_id, Consulta.agendada_para >= now))
            .order_by(Consulta.agendada_para.asc())
            .limit(limit)
        )
        consultas = (await db.execute(stmt)).scalars().all()
        return [
            {
                "id": str(c.id),
                "tipo": c.tipo.value,
                "status": c.status.value,
                "especialidade": c.especialidade,
                "agendada_para": c.agendada_para.isoformat(),
            }
            for c in consultas
        ]

    async def fetch_due_reminders(self, db: AsyncSession) -> list[Lembrete]:
        now = datetime.now(timezone.utc)
        stmt = select(Lembrete).where(
            Lembrete.status == StatusLembreteEnum.agendado,
            Lembrete.agendado_para <= now,
            Lembrete.tentativas_envio < 3,
        )
        return list((await db.execute(stmt)).scalars().all())

    async def mark_reminder_sent(self, db: AsyncSession, reminder: Lembrete) -> None:
        reminder.status = StatusLembreteEnum.enviado
        reminder.enviado_em = datetime.now(timezone.utc)
        reminder.tentativas_envio += 1
        await db.commit()
