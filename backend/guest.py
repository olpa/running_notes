import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def expired_guest_note_directories(
    notes_dir: Path, cutoff: datetime
) -> dict[str, Path]:
    expired = {}
    if not notes_dir.exists():
        return expired

    for note_dir in notes_dir.iterdir():
        if not note_dir.is_dir():
            continue
        note_id, created_at = _guest_note_identity(note_dir)
        if created_at <= cutoff:
            expired[note_id] = note_dir
    return expired


def _guest_note_identity(note_dir: Path) -> tuple[str, datetime]:
    try:
        metadata = json.loads((note_dir / "metadata.json").read_text())
        note_id = metadata["id"]
        if not isinstance(note_id, str) or not note_id:
            raise ValueError("invalid note id")
        created_at = datetime.fromisoformat(
            metadata["created_at"].replace("Z", "+00:00")
        )
        if created_at.tzinfo is None:
            raise ValueError("recording timestamp has no timezone")
        return note_id, created_at.astimezone(timezone.utc)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        logger.warning(
            "Invalid guest note metadata; using directory age for retention: %s",
            note_dir,
        )
        modified_at = datetime.fromtimestamp(note_dir.stat().st_mtime, timezone.utc)
        return note_dir.name, modified_at
