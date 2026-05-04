from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.entities import Cuidador
from src.services.twilio_service import TwilioService


async def run_daily_checkins(session_factory: async_sessionmaker) -> None:
    twilio = TwilioService()
    mensagem = (
        "Bom dia! 💙 Passando para o check-in diário do CuidaFamília. "
        "Como a pessoa cuidada está hoje? Se quiser, posso registrar sintomas, rotina, medicações e lembretes."
    )

    async with session_factory() as db:
        caregivers = (await db.execute(select(Cuidador).where(Cuidador.ativo.is_(True)))).scalars().all()
        for caregiver in caregivers:
            try:
                await twilio.send_whatsapp_message(caregiver.telefone_whatsapp, mensagem)
            except Exception:
                # Evita que erro de um número interrompa o lote inteiro.
                continue
