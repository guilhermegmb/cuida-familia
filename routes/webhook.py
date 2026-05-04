from fastapi import APIRouter, Depends, Form
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from twilio.twiml.messaging_response import MessagingResponse

from src.database.session import get_db_session
from src.services.agent_service import AgentService
from src.utils.formatters import normalize_whatsapp_number

router = APIRouter(prefix="/webhook", tags=["webhook"])
agent_service = AgentService()


@router.post("/twilio/whatsapp", summary="Webhook de mensagens WhatsApp via Twilio")
async def twilio_whatsapp_webhook(
    Body: str = Form(default=""),
    From: str = Form(default=""),
    MessageSid: str = Form(default=""),
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    _ = MessageSid
    incoming_text = Body.strip()
    sender_phone = normalize_whatsapp_number(From)

    if not incoming_text:
        outgoing_text = "Recebi uma mensagem vazia. Pode me contar como posso te ajudar hoje?"
    else:
        outgoing_text = await agent_service.process_incoming_message(db, sender_phone, incoming_text)

    twiml = MessagingResponse()
    twiml.message(outgoing_text)
    return Response(content=str(twiml), media_type="application/xml")
