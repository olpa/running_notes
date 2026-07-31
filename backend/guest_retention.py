import asyncio
import logging
import shutil
from datetime import datetime, timedelta, timezone

import config
import users
from guest import expired_guest_note_directories
from notes_routes import user_notes_dir
from users import (
    UserAlreadyExistsError,
    create_user,
    get_guest_user,
    mark_user_as_guest,
    set_imap_password,
)

logger = logging.getLogger(__name__)


def ensure_guest_user() -> None:
    if not config.GUEST_USER_PASSWORD:
        raise RuntimeError("GUEST_USER_PASSWORD is required")

    guest = get_guest_user()
    if guest is not None:
        set_imap_password(guest["id"], config.GUEST_USER_PASSWORD)
        return

    try:
        user = create_user(config.GUEST_USER_EMAIL, imap_password=config.GUEST_USER_PASSWORD)
    except UserAlreadyExistsError:
        # Another backend startup may have created the fixed account first.
        guest = get_guest_user()
        if guest is None:
            raise
        set_imap_password(guest["id"], config.GUEST_USER_PASSWORD)
        return
    mark_user_as_guest(user["id"])
    logger.info(
        "Guest user created user_id=%s email=%s",
        user["id"],
        user["email"],
    )


def remove_guest_maildir_messages(user_id: str, note_ids: set[str]) -> None:
    message_ids = {
        f"<note-{note_id}-audio@voiceinbox.local>".encode() for note_id in note_ids
    }
    maildir = users.MAIL_ROOT / user_id
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


def cleanup_expired_guest_recordings(now: datetime | None = None) -> None:
    guest = get_guest_user()
    if guest is None:
        return

    cutoff = (now or datetime.now(timezone.utc)) - timedelta(
        hours=config.GUEST_RETENTION_HOURS
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


async def guest_retention_loop() -> None:
    while True:
        await asyncio.sleep(config.GUEST_RETENTION_CHECK_SECONDS)
        try:
            await asyncio.to_thread(cleanup_expired_guest_recordings)
        except Exception:
            logger.exception("Guest retention cleanup failed")
