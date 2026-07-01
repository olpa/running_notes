import json
import smtplib
import uuid
from datetime import datetime, timezone
from email.mime.audio import MIMEAudio
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import format_datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from starlette.middleware.sessions import SessionMiddleware

from database import initialize_database
from oauth import (
    OAuthConfigurationError,
    UnknownOAuthProviderError,
    build_redirect_uri,
    create_oauth_registry,
    get_oauth_client,
    session_cookie_secure,
    session_secret,
)
from users import get_user_by_id

DATA_DIR = Path("/data")
LMTP_HOST = "dovecot"
LMTP_PORT = 24
MAIL_FROM = "voiceinbox@voiceinbox.local"
MAIL_TO = "voiceinbox"

app = FastAPI()
app.add_middleware(
    SessionMiddleware,
    secret_key=session_secret(),
    https_only=session_cookie_secure(),
    same_site="lax",
)
oauth = create_oauth_registry()


@app.on_event("startup")
def startup():
    initialize_database()


def deliver_via_lmtp(note_id: str, created_at: datetime, audio_bytes: bytes):
    msg = MIMEMultipart()
    msg["From"] = MAIL_FROM
    msg["To"] = MAIL_TO
    msg["Subject"] = f"Voice note {created_at.strftime('%Y-%m-%dT%H:%M:%SZ')}"
    msg["Message-ID"] = f"<note-{note_id}-audio@voiceinbox.local>"
    msg["Date"] = format_datetime(created_at)

    body = MIMEText("Voice note recorded via running-notes.", "plain")
    msg.attach(body)

    attachment = MIMEAudio(audio_bytes, "webm")
    attachment.add_header("Content-Disposition", "attachment", filename="audio.webm")
    msg.attach(attachment)

    with smtplib.LMTP(LMTP_HOST, LMTP_PORT) as lmtp:
        lmtp.sendmail(MAIL_FROM, [MAIL_TO], msg.as_bytes())


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/me")
def me(request: Request):
    user_id = request.session.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = get_user_by_id(user_id)
    if user is None or user["status"] != "active":
        raise HTTPException(status_code=401, detail="Not authenticated")

    return {"user": user}


@app.get("/auth/login/{provider}")
async def oauth_login(provider: str, request: Request):
    try:
        client = get_oauth_client(oauth, provider)
        redirect_uri = build_redirect_uri(provider)
    except UnknownOAuthProviderError:
        raise HTTPException(status_code=404, detail="Unknown OAuth provider")
    except OAuthConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return await client.authorize_redirect(request, redirect_uri)


@app.post("/auth/logout", status_code=204)
def logout(request: Request):
    request.session.clear()
    return None


@app.post("/record", status_code=201)
async def record(file: UploadFile):
    note_id = f"note-{uuid.uuid4().hex[:12]}"
    note_dir = DATA_DIR / note_id
    note_dir.mkdir(parents=True, exist_ok=True)

    audio_bytes = await file.read()
    audio_path = note_dir / "audio.webm"
    audio_path.write_bytes(audio_bytes)

    created_at = datetime.now(timezone.utc)
    created_at_str = created_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    subject = f"Voice note {created_at_str}"
    metadata = {"id": note_id, "created_at": created_at_str, "subject": subject}
    (note_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))

    deliver_via_lmtp(note_id, created_at, audio_bytes)

    return metadata


@app.get("/note/{note_id}")
def get_note(note_id: str):
    meta_path = DATA_DIR / note_id / "metadata.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="Note not found")
    return json.loads(meta_path.read_text())


@app.get("/note/{note_id}/audio")
def get_audio(note_id: str):
    audio_path = DATA_DIR / note_id / "audio.webm"
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio not found")
    return FileResponse(audio_path, media_type="audio/webm")
