import unittest

from oauth import oauth_claims_options


class OAuthClaimsOptionsTests(unittest.TestCase):
    def test_microsoft_accepts_issuer_for_token_tenant(self):
        tenant_id = "9188040d-6c67-4c5b-b112-36a304b66dad"
        validate = oauth_claims_options("microsoft")["iss"]["validate"]

        self.assertTrue(
            validate(
                {"tid": tenant_id},
                f"https://login.microsoftonline.com/{tenant_id}/v2.0",
            )
        )

    def test_microsoft_rejects_issuer_for_different_tenant(self):
        validate = oauth_claims_options("microsoft")["iss"]["validate"]

        self.assertFalse(
            validate(
                {"tid": "9188040d-6c67-4c5b-b112-36a304b66dad"},
                "https://login.microsoftonline.com/"
                "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee/v2.0",
            )
        )

    def test_microsoft_rejects_invalid_or_missing_tenant(self):
        validate = oauth_claims_options("microsoft")["iss"]["validate"]

        self.assertFalse(
            validate(
                {},
                "https://login.microsoftonline.com/common/v2.0",
            )
        )
        self.assertFalse(
            validate(
                {"tid": "../common"},
                "https://login.microsoftonline.com/../common/v2.0",
            )
        )

    def test_google_uses_metadata_issuer_validation(self):
        self.assertIsNone(oauth_claims_options("google"))


if __name__ == "__main__":
    unittest.main()
