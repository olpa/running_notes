import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from audio import (
    AudioConversionError,
    AudioTooLongError,
    InvalidAudioRange,
    convert_webm_to_mp3,
    convert_webm_to_mp3_with_duration,
    format_audio_duration,
    parse_audio_byte_range,
)


class AudioConversionTests(unittest.TestCase):
    @patch("audio.subprocess.run")
    def test_converts_to_small_speech_mp3(self, run):
        def create_output(command, **_kwargs):
            if command[0] == "ffmpeg":
                Path(command[-1]).write_bytes(b"mp3-data")
                return subprocess.CompletedProcess(command, 0, b"", b"")
            return subprocess.CompletedProcess(command, 0, b"30.500000\n", b"")

        run.side_effect = create_output

        result = convert_webm_to_mp3(b"webm-data")

        self.assertEqual(result, b"mp3-data")
        command = run.call_args_list[0].args[0]
        self.assertIn("libmp3lame", command)
        self.assertEqual(command[command.index("-ac") + 1], "1")
        self.assertEqual(command[command.index("-ar") + 1], "16000")
        self.assertEqual(command[command.index("-b:a") + 1], "48k")
        self.assertEqual(command[command.index("-id3v2_version") + 1], "0")
        self.assertEqual(run.call_args_list[0].kwargs["input"], b"webm-data")
        self.assertEqual(
            run.call_args_list[0].kwargs["stdout"], subprocess.DEVNULL
        )

    @patch("audio.subprocess.run")
    def test_returns_measured_duration_with_converted_audio(self, run):
        def create_output(command, **_kwargs):
            if command[0] == "ffmpeg":
                Path(command[-1]).write_bytes(b"mp3-data")
                return subprocess.CompletedProcess(command, 0, b"", b"")
            return subprocess.CompletedProcess(command, 0, b"8.125000\n", b"")

        run.side_effect = create_output

        self.assertEqual(
            convert_webm_to_mp3_with_duration(b"webm-data"),
            (b"mp3-data", 8.125),
        )

    def test_formats_audio_duration_for_email(self):
        self.assertEqual(format_audio_duration(0.1), "00:01")
        self.assertEqual(format_audio_duration(8.125), "00:09")
        self.assertEqual(format_audio_duration(60), "01:00")

    @patch("audio.subprocess.run")
    def test_rejects_recordings_over_backend_tolerance(self, run):
        def create_overlong_output(command, **_kwargs):
            if command[0] == "ffmpeg":
                Path(command[-1]).write_bytes(b"mp3-data")
                return subprocess.CompletedProcess(command, 0, b"", b"")
            return subprocess.CompletedProcess(command, 0, b"33.100000\n", b"")

        run.side_effect = create_overlong_output

        with self.assertRaises(AudioTooLongError):
            convert_webm_to_mp3(b"webm-data")

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
