import asyncio
import json
import logging
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

import config
import services
from audio import (
    AudioConversionError,
    AudioTooLongError,
    convert_webm_to_mp3_with_duration,
    format_audio_duration,
)
from auth_deps import current_active_user, is_guest_user
from guest import GuestUploadBusy, GuestUploadRateLimited
from lmtp_delivery import deliver_via_lmtp

logger = logging.getLogger(__name__)
router = APIRouter()

USER_STATE_DIR = config.STATE_DIR / "users"


def note_id_for(created_at: datetime) -> str:
    timestamp = created_at.strftime("%Y%m%dT%H%M%SZ")
    return f"note-{timestamp}-{secrets.token_hex(4)}"


def user_notes_dir(user_id: str) -> Path:
    return USER_STATE_DIR / user_id / "notes"


def note_dir_for(user_id: str, note_id: str) -> Path:
    return user_notes_dir(user_id) / note_id


def validate_upload_type(file: UploadFile) -> None:
    media_type = (file.content_type or "").split(";", 1)[0].strip().lower()
    if media_type not in config.ACCEPTED_AUDIO_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported audio type")


async def read_limited_upload(
    file: UploadFile, max_bytes: int = config.MAX_UPLOAD_BYTES
) -> bytes:
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


def user_quota_limits(user: dict) -> tuple[int, int]:
    quota_factor = config.GUEST_QUOTA_FACTOR if is_guest_user(user) else 1
    return (
        config.MAX_USER_NOTES_PER_DAY * quota_factor,
        config.MAX_USER_NOTE_BYTES * quota_factor,
    )


def enforce_user_quota(user: dict, upload_bytes: int, created_at: datetime) -> None:
    daily_note_count, total_bytes = user_note_usage(
        user_notes_dir(user["id"]), created_at
    )
    note_limit, byte_limit = user_quota_limits(user)
    if daily_note_count >= note_limit:
        raise HTTPException(status_code=429, detail="Daily note quota exceeded")
    if total_bytes + upload_bytes > byte_limit:
        raise HTTPException(status_code=403, detail="Storage quota exceeded")


@router.post("/api/record", status_code=201)
async def record(request: Request, file: UploadFile):
    user = current_active_user(request)
    media_type = file.content_type or ""
    validate_upload_type(file)

    guest_slot = False
    upload_limit = config.MAX_UPLOAD_BYTES
    if is_guest_user(user):
        session_key = str(request.session.get("login_nonce", "guest"))
        try:
            services.guest_upload_limiter.acquire(session_key, time.monotonic())
            guest_slot = True
        except GuestUploadRateLimited as exc:
            raise HTTPException(
                status_code=429,
                detail=str(exc),
                headers={"Retry-After": str(config.GUEST_UPLOAD_WINDOW_SECONDS)},
            ) from exc
        except GuestUploadBusy as exc:
            raise HTTPException(
                status_code=503,
                detail=str(exc),
                headers={"Retry-After": "5"},
            ) from exc
        upload_limit = config.MAX_GUEST_UPLOAD_BYTES

    try:
        return await process_recording(user, file, media_type, upload_limit)
    finally:
        if guest_slot:
            services.guest_upload_limiter.release()


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


@router.get("/api/note/{note_id}")
def get_note(note_id: str, request: Request):
    user = current_active_user(request)
    meta_path = note_dir_for(user["id"], note_id) / "metadata.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="Note not found")
    return json.loads(meta_path.read_text())


@router.get("/api/note/{note_id}/audio")
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
