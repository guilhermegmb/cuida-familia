from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Select, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.entities import Interacao
from src.models.enums import CanalInteracaoEnum, PapelInteracaoEnum, TipoInteracaoEnum


class MemoryService:
    async def save_interaction(
        self,
        db: AsyncSession,
        cuidador_id: uuid.UUID,
        papel_origem: PapelInteracaoEnum,
        conteudo: str,
        pessoa_cuidada_id: uuid.UUID | None = None,
        contexto_json: dict[str, Any] | None = None,
    ) -> Interacao:
        interaction = Interacao(
            cuidador_id=cuidador_id,
            pessoa_cuidada_id=pessoa_cuidada_id,
            tipo=TipoInteracaoEnum.mensagem,
            papel_origem=papel_origem,
            canal=CanalInteracaoEnum.whatsapp,
            conteudo=conteudo,
            contexto_json=contexto_json or {},
        )
        db.add(interaction)
        await db.commit()
        await db.refresh(interaction)
        return interaction

    async def fetch_recent_context(self, db: AsyncSession, cuidador_id: uuid.UUID, limit: int = 20) -> list[Interacao]:
        stmt: Select[tuple[Interacao]] = (
            select(Interacao)
            .where(Interacao.cuidador_id == cuidador_id)
            .order_by(desc(Interacao.ocorreu_em))
            .limit(limit)
        )
        rows = (await db.execute(stmt)).scalars().all()
        return list(reversed(rows))
