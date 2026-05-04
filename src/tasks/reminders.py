from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.entities import Cuidador, Lembrete
from src.services.reminder_service import ReminderService
from src.services.twilio_service import TwilioService


async def dispatch_due_reminders(session_factory: async_sessionmaker) -> None:
    reminder_service = ReminderService()
    twilio = TwilioService()

    async with session_factory() as db:
        due_reminders = await reminder_service.fetch_due_reminders(db)
        for reminder in due_reminders:
            caregiver = await db.get(Cuidador, reminder.cuidador_id)
            if caregiver is None:
                continue
            try:
                await twilio.send_whatsapp_message(caregiver.telefone_whatsapp, reminder.mensagem)
                await reminder_service.mark_reminder_sent(db, reminder)
            except Exception:
                reminder.tentativas_envio += 1
                await db.commit()
