from twilio.rest import Client

from src.config.settings import get_settings
from src.utils.formatters import to_whatsapp_address


class TwilioService:
    def __init__(self) -> None:
        settings = get_settings()
        self.from_whatsapp = to_whatsapp_address(settings.twilio_phone_number)
        self.client = Client(settings.twilio_account_sid, settings.twilio_auth_token)

    async def send_whatsapp_message(self, to_phone: str, message: str) -> str:
        twilio_message = self.client.messages.create(
            body=message,
            from_=self.from_whatsapp,
            to=to_whatsapp_address(to_phone),
        )
        return twilio_message.sid
