import json
import logging
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


class GuestUploadRateLimited(RuntimeError):
    pass


class GuestUploadBusy(RuntimeError):
    pass


class GuestUploadLimiter:
    def __init__(
        self,
        per_session_limit: int,
        global_limit: int,
        window_seconds: int,
        concurrent_limit: int,
    ):
        self.per_session_limit = per_session_limit
        self.global_limit = global_limit
        self.window_seconds = window_seconds
        self.concurrent_limit = concurrent_limit
        self._global_attempts: deque[float] = deque()
        self._session_attempts: dict[str, deque[float]] = defaultdict(deque)
        self._active = 0

    def acquire(self, session_key: str, now: float) -> None:
        cutoff = now - self.window_seconds
        self._prune(self._global_attempts, cutoff)
        self._prune_sessions(cutoff)
        session_attempts = self._session_attempts.get(session_key, deque())
        if len(session_attempts) >= self.per_session_limit:
            raise GuestUploadRateLimited("Guest session recording limit exceeded")
        if len(self._global_attempts) >= self.global_limit:
            raise GuestUploadRateLimited("Guest recording service is rate limited")
        if self._active >= self.concurrent_limit:
            raise GuestUploadBusy("Guest recording service is busy")
        session_attempts.append(now)
        self._session_attempts[session_key] = session_attempts
        self._global_attempts.append(now)
        self._active += 1

    def release(self) -> None:
        if self._active < 1:
            raise RuntimeError("Guest upload limiter released without acquisition")
        self._active -= 1

    @staticmethod
    def _prune(attempts: deque[float], cutoff: float) -> None:
        while attempts and attempts[0] <= cutoff:
            attempts.popleft()

    def _prune_sessions(self, cutoff: float) -> None:
        for session_key, attempts in list(self._session_attempts.items()):
            self._prune(attempts, cutoff)
            if not attempts:
                del self._session_attempts[session_key]


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
