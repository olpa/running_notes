import subprocess
import unittest
from unittest.mock import patch

from audio import AudioConversionError, convert_webm_to_mp3


class AudioConversionTests(unittest.TestCase):
    @patch("audio.subprocess.run")
    def test_converts_to_small_speech_mp3(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, b"mp3-data", b"")

        result = convert_webm_to_mp3(b"webm-data")

        self.assertEqual(result, b"mp3-data")
        command = run.call_args.args[0]
        self.assertIn("libmp3lame", command)
        self.assertEqual(command[command.index("-ac") + 1], "1")
        self.assertEqual(command[command.index("-ar") + 1], "16000")
        self.assertEqual(command[command.index("-b:a") + 1], "48k")
        self.assertEqual(command[command.index("-id3v2_version") + 1], "0")
        self.assertEqual(run.call_args.kwargs["input"], b"webm-data")

    @patch("audio.subprocess.run")
    def test_rejects_invalid_audio(self, run):
        run.return_value = subprocess.CompletedProcess([], 1, b"", b"invalid")

        with self.assertRaises(AudioConversionError):
            convert_webm_to_mp3(b"not-a-recording")


if __name__ == "__main__":
    unittest.main()
