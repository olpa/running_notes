from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime


def parse_message_summary(raw: bytes, key: str) -> dict:
    message = BytesParser(policy=policy.default).parsebytes(raw)
    text = ""
    audio = []
    for part in message.walk():
        content_type = part.get_content_type()
        disposition = part.get_content_disposition()
        if content_type.startswith("audio/"):
            audio.append({"index": len(audio), "content_type": content_type, "filename": part.get_filename()})
        elif not text and content_type == "text/plain" and disposition != "attachment":
            try:
                text = part.get_content()
            except (LookupError, UnicodeError):
                text = ""
    date = message.get("Date")
    try:
        parsed_date = parsedate_to_datetime(date).isoformat() if date else None
    except (TypeError, ValueError):
        parsed_date = None
    preview = " ".join(text.split())[:500]
    return {
        "id": key,
        "subject": str(message.get("Subject", "(No subject)")),
        "from": str(message.get("From", "")),
        "date": parsed_date,
        "preview": preview,
        "audio": audio,
    }


def extract_audio(raw: bytes, index: int) -> tuple[bytes, str, str | None] | None:
    if index < 0:
        return None
    message = BytesParser(policy=policy.default).parsebytes(raw)
    audio_parts = [part for part in message.walk() if part.get_content_type().startswith("audio/")]
    if index >= len(audio_parts):
        return None
    part = audio_parts[index]
    payload = part.get_payload(decode=True)
    if payload is None:
        return None
    return payload, part.get_content_type(), part.get_filename()
