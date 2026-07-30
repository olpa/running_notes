import asyncio
import json
import logging
import os
import secrets
import shutil
import smtplib
import time
from datetime import datetime, timedelta, timezone
from email.mime.audio import MIMEAudio
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import format_datetime, formataddr
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Query, Request, UploadFile
from authlib.integrations.base_client.errors import OAuthError
from fastapi.responses import FileResponse, RedirectResponse, Response
from starlette.middleware.sessions import SessionMiddleware

from audio import (
    AudioConversionError,
    AudioTooLongError,
    InvalidAudioRange,
    convert_webm_to_mp3_with_duration,
    format_audio_duration,
    parse_audio_byte_range,
)
from autoconfig import (
    AutoconfigRequestError,
    outlook_request_email,
    outlook_response_xml,
    thunderbird_config_xml,
)
from application_routes import safe_application_return_path
from database import initialize_database
from guest import (
    GuestUploadBusy,
    GuestUploadLimiter,
    GuestUploadRateLimited,
    expired_guest_note_directories,
)
from mailbox import (
    DoveadmMailbox,
    MailboxError,
    MailReference,
    references_with_requested,
)
from messages import extract_audio, parse_message_summary
from oauth import (
    OAuthConfigurationError,
    OAuthUserInfoError,
    UnknownOAuthProviderError,
    SESSION_COOKIE_NAME,
    SESSION_MAX_AGE_SECONDS,
    SESSION_SAME_SITE,
    build_redirect_uri,
    create_oauth_registry,
    extract_userinfo_identity,
    get_oauth_client,
    new_session_nonce,
    oauth_claims_options,
    session_cookie_secure,
    session_secret,
)
from oauth_identities import OAuthIdentityError, get_or_create_oauth_user
from users import (
    MAIL_ROOT,
    InvalidEmailError,
    UserAlreadyExistsError,
    create_user,
    get_guest_user,
    get_user_by_id,
    mark_user_as_guest,
    normalize_email,
    reset_imap_password,
    set_imap_password,
)

STATE_DIR = Path(os.environ.get("STATE_DIR", "/state"))
USER_STATE_DIR = STATE_DIR / "users"
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

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").strip().upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logging.getLogger().setLevel(LOG_LEVEL)
logger = logging.getLogger(__name__)

app = FastAPI()
app.add_middleware(
    SessionMiddleware,
    secret_key=session_secret(),
    session_cookie=SESSION_COOKIE_NAME,
    max_age=SESSION_MAX_AGE_SECONDS,
    path="/",
    same_site=SESSION_SAME_SITE,
    https_only=session_cookie_secure(),
)
oauth = create_oauth_registry()
mailbox = DoveadmMailbox(DOVEADM_URL, DOVEADM_PASSWORD)
guest_upload_limiter = GuestUploadLimiter(
    GUEST_UPLOADS_PER_WINDOW,
    GUEST_GLOBAL_UPLOADS_PER_WINDOW,
    GUEST_UPLOAD_WINDOW_SECONDS,
    GUEST_CONCURRENT_UPLOADS,
)


@app.on_event("startup")
async def startup():
    initialize_database()
    ensure_guest_user()
    await asyncio.to_thread(cleanup_expired_guest_recordings)
    app.state.guest_retention_task = asyncio.create_task(guest_retention_loop())


@app.on_event("shutdown")
async def shutdown():
    task = getattr(app.state, "guest_retention_task", None)
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def ensure_guest_user() -> None:
    if not GUEST_USER_PASSWORD:
        raise RuntimeError("GUEST_USER_PASSWORD is required")

    guest = get_guest_user()
    if guest is not None:
        set_imap_password(guest["id"], GUEST_USER_PASSWORD)
        return

    try:
        user = create_user(GUEST_USER_EMAIL, imap_password=GUEST_USER_PASSWORD)
    except UserAlreadyExistsError:
        # Another backend startup may have created the fixed account first.
        guest = get_guest_user()
        if guest is None:
            raise
        set_imap_password(guest["id"], GUEST_USER_PASSWORD)
        return
    mark_user_as_guest(user["id"])
    logger.info(
        "Guest user created user_id=%s email=%s",
        user["id"],
        user["email"],
    )


def can_change_imap_password(user: dict) -> bool:
    return not is_guest_user(user)


def is_guest_user(user: dict) -> bool:
    return bool(user["is_guest"])


def require_writable_profile(user: dict) -> None:
    if is_guest_user(user):
        raise HTTPException(
            status_code=403,
            detail="Guest profile is read-only",
        )


