import signal
import sys
from functools import partial
from pathlib import Path
from typing import List

import ffpb
from tqdm import tqdm

QUALITIES_INT_TO_STR = {0: "240p", 1: "360p", 2: "480p", 3: "720p", 4: "1080p"}
QUALITIES_STR_TO_INT = {value: key for key, value in QUALITIES_INT_TO_STR.items()}


def download_m3u8_file(m3u8_url: str, stream_num: int, output_file: Path) -> bool:
    ffmpeg_command = _create_ffmpeg_download_command(m3u8_url, stream_num, output_file=output_file)
    retval = ffpb.main(argv=ffmpeg_command, stream=sys.stderr, encoding="utf-8", tqdm=partial(tqdm, leave=False))
    if retval != 0:
        if output_file.exists():
            output_file.unlink()
        if retval == signal.SIGINT + 128:
            raise KeyboardInterrupt
        return False
    return True


def check_mp4_integrity(file_path: Path) -> bool:
    ffmpeg_command = _create_integrity_check_ffmpeg_command(file_path)
    retval = ffpb.main(argv=ffmpeg_command, stream=sys.stderr, encoding="utf-8", tqdm=partial(tqdm, leave=False))
    if retval != 0:
        file_path.unlink()
        if retval == signal.SIGINT + 128:
            raise KeyboardInterrupt
        return False
    return True


def _create_integrity_check_ffmpeg_command(file_path: Path) -> List[str]:
    return [
        # fmt: off
        "-i", str(file_path),
        "-map", "0:1",
        "-f", "null", "-"
        # fmt: on
    ]


def _create_ffmpeg_download_command(url: str, stream_num: int, output_file: Path):
    """Create the ffmpeg command required to download a specific stream from a m3u8 playlist."""
    return [
        # fmt: off
        "-i", url,
        "-map", f"0:v:{stream_num}",  # First input file, select stream_num from video streams
        "-map", f"0:a:{stream_num}",  # Same for audio
        "-codec", "copy",  # No re-encoding
        # This last line does nothing, since subtitles are burnt in.
        "-codec:s", "srt",  # Except for subtitles due to some caveats in ffmpeg subtitle handling.
        str(output_file)
        # fmt: on
    ]
