from twilio.rest import Client
from twilio.request_validator import RequestValidator
from src.core.config import get_settings
from src.utils.logger import get_logger, log_erro

logger = get_logger("twilio")
_client = None


def get_twilio_client() -> Client:
    global _client
    if _client is None:
        settings = get_settings()
        _client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    return _client


def enviar_mensagem(para: str, texto: str) -> bool:
    """
    Envia mensagem WhatsApp via Twilio.
    'para' deve estar no formato: whatsapp:+5511999999999
    """
    settings = get_settings()
    try:
        client = get_twilio_client()

        # Garante formato correto
        if not para.startswith("whatsapp:"):
            para = f"whatsapp:{para}"

        de = settings.twilio_whatsapp_number
        if not de.startswith("whatsapp:"):
            de = f"whatsapp:{de}"

        message = client.messages.create(
            body=texto,
            from_=de,
            to=para,
        )
        logger.info(f"Mensagem enviada — SID: {message.sid} → {para}")
        return True

    except Exception as e:
        log_erro("twilio_envio_falhou", {"erro": str(e)}, para)
        return False


def validar_assinatura_twilio(
    url: str,
    params: dict,
    assinatura: str,
) -> bool:
    """Valida que a requisição veio realmente do Twilio."""
    settings = get_settings()
    try:
        validator = RequestValidator(settings.twilio_auth_token)
        return validator.validate(url, params, assinatura)
    except Exception as e:
        log_erro("twilio_validacao_falhou", {"erro": str(e)})
        return False
