import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from database import connect

MAIL_ROOT = Path("/var/mail/voiceinbox/users")
IMAP_USERNAME_SUFFIX = "voiceinbox.local"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class UserAlreadyExistsError(ValueError):
    pass


class InvalidEmailError(ValueError):
    pass


def create_user(email: str) -> dict:
    normalized_email = _normalize_email(email)
    user_id = uuid.uuid4().hex
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    imap_username = f"{user_id}@{IMAP_USERNAME_SUFFIX}"

    try:
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO users (
                    id,
                    email,
                    created_at,
                    status,
                    imap_username,
                    imap_password_hash
                )
                VALUES (?, ?, ?, 'active', ?, ?)
                """,
                (
                    user_id,
                    normalized_email,
                    created_at,
                    imap_username,
                    _disabled_password_hash(),
                ),
            )
    except sqlite3.IntegrityError as exc:
        raise UserAlreadyExistsError(normalized_email) from exc

    _provision_maildir(user_id)

    return {
        "id": user_id,
        "email": normalized_email,
        "created_at": created_at,
        "status": "active",
        "imap_username": imap_username,
    }


def _normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not EMAIL_RE.match(normalized):
        raise InvalidEmailError(email)
    return normalized


def _disabled_password_hash() -> str:
    return "!"


def _provision_maildir(user_id: str) -> None:
    maildir = MAIL_ROOT / user_id
    for child in ("cur", "new", "tmp"):
        (maildir / child).mkdir(parents=True, exist_ok=True)
