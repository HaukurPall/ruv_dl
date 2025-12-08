import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, cast

import httpx
import m3u8
from tqdm import tqdm

from ruv_dl import ffmpeg
from ruv_dl.ffmpeg import check_mp4_integrity, download_m3u8_file, qualities_str_to_int
from ruv_dl.hls_downloader import load_m3u8_available_resolutions
from ruv_dl.organize import _guess_show_num
from ruv_dl.organize import organize as _organize
from ruv_dl.ruv_client import Program, Programs, RUVClient
from ruv_dl.search import get_all_programs_by_pattern
from ruv_dl.storage import EpisodeDownload, filter_downloaded_episodes

log = logging.getLogger(__name__)


class Config:
    """The program config. Mantains all file-paths, flags and options."""

    def __init__(self, work_dir: Path = Path.cwd()) -> None:
        self.work_dir = work_dir
        self.organization_dest_dir = work_dir / "organized"
        self.download_dir = work_dir / "downloads"
        self.programs_json = work_dir / "programs.json"
        self.download_log = work_dir / "downloaded.jsonl"
        self.translations = work_dir / "translations.json"
        self.last_run_file = work_dir / "programs_last_fetched.txt"
        self.ignore_case = False
        self.only_ids = False
        self.force_reload_programs = False
        self.quality: str = "1080p"
        self.dry_run = False

    def initialize_dirs(self):
        """Creates all necessary directories which the progam expects."""
        if not self.work_dir.exists():
            self.work_dir.mkdir(parents=True, exist_ok=True)
        if not self.download_dir.exists():
            self.download_dir.mkdir(parents=True, exist_ok=True)
        if not self.organization_dest_dir.exists():
            self.organization_dest_dir.mkdir(parents=True, exist_ok=True)


async def search(patterns: Tuple[str, ...], config: Config) -> Programs:
    """Search for a RÚV program based on the patterns provided.
    Is limited to main title only.
    Either returns a human readable table with the program results or a string of program ids found."""
    async with RUVClient() as client:
        programs = await client.get_all_programs()
        found_programs: Programs = {}
        for pattern in patterns:
            found_programs.update(get_all_programs_by_pattern(programs, pattern, config.ignore_case))
        found_programs = await client.get_programs_with_episodes(
            program_ids=list(p["programID"] for p in found_programs.values())
        )
    return found_programs


async def download_program(
    program_ids: Tuple[str, ...], config: Config
) -> Tuple[List[EpisodeDownload], List[EpisodeDownload]]:
    """Download all episodes (not previously downloaded) of the supplied program ids (plural).
    Use the 'search' functionality with --only-ids to get them and pipe them to this command."""
    downloaded_episodes: List[EpisodeDownload] = []
    skipped_episodes: List[EpisodeDownload] = []
    try:
        async with RUVClient() as client:
            selected_programs = await client.get_programs_with_episodes(program_ids=[int(p) for p in program_ids])
    except KeyError:
        log.error("Invalid program id(s): " + ", ".join(program_ids))
        return downloaded_episodes, skipped_episodes

    selected_episodes = [
        EpisodeDownload.from_episode_and_program(episode, program, config.quality)
        for program in selected_programs.values()
        for episode in program["episodes"]
    ]
    previously_downloaded_episodes = read_downloaded_episodes(config.download_log)
    episodes_to_download = filter_downloaded_episodes(
        downloaded_episodes=previously_downloaded_episodes,
        episodes_to_download=selected_episodes,
    )

    # Track episodes that were already downloaded and add them to skipped_episodes
    already_downloaded_episodes = [ep for ep in selected_episodes if ep not in episodes_to_download]
    skipped_episodes.extend(already_downloaded_episodes)

    log.info(f"Will download {len(episodes_to_download)} episodes")
    if already_downloaded_episodes:
        log.info(f"Skipping {len(already_downloaded_episodes)} episodes that were already downloaded")

    tqdm_iter = tqdm(episodes_to_download)
    try:
        for episode in tqdm_iter:
            episode = cast(EpisodeDownload, episode)
            tqdm_iter.set_description(f"Downloading {episode.program_title} - {episode.title}")
            # TODO: Handle mp3 files
            output_file = config.download_dir / f"{episode.file_name()}.mp4"
            # No need to download file again if it's there and ok.
            if check_file_validity(output_file):
                skipped_episodes.append(episode)
                append_downloaded_episode(config.download_log, episode)
                continue

            m3u8_playlist = m3u8.load(episode.url)
            stream_num = -1
            for idx, playlist in enumerate(m3u8_playlist.playlists):
                log.debug(playlist.stream_info.resolution)
                # the resolution is a tuple of (width, height)
                if playlist.stream_info.resolution[1] == qualities_str_to_int(episode.quality_str):
                    stream_num = idx
                    break
            if stream_num == -1:
                log.error(f"Unable to find stream with resolution {episode.quality_str}")
                continue

            subtitle_file = None
            if episode.subtitle_url:
                subtitle_path = config.download_dir / f"{episode.file_name()}.vtt"
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.get(episode.subtitle_url)
                        response.raise_for_status()
                        with open(subtitle_path, "w", encoding="utf-8") as f:
                            f.write(response.text)
                    subtitle_file = subtitle_path
                except Exception as e:
                    log.error(f"Failed to download subtitle from {episode.subtitle_url}: {e}")

            if download_m3u8_file(
                episode.url,
                stream_num=stream_num,
                output_file=output_file,
                subtitle_file=subtitle_file,
            ):
                downloaded_episodes.append(episode)
                append_downloaded_episode(config.download_log, episode)
            else:
                log.error(f"Unable to download m3u8. Check the url with ffmpeg: {episode.url}")

            if subtitle_file and subtitle_file.exists():
                subtitle_file.unlink()

    except KeyboardInterrupt:
        log.warning("Stopping.")
    return downloaded_episodes, skipped_episodes


