import unittest
from unittest.mock import Mock, patch
from mailbox import (
    DoveadmMailbox,
    MailboxError,
    MailReference,
    references_with_requested,
)

class MailReferenceTests(unittest.TestCase):
    def test_key_round_trip(self):
        ref = MailReference("08d95622e06c5b6a16000000db602fe0", 42)
        self.assertEqual(MailReference.from_key(ref.key), ref)
    def test_rejects_invalid_key(self):
        with self.assertRaises(ValueError): MailReference.from_key("bad")

    def test_prepends_requested_reference_outside_latest_list(self):
        latest = [MailReference("a" * 32, 1)]
        requested = MailReference("b" * 32, 2)
        references, parsed = references_with_requested(latest, requested.key)
        self.assertEqual([requested, *latest], references)
        self.assertEqual(requested, parsed)

    def test_invalid_requested_reference_leaves_list_unchanged(self):
        latest = [MailReference("a" * 32, 1)]
        references, parsed = references_with_requested(latest, "not-a-key")
        self.assertEqual(latest, references)
        self.assertIsNone(parsed)

class DoveadmMailboxTests(unittest.TestCase):
    def setUp(self): self.mailbox = DoveadmMailbox("http://dovecot/doveadm/v1", "secret")
    def test_latest_references_sorts_and_limits(self):
        self.mailbox._fetch = Mock(return_value=[
            {"mailbox-guid":"a"*32,"uid":"2","date.saved.unixtime":"20"},
            {"mailbox-guid":"a"*32,"uid":"1","date.saved.unixtime":"10"},
            {"mailbox-guid":"a"*32,"uid":"3","date.saved.unixtime":"20"}])
        self.assertEqual([r.uid for r in self.mailbox.latest_references("alice", 2)], [3, 2])

    def test_deletes_an_existing_message_by_guid_and_uid(self):
        reference = MailReference("a" * 32, 42)
        self.mailbox.fetch_message = Mock(return_value=b"message")
        self.mailbox._request = Mock(return_value=[])

        self.assertTrue(self.mailbox.delete_message("alice", reference))
        self.mailbox._request.assert_called_once_with(
            "expunge",
            {
                "user": "alice",
                "query": ["mailbox-guid", "a" * 32, "uid", "42"],
            },
        )

    def test_does_not_expunge_a_missing_message(self):
        reference = MailReference("a" * 32, 42)
        self.mailbox.fetch_message = Mock(return_value=None)
        self.mailbox._request = Mock(return_value=[])

        self.assertFalse(self.mailbox.delete_message("alice", reference))
        self.mailbox._request.assert_not_called()

    @patch("mailbox.httpx.post")
    def test_rejects_doveadm_error(self, post):
        response = Mock(); response.raise_for_status.return_value = None
        response.json.return_value = [["error", {"exitCode":75}, "mail"]]; post.return_value = response
        with self.assertRaises(MailboxError): self.mailbox.latest_references("alice", 100)
        self.assertTrue(post.call_args.kwargs["headers"]["Authorization"].startswith("X-Dovecot-API "))

if __name__ == "__main__": unittest.main()
