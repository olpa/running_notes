import logging
import smtplib
from datetime import datetime
from email.mime.audio import MIMEAudio
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import format_datetime

import config

logger = logging.getLogger(__name__)


def deliver_via_lmtp(
    recipient: str,
    note_id: str,
    created_at: datetime,
    audio_bytes: bytes,
    duration: str,
):
    msg = MIMEMultipart()
    msg["From"] = config.MAIL_FROM_HEADER
    msg["To"] = recipient
    recorded_at = created_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    msg["Subject"] = f"Voice note ({duration}) {recorded_at}"
    msg["Message-ID"] = f"<note-{note_id}-audio@voiceinbox.local>"
    msg["Date"] = format_datetime(created_at)

    body = MIMEText(
        "Voice note recorded via running-notes.\n\n"
        f"Recorded: {recorded_at}\n"
        f"Duration: {duration}\n\n"
        "This is an automated message. Please do not reply; "
        "this address is not monitored.\n",
        "plain",
    )
    msg.attach(body)

    attachment = MIMEAudio(audio_bytes, "mpeg")
    attachment.add_header("Content-Disposition", "attachment", filename="audio.mp3")
    msg.attach(attachment)

    try:
        with smtplib.LMTP(config.LMTP_HOST, config.LMTP_PORT) as lmtp:
            refused = lmtp.sendmail(config.MAIL_FROM, [recipient], msg.as_bytes())
    except smtplib.SMTPException:
        logger.exception(
            "LMTP delivery failed for note %s to %s", note_id, recipient
        )
        raise

    if refused:
        logger.error(
            "LMTP delivery refused recipients for note %s to %s: %s",
            note_id,
            recipient,
            refused,
        )
    else:
        logger.info("LMTP delivered note %s to %s", note_id, recipient)