def organize(shows: List[Path], config: Config) -> Dict[str, str]:
    """
    Organize shows into seasons and directories. A best effort approach.
    """
    translations = read_translations(config.translations)
    return _organize(
        episodes_to_organize=shows,
        destination_dir=config.organization_dest_dir,
        translations=translations,
        dry_run=config.dry_run,
    )


async def details(program_ids: Tuple[str, ...], config: Config) -> Programs:
    """
    Get detailed information about programs and their episodes.
    Returns a dictionary of Program data (Programs type).
    """
    if not program_ids:
        log.info("No program IDs provided to details function.")
        return {}

    valid_program_ids_int: List[int] = []
    for pid_str in program_ids:
        if pid_str.isdigit():
            valid_program_ids_int.append(int(pid_str))
        else:
            log.warning(f"Invalid program ID format: '{pid_str}'. Will be skipped.")

    if not valid_program_ids_int:
        log.warning("No valid program IDs remaining after filtering.")
        return {}

    log.info(f"Fetching details for program IDs: {valid_program_ids_int}")
    async with RUVClient() as client:
        programs_data: Programs = await client.get_programs_with_episodes(program_ids=valid_program_ids_int)

    if not programs_data:
        log.info(f"No program data found for IDs: {valid_program_ids_int}")

    return programs_data


async def find_all_subtitles(config: Config) -> Programs:
    """
    Get all programs with detailed episode information including subtitle data.
    Returns a dictionary of Program data (Programs type).
    """
    log.info("Fetching all programs...")
    async with RUVClient() as client:
        all_programs = await client.get_all_programs()
        program_ids = [p["programID"] for p in all_programs.values()]
        log.info(f"Fetching episode details for {len(program_ids)} programs...")
        programs_data: Programs = await client.get_programs_with_episodes(program_ids=program_ids)

    return programs_data


def split_episode(file_path: Path, timestamp: str) -> Optional[Tuple[Path, Path]]:
    """Split an episode into two files, the first will have duration=timestamp.
    The other starts=timestamp."""
    first_file = file_path.with_suffix(".mp4.part1")
    second_file = file_path.with_suffix(".mp4.part2")
    # We check if the filename has EXX-EYY in it, we will use it.
    filename = file_path.name
    parent = file_path.parent
    match = re.match(r".*(E\d+-E\d+).*", filename)
    if match:
        show_nums = _guess_show_num(match.group(1))
        if show_nums is not None:
            first_file = parent / filename.replace(match.group(1), f"E{show_nums[0]:02}")
            second_file = parent / filename.replace(match.group(1), f"E{show_nums[1]:02}")
    if ffmpeg.split_mp4_in_two(file_path, timestamp, first_file, second_file):
        return first_file, second_file
    else:
        return None


def check_file_validity(file_path: Path) -> bool:
    if not file_path.exists():
        return False
    # The file exists - check integrity
    return check_mp4_integrity(file_path)


def read_translations(path: Path) -> Dict[str, str]:
    if path.exists():
        with path.open() as f:
            return json.load(f)
    return {}


def read_downloaded_episodes(path: Path) -> List[EpisodeDownload]:
    downloaded_episodes = []
    if path.exists():
        with path.open() as f:
            for line in f:
                downloaded_episodes.append(EpisodeDownload.from_json(line.strip()))
    return downloaded_episodes


def append_downloaded_episode(path: Path, episode: EpisodeDownload):
    with path.open("a+") as f:
        f.write(episode.to_json() + "\n")
