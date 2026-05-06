from fastapi import FastAPI
from fastapi.responses import JSONResponse
from src.api.webhook import router as webhook_router
from src.services.scheduler import iniciar_scheduler, parar_scheduler
from src.utils.logger import get_logger
import os

logger = get_logger("main")

if os.path.exists(".env"):
    from dotenv import load_dotenv
    load_dotenv()

app = FastAPI(
    title="CuidaFamília",
    description="Agente de IA Concierge de Cuidado — API Backend",
    version="0.2.0",
    docs_url="/docs" if os.getenv("APP_ENV") != "production" else None,
)

app.include_router(webhook_router)


@app.get("/health")
async def health_check():
    return JSONResponse({
        "status": "ok",
        "servico": "CuidaFamília",
        "versao": "0.2.0",
        "ambiente": os.getenv("APP_ENV", "development"),
    })


@app.get("/")
async def root():
    return JSONResponse({
        "mensagem": "CuidaFamília API está rodando 💙",
        "versao": "0.2.0",
        "docs": "/docs",
        "health": "/health",
    })


@app.on_event("startup")
async def startup():
    logger.info("🚀 CuidaFamília v0.2.0 iniciando...")
    logger.info(f"   Ambiente: {os.getenv('APP_ENV', 'development')}")
    logger.info("   Endpoints: POST /webhook/whatsapp | GET /health")
    iniciar_scheduler()


@app.on_event("shutdown")
async def shutdown():
    logger.info("🛑 CuidaFamília encerrando...")
    parar_scheduler()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
