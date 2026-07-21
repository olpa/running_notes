import hashlib
import logging
import os
import re
import shutil
import sqlite3
import secrets
import unicodedata
import uuid
from crypt import METHOD_SHA512, crypt, mksalt
from datetime import datetime, timezone
from pathlib import Path

from database import connect

logger = logging.getLogger(__name__)

MAIL_ROOT = Path(os.environ.get("MAIL_ROOT", "/var/mail/voiceinbox/users"))
MAIL_UID = int(os.environ.get("MAIL_UID", "1000"))
MAIL_GID = int(os.environ.get("MAIL_GID", "1000"))
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


class AmbiguousUserError(ValueError):
    pass


def serialize_user(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "email": row["provider_email"],
        "status": row["status"],
        "imap_username": row["imap_username"],
        "is_guest": bool(row["is_guest"]),
    }


def create_user(email: str, imap_password: str | None = None) -> dict:
    normalized_email = normalize_email(email)
    if get_user_by_email(normalized_email) is not None:
        raise UserAlreadyExistsError(normalized_email)
    return _create_user(normalized_email, (normalized_email,), imap_password)


def create_oauth_user(
    email: str,
    provider: str,
    provider_subject: str,
    mailbox_domain: str,
) -> dict:
    normalized_email = normalize_email(email)
    usernames = _oauth_imap_usernames(
        normalized_email, provider, provider_subject, mailbox_domain
    )
    return _create_user(normalized_email, usernames)


def _create_user(
    normalized_email: str,
    imap_usernames,
    imap_password: str | None = None,
) -> dict:
    user_id = uuid.uuid4().hex
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    password_source = "generated"
    if imap_password is None:
        imap_password = _generate_imap_password()
    elif not imap_password:
        raise ValueError("IMAP password must not be empty")
    else:
        password_source = "configured"
    imap_password_hash = _hash_imap_password(imap_password)

    imap_username = None
    for candidate in imap_usernames:
        try:
            with connect() as conn:
                conn.execute(
                    """
                    INSERT INTO users (
                        id,
                        provider_email,
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
                        candidate,
                        imap_password_hash,
                    ),
                )
        except sqlite3.IntegrityError:
            with connect() as conn:
                collision = conn.execute(
                    "SELECT 1 FROM users WHERE imap_username = ?", (candidate,)
                ).fetchone()
            if collision is not None:
                continue
            raise
        imap_username = candidate
        break

    if imap_username is None:
        raise UserAlreadyExistsError("mailbox alias namespace is exhausted")

    logger.info(
        "IMAP password %s for new user_id=%s email=%s imap_username=%s",
        password_source,
        user_id,
        normalized_email,
        imap_username,
    )

    try:
        _provision_maildir(user_id)
    except OSError:
        logger.exception(
            "Maildir provisioning failed for user_id=%s email=%s",
            user_id,
            normalized_email,
        )
        _delete_user(user_id)
        raise

    logger.info(
        "User created user_id=%s email=%s imap_username=%s",
        user_id,
        normalized_email,
        imap_username,
    )

    return {
        "id": user_id,
        "email": normalized_email,
        "created_at": created_at,
        "status": "active",
        "imap_username": imap_username,
        "imap_password": imap_password,
        "is_guest": False,
    }


def reset_imap_password(identifier: str) -> dict:
    user = _find_user(identifier)
    if user is None:
        raise UserNotFoundError(identifier)

    imap_password = _generate_imap_password()
    logger.info(
        "IMAP password generated for existing user_id=%s email=%s imap_username=%s",
        user["id"],
        user["email"],
        user["imap_username"],
    )
    imap_password_hash = _hash_imap_password(imap_password)

    with connect() as conn:
        conn.execute(
            "UPDATE users SET imap_password_hash = ? WHERE id = ?",
            (imap_password_hash, user["id"]),
        )

    logger.info(
        "IMAP password hash replaced for user_id=%s email=%s imap_username=%s",
        user["id"],
        user["email"],
        user["imap_username"],
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
            SELECT id, provider_email, status, imap_username, is_guest
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()

    if row is None:
        return None
    return serialize_user(row)


def get_user_by_email(email: str) -> dict | None:
    normalized_email = normalize_email(email)
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, provider_email, status, imap_username, is_guest
            FROM users
            WHERE provider_email = ?
            """,
            (normalized_email,),
        ).fetchone()

    if row is None:
        return None
    return serialize_user(row)


def get_guest_user() -> dict | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, provider_email, status, imap_username, is_guest
            FROM users
            WHERE is_guest = 1
            """
        ).fetchone()

    if row is None:
        return None
    return serialize_user(row)


def mark_user_as_guest(user_id: str) -> None:
    with connect() as conn:
        conn.execute("UPDATE users SET is_guest = 0 WHERE is_guest != 0")
        cursor = conn.execute(
            "UPDATE users SET is_guest = 1 WHERE id = ?",
            (user_id,),
        )

    if cursor.rowcount != 1:
        raise UserNotFoundError(user_id)


def delete_orphaned_user(user_id: str) -> None:
    with connect() as conn:
        cursor = conn.execute(
            """
            DELETE FROM users
            WHERE id = ?
              AND NOT EXISTS (
                  SELECT 1 FROM oauth_identities
                  WHERE oauth_identities.user_id = users.id
              )
            """,
            (user_id,),
        )
    if cursor.rowcount == 1:
        shutil.rmtree(MAIL_ROOT / user_id, ignore_errors=True)


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
        by_username = conn.execute(
            """
            SELECT id, provider_email, status, imap_username, is_guest
            FROM users
            WHERE imap_username = ?
            """,
            (normalized_identifier,),
        ).fetchone()
        if by_username is not None:
            return by_username

        by_email = conn.execute(
            """
            SELECT id, provider_email, status, imap_username, is_guest
            FROM users
            WHERE provider_email = ?
            """,
            (normalized_identifier,),
        ).fetchall()

    if len(by_email) > 1:
        raise AmbiguousUserError(identifier)
    return by_email[0] if by_email else None


def _oauth_imap_usernames(
    email: str,
    provider: str,
    provider_subject: str,
    mailbox_domain: str,
):
    local_part = email.rsplit("@", 1)[0]
    normalized_local_part = unicodedata.normalize("NFKD", local_part)
    normalized_local_part = "".join(
        character
        for character in normalized_local_part
        if not unicodedata.combining(character)
    )
    prefix = re.sub(r"[^a-z0-9._-]+", "-", normalized_local_part.lower())
    prefix = prefix.strip("._-")[:48] or "user"
    domain = mailbox_domain.strip().lower()
    if not domain or "@" in domain or any(character.isspace() for character in domain):
        raise ValueError("Invalid mailbox domain")

    seed = "\0".join((email, provider, provider_subject)).encode("utf-8")
    digest = hashlib.sha256(seed).digest()
    initial_suffix = int.from_bytes(digest[:8], "big") % 10_000
    for attempt in range(10_000):
        suffix = (initial_suffix + attempt) % 10_000
        yield f"{prefix}-{suffix:04d}@{domain}"


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
