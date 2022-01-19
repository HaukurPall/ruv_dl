import json
from dataclasses import asdict, dataclass
from typing import Optional

from ruv_dl.ffmpeg import QUALITIES_INT_TO_STR
from ruv_dl.ruv_client import Episode, Program


@dataclass
class EpisodeDownload:
    id: str
    program_id: str
    program_title: str
    title: Optional[str]
    foreign_title: Optional[str]
    quality_str: str
    url: str

    @staticmethod
    def from_episode_and_program(episode: Episode, program: Program, quality_num: int) -> "EpisodeDownload":
        return EpisodeDownload(
            id=episode["id"],
            program_id=program["id"],
            program_title=program["title"],
            title=episode["title"],
            foreign_title=program["foreign_title"],
            quality_str=QUALITIES_INT_TO_STR[quality_num],
            url=episode["file"],
        )

    @staticmethod
    def from_json(line: str) -> "EpisodeDownload":
        return EpisodeDownload(**json.loads(line))

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    def file_name(self) -> str:
        return f"{self.program_title} ||| {self.title} ||| {self.foreign_title} [{self.quality_str}]".replace("/", "|")

    @staticmethod
    def file_name_regexp(extension: str) -> str:
        return (
            r"^(?P<program_title>.+?) \|\|\| (?P<title>.+?) \|\|\| (?P<foreign_title>.+?)(?P<quality_str> \[.+?\])?"
            + f".{extension}"
        )
