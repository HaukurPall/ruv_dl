import shutil
import signal
import sys
from functools import partial
from pathlib import Path
from typing import List, Optional

import ffpb
from tqdm import tqdm


class FFmpegNotInstalledError(Exception):
    """Raised when ffmpeg is not installed on the system."""

    pass


def _check_ffmpeg_installed() -> None:
    """Check if ffmpeg is installed and raise FFmpegNotInstalledError if not."""
    if shutil.which("ffmpeg") is None:
        raise FFmpegNotInstalledError(
            "ffmpeg is not installed or not found in PATH. Please install ffmpeg to use this functionality."
        )


QUALITIES_STR = ["1080p", "720p", "480p"]


def qualities_str_to_int(quality_str: str) -> int:
    return int(quality_str[:-1])


def download_m3u8_file(
    m3u8_url: str,
    stream_num: int,
    output_file: Path,
    subtitle_file: Optional[Path] = None,
    audio_only: bool = False,
) -> bool:
    _check_ffmpeg_installed()
    ffmpeg_command = _create_ffmpeg_download_command(
        m3u8_url, stream_num, output_file=output_file, subtitle_file=subtitle_file, audio_only=audio_only
    )
    retval = ffpb.main(
        argv=ffmpeg_command,
        stream=sys.stderr,
        encoding="utf-8",
        tqdm=partial(tqdm, leave=False),
    )
    if retval != 0:
        if output_file.exists():
            output_file.unlink()
        if retval == signal.SIGINT + 128:
            raise KeyboardInterrupt
        return False
    return True


def check_mp4_integrity(file_path: Path) -> bool:
    _check_ffmpeg_installed()
    ffmpeg_command = _create_integrity_check_ffmpeg_command(file_path)
    retval = ffpb.main(
        argv=ffmpeg_command,
        stream=sys.stderr,
        encoding="utf-8",
        tqdm=partial(tqdm, leave=False),
    )
    if retval != 0:
        file_path.unlink()
        if retval == signal.SIGINT + 128:
            raise KeyboardInterrupt
        return False
    return True


def _create_integrity_check_ffmpeg_command(file_path: Path) -> List[str]:
    return [
        # fmt: off
        "-i",
        str(file_path),
        "-map",
        "0:1",
        "-f",
        "null",
        "-",
        # fmt: on
    ]


def _create_ffmpeg_download_command(
    url: str, stream_num: int, output_file: Path, subtitle_file: Optional[Path] = None, audio_only: bool = False
):
    """Create the ffmpeg command required to download a specific stream from a m3u8 playlist."""
    cmd = [
        # fmt: off
        "-i",
        url,
    ]
    if subtitle_file:
        cmd.extend(["-i", str(subtitle_file)])

    if audio_only:
        # Audio-only mode: only map audio stream
        cmd.extend(["-map", f"0:a:{stream_num}"])
    else:
        # Normal mode: map both video and audio
        cmd.extend(
            [
                "-map",
                f"0:v:{stream_num}",  # First input file, select stream_num from video streams
                "-map",
                f"0:a:{stream_num}",  # Same for audio
            ]
        )

    if subtitle_file:
        cmd.extend(["-map", "1:0"])

    if audio_only:
        # Audio-only mode: only copy audio codec
        cmd.extend(["-c:a", "copy"])
    else:
        # Normal mode: copy both video and audio codecs
        cmd.extend(
            [
                "-c:v",
                "copy",
                "-c:a",
                "copy",
            ]
        )

    if subtitle_file:
        cmd.extend(["-c:s", "mov_text", "-metadata:s:s:0", "language=isl"])

    cmd.append(str(output_file))
    return cmd
