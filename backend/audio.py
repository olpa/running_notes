import subprocess
import tempfile
from pathlib import Path

MP3_CHANNELS = 1
MP3_SAMPLE_RATE = 16_000
MP3_BITRATE = "48k"
MAX_AUDIO_DURATION_SECONDS = 33
TRANSCODE_TIMEOUT_SECONDS = 120


class AudioConversionError(RuntimeError):
    pass


class AudioTooLongError(AudioConversionError):
    pass


class InvalidAudioRange(ValueError):
    pass


def convert_webm_to_mp3(webm_bytes: bytes) -> bytes:
    with tempfile.TemporaryDirectory(prefix="running-notes-audio-") as temp_dir:
        output_path = Path(temp_dir) / "audio.mp3"
        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-i",
            "pipe:0",
            "-map",
            "0:a:0",
            "-vn",
            "-ac",
            str(MP3_CHANNELS),
            "-ar",
            str(MP3_SAMPLE_RATE),
            "-codec:a",
            "libmp3lame",
            "-b:a",
            MP3_BITRATE,
            "-id3v2_version",
            "0",
            "-write_id3v1",
            "0",
            "-threads",
            "1",
            str(output_path),
        ]
        try:
            result = subprocess.run(
                command,
                input=webm_bytes,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                check=False,
                timeout=TRANSCODE_TIMEOUT_SECONDS,
            )
            mp3_bytes = output_path.read_bytes() if result.returncode == 0 else b""
            if mp3_bytes:
                duration = _probe_audio_duration(output_path)
                if duration > MAX_AUDIO_DURATION_SECONDS:
                    raise AudioTooLongError("Audio recording is too long")
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AudioConversionError("Audio conversion failed") from exc

    if not mp3_bytes:
        raise AudioConversionError("Audio conversion failed")
    return mp3_bytes


def _probe_audio_duration(audio_path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=TRANSCODE_TIMEOUT_SECONDS,
    )
    try:
        duration = float(result.stdout.strip())
    except ValueError as exc:
        raise AudioConversionError("Could not determine audio duration") from exc
    if result.returncode != 0 or duration <= 0:
        raise AudioConversionError("Could not determine audio duration")
    return duration


def parse_audio_byte_range(value: str, total_bytes: int) -> tuple[int, int]:
    if total_bytes < 1 or not value.startswith("bytes="):
        raise InvalidAudioRange(value)
    specification = value.removeprefix("bytes=")
    if "," in specification or "-" not in specification:
        raise InvalidAudioRange(value)

    start_text, end_text = specification.split("-", 1)
    try:
        if not start_text:
            suffix_length = int(end_text)
            if suffix_length < 1:
                raise InvalidAudioRange(value)
            start = max(total_bytes - suffix_length, 0)
            return start, total_bytes - 1

        start = int(start_text)
        end = int(end_text) if end_text else total_bytes - 1
    except ValueError as exc:
        raise InvalidAudioRange(value) from exc

    if start < 0 or start >= total_bytes or end < start:
        raise InvalidAudioRange(value)
    return start, min(end, total_bytes - 1)