def current_active_user(request: Request) -> dict:
    user_id = request.session.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = get_user_by_id(user_id)
    if user is None or user["status"] != "active":
        request.session.clear()
        raise HTTPException(status_code=401, detail="Not authenticated")

    return user


def deliver_via_lmtp(
    recipient: str,
    note_id: str,
    created_at: datetime,
    audio_bytes: bytes,
    duration: str,
):
    msg = MIMEMultipart()
    msg["From"] = MAIL_FROM_HEADER
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
        with smtplib.LMTP(LMTP_HOST, LMTP_PORT) as lmtp:
            refused = lmtp.sendmail(MAIL_FROM, [recipient], msg.as_bytes())
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


def note_id_for(created_at: datetime) -> str:
    timestamp = created_at.strftime("%Y%m%dT%H%M%SZ")
    return f"note-{timestamp}-{secrets.token_hex(4)}"


def user_notes_dir(user_id: str) -> Path:
    return USER_STATE_DIR / user_id / "notes"


def note_dir_for(user_id: str, note_id: str) -> Path:
    return user_notes_dir(user_id) / note_id


def validate_upload_type(file: UploadFile) -> None:
    media_type = (file.content_type or "").split(";", 1)[0].strip().lower()
    if media_type not in ACCEPTED_AUDIO_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported audio type")


async def read_limited_upload(file: UploadFile, max_bytes: int = MAX_UPLOAD_BYTES) -> bytes:
    chunks = []
    total = 0

    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(status_code=413, detail="Upload too large")
        chunks.append(chunk)

    if total == 0:
        raise HTTPException(status_code=400, detail="Empty upload")

    return b"".join(chunks)


def user_note_usage(notes_dir: Path, day: datetime) -> tuple[int, int]:
    daily_note_count = 0
    total_bytes = 0
    if not notes_dir.exists():
        return daily_note_count, total_bytes

    for note_dir in notes_dir.iterdir():
        if not note_dir.is_dir():
            continue

        metadata_path = note_dir / "metadata.json"
        try:
            metadata = json.loads(metadata_path.read_text())
            created_at = datetime.fromisoformat(
                metadata["created_at"].replace("Z", "+00:00")
            )
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            logger.warning("Ignoring invalid note metadata for quota: %s", metadata_path)
        else:
            if created_at.astimezone(timezone.utc).date() == day.date():
                daily_note_count += 1

        for filename in ("audio.mp3", "audio.webm"):
            audio_path = note_dir / filename
            if audio_path.exists():
                total_bytes += audio_path.stat().st_size

    return daily_note_count, total_bytes


def enforce_user_quota(user: dict, upload_bytes: int, created_at: datetime) -> None:
    daily_note_count, total_bytes = user_note_usage(
        user_notes_dir(user["id"]), created_at
    )
    quota_factor = GUEST_QUOTA_FACTOR if is_guest_user(user) else 1
    if daily_note_count >= MAX_USER_NOTES_PER_DAY * quota_factor:
        raise HTTPException(status_code=429, detail="Daily note quota exceeded")
    if total_bytes + upload_bytes > MAX_USER_NOTE_BYTES * quota_factor:
        raise HTTPException(status_code=403, detail="Storage quota exceeded")


def cleanup_expired_guest_recordings(now: datetime | None = None) -> None:
    guest = get_guest_user()
    if guest is None:
        return

    cutoff = (now or datetime.now(timezone.utc)) - timedelta(
        hours=GUEST_RETENTION_HOURS
    )
    notes_dir = user_notes_dir(guest["id"])
    expired_notes = expired_guest_note_directories(notes_dir, cutoff)

    if expired_notes:
        remove_guest_maildir_messages(guest["id"], set(expired_notes))
        for note_dir in expired_notes.values():
            shutil.rmtree(note_dir)
        logger.info(
            "Guest retention removed recordings user_id=%s count=%d cutoff=%s",
            guest["id"],
            len(expired_notes),
            cutoff.strftime("%Y-%m-%dT%H:%M:%SZ"),
        )


def remove_guest_maildir_messages(user_id: str, note_ids: set[str]) -> None:
    message_ids = {
        f"<note-{note_id}-audio@voiceinbox.local>".encode() for note_id in note_ids
    }
    maildir = MAIL_ROOT / user_id
    if not maildir.exists():
        return
    for mailbox_dir in maildir.rglob("*"):
        if not mailbox_dir.is_dir() or mailbox_dir.name not in {"cur", "new"}:
            continue
        for message_path in mailbox_dir.iterdir():
            if not message_path.is_file():
                continue
            try:
                with message_path.open("rb") as message:
                    headers = message.read(64 * 1024).split(b"\r\n\r\n", 1)[0]
                if any(message_id in headers for message_id in message_ids):
                    message_path.unlink()
            except OSError:
                logger.exception("Failed to inspect guest Maildir message: %s", message_path)


