import json
from dataclasses import asdict, dataclass
from typing import List, Optional

from ruv_dl.ruv_client import Episode, Program


@dataclass
class EpisodeDownload:
    """A downloaded episode"""

    id: str
    program_id: str
    program_title: str
    title: Optional[str]
    foreign_title: Optional[str]
    quality_str: str
    url: str
    firstrun: Optional[str] = None
    subtitle_url: Optional[str] = None

    @staticmethod
    def from_episode_and_program(episode: Episode, program: Program, quality: str) -> "EpisodeDownload":
        subtitle_url = None
        subtitles = episode.subtitles
        if subtitles:
            for sub in subtitles:
                if sub.name == "is":
                    subtitle_url = sub.value
                    break
            # Fallback to the first available subtitle if 'is' not found
            if subtitle_url is None and len(subtitles) > 0:
                subtitle_url = subtitles[0].value

        return EpisodeDownload(
            id=episode.id,
            program_id=program.id,
            program_title=program.title,
            title=episode.title,
            foreign_title=program.foreign_title,
            quality_str=quality,
            url=episode.file,
            firstrun=episode.firstrun,
            subtitle_url=subtitle_url,
        )

    @staticmethod
    def from_json(line: str) -> "EpisodeDownload":
        return EpisodeDownload(**json.loads(line))

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    def file_name(self) -> str:
        return (
            f"{self.program_title} ||| {self.title} ||| {self.foreign_title} [{self.quality_str}] [{self.id}]".replace(
                "/", "|"
            )
        )

    def legacy_file_name(self) -> str:
        return f"{self.program_title} ||| {self.title} ||| {self.foreign_title} [{self.quality_str}]".replace("/", "|")

    @staticmethod
    def file_name_regexp(extension: str) -> str:
        return (
            r"^(?P<program_title>.+?) \|\|\| (?P<title>.+?) \|\|\| (?P<foreign_title>.+?)(?P<quality_str> \[.+?\])? \[(?P<id>.+?)\]"
            + f".{extension}"
        )


def filter_downloaded_episodes(
    downloaded_episodes: List[EpisodeDownload],
    episodes_to_download: List[EpisodeDownload],
) -> List[EpisodeDownload]:
    """Filter out episodes that are already downloaded.

    First we check if the title and firstrun are the same.
    If firstrun is not present we check if the id is the same."""
    return [
        episode
        for episode in episodes_to_download
        # This might be slow when the downloaded list becomes large
        if not any(
            (
                episode.program_title == downloaded_episode.program_title
                and episode.firstrun == downloaded_episode.firstrun
                or episode.id == downloaded_episode.id
            )
            for downloaded_episode in downloaded_episodes
        )
    ]
