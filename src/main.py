from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI

from src.config.settings import get_settings
from src.database.session import get_session_factory, init_db
from src.routes.health import router as health_router
from src.routes.webhook import router as webhook_router
from src.tasks.checkins import run_daily_checkins
from src.tasks.reminders import dispatch_due_reminders

settings = get_settings()
scheduler = AsyncIOScheduler(timezone=settings.timezone)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    session_factory = get_session_factory()
    scheduler.add_job(
        run_daily_checkins,
        trigger=CronTrigger.from_crontab(settings.checkin_cron, timezone=settings.timezone),
        kwargs={"session_factory": session_factory},
        id="daily_checkins",
        replace_existing=True,
    )
    scheduler.add_job(
        dispatch_due_reminders,
        trigger=CronTrigger.from_crontab(settings.reminders_cron, timezone=settings.timezone),
        kwargs={"session_factory": session_factory},
        id="due_reminders",
        replace_existing=True,
    )
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Backend do Agente CuidaFamília com integração Twilio + OpenRouter + PostgreSQL.",
    lifespan=lifespan,
)

app.include_router(health_router)
@router.get("/health")
async def health():
    return {"status": "ok"}

app.include_router(webhook_router)
