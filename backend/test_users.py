import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import database
import users


class ConfiguredPasswordTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_state_dir = database.STATE_DIR
        self.original_database_path = database.DATABASE_PATH
        self.original_mail_root = users.MAIL_ROOT
        database.STATE_DIR = Path(self.temp_dir.name) / "state"
        database.DATABASE_PATH = database.STATE_DIR / "users.db"
        users.MAIL_ROOT = Path(self.temp_dir.name) / "mail"
        database.initialize_database()

    def tearDown(self):
        database.STATE_DIR = self.original_state_dir
        database.DATABASE_PATH = self.original_database_path
        users.MAIL_ROOT = self.original_mail_root
        self.temp_dir.cleanup()

    @patch.object(users, "_provision_maildir")
    def test_applies_configured_password_to_existing_user(self, _provision):
        with patch.object(users, "_hash_imap_password", return_value="!initial"):
            user = users.create_user("guest@example.com", "initial")
        with patch.object(users, "_hash_imap_password", return_value="!configured"):
            users.set_imap_password(user["id"], "configured")

        with database.connect() as conn:
            password_hash = conn.execute(
                "SELECT imap_password_hash FROM users WHERE id = ?",
                (user["id"],),
            ).fetchone()["imap_password_hash"]
        self.assertEqual("!configured", password_hash)


if __name__ == "__main__":
    unittest.main()