async def guest_retention_loop() -> None:
    while True:
        await asyncio.sleep(GUEST_RETENTION_CHECK_SECONDS)
        try:
            await asyncio.to_thread(cleanup_expired_guest_recordings)
        except Exception:
            logger.exception("Guest retention cleanup failed")


def public_imap_host() -> str:
    if PUBLIC_IMAP_HOST:
        return PUBLIC_IMAP_HOST

    parsed = urlparse(PUBLIC_BASE_URL)
    return parsed.hostname or "localhost"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/autodiscover/autodiscover.xml")
@app.post("/Autodiscover/Autodiscover.xml")
async def outlook_autodiscover(request: Request):
    body = await request.body()
    if len(body) > 64 * 1024:
        raise HTTPException(status_code=413, detail="Autodiscover request is too large")
    try:
        email = normalize_email(outlook_request_email(body))
    except (AutoconfigRequestError, InvalidEmailError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if email.rsplit("@", 1)[1] != public_imap_host().lower():
        raise HTTPException(status_code=400, detail="Unsupported email domain")
    return Response(
        outlook_response_xml(
            email, public_imap_host(), PUBLIC_IMAP_PORT, PUBLIC_SMTP_PORT
        ),
        media_type="application/xml",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/.well-known/autoconfig/mail/config-v1.1.xml")
def thunderbird_autoconfig():
    return Response(
        thunderbird_config_xml(
            public_imap_host(), PUBLIC_IMAP_PORT, PUBLIC_SMTP_PORT
        ),
        media_type="application/xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@app.get("/api/me")
def me(request: Request):
    user = current_active_user(request)
    return {
        "user": {
            **user,
            "is_guest": is_guest_user(user),
            "guest_retention_hours": (
                GUEST_RETENTION_HOURS if is_guest_user(user) else None
            ),
            "can_change_imap_password": can_change_imap_password(user),
        }
    }


@app.patch("/api/me")
def update_profile(request: Request):
    user = current_active_user(request)
    require_writable_profile(user)
    raise HTTPException(status_code=501, detail="Profile updates are not implemented")


@app.get("/api/me/imap-settings")
def imap_settings(request: Request):
    user = current_active_user(request)
    settings = {
        "host": public_imap_host(),
        "port": PUBLIC_IMAP_PORT,
        "smtp_port": PUBLIC_SMTP_PORT,
        "security": PUBLIC_IMAP_SECURITY,
        "username": user["imap_username"],
    }
    if not can_change_imap_password(user):
        settings["password"] = GUEST_USER_PASSWORD
    return {"imap": settings}


@app.post("/api/me/imap-password")
def regenerate_imap_password(request: Request):
    user = current_active_user(request)
    if not can_change_imap_password(user):
        raise HTTPException(
            status_code=403,
            detail="Guest IMAP password can only be changed by an administrator",
        )
    reset = reset_imap_password(user["imap_username"])
    logger.info(
        "IMAP password regenerated for user_id=%s email=%s imap_username=%s",
        reset["id"],
        reset["email"],
        reset["imap_username"],
    )
    return {
        "imap": {
            "username": reset["imap_username"],
            "password": reset["imap_password"],
        }
    }


@app.get("/auth/login/{provider}")
async def oauth_login(
    provider: str,
    request: Request,
    return_to: str | None = Query(default=None),
):
    try:
        client = get_oauth_client(oauth, provider)
        redirect_uri = build_redirect_uri(provider)
    except UnknownOAuthProviderError:
        logger.warning("OAuth login rejected for unknown provider=%s", provider)
        raise HTTPException(status_code=404, detail="Unknown OAuth provider")
    except OAuthConfigurationError as exc:
        logger.warning("OAuth login configuration error for provider=%s", provider)
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    logger.info(
        "OAuth login started provider=%s redirect_uri=%s", provider, redirect_uri
    )
    request.session.clear()
    request.session["oauth_return_to"] = safe_application_return_path(return_to)
    return await client.authorize_redirect(request, redirect_uri)


@app.get("/auth/callback/{provider}")
async def oauth_callback(provider: str, request: Request):
    return_to = safe_application_return_path(
        request.session.get("oauth_return_to")
    )
    try:
        client = get_oauth_client(oauth, provider)
        token = await client.authorize_access_token(
            request,
            claims_options=oauth_claims_options(provider),
        )
        provider_subject, email, email_verified = extract_userinfo_identity(
            provider, token["userinfo"]
        )
        user = get_or_create_oauth_user(
            provider,
            provider_subject,
            email,
            email_verified,
            public_imap_host(),
        )
    except UnknownOAuthProviderError:
        logger.warning("OAuth callback rejected for unknown provider=%s", provider)
        raise HTTPException(status_code=404, detail="Unknown OAuth provider")
    except OAuthConfigurationError as exc:
        logger.warning("OAuth callback configuration error provider=%s", provider)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except OAuthUserInfoError as exc:
        logger.warning(
            "OAuth callback userinfo rejected provider=%s error=%s", provider, exc
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OAuthIdentityError as exc:
        logger.warning(
            "OAuth callback identity rejected provider=%s error=%s", provider, exc
        )
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except OAuthError as exc:
        logger.warning(
            "OAuth callback failed provider=%s error=%s",
            provider,
            exc.__class__.__name__,
        )
        raise HTTPException(status_code=400, detail="OAuth login failed") from exc
    except KeyError as exc:
        logger.warning("OAuth callback missing userinfo provider=%s", provider)
        raise HTTPException(
            status_code=400, detail="OAuth provider did not return user info"
        ) from exc

    request.session.clear()
    request.session["user_id"] = user["id"]
    request.session["login_nonce"] = new_session_nonce()
    logger.info(
        "OAuth login completed provider=%s user_id=%s email=%s",
        provider,
        user["id"],
        user["email"],
    )
    return RedirectResponse(url=return_to, status_code=303)


@app.post("/auth/logout", status_code=204)
def logout(request: Request):
    request.session.clear()
    return None


@app.post("/auth/guest", status_code=204)
def guest_login(request: Request):
    user = get_guest_user()
    if user is None or user["status"] != "active":
        raise HTTPException(status_code=503, detail="Guest account is unavailable")

    request.session.clear()
    request.session["user_id"] = user["id"]
    request.session["login_nonce"] = new_session_nonce()
    logger.info("Guest login completed user_id=%s email=%s", user["id"], user["email"])
    return None


@app.post("/api/record", status_code=201)
async def record(request: Request, file: UploadFile):
    user = current_active_user(request)
    media_type = file.content_type or ""
    validate_upload_type(file)

    guest_slot = False
    upload_limit = MAX_UPLOAD_BYTES
    if is_guest_user(user):
        session_key = str(request.session.get("login_nonce", "guest"))
        try:
            guest_upload_limiter.acquire(session_key, time.monotonic())
            guest_slot = True
        except GuestUploadRateLimited as exc:
            raise HTTPException(
                status_code=429,
                detail=str(exc),
                headers={"Retry-After": str(GUEST_UPLOAD_WINDOW_SECONDS)},
            ) from exc
        except GuestUploadBusy as exc:
            raise HTTPException(
                status_code=503,
                detail=str(exc),
                headers={"Retry-After": "5"},
            ) from exc
        upload_limit = MAX_GUEST_UPLOAD_BYTES

    try:
        return await process_recording(user, file, media_type, upload_limit)
    finally:
        if guest_slot:
            guest_upload_limiter.release()


async def process_recording(
    user: dict, file: UploadFile, media_type: str, upload_limit: int
):
    uploaded_audio_bytes = await read_limited_upload(file, upload_limit)
    try:
        audio_bytes, duration_seconds = await asyncio.to_thread(
            convert_webm_to_mp3_with_duration, uploaded_audio_bytes
        )
    except AudioTooLongError as exc:
        logger.info(
            "Overlong audio rejected user_id=%s email=%s", user["id"], user["email"]
        )
        raise HTTPException(
            status_code=413, detail="Recording exceeds the 30-second limit"
        ) from exc
    except AudioConversionError as exc:
        logger.warning(
            "Audio conversion failed user_id=%s email=%s", user["id"], user["email"]
        )
        raise HTTPException(status_code=422, detail="Invalid audio recording") from exc

    created_at = datetime.now(timezone.utc)
    enforce_user_quota(user, len(audio_bytes), created_at)
    note_id = note_id_for(created_at)
    note_dir = note_dir_for(user["id"], note_id)
    note_dir.mkdir(parents=True, exist_ok=False)

    audio_path = note_dir / "audio.mp3"
    audio_path.write_bytes(audio_bytes)

    created_at_str = created_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    duration = format_audio_duration(duration_seconds)
    subject = f"Voice note ({duration}) {created_at_str}"
    metadata = {
        "id": note_id,
        "created_at": created_at_str,
        "subject": subject,
        "user_id": user["id"],
    }
    (note_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))

    logger.info(
        "Note uploaded note_id=%s user_id=%s email=%s upload_bytes=%d "
        "stored_bytes=%d content_type=%s",
        note_id,
        user["id"],
        user["email"],
        len(uploaded_audio_bytes),
        len(audio_bytes),
        media_type,
    )

    deliver_via_lmtp(
        user["imap_username"], note_id, created_at, audio_bytes, duration
    )

    return metadata


@app.get("/api/note/{note_id}")
def get_note(note_id: str, request: Request):
    user = current_active_user(request)
    meta_path = note_dir_for(user["id"], note_id) / "metadata.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="Note not found")
    return json.loads(meta_path.read_text())


@app.get("/api/note/{note_id}/audio")
def get_audio(note_id: str, request: Request):
    user = current_active_user(request)
    note_dir = note_dir_for(user["id"], note_id)
    mp3_path = note_dir / "audio.mp3"
    if mp3_path.exists():
        return FileResponse(mp3_path, media_type="audio/mpeg")
    webm_path = note_dir / "audio.webm"
    if webm_path.exists():
        return FileResponse(webm_path, media_type="audio/webm")
    raise HTTPException(status_code=404, detail="Audio not found")

@app.get("/api/messages")
def list_messages(
    request: Request,
    include: str | None = Query(default=None),
):
    user = current_active_user(request)
    try:
        references = mailbox.latest_references(user["imap_username"], WEB_MESSAGE_LIMIT)
        references, requested_reference = references_with_requested(
            references, include
        )
        raw_messages = mailbox.fetch_messages(user["imap_username"], references)
    except MailboxError as exc:
        logger.exception("Dovecot message listing failed user_id=%s", user["id"])
        raise HTTPException(status_code=503, detail="Mailbox is unavailable") from exc
    messages = []
    for reference, raw in raw_messages:
        try:
            messages.append(parse_message_summary(raw, reference.key))
        except Exception:
            logger.warning("Ignoring malformed mailbox message user_id=%s uid=%s", user["id"], reference.uid)
    requested_message_found = (
        requested_reference is not None
        and any(message["id"] == requested_reference.key for message in messages)
        if include
        else None
    )
    return {
        "messages": messages,
        "limit": WEB_MESSAGE_LIMIT,
        "requested_message_found": requested_message_found,
    }


@app.get("/api/messages/{message_key}/audio/{audio_index}")
def message_audio(message_key: str, audio_index: int, request: Request):
    user = current_active_user(request)
    try:
        reference = MailReference.from_key(message_key)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Message not found") from exc
    try:
        raw = mailbox.fetch_message(user["imap_username"], reference)
    except MailboxError as exc:
        logger.exception("Dovecot audio fetch failed user_id=%s", user["id"])
        raise HTTPException(status_code=503, detail="Mailbox is unavailable") from exc
    if raw is None:
        raise HTTPException(status_code=404, detail="Message not found")
    audio = extract_audio(raw, audio_index)
    if audio is None:
        raise HTTPException(status_code=404, detail="Audio attachment not found")
    payload, content_type, _filename = audio
    headers = {"Accept-Ranges": "bytes"}
    requested_range = request.headers.get("range")
    if requested_range is None:
        return Response(payload, media_type=content_type, headers=headers)

    try:
        start, end = parse_audio_byte_range(requested_range, len(payload))
    except InvalidAudioRange as exc:
        raise HTTPException(
            status_code=416,
            detail="Requested range not satisfiable",
            headers={"Content-Range": f"bytes */{len(payload)}"},
        ) from exc

    headers["Content-Range"] = f"bytes {start}-{end}/{len(payload)}"
    return Response(
        payload[start : end + 1],
        status_code=206,
        media_type=content_type,
        headers=headers,
    )


@app.delete("/api/messages/{message_key}", status_code=204)
def delete_message(message_key: str, request: Request):
    user = current_active_user(request)
    if user["is_guest"]:
        raise HTTPException(
            status_code=403,
            detail="Guest users cannot delete messages",
        )
    try:
        reference = MailReference.from_key(message_key)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Message not found") from exc
    try:
        deleted = mailbox.delete_message(user["imap_username"], reference)
    except MailboxError as exc:
        logger.exception("Dovecot message deletion failed user_id=%s", user["id"])
        raise HTTPException(status_code=503, detail="Mailbox is unavailable") from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Message not found")
    logger.info(
        "Message deleted user_id=%s mailbox_guid=%s uid=%s",
        user["id"],
        reference.mailbox_guid,
        reference.uid,
    )
    return Response(status_code=204)
