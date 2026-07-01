from datetime import datetime, timezone

from database import connect
from users import UserAlreadyExistsError, create_user, serialize_user


class OAuthIdentityError(ValueError):
    pass


def get_or_create_oauth_user(provider: str, provider_subject: str, email: str) -> dict:
    normalized_email = _normalize_email(email)
    existing_user = _find_user_by_oauth_identity(provider, provider_subject)
    if existing_user is not None:
        _ensure_active_user(existing_user)
        return existing_user

    user = _find_user_by_email(normalized_email)
    if user is None:
        try:
            user = create_user(normalized_email)
        except UserAlreadyExistsError:
            user = _find_user_by_email(normalized_email)
            if user is None:
                raise

    _ensure_active_user(user)
    _link_oauth_identity(
        user_id=user["id"],
        provider=provider,
        provider_subject=provider_subject,
        email=normalized_email,
    )
    return user


def _ensure_active_user(user: dict) -> None:
    if user.get("status") != "active":
        raise OAuthIdentityError("User is disabled")


def _find_user_by_oauth_identity(provider: str, provider_subject: str) -> dict | None:
    with connect() as conn:
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


def _find_user_by_email(email: str) -> dict | None:
    with connect() as conn:
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
    user_id: str,
    provider: str,
    provider_subject: str,
    email: str,
) -> None:
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with connect() as conn:
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


def _normalize_email(email: str) -> str:
    normalized_email = email.strip().lower()
    if not normalized_email:
        raise OAuthIdentityError("OAuth provider did not return an email")
    return normalized_email
