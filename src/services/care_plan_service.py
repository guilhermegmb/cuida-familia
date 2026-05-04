from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.entities import Cuidador, PessoaCuidada, PlanoCuidado
from src.models.enums import ParentescoEnum, StatusPlanoEnum


class CarePlanService:
    async def get_or_create_caregiver_by_phone(self, db: AsyncSession, telefone_whatsapp: str) -> Cuidador:
        stmt = select(Cuidador).where(Cuidador.telefone_whatsapp == telefone_whatsapp)
        caregiver = (await db.execute(stmt)).scalar_one_or_none()
        if caregiver:
            return caregiver

        caregiver = Cuidador(
            nome_completo=f"Cuidador {telefone_whatsapp[-4:]}",
            telefone_whatsapp=telefone_whatsapp,
            parentesco=ParentescoEnum.outro,
            idioma_preferido="pt-BR",
            fuso_horario="America/Sao_Paulo",
        )
        db.add(caregiver)
        await db.commit()
        await db.refresh(caregiver)
        return caregiver

    async def upsert_caregiver_profile(
        self,
        db: AsyncSession,
        telefone_whatsapp: str,
        nome_completo: str | None = None,
        parentesco: str | None = None,
        email: str | None = None,
    ) -> dict[str, Any]:
        caregiver = await self.get_or_create_caregiver_by_phone(db, telefone_whatsapp)
        if nome_completo:
            caregiver.nome_completo = nome_completo
        if parentesco:
            caregiver.parentesco = ParentescoEnum(parentesco)
        if email:
            caregiver.email = email
        await db.commit()
        return {
            "id": str(caregiver.id),
            "nome_completo": caregiver.nome_completo,
            "telefone_whatsapp": caregiver.telefone_whatsapp,
            "email": caregiver.email,
            "parentesco": caregiver.parentesco.value,
        }

    async def upsert_cared_person(
        self,
        db: AsyncSession,
        cuidador_id: uuid.UUID,
        nome_completo: str,
        grau_dependencia: int = 3,
        condicoes_clinicas: str | None = None,
    ) -> dict[str, Any]:
        stmt = select(PessoaCuidada).where(
            PessoaCuidada.cuidador_id == cuidador_id,
            func.lower(PessoaCuidada.nome_completo) == nome_completo.lower(),
        )
        person = (await db.execute(stmt)).scalar_one_or_none()
        if person is None:
            person = PessoaCuidada(
                cuidador_id=cuidador_id,
                nome_completo=nome_completo,
                grau_dependencia=grau_dependencia,
                condicoes_clinicas=condicoes_clinicas,
            )
            db.add(person)
        else:
            person.grau_dependencia = grau_dependencia
            if condicoes_clinicas:
                person.condicoes_clinicas = condicoes_clinicas
        await db.commit()
        await db.refresh(person)
        return {
            "id": str(person.id),
            "nome_completo": person.nome_completo,
            "grau_dependencia": person.grau_dependencia,
            "condicoes_clinicas": person.condicoes_clinicas,
        }

    async def get_primary_person(self, db: AsyncSession, cuidador_id: uuid.UUID) -> PessoaCuidada | None:
        stmt = (
            select(PessoaCuidada)
            .where(PessoaCuidada.cuidador_id == cuidador_id, PessoaCuidada.ativo.is_(True))
            .order_by(PessoaCuidada.created_at.asc())
            .limit(1)
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    async def create_care_plan(
        self,
        db: AsyncSession,
        cuidador_id: uuid.UUID,
        pessoa_cuidada_id: uuid.UUID,
        titulo: str,
        objetivo_geral: str,
        detalhes: str | None = None,
        inicio_em: date | None = None,
    ) -> dict[str, Any]:
        versao_stmt = select(func.coalesce(func.max(PlanoCuidado.versao), 0)).where(
            PlanoCuidado.pessoa_cuidada_id == pessoa_cuidada_id
        )
        current_version = (await db.execute(versao_stmt)).scalar_one()
        plan = PlanoCuidado(
            pessoa_cuidada_id=pessoa_cuidada_id,
            cuidador_id=cuidador_id,
            titulo=titulo,
            objetivo_geral=objetivo_geral,
            detalhes=detalhes,
            status=StatusPlanoEnum.ativo,
            inicio_em=inicio_em or date.today(),
            versao=current_version + 1,
            gerado_por_ia=True,
        )
        db.add(plan)
        await db.commit()
        await db.refresh(plan)
        return {
            "id": str(plan.id),
            "titulo": plan.titulo,
            "objetivo_geral": plan.objetivo_geral,
            "versao": plan.versao,
            "status": plan.status.value,
        }
