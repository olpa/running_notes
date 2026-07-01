import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any

SESSION_COOKIE_NAME = "rn_session"
SESSION_MAX_AGE_SECONDS = 14 * 24 * 60 * 60
SESSION_SAME_SITE = "lax"


class InvalidSessionError(ValueError):
    pass


def create_session(response: Any, user_id: str) -> None:
    now = int(time.time())
    payload = {
        "user_id": user_id,
        "iat": now,
        "exp": now + SESSION_MAX_AGE_SECONDS,
        "nonce": secrets.token_urlsafe(12),
    }
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=_encode_session(payload),
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        secure=_cookie_secure(),
        samesite=SESSION_SAME_SITE,
    )


def clear_session(response: Any) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        secure=_cookie_secure(),
        samesite=SESSION_SAME_SITE,
    )


def get_session_user_id(request: Any) -> str | None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None

    try:
        payload = _decode_session(token)
    except InvalidSessionError:
        return None

    expires_at = payload.get("exp")
    user_id = payload.get("user_id")
    if not isinstance(expires_at, int) or expires_at < int(time.time()):
        return None
    if not isinstance(user_id, str) or not user_id:
        return None
    return user_id


def _encode_session(payload: dict[str, Any]) -> str:
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    payload_part = _base64url_encode(payload_bytes)
    signature = _sign(payload_part)
    return f"{payload_part}.{signature}"


def _decode_session(token: str) -> dict[str, Any]:
    payload_part, separator, signature = token.partition(".")
    if not separator or not payload_part or not signature:
        raise InvalidSessionError("malformed session")

    expected_signature = _sign(payload_part)
    if not hmac.compare_digest(signature, expected_signature):
        raise InvalidSessionError("invalid session signature")

    try:
        payload_bytes = _base64url_decode(payload_part)
        payload = json.loads(payload_bytes)
    except (ValueError, json.JSONDecodeError) as exc:
        raise InvalidSessionError("invalid session payload") from exc

    if not isinstance(payload, dict):
        raise InvalidSessionError("invalid session payload")
    return payload


def _sign(payload_part: str) -> str:
    digest = hmac.new(
        _session_secret(),
        payload_part.encode(),
        hashlib.sha256,
    ).digest()
    return _base64url_encode(digest)


def _session_secret() -> bytes:
    secret = os.environ.get("SESSION_SECRET", "")
    if not secret:
        raise RuntimeError("SESSION_SECRET is required for web sessions")
    return secret.encode()


def _cookie_secure() -> bool:
    value = os.environ.get("SESSION_COOKIE_SECURE", "true").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
