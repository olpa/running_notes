import unittest

from application_routes import safe_application_return_path


class ApplicationReturnPathTests(unittest.TestCase):
    def test_accepts_declared_application_routes(self):
        for path in (
            "/record",
            "/messages",
            "/messages/abc_123-XYZ",
            "/imap",
            "/account",
        ):
            with self.subTest(path=path):
                self.assertEqual(path, safe_application_return_path(path))

    def test_rejects_external_and_unknown_routes(self):
        for path in (
            None,
            "",
            "//example.com",
            "https://example.com/account",
            "/messages/key/extra",
            "/privacy.html",
            "/unknown",
        ):
            with self.subTest(path=path):
                self.assertEqual("/record", safe_application_return_path(path))


if __name__ == "__main__":
    unittest.main()
