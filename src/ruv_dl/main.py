import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple, cast

from tabulate import tabulate
from tqdm import tqdm

from ruv_dl.ffmpeg import QUALITIES_STR_TO_INT, check_mp4_integrity, download_m3u8_file
from ruv_dl.hls_downloader import load_m3u8_available_resolutions
from ruv_dl.organize import organize as _organize
from ruv_dl.ruv_client import Program, Programs, load_programs
from ruv_dl.search import get_all_programs_by_pattern
from ruv_dl.storage import EpisodeDownload

log = logging.getLogger(__name__)


class Config:
    """The program config. Mantains all file-paths, flags and options."""

    def __init__(self, work_dir: Path = Path.cwd()) -> None:
        self.work_dir = work_dir
        self.organization_dest_dir = work_dir / "organized"
        self.download_dir = work_dir / "downloads"
        self.programs_json = work_dir / "programs.json"
        self.download_log = work_dir / "downloaded.jsonl"
        self.run_log = work_dir / "debug.log"
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


def search(patterns: Tuple[str, ...], config: Config) -> Programs:
    """Search for a RÚV program based on the patterns provided.
    Either returns a human readable table with the program results or a string of program ids found."""
    programs = load_programs(
        force_reload=config.force_reload_programs,
        programs_cache=config.programs_json,
        last_fetched_file=config.last_run_file,
    )
    found_programs: Programs = {}
    for pattern in patterns:
        found_programs.update(get_all_programs_by_pattern(programs, pattern, config.ignore_case))
    return found_programs


def download_program(
    program_ids: Tuple[str, ...], config: Config
) -> Tuple[List[EpisodeDownload], List[EpisodeDownload]]:
    """Download all episodes (not previously downloaded) of the supplied program ids (plural).
    Use the 'search' functionality with --only-ids to get them and pipe them to this command."""
    downloaded_episodes: List[EpisodeDownload] = []
    skipped_episodes: List[EpisodeDownload] = []
    programs = load_programs(
        force_reload=config.force_reload_programs,
        programs_cache=config.programs_json,
        last_fetched_file=config.last_run_file,
    )
    try:
        selected_programs = [programs[program_id] for program_id in program_ids]
    except KeyError:
        log.error("Invalid program id(s): " + ", ".join(program_ids))
        return downloaded_episodes, skipped_episodes
    selected_episodes = [
        EpisodeDownload.from_episode_and_program(episode, program, config.quality)
        for program in selected_programs
        for episode in program["episodes"]
    ]
    previously_downloaded_episodes = read_downloaded_episodes(config.download_log)
    episodes_to_download = [episode for episode in selected_episodes if episode not in previously_downloaded_episodes]
    log.info(f"Will download {len(episodes_to_download)} episodes")
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

            download_m3u8_file(episode.url, QUALITIES_STR_TO_INT[episode.quality_str], output_file=output_file)
            downloaded_episodes.append(episode)
            append_downloaded_episode(config.download_log, episode)

    except KeyboardInterrupt:
        log.warning("Stopping.")
    return downloaded_episodes, skipped_episodes


def organize(shows: List[Path], config: Config):
    """
    Organize shows into seasons and directories. A best effort approach.
    """
    translations = read_translations(config.translations)
    _organize(
        episodes_to_organize=shows,
        destination_dir=config.organization_dest_dir,
        translations=translations,
        dry_run=config.dry_run,
    )


def details(program_ids: Tuple[str, ...], config: Config) -> str:
    """
    Get detailed information about a program's episodes.
    """
    if len(program_ids) == 0:
        return ""
    programs = load_programs(
        force_reload=config.force_reload_programs,
        programs_cache=config.programs_json,
        last_fetched_file=config.last_run_file,
    )
    rows = []
    for program_id in program_ids:
        program = programs[program_id]
        p_headers, p_rows = program_details(program)
        rows.extend(p_rows)

    return tabulate(tabular_data=rows, headers=p_headers, tablefmt="github")  # type: ignore


def program_details(program: Program) -> Tuple[List[str], List[List[str]]]:
    header = [
        "Program title",
        "Foreign title",
        "Title",
        "Program ID",
        "Episode ID",
        "Short description",
        "Qualities",
        "URL",
    ]
    rows = []
    for episode in program["episodes"]:
        resolutions = load_m3u8_available_resolutions(episode["file"])
        rows.append(
            [
                program["title"],
                program["foreign_title"],
                episode["title"],
                program["id"],
                episode["id"],
                program["short_description"],
                "/".join(str(res) + "p" for _, res in resolutions),
                episode["file"],
            ]
        )
    return header, rows


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
