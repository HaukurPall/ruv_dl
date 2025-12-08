import signal
import sys
from functools import partial
from pathlib import Path
from typing import List, Optional, Tuple

import ffpb
from tqdm import tqdm

QUALITIES_STR = ["1080p", "720p", "480p"]


def qualities_str_to_int(quality_str: str) -> int:
    return int(quality_str[:-1])


def download_m3u8_file(
    m3u8_url: str,
    stream_num: int,
    output_file: Path,
    subtitle_file: Optional[Path] = None,
) -> bool:
    ffmpeg_command = _create_ffmpeg_download_command(
        m3u8_url, stream_num, output_file=output_file, subtitle_file=subtitle_file
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


def split_mp4_in_two(file_path: Path, split_at_time_sec: str, first_chunk: Path, second_chunk: Path) -> bool:
    """Split an mp4 file into two files at the given time."""
    commands = _create_ffmpeg_split_in_two_commands(
        file_path,
        split_at_time_sec=split_at_time_sec,
        first_chunk=first_chunk,
        second_chunk=second_chunk,
    )
    for command in commands:
        retval = ffpb.main(
            argv=command,
            stream=sys.stderr,
            encoding="utf-8",
            tqdm=partial(tqdm, leave=False),
        )
        if retval != 0:
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


def _create_ffmpeg_download_command(url: str, stream_num: int, output_file: Path, subtitle_file: Optional[Path] = None):
    """Create the ffmpeg command required to download a specific stream from a m3u8 playlist."""
    cmd = [
        # fmt: off
        "-i",
        url,
    ]
    if subtitle_file:
        cmd.extend(["-i", str(subtitle_file)])

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


def _create_ffmpeg_split_in_two_commands(
    filepath: Path, split_at_time_sec: str, first_chunk: Path, second_chunk: Path
) -> Tuple[List[str], List[str]]:
    return (
        _create_ffmpeg_split_command(
            filepath=filepath,
            start_time_sec="00:00",
            duration_sec=split_at_time_sec,
            output=first_chunk,
        ),
        _create_ffmpeg_split_command(
            filepath=filepath,
            start_time_sec=split_at_time_sec,
            duration_sec=None,
            output=second_chunk,
        ),
    )


def _create_ffmpeg_split_command(
    filepath: Path, start_time_sec: str, duration_sec: Optional[str], output: Path
) -> List[str]:
    """Create the ffmpeg command required to split a file into two separate files."""
    # $ ffmpeg -i source.m4v -ss 0 -t 593.3 -c copy part1.m4v
    # $ ffmpeg -i source.m4v -ss 593.3 -t 551.64 -c copy part2.m4v
    # $ ffmpeg -i source.m4v -ss 1144.94 -t 581.25 -c copy part3.m4v

    # From the timestamp to the end
    if duration_sec is None:
        return [
            # fmt: off
            "-i",
            str(filepath),
            "-ss",
            str(start_time_sec),  # Accurate seek
            "-c",
            "copy",  # Copy the encoding
            str(output),
            # fmt: on
        ]
    # From timestamp to duration
    return [
        # fmt: off
        "-i",
        str(filepath),
        "-ss",
        str(start_time_sec),  # Accurate seek
        "-t",
        str(duration_sec),
        "-c",
        "copy",  # Copy the encoding
        str(output),
        # fmt: on
    ]
