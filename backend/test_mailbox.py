import unittest
from unittest.mock import Mock, patch
from mailbox import DoveadmMailbox, MailboxError, MailReference

class MailReferenceTests(unittest.TestCase):
    def test_key_round_trip(self):
        ref = MailReference("08d95622e06c5b6a16000000db602fe0", 42)
        self.assertEqual(MailReference.from_key(ref.key), ref)
    def test_rejects_invalid_key(self):
        with self.assertRaises(ValueError): MailReference.from_key("bad")

class DoveadmMailboxTests(unittest.TestCase):
    def setUp(self): self.mailbox = DoveadmMailbox("http://dovecot/doveadm/v1", "secret")
    def test_latest_references_sorts_and_limits(self):
        self.mailbox._fetch = Mock(return_value=[
            {"mailbox-guid":"a"*32,"uid":"2","date.saved.unixtime":"20"},
            {"mailbox-guid":"a"*32,"uid":"1","date.saved.unixtime":"10"},
            {"mailbox-guid":"a"*32,"uid":"3","date.saved.unixtime":"20"}])
        self.assertEqual([r.uid for r in self.mailbox.latest_references("alice", 2)], [3, 2])
    @patch("mailbox.httpx.post")
    def test_rejects_doveadm_error(self, post):
        response = Mock(); response.raise_for_status.return_value = None
        response.json.return_value = [["error", {"exitCode":75}, "mail"]]; post.return_value = response
        with self.assertRaises(MailboxError): self.mailbox.latest_references("alice", 100)
        self.assertTrue(post.call_args.kwargs["headers"]["Authorization"].startswith("X-Dovecot-API "))

if __name__ == "__main__": unittest.main()
