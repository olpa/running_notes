import logging
import sqlite3
from datetime import datetime, timezone

from database import connect
from users import UserAlreadyExistsError, create_user, normalize_email, serialize_user

logger = logging.getLogger(__name__)


class OAuthIdentityError(ValueError):
    pass


def get_or_create_oauth_user(
    provider: str,
    provider_subject: str,
    email: str,
    email_verified: bool,
) -> dict:
    if not email_verified:
        raise OAuthIdentityError("OAuth provider did not verify the email")

    normalized_email = _normalize_oauth_email(email)
    with connect() as conn:
        existing_user = _find_user_by_oauth_identity(conn, provider, provider_subject)
        if existing_user is not None:
            _ensure_active_user(existing_user)
            logger.info(
                "OAuth identity reused provider=%s user_id=%s email=%s",
                provider,
                existing_user["id"],
                existing_user["email"],
            )
            return existing_user

        user = _find_user_by_email(conn, normalized_email)

    if user is None:
        try:
            user = create_user(normalized_email)
        except UserAlreadyExistsError:
            with connect() as conn:
                user = _find_user_by_email(conn, normalized_email)
            if user is None:
                raise

    _ensure_active_user(user)

    with connect() as conn:
        existing_user = _find_user_by_oauth_identity(conn, provider, provider_subject)
        if existing_user is not None:
            _ensure_active_user(existing_user)
            logger.info(
                "OAuth identity reused after race provider=%s user_id=%s email=%s",
                provider,
                existing_user["id"],
                existing_user["email"],
            )
            return existing_user

        user = _find_user_by_email(conn, normalized_email)
        if user is None:
            raise OAuthIdentityError("Linked user disappeared during OAuth login")
        _ensure_active_user(user)

        try:
            _link_oauth_identity(
                conn=conn,
                user_id=user["id"],
                provider=provider,
                provider_subject=provider_subject,
                email=normalized_email,
            )
        except OAuthIdentityError:
            existing_user = _find_user_by_oauth_identity(
                conn, provider, provider_subject
            )
            if existing_user is None:
                raise
            _ensure_active_user(existing_user)
            logger.info(
                "OAuth identity reused after link conflict provider=%s user_id=%s email=%s",
                provider,
                existing_user["id"],
                existing_user["email"],
            )
            return existing_user

        logger.info(
            "OAuth identity linked provider=%s user_id=%s email=%s",
            provider,
            user["id"],
            user["email"],
        )
        return user


def _ensure_active_user(user: dict) -> None:
    if user.get("status") != "active":
        raise OAuthIdentityError("User is disabled")


def _find_user_by_oauth_identity(
    conn: sqlite3.Connection,
    provider: str,
    provider_subject: str,
) -> dict | None:
    row = conn.execute(
        """
        SELECT users.id, users.email, users.status, users.imap_username
        FROM oauth_identities
        JOIN users ON users.id = oauth_identities.user_id
        WHERE oauth_identities.provider = ?
          AND oauth_identities.provider_subject = ?
        """,
        (provider, provider_subject),
    ).fetchone()

    if row is None:
        return None
    return serialize_user(row)


def _find_user_by_email(conn: sqlite3.Connection, email: str) -> dict | None:
    row = conn.execute(
        """
        SELECT id, email, status, imap_username
        FROM users
        WHERE email = ?
        """,
        (email,),
    ).fetchone()

    if row is None:
        return None
    return serialize_user(row)


def _link_oauth_identity(
    conn: sqlite3.Connection,
    user_id: str,
    provider: str,
    provider_subject: str,
    email: str,
) -> None:
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        conn.execute(
            """
            INSERT INTO oauth_identities (
                user_id,
                provider,
                provider_subject,
                email,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, provider, provider_subject, email, created_at),
        )
    except sqlite3.IntegrityError as exc:
        raise OAuthIdentityError("OAuth identity is already linked") from exc


def _normalize_oauth_email(email: str) -> str:
    try:
        return normalize_email(email)
    except ValueError as exc:
        raise OAuthIdentityError("OAuth provider returned an invalid email") from exc
