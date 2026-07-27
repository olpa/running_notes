import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from audio import (
    AudioConversionError,
    InvalidAudioRange,
    convert_webm_to_mp3,
    parse_audio_byte_range,
)


class AudioConversionTests(unittest.TestCase):
    @patch("audio.subprocess.run")
    def test_converts_to_small_speech_mp3(self, run):
        def create_output(command, **_kwargs):
            Path(command[-1]).write_bytes(b"mp3-data")
            return subprocess.CompletedProcess(command, 0, b"", b"")

        run.side_effect = create_output

        result = convert_webm_to_mp3(b"webm-data")

        self.assertEqual(result, b"mp3-data")
        command = run.call_args.args[0]
        self.assertIn("libmp3lame", command)
        self.assertEqual(command[command.index("-ac") + 1], "1")
        self.assertEqual(command[command.index("-ar") + 1], "16000")
        self.assertEqual(command[command.index("-b:a") + 1], "48k")
        self.assertEqual(command[command.index("-id3v2_version") + 1], "0")
        self.assertEqual(run.call_args.kwargs["input"], b"webm-data")
        self.assertEqual(run.call_args.kwargs["stdout"], subprocess.DEVNULL)

    @patch("audio.subprocess.run")
    def test_rejects_invalid_audio(self, run):
        run.return_value = subprocess.CompletedProcess([], 1, b"", b"invalid")

        with self.assertRaises(AudioConversionError):
            convert_webm_to_mp3(b"not-a-recording")

    def test_parses_audio_byte_ranges(self):
        self.assertEqual(parse_audio_byte_range("bytes=2-5", 10), (2, 5))
        self.assertEqual(parse_audio_byte_range("bytes=7-", 10), (7, 9))
        self.assertEqual(parse_audio_byte_range("bytes=-4", 10), (6, 9))
        self.assertEqual(parse_audio_byte_range("bytes=2-99", 10), (2, 9))

    def test_rejects_invalid_audio_byte_ranges(self):
        for value in ("items=0-1", "bytes=10-", "bytes=5-2", "bytes=0-1,3-4"):
            with self.subTest(value=value):
                with self.assertRaises(InvalidAudioRange):
                    parse_audio_byte_range(value, 10)


if __name__ == "__main__":
    unittest.main()
