import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SESSION_SECRET", "guest-route-test-secret")
os.environ.setdefault("GUEST_USER_PASSWORD", "guest-route-test-password")

import config
import database
import main
import notes_routes
import services
import users
from fastapi import HTTPException
from fastapi.testclient import TestClient
from guest import GuestUploadLimiter


class GuestRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.originals = (
            database.STATE_DIR,
            database.DATABASE_PATH,
            users.MAIL_ROOT,
            users.MAIL_UID,
            users.MAIL_GID,
            notes_routes.USER_STATE_DIR,
            services.guest_upload_limiter,
        )
        database.STATE_DIR = root / "state"
        database.DATABASE_PATH = database.STATE_DIR / "users.db"
        users.MAIL_ROOT = root / "mail"
        users.MAIL_UID = os.getuid()
        users.MAIL_GID = os.getgid()
        notes_routes.USER_STATE_DIR = root / "state" / "users"
        services.guest_upload_limiter = GuestUploadLimiter(10, 60, 600, 2)

    def tearDown(self):
        (
            database.STATE_DIR,
            database.DATABASE_PATH,
            users.MAIL_ROOT,
            users.MAIL_UID,
            users.MAIL_GID,
            notes_routes.USER_STATE_DIR,
            services.guest_upload_limiter,
        ) = self.originals
        self.temp_dir.cleanup()

    def test_guest_login_and_restricted_profile_endpoints(self):
        with TestClient(main.app, base_url="https://testserver") as client:
            self.assertEqual(204, client.post("/auth/guest").status_code)
            session = client.get("/api/me")
            self.assertEqual(200, session.status_code)
            self.assertTrue(session.json()["user"]["is_guest"])
            self.assertEqual(403, client.patch("/api/me", json={}).status_code)
            self.assertEqual(403, client.post("/api/me/imap-password").status_code)

    def test_guest_restrictions_do_not_apply_to_ordinary_users(self):
        from auth_deps import can_change_imap_password, require_writable_profile

        ordinary = {"is_guest": False}
        require_writable_profile(ordinary)
        self.assertTrue(can_change_imap_password(ordinary))
        with self.assertRaises(HTTPException):
            require_writable_profile({"is_guest": True})

    def test_guest_quota_multiplier_does_not_change_ordinary_limits(self):
        with (
            patch.object(config, "MAX_USER_NOTES_PER_DAY", 100),
            patch.object(config, "MAX_USER_NOTE_BYTES", 250),
            patch.object(config, "GUEST_QUOTA_FACTOR", 10),
        ):
            self.assertEqual(
                (100, 250), notes_routes.user_quota_limits({"is_guest": False})
            )
            self.assertEqual(
                (1_000, 2_500),
                notes_routes.user_quota_limits({"is_guest": True}),
            )


if __name__ == "__main__":
    unittest.main()
