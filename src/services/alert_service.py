from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.entities import Alerta, EventoSaude
from src.models.enums import GravidadeEnum, PrioridadeAlertaEnum, StatusAlertaEnum, TipoAlertaEnum, TipoEventoSaudeEnum
from src.utils.constants import EMERGENCY_KEYWORDS


class AlertService:
    def analyze_text_for_risk(self, text: str) -> dict[str, Any] | None:
        lowered = text.lower()
        matched = [k for k in EMERGENCY_KEYWORDS if k in lowered]
        if not matched:
            return None
        prioridade = PrioridadeAlertaEnum.alta
        tipo = TipoAlertaEnum.risco_saude
        if any(k in lowered for k in ["não acorda", "sem resposta", "convuls", "sangramento"]):
            prioridade = PrioridadeAlertaEnum.critica
            tipo = TipoAlertaEnum.emergencia
        return {
            "tipo": tipo,
            "prioridade": prioridade,
            "titulo": "Possível risco de saúde detectado",
            "descricao": f"Sinais detectados na mensagem: {', '.join(matched)}",
        }

    async def create_alert(
        self,
        db: AsyncSession,
        cuidador_id: uuid.UUID,
        pessoa_cuidada_id: uuid.UUID,
        tipo: TipoAlertaEnum | str,
        prioridade: PrioridadeAlertaEnum | str,
        titulo: str,
        descricao: str,
        acao_recomendada: str | None = None,
        evento_saude_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        if isinstance(tipo, str):
            tipo = TipoAlertaEnum(tipo)
        if isinstance(prioridade, str):
            prioridade = PrioridadeAlertaEnum(prioridade)

        alert = Alerta(
            cuidador_id=cuidador_id,
            pessoa_cuidada_id=pessoa_cuidada_id,
            evento_saude_id=evento_saude_id,
            tipo=tipo,
            prioridade=prioridade,
            status=StatusAlertaEnum.novo,
            titulo=titulo,
            descricao=descricao,
            acao_recomendada=acao_recomendada,
            detectado_em=datetime.now(timezone.utc),
            gerado_por_ia=True,
        )
        db.add(alert)
        await db.commit()
        await db.refresh(alert)
        return {
            "id": str(alert.id),
            "tipo": alert.tipo.value,
            "prioridade": alert.prioridade.value,
            "status": alert.status.value,
            "titulo": alert.titulo,
        }

    async def register_health_event(
        self,
        db: AsyncSession,
        pessoa_cuidada_id: uuid.UUID,
        cuidador_id: uuid.UUID,
        titulo: str,
        descricao: str,
        tipo: TipoEventoSaudeEnum = TipoEventoSaudeEnum.sintoma,
        gravidade: GravidadeEnum = GravidadeEnum.baixa,
    ) -> dict[str, Any]:
        event = EventoSaude(
            pessoa_cuidada_id=pessoa_cuidada_id,
            cuidador_id=cuidador_id,
            tipo=tipo,
            gravidade=gravidade,
            titulo=titulo,
            descricao=descricao,
            ocorreu_em=datetime.now(timezone.utc),
            requer_atencao_imediata=gravidade in {GravidadeEnum.alta, GravidadeEnum.critica},
        )
        db.add(event)
        await db.commit()
        await db.refresh(event)
        return {
            "id": str(event.id),
            "tipo": event.tipo.value,
            "gravidade": event.gravidade.value,
            "titulo": event.titulo,
            "requer_atencao_imediata": event.requer_atencao_imediata,
        }

    async def list_active_alerts(self, db: AsyncSession, cuidador_id: uuid.UUID, limit: int = 10) -> list[dict[str, Any]]:
        stmt = (
            select(Alerta)
            .where(Alerta.cuidador_id == cuidador_id, Alerta.status.in_([StatusAlertaEnum.novo, StatusAlertaEnum.em_analise]))
            .order_by(Alerta.detectado_em.desc())
            .limit(limit)
        )
        alerts = (await db.execute(stmt)).scalars().all()
        return [
            {
                "id": str(a.id),
                "tipo": a.tipo.value,
                "prioridade": a.prioridade.value,
                "status": a.status.value,
                "titulo": a.titulo,
                "descricao": a.descricao,
            }
            for a in alerts
        ]
