import asyncio
import logging
from pathlib import Path
from typing import List, Tuple

import httpx
import m3u8
from tqdm import tqdm

from ruv_dl.ffmpeg import download_m3u8_file, qualities_str_to_int
from ruv_dl.ruv_client import Programs, RUVClient
from ruv_dl.search import get_all_programs_by_pattern
from ruv_dl.storage import EpisodeDownload, filter_downloaded_episodes

log = logging.getLogger(__name__)


class Config:
    """The program config. Mantains all file-paths, flags and options."""

    def __init__(self, work_dir: Path = Path.cwd()) -> None:
        self.work_dir = work_dir
        self.download_dir = work_dir / "downloads"
        self.download_log = work_dir / "downloaded.jsonl"
        self.ignore_case = False
        self.only_ids = False
        self.quality: str = "1080p"
        self.audio_only: bool = False
        self.dry_run = False
        self.max_concurrent_requests = 10
        self.max_parallel_downloads = 1

    def initialize_dirs(self):
        """Creates all necessary directories which the progam expects."""
        if not self.work_dir.exists():
            self.work_dir.mkdir(parents=True, exist_ok=True)
        if not self.download_dir.exists():
            self.download_dir.mkdir(parents=True, exist_ok=True)


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
            program_ids=list(p.programID for p in found_programs.values()),
            limit=config.max_concurrent_requests,
        )
    return found_programs


async def _process_episode(episode: EpisodeDownload, config: Config) -> Tuple[str, EpisodeDownload]:
    # TODO: Handle mp3 files
    suffix = "_audio_only" if config.audio_only else ""
    output_file = config.download_dir / f"{episode.file_name()}{suffix}.mp4"

    # Check for legacy file and migrate if necessary
    if not output_file.exists():
        legacy_file = config.download_dir / f"{episode.legacy_file_name()}{suffix}.mp4"
        if legacy_file.exists():
            log.info(f"Migrating legacy file: {legacy_file.name} -> {output_file.name}")
            legacy_file.rename(output_file)

            # Also migrate subtitle if it exists
            legacy_sub = config.download_dir / f"{episode.legacy_file_name()}.vtt"
            new_sub = config.download_dir / f"{episode.file_name()}.vtt"
            if legacy_sub.exists() and not new_sub.exists():
                legacy_sub.rename(new_sub)

    # No need to download file again if it's there and ok.
    if check_file_validity(output_file):
        return "skipped", episode

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(episode.url)
            response.raise_for_status()
            m3u8_content = response.text

        m3u8_playlist = m3u8.loads(m3u8_content, uri=episode.url)
        variant_index = -1

        if config.audio_only:
            # For audio-only, select the variant with the lowest bandwidth
            # This often results in better speeds for audio extraction
            lowest_bandwidth = float("inf")
            for idx, playlist in enumerate(m3u8_playlist.playlists):
                if playlist.stream_info.bandwidth and playlist.stream_info.bandwidth < lowest_bandwidth:
                    lowest_bandwidth = playlist.stream_info.bandwidth
                    variant_index = idx
        else:
            # Use requested quality for video downloads
            for idx, playlist in enumerate(m3u8_playlist.playlists):
                log.debug(playlist.stream_info.resolution)
                # the resolution is a tuple of (width, height)
                if playlist.stream_info.resolution[1] == qualities_str_to_int(episode.quality_str):
                    variant_index = idx
                    break

        if variant_index == -1:
            log.error(f"Unable to find suitable stream for {episode.title}")
            return "failed", episode

        # Always use the specific variant's playlist URL for reliability and efficiency
        variant_url = m3u8_playlist.playlists[variant_index].absolute_uri
        log.info(f"Selected variant URL for {episode.title}: {variant_url}")

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

        # Run ffmpeg in a thread to avoid blocking asyncio loop
        success = await asyncio.to_thread(
            download_m3u8_file,
            variant_url,
            output_file=output_file,
            subtitle_file=subtitle_file,
            audio_only=config.audio_only,
        )

        if success:
            return "downloaded", episode

    except Exception as e:
        log.error(f"Error downloading {episode.title}: {e}")

    return "failed", episode


