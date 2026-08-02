import os
from email.utils import formataddr
from pathlib import Path
from urllib.parse import urlparse

from users import normalize_email

STATE_DIR = Path(os.environ.get("STATE_DIR", "/state"))
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))
MAX_GUEST_UPLOAD_BYTES = int(
    os.environ.get("MAX_GUEST_UPLOAD_BYTES", str(2 * 1024 * 1024))
)
MAX_USER_NOTE_BYTES = int(
    os.environ.get("MAX_USER_NOTE_BYTES", str(250 * 1024 * 1024))
)
MAX_USER_NOTES_PER_DAY = int(os.environ.get("MAX_USER_NOTES_PER_DAY", "100"))
GUEST_QUOTA_FACTOR = int(os.environ.get("GUEST_QUOTA_FACTOR", "10"))
GUEST_RETENTION_HOURS = int(os.environ.get("GUEST_RETENTION_HOURS", "24"))
GUEST_UPLOADS_PER_WINDOW = int(os.environ.get("GUEST_UPLOADS_PER_WINDOW", "10"))
GUEST_GLOBAL_UPLOADS_PER_WINDOW = int(
    os.environ.get("GUEST_GLOBAL_UPLOADS_PER_WINDOW", "60")
)
GUEST_UPLOAD_WINDOW_SECONDS = int(
    os.environ.get("GUEST_UPLOAD_WINDOW_SECONDS", "600")
)
GUEST_CONCURRENT_UPLOADS = int(os.environ.get("GUEST_CONCURRENT_UPLOADS", "2"))
WEB_MESSAGE_LIMIT = int(os.environ.get("WEB_MESSAGE_LIMIT", "100"))
DOVEADM_URL = os.environ.get("DOVEADM_URL", "http://dovecot:8080/doveadm/v1")
DOVEADM_PASSWORD = os.environ.get("DOVEADM_PASSWORD", "")
GUEST_RETENTION_CHECK_SECONDS = 60 * 60
ACCEPTED_AUDIO_TYPES = {"audio/webm"}
LMTP_HOST = "dovecot"
LMTP_PORT = 24
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://localhost")
PUBLIC_IMAP_HOST = os.environ.get("PUBLIC_IMAP_HOST", "").strip()
MAIL_DOMAIN = PUBLIC_IMAP_HOST or urlparse(PUBLIC_BASE_URL).hostname or "localhost"
MAIL_FROM = f"no-reply@{MAIL_DOMAIN}"
MAIL_FROM_HEADER = formataddr(("Running Notes", MAIL_FROM))
PUBLIC_IMAP_PORT = int(os.environ.get("PUBLIC_IMAP_PORT", "993"))
PUBLIC_SMTP_PORT = int(os.environ.get("PUBLIC_SMTP_PORT", "587"))
PUBLIC_IMAP_SECURITY = os.environ.get("PUBLIC_IMAP_SECURITY", "TLS").strip() or "TLS"
GUEST_USER_EMAIL = normalize_email(
    os.environ.get("GUEST_USER_EMAIL", "").strip()
    or f"public@{MAIL_DOMAIN}"
)
GUEST_USER_PASSWORD = os.environ.get("GUEST_USER_PASSWORD", "")

if GUEST_QUOTA_FACTOR < 1:
    raise ValueError("GUEST_QUOTA_FACTOR must be at least 1")
if WEB_MESSAGE_LIMIT < 1:
    raise ValueError("WEB_MESSAGE_LIMIT must be at least 1")

if GUEST_RETENTION_HOURS < 1:
    raise ValueError("GUEST_RETENTION_HOURS must be at least 1")
if not 0 < MAX_GUEST_UPLOAD_BYTES <= MAX_UPLOAD_BYTES:
    raise ValueError("MAX_GUEST_UPLOAD_BYTES must be between 1 and MAX_UPLOAD_BYTES")
if min(
    GUEST_UPLOADS_PER_WINDOW,
    GUEST_GLOBAL_UPLOADS_PER_WINDOW,
    GUEST_UPLOAD_WINDOW_SECONDS,
    GUEST_CONCURRENT_UPLOADS,
) < 1:
    raise ValueError("Guest upload controls must be positive")


def public_imap_host() -> str:
    if PUBLIC_IMAP_HOST:
        return PUBLIC_IMAP_HOST

    parsed = urlparse(PUBLIC_BASE_URL)
    return parsed.hostname or "localhost"
