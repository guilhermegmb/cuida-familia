from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import PlainTextResponse
from src.core.agent import processar_mensagem
from src.services.twilio_service import enviar_mensagem, validar_assinatura_twilio
from src.core.config import get_settings
from src.utils.logger import get_logger, log_erro

router = APIRouter()
logger = get_logger("webhook")


@router.post("/webhook/whatsapp", response_class=PlainTextResponse)
async def receber_mensagem_whatsapp(
    request: Request,
    Body: str = Form(default=""),
    From: str = Form(default=""),
    To: str = Form(default=""),
    MessageSid: str = Form(default=""),
):
    """
    Endpoint principal — recebe mensagens do WhatsApp via Twilio.
    O Twilio envia os dados como form-data (não JSON).
    """
    settings = get_settings()

    # ── Validação de assinatura Twilio (apenas em produção) ──
    if settings.app_env == "production":
        assinatura = request.headers.get("X-Twilio-Signature", "")
        url = str(request.url)
        form_data = await request.form()
        params = dict(form_data)

        if not validar_assinatura_twilio(url, params, assinatura):
            logger.warning(f"Assinatura Twilio inválida — IP: {request.client.host}")
            raise HTTPException(status_code=403, detail="Assinatura inválida")

    # ── Validação básica ──
    if not From or not Body:
        logger.warning("Webhook recebido sem 'From' ou 'Body'")
        return PlainTextResponse("OK", status_code=200)

    telefone = From.replace("whatsapp:", "")
    mensagem = Body.strip()

    logger.info(f"📨 Mensagem recebida — SID: {MessageSid} | De: {telefone}")

    # ── Mensagem vazia ──
    if not mensagem:
        enviar_mensagem(From, "Recebi sua mensagem, mas parece estar vazia. Pode escrever de novo? 😊")
        return PlainTextResponse("OK", status_code=200)

    try:
        # ── Processa com o agente ──
        resposta = await processar_mensagem(telefone, mensagem)

        # ── Envia resposta via Twilio ──
        enviado = enviar_mensagem(From, resposta)
        if not enviado:
            log_erro("falha_envio_resposta", {"para": From}, telefone)

    except Exception as e:
        log_erro("webhook_erro_critico", {"erro": str(e)}, telefone)
        enviar_mensagem(
            From,
            "Desculpe, tive um problema técnico agora. Pode tentar novamente em instantes? 🙏"
        )

    # Twilio espera 200 OK — sempre retornar isso
    return PlainTextResponse("OK", status_code=200)
