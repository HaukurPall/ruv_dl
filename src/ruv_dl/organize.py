import hashlib
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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


def _format_show_name(
    show_name: str, season_num: int, show_num_tuple: Optional[Tuple[int, int]], original_title: str, quality: str
) -> str:
    """
    Format the show number into 'Show Name - SxxEyy' if show_num_tuple is not None and has the same value.
    Format the show number into 'Show Name - SxxEyy-Ezz' if show_num_tuple is not None and has different values.
    Otherwise, just return 'Show Name - Sxx - Original title'.
    """
    if show_num_tuple is not None:
        show_num_start, show_num_end = show_num_tuple
        if show_num_start == show_num_end:
            return f"{show_name} - S{season_num:02}E{show_num_start:02}{quality}"
        else:
            return f"{show_name} - S{season_num:02}E{show_num_start:02}-E{show_num_end:02}{quality}"
    else:
        return f"{show_name} - S{season_num:02} - {original_title}{quality}"


def _guess_show_num(episode_name: str) -> Optional[Tuple[int, int]]:
    """
    Guess the show number from the episode name.
    Supports:
        Exx-Eyy
        Exx
        YYYYY show_num ZZZZZZZZ ...
    Returns:
        (show_num_start, show_num_end) where show_num_end is equal show_num_start if only one show number is present.
        if no show number is present, returns None.
    """
    one_episode_regexp = re.compile(r"^E(?P<show_num_start>\d+)$")
    two_episode_regexp = re.compile(r"^E(?P<show_num_start>\d+)-E(?P<show_num_end>\d+)$")
    match = two_episode_regexp.match(episode_name)
    if match:
        return (
            int(match.group("show_num_start")),
            int(match.group("show_num_end")),
        )
    match = one_episode_regexp.match(episode_name)
    if match:
        return (int(match.group("show_num_start")), int(match.group("show_num_start")))
    try:
        show_num = int(episode_name.split(" ")[1])
        return (show_num, show_num)
    except (IndexError, ValueError):
        return None


def organize(episodes_to_organize: List[Path], destination_dir: Path, translations: Dict[str, str], dry_run=True):
    """
    Organize shows into seasons and directories.
    """

    def map_path(show, destination_dir: Path, translations: Dict[str, str]) -> Optional[Path]:
        log.info(f"Processing {show}")
        show_regex_match = re.match(EpisodeDownload.file_name_regexp("mp4"), show.name)
        if show_regex_match is None:
            log.warning(f"Skipping {show} (no regex match)")
            return None
        program_name_is, episode_name, program_name_en, quality = show_regex_match.groups()
        if program_name_en == "None":
            if program_name_is in translations:
                program_name_en = translations[program_name_is]
                log.info(f"Foreign title translation {program_name_en}")
            else:
                log.warning(f"Skipping {show} (no foreign title)")
                return None
        season_num = 1
        roman_numeral_regex_match = re.search(ROMAN_NUMERALS_REGEX, program_name_en)
        if roman_numeral_regex_match is not None:
            roman_numeral = roman_numeral_regex_match.group(0)
            season_num = ROMAN_NUMERALS_TO_INT[roman_numeral]
            program_name_en = program_name_en.replace(roman_numeral_regex_match.group(0), "").strip()

        season_dir = destination_dir / program_name_en / f"Season {season_num:02}"
        show_name = _format_show_name(program_name_en, season_num, _guess_show_num(episode_name), episode_name, quality)
        return season_dir / (show_name + ".mp4")

    path_mapping = {
        episode_to_organize: map_path(episode_to_organize, destination_dir, translations)
        for episode_to_organize in episodes_to_organize
    }
    for old_path, new_path in path_mapping.items():
        if new_path is None:
            continue
        if new_path.exists():
            log.warning(f"{new_path} is already in {destination_dir}. Not moving.")
            if hashlib.md5(new_path.read_bytes()).hexdigest() == hashlib.md5(old_path.read_bytes()).hexdigest():
                log.warning(f"{new_path} has same checksum as {old_path}")
            else:
                log.warning(f"{new_path} does not have the same checksum as {old_path}")
            continue
        if dry_run:
            log.warning(f"Would move {old_path} to {new_path}")
        else:
            new_path.parent.mkdir(parents=True, exist_ok=True)
            log.info(f"Moving {old_path} to {new_path}")
            old_path.rename(new_path)
