import subprocess

MP3_CHANNELS = 1
MP3_SAMPLE_RATE = 16_000
MP3_BITRATE = "48k"
TRANSCODE_TIMEOUT_SECONDS = 120


class AudioConversionError(RuntimeError):
    pass


def convert_webm_to_mp3(webm_bytes: bytes) -> bytes:
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
        "-f",
        "mp3",
        "pipe:1",
    ]
    try:
        result = subprocess.run(
            command,
            input=webm_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=TRANSCODE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AudioConversionError("Audio conversion failed") from exc

    if result.returncode != 0 or not result.stdout:
        raise AudioConversionError("Audio conversion failed")
    return result.stdout
