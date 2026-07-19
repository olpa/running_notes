import unittest
from email.message import EmailMessage
from messages import extract_audio, parse_message_summary

class MessageParsingTests(unittest.TestCase):
    def setUp(self):
        message = EmailMessage()
        message["Subject"] = "Voice note"
        message["From"] = "Sender <sender@example.com>"
        message["Date"] = "Sun, 19 Jul 2026 12:00:00 +0000"
        message.set_content("A short message.\n")
        message.add_attachment(b"webm-data", maintype="audio", subtype="webm", filename="note.webm")
        self.raw = message.as_bytes()
    def test_summary(self):
        result = parse_message_summary(self.raw, "key")
        self.assertEqual(result["subject"], "Voice note")
        self.assertEqual(result["preview"], "A short message.")
        self.assertEqual(result["audio"][0]["content_type"], "audio/webm")
    def test_extract_audio(self):
        self.assertEqual(extract_audio(self.raw, 0), (b"webm-data", "audio/webm", "note.webm"))
        self.assertIsNone(extract_audio(self.raw, 1))

if __name__ == "__main__": unittest.main()
