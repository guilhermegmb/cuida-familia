from fastapi import FastAPI
from fastapi.responses import JSONResponse
from src.api.webhook import router as webhook_router
from src.utils.logger import get_logger
import os

logger = get_logger("main")

# ── Carrega .env em desenvolvimento ──
if os.path.exists(".env"):
    from dotenv import load_dotenv
    load_dotenv()

app = FastAPI(
    title="CuidaFamília",
    description="Agente de IA Concierge de Cuidado — API Backend",
    version="0.1.0",
    docs_url="/docs" if os.getenv("APP_ENV") != "production" else None,
)

# ── Routers ──
app.include_router(webhook_router)


# ── Health Check ──
@app.get("/health")
async def health_check():
    return JSONResponse({
        "status": "ok",
        "servico": "CuidaFamília",
        "versao": "0.1.0",
        "ambiente": os.getenv("APP_ENV", "development"),
    })


# ── Root ──
@app.get("/")
async def root():
    return JSONResponse({
        "mensagem": "CuidaFamília API está rodando 💙",
        "docs": "/docs",
        "health": "/health",
    })


# ── Startup ──
@app.on_event("startup")
async def startup():
    logger.info("🚀 CuidaFamília iniciando...")
    logger.info(f"   Ambiente: {os.getenv('APP_ENV', 'development')}")
    logger.info("   Endpoints: POST /webhook/whatsapp | GET /health")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
