import os
import re
import shutil
import sqlite3
import secrets
import uuid
from crypt import METHOD_SHA512, crypt, mksalt
from datetime import datetime, timezone
from pathlib import Path

from database import connect

MAIL_ROOT = Path(os.environ.get("MAIL_ROOT", "/var/mail/voiceinbox/users"))
MAIL_UID = int(os.environ.get("MAIL_UID", "5000"))
MAIL_GID = int(os.environ.get("MAIL_GID", "5000"))
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
IMAP_PASSWORD_DIGITS = 4
IMAP_PASSWORD_CHUNKS = 3
IMAP_PASSWORD_SYLLABLES_PER_CHUNK = 3
IMAP_PASSWORD_ONSETS = ("b", "d", "f", "g", "k", "l", "m", "n", "p", "r", "s", "t", "v", "z")
IMAP_PASSWORD_VOWELS = ("a", "e", "i", "o", "u")

# Dovecot can verify this directly when SQL passdb returns the stored value.
IMAP_PASSWORD_SCHEME = "{SHA512-CRYPT}"


class UserAlreadyExistsError(ValueError):
    pass


class InvalidEmailError(ValueError):
    pass


class UserNotFoundError(ValueError):
    pass


def serialize_user(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "email": row["email"],
        "status": row["status"],
        "imap_username": row["imap_username"],
    }


def create_user(email: str) -> dict:
    normalized_email = normalize_email(email)
    user_id = uuid.uuid4().hex
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    imap_username = normalized_email
    imap_password = _generate_imap_password()
    imap_password_hash = _hash_imap_password(imap_password)

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
                    imap_password_hash,
                ),
            )
    except sqlite3.IntegrityError as exc:
        raise UserAlreadyExistsError(normalized_email) from exc

    try:
        _provision_maildir(user_id)
    except OSError:
        _delete_user(user_id)
        raise

    return {
        "id": user_id,
        "email": normalized_email,
        "created_at": created_at,
        "status": "active",
        "imap_username": imap_username,
        "imap_password": imap_password,
    }


def reset_imap_password(identifier: str) -> dict:
    user = _find_user(identifier)
    if user is None:
        raise UserNotFoundError(identifier)

    imap_password = _generate_imap_password()
    imap_password_hash = _hash_imap_password(imap_password)

    with connect() as conn:
        conn.execute(
            "UPDATE users SET imap_password_hash = ? WHERE id = ?",
            (imap_password_hash, user["id"]),
        )

    return {
        "id": user["id"],
        "email": user["email"],
        "status": user["status"],
        "imap_username": user["imap_username"],
        "imap_password": imap_password,
    }


def get_user_by_id(user_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, email, status, imap_username
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()

    if row is None:
        return None
    return serialize_user(row)


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not EMAIL_RE.match(normalized):
        raise InvalidEmailError(email)
    return normalized


def _disabled_password_hash() -> str:
    return "!"


def _generate_imap_password() -> str:
    chunks = [_generate_pronounceable_chunk() for _ in range(IMAP_PASSWORD_CHUNKS)]
    digits = f"{secrets.randbelow(10 ** IMAP_PASSWORD_DIGITS):0{IMAP_PASSWORD_DIGITS}d}"
    return "-".join(chunks + [digits])


def _generate_pronounceable_chunk() -> str:
    syllables = (
        secrets.choice(IMAP_PASSWORD_ONSETS)
        + secrets.choice(IMAP_PASSWORD_VOWELS)
        for _ in range(IMAP_PASSWORD_SYLLABLES_PER_CHUNK)
    )
    return "".join(syllables)


def _hash_imap_password(password: str) -> str:
    return f"{IMAP_PASSWORD_SCHEME}{crypt(password, mksalt(METHOD_SHA512))}"


def _find_user(identifier: str) -> sqlite3.Row | None:
    normalized_identifier = identifier.strip().lower()
    with connect() as conn:
        return conn.execute(
            """
            SELECT id, email, status, imap_username
            FROM users
            WHERE email = ? OR imap_username = ?
            """,
            (normalized_identifier, normalized_identifier),
        ).fetchone()


def _delete_user(user_id: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    shutil.rmtree(MAIL_ROOT / user_id, ignore_errors=True)


def _provision_maildir(user_id: str) -> None:
    maildir = MAIL_ROOT / user_id
    maildir.mkdir(parents=True, exist_ok=True)
    _set_maildir_permissions(maildir)

    for child in ("cur", "new", "tmp"):
        child_path = maildir / child
        child_path.mkdir(parents=True, exist_ok=True)
        _set_maildir_permissions(child_path)


def _set_maildir_permissions(path: Path) -> None:
    os.chown(path, MAIL_UID, MAIL_GID)
    path.chmod(0o700)
