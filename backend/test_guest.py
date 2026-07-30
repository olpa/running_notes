import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from guest import expired_guest_note_directories


class GuestRetentionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.notes_dir = Path(self.temp_dir.name)
        self.now = datetime(2026, 7, 30, 12, tzinfo=timezone.utc)
        self.cutoff = self.now - timedelta(hours=24)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_selects_expired_note_from_valid_metadata(self):
        note_dir = self.notes_dir / "directory-name"
        note_dir.mkdir()
        (note_dir / "metadata.json").write_text(
            json.dumps(
                {
                    "id": "metadata-note-id",
                    "created_at": "2026-07-29T11:59:59Z",
                }
            )
        )

        self.assertEqual(
            {"metadata-note-id": note_dir},
            expired_guest_note_directories(self.notes_dir, self.cutoff),
        )

    def test_uses_directory_age_for_missing_or_invalid_metadata(self):
        missing = self._aged_note("missing-metadata", hours=25)
        invalid = self._aged_note("invalid-metadata", hours=26)
        (invalid / "metadata.json").write_text("{invalid")
        self._set_age(invalid, hours=26)
        recent = self._aged_note("recent-invalid-metadata", hours=23)
        (recent / "metadata.json").write_text("{}")
        self._set_age(recent, hours=23)

        self.assertEqual(
            {
                "missing-metadata": missing,
                "invalid-metadata": invalid,
            },
            expired_guest_note_directories(self.notes_dir, self.cutoff),
        )

    def _aged_note(self, name: str, hours: int) -> Path:
        note_dir = self.notes_dir / name
        note_dir.mkdir()
        self._set_age(note_dir, hours)
        return note_dir

    def _set_age(self, note_dir: Path, hours: int) -> None:
        timestamp = (self.now - timedelta(hours=hours)).timestamp()
        os.utime(note_dir, (timestamp, timestamp))


if __name__ == "__main__":
    unittest.main()
