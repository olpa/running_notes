import tempfile
import unittest
from itertools import islice
from pathlib import Path
from unittest.mock import patch

import database
import users
from oauth_identities import get_or_create_oauth_user


class OAuthIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_dir = Path(self.temp_dir.name) / "state"
        self.mail_root = Path(self.temp_dir.name) / "mail"
        self.original_state_dir = database.STATE_DIR
        self.original_database_path = database.DATABASE_PATH
        self.original_mail_root = users.MAIL_ROOT
        database.STATE_DIR = self.state_dir
        database.DATABASE_PATH = self.state_dir / "users.db"
        users.MAIL_ROOT = self.mail_root
        database.initialize_database()
        self.hash_patch = patch.object(users, "_hash_imap_password", return_value="!test")
        self.maildir_patch = patch.object(users, "_provision_maildir")
        self.hash_patch.start()
        self.maildir_patch.start()

    def tearDown(self):
        self.maildir_patch.stop()
        self.hash_patch.stop()
        database.STATE_DIR = self.original_state_dir
        database.DATABASE_PATH = self.original_database_path
        users.MAIL_ROOT = self.original_mail_root
        self.temp_dir.cleanup()

    def test_provider_subject_is_identity_even_when_emails_match(self):
        google = get_or_create_oauth_user(
            "google", "google-sub", "alice@example.com", True, "notes.example"
        )
        same_google = get_or_create_oauth_user(
            "google", "google-sub", "alice@example.com", True, "notes.example"
        )
        microsoft = get_or_create_oauth_user(
            "microsoft",
            "microsoft-sub",
            "alice@example.com",
            True,
            "notes.example",
        )

        self.assertEqual(google["id"], same_google["id"])
        self.assertNotEqual(google["id"], microsoft["id"])
        self.assertNotEqual(google["imap_username"], microsoft["imap_username"])
        self.assertRegex(google["imap_username"], r"^alice-\d{4}@notes\.example$")
        self.assertRegex(microsoft["imap_username"], r"^alice-\d{4}@notes\.example$")

        reset = users.reset_imap_password(google["imap_username"])
        self.assertEqual(google["id"], reset["id"])
        self.assertEqual("alice@example.com", reset["email"])
        self.assertEqual(google["imap_username"], reset["imap_username"])

    def test_alias_collision_uses_next_suffix_for_same_local_part(self):
        candidates = list(
            islice(
                users._oauth_imap_usernames(
                    "alice@example.com", "google", "subject", "notes.example"
                ),
                2,
            )
        )
        with database.connect() as conn:
            conn.execute(
                """
                INSERT INTO users (
                    id, provider_email, created_at, status, imap_username,
                    imap_password_hash, is_guest
                )
                VALUES ('blocker', 'other@example.com', '2026-01-01T00:00:00Z',
                        'active', ?, '!test', 0)
                """,
                (candidates[0],),
            )

        user = get_or_create_oauth_user(
            "google", "subject", "alice@example.com", True, "notes.example"
        )
        self.assertEqual(candidates[1], user["imap_username"])

    def test_clean_schema_names_provider_email_explicitly(self):
        with database.connect() as conn:
            user_columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(users)")
            }
            identity_columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(oauth_identities)")
            }

        self.assertIn("provider_email", user_columns)
        self.assertNotIn("email", user_columns)
        self.assertIn("provider_email", identity_columns)
        self.assertNotIn("email", identity_columns)


if __name__ == "__main__":
    unittest.main()
