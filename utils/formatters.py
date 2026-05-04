import re


def normalize_whatsapp_number(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("whatsapp:"):
        raw = raw.split(":", 1)[1]
    digits = re.sub(r"\D", "", raw)
    if not digits.startswith("+"):
        digits = f"+{digits}"
    return digits


def to_whatsapp_address(phone_number: str) -> str:
    normalized = normalize_whatsapp_number(phone_number)
    return f"whatsapp:{normalized}"