async def _download_episodes(
    episodes: List[EpisodeDownload], config: Config
) -> Tuple[List[EpisodeDownload], List[EpisodeDownload]]:
    """Download specific episodes.
    Returns tuple of (downloaded_episodes, skipped_episodes)."""
    downloaded_episodes: List[EpisodeDownload] = []
    skipped_episodes: List[EpisodeDownload] = []

    previously_downloaded_episodes = read_downloaded_episodes(config.download_log)
    episodes_to_download = filter_downloaded_episodes(
        downloaded_episodes=previously_downloaded_episodes,
        episodes_to_download=episodes,
    )

    # Track episodes that were already downloaded and add them to skipped_episodes
    already_downloaded_episodes = [ep for ep in episodes if ep not in episodes_to_download]
    skipped_episodes.extend(already_downloaded_episodes)

    log.info(f"Will download {len(episodes_to_download)} episodes")
    if already_downloaded_episodes:
        log.info(f"Skipping {len(already_downloaded_episodes)} episodes that were already downloaded")

    semaphore = asyncio.Semaphore(config.max_parallel_downloads)

    async def worker(episode: EpisodeDownload) -> Tuple[str, EpisodeDownload]:
        async with semaphore:
            return await _process_episode(episode, config)

    tasks = [worker(ep) for ep in episodes_to_download]
    if tasks:
        try:
            for coro in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="Downloading episodes"):
                status, episode = await coro
                if status == "skipped":
                    skipped_episodes.append(episode)
                    append_downloaded_episode(config.download_log, episode)
                elif status == "downloaded":
                    downloaded_episodes.append(episode)
                    append_downloaded_episode(config.download_log, episode)
        except KeyboardInterrupt:
            # If the user cancels the download, we want to exit cleanly
            pass
        log.warning("Stopping.")
    return downloaded_episodes, skipped_episodes


async def _download_episodes_from_programs(
    programs: Programs, config: Config
) -> Tuple[List[EpisodeDownload], List[EpisodeDownload]]:
    """Download all episodes from already-fetched programs.
    Returns tuple of (downloaded_episodes, skipped_episodes)."""
    selected_episodes = [
        EpisodeDownload.from_episode_and_program(episode, program, config.quality)
        for program in programs.values()
        for episode in program.episodes
    ]
    return await _download_episodes(selected_episodes, config)


async def download_program(
    program_ids: Tuple[str, ...], config: Config
) -> Tuple[List[EpisodeDownload], List[EpisodeDownload]]:
    """Download all episodes (not previously downloaded) of the supplied program ids (plural).
    Use the 'search' functionality with --only-ids to get them and pipe them to this command."""
    try:
        async with RUVClient() as client:
            selected_programs = await client.get_programs_with_episodes(
                program_ids=[int(p) for p in program_ids],
                limit=config.max_concurrent_requests,
            )
    except KeyError:
        log.error("Invalid program id(s): " + ", ".join(program_ids))
        return [], []

    return await _download_episodes_from_programs(selected_programs, config)


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
        programs_data: Programs = await client.get_programs_with_episodes(
            program_ids=valid_program_ids_int,
            limit=config.max_concurrent_requests,
        )

    if not programs_data:
        log.info(f"No program data found for IDs: {valid_program_ids_int}")

    return programs_data


async def get_all_programs_with_episodes(config: Config) -> Programs:
    """
    Get all programs with detailed episode information.
    Returns a dictionary of Program data (Programs type).
    """
    log.info("Fetching all programs...")
    async with RUVClient() as client:
        all_programs = await client.get_all_programs()
        program_ids = [p.programID for p in all_programs.values()]
        log.info(f"Fetching episode details for {len(program_ids)} programs...")
        programs_data: Programs = await client.get_programs_with_episodes(
            program_ids=program_ids,
            limit=config.max_concurrent_requests,
        )

    return programs_data


def check_file_validity(file_path: Path) -> bool:
    return file_path.exists()


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
