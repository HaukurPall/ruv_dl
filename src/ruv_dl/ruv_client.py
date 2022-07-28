import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, TypedDict

from gql import Client, gql
from gql.client import AsyncClientSession
from gql.transport.aiohttp import AIOHTTPTransport

log = logging.getLogger(__name__)


class Episode(TypedDict):
    """A single episode"""

    id: str
    title: str
    file: str
    firstrun: str  # 2009-01-01 22:10:00


class Program(TypedDict):
    """A single program"""

    id: str
    title: str
    foreign_title: Optional[str]
    short_description: Optional[str]
    episodes: Optional[List[Episode]]


Programs = Dict[str, Program]


class RUVClient:
    """An HTTP client to gather a program list from ruv.is."""

    def __init__(self) -> None:
        self.url = "https://www.ruv.is/gql/"
        transport = AIOHTTPTransport(self.url)
        self.client = Client(transport=transport, execute_timeout=30)

    @staticmethod
    async def _query_all_programs(session: AsyncClientSession) -> List[Program]:
        query = gql(
            """
            query {
                Programs {
                    title
                    foreign_title
                    short_description
                    id
                }
            }
            """
        )
        result = await session.execute(query)
        return [program for program in result["Programs"]]

    @staticmethod
    async def _query_program_episodes(session: AsyncClientSession, program_id: str) -> Program:
        query = gql(
            """
            query ($program_id: Int!) {
                Program(id: $program_id) {
                    title
                    foreign_title
                    short_description
                    id
                    episodes {
                        id
                        title
                        file
                        firstrun
                    }
                }
            }
            """
            )
        result = await session.execute(query, variable_values={"program_id": int(program_id)})
        return result["Program"]

    async def _get_all_programs(self) -> Programs:
        """Return a list of all programs without episodes."""
        async with self.client as session:
            programs = await self._query_all_programs(session)
            return {program["id"]: program for program in programs}

    async def _get_program_episodes(self, program_ids: List[str]) -> Dict[str, Program]:
        """Return a list of specified programs with episodes."""
        async with self.client as session:
            list_of_programs = await asyncio.gather(
                *[asyncio.create_task(self._query_program_episodes(session, program_id)) for program_id in program_ids]
            )
            return {program_id: program for program_id, program in zip(program_ids, list_of_programs)}

    def get_all_programs(self) -> Programs:
        """Get all programs from ruv.is."""
        return asyncio.run(self._get_all_programs())

    def get_program_episodes(self, program_ids: List[str]) -> Dict[str, Program]:
        """Get episodes for a list of programs."""
        return asyncio.run(self._get_program_episodes(program_ids))


def save_programs_cache(file_path: Path, programs: Programs):
    with file_path.open("w", encoding="utf-8") as f:
        json.dump(programs, f, ensure_ascii=False)


def load_programs_cache(file_path: Path) -> Programs:
    with file_path.open("r") as f:
        return json.load(f)


def load_last_fetched(file_path: Path) -> Optional[datetime]:
    if file_path.exists():
        with file_path.open() as f:
            lines = f.readlines()
            date_time_str = lines[0].strip()
            return datetime.fromisoformat(date_time_str)
    return None


def save_last_fetched(file_path: Path):
    with file_path.open("w") as f:
        f.write(datetime.now().isoformat())


def load_programs(
    force_reload: bool, programs_cache: Path, last_fetched_file: Path, refresh_interval_sec=10 * 60
) -> Programs:
    """Load the programs by either loading from cache or by querying ruv.is."""
    last_fetched = load_last_fetched(last_fetched_file)
    fetched = False
    # We have not fetched before
    if last_fetched is None:
        force_reload = True
        log.info("No previous timestamp")
    # It's been a while since we fetched - gotta refresh
    elif last_fetched + timedelta(seconds=refresh_interval_sec) < datetime.now():
        log.info("It's been a while since we refreshed the programs - doing it.")
        force_reload = True
    if force_reload:
        programs = RUVClient().get_all_programs()
        fetched = True
    else:
        try:
            programs = load_programs_cache(programs_cache)
        except FileNotFoundError:
            programs = RUVClient().get_all_programs()
            fetched = True
    if fetched:
        save_programs_cache(programs_cache, programs)
        save_last_fetched(last_fetched_file)
    log.info(f"Loaded {len(programs)} programs")
    return programs
