import hashlib
import logging
import re
from pathlib import Path
from typing import Dict, Optional

from ruv_dl.storage import EpisodeDownload

log = logging.getLogger(__name__)

ROMAN_NUMERALS_TO_INT = {
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4,
    "V": 5,
    "VI": 6,
    "VII": 7,
    "VIII": 8,
    "IX": 9,
    "X": 10,
}

ROMAN_NUMERALS = set(ROMAN_NUMERALS_TO_INT.keys())

ROMAN_NUMERALS_REGEX = "("
for roman_numeral in ROMAN_NUMERALS:
    ROMAN_NUMERALS_REGEX += roman_numeral + "|"
ROMAN_NUMERALS_REGEX = ROMAN_NUMERALS_REGEX[:-1] + ")$"


def _make_show_dir(parent_dir: Path, show_name: str) -> Path:
    """
    Create a directory for a show in the parent directory.
    """
    show_dir = parent_dir / show_name
    show_dir.mkdir(parents=True, exist_ok=True)
    return show_dir


def _make_season_dir(show_dir: Path, season_num: int) -> Path:
    """
    Create a directory for a season in a show directory.
    """
    season_dir = show_dir / f"Season {season_num:02}"
    season_dir.mkdir(parents=True, exist_ok=True)
    return season_dir


def _format_show_name(
    show_name: str, season_num: int, show_num: Optional[int], original_title: str, quality: str
) -> str:
    """
    Format the show number into 'Show Name - SxxEyy' if show_num is not None.
    Otherwise, just return 'Show Name - Sxx - Original title'.
    """
    if show_num is not None:
        return f"{show_name} - S{season_num:02}E{show_num:02}{quality}"
    else:
        return f"{show_name} - S{season_num:02} - {original_title}{quality}"


def organize(downloads_dir: Path, destination_dir: Path, translations: Dict[str, str], dry_run=True):
    """
    Organize shows into seasons and directories.
    """
    destination_dir.mkdir(parents=True, exist_ok=True)

    partial_renames = []
    for episode in downloads_dir.iterdir():
        is_partial_rename = False
        log.info(f"Processing {episode}")
        show_regex_match = re.match(EpisodeDownload.file_name_regexp("mp4"), episode.name)
        if show_regex_match is None:
            log.warning(f"Skipping {episode} (no regex match)")
            continue
        program_name_is, episode_name, program_name_en, quality = show_regex_match.groups()
        if program_name_en == "None":
            if program_name_is in translations:
                program_name_en = translations[program_name_is]
                log.info(f"Foreign title translation {program_name_en}")
            else:
                log.warning(f"Skipping {episode} (no foreign title)")
                continue
        season_num = 1
        roman_numeral_regex_match = re.search(ROMAN_NUMERALS_REGEX, program_name_en)
        if roman_numeral_regex_match is not None:
            roman_numeral = roman_numeral_regex_match.group(0)
            season_num = ROMAN_NUMERALS_TO_INT[roman_numeral]
            program_name_en = program_name_en.replace(roman_numeral_regex_match.group(0), "").strip()
        show_num: Optional[int] = None
        try:
            show_num = int(episode_name.split(" ")[1])
        except (IndexError, ValueError):
            is_partial_rename = True

        show_dir = _make_show_dir(destination_dir, program_name_en)
        season_dir = _make_season_dir(show_dir, season_num)
        show_name = _format_show_name(program_name_en, season_num, show_num, episode_name, quality)
        show_path = season_dir / (show_name + ".mp4")
        if show_path.exists():
            if hashlib.md5(episode.read_bytes()).hexdigest() == hashlib.md5(show_path.read_bytes()).hexdigest():
                log.warning(f"Skipping {episode} (checksum matches)")
                continue
        if is_partial_rename:
            partial_renames.append(str(show_path))
        if dry_run:
            log.info(f"Would rename {episode} to {show_path}")
        else:
            episode.rename(show_path)
    print("Partial renames:")
    for episode in partial_renames:
        print(episode)
