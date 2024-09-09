import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, TypedDict

import httpx

from .ruv_urls import construct_categories_url, construct_category_url, construct_episode_url, construct_serie_url

log = logging.getLogger(__name__)


class Episode(TypedDict):
    """A single episode"""

    id: str
    title: str
    file: str
    firstrun: str  # 2009-01-01 22:10:00


class Program(TypedDict):
    """A single program"""

    programID: int
    id: str
    title: str
    foreign_title: Optional[str]
    short_description: Optional[str]
    episodes: List[Episode]


class Category(TypedDict):
    """A single category"""

    title: str
    slug: str


Programs = Dict[str, Program]


async def get_tv_categories(client, category_type="tv") -> list[Category]:
    log.debug(f"Fetching categories: category_type={category_type}")
    get_categories_url = construct_categories_url(category_type=category_type)
    log.debug(get_categories_url)
    response = await client.get(get_categories_url)
    response.raise_for_status()
    json_response = response.json()
    log.debug(json_response)
    if "error" in json_response:
        log.warning("Error fetching categories: %s", json_response["error"])
        return []
    if "data" not in json_response:
        log.warning("No data in response: %s", json_response)
        return []
    return json_response["data"]["Category"]["categories"]


async def get_tv_category(client, slug: str, category_type="tv") -> list[Program]:
    log.debug(f"Fetching category: slug={slug}, category_type={category_type}")
    get_category_url = construct_category_url(slug, station=category_type)
    log.debug(get_category_url)
    response = await client.get(get_category_url)
    response.raise_for_status()
    json_response = response.json()
    if "error" in json_response:
        log.warning("Error fetching category: %s", json_response["error"])
        return []
    if "data" not in json_response:
        log.warning("No data in response: %s", json_response)
        return []
    return json_response["data"]["Category"]["categories"][0]["programs"]


async def get_episode(client, program_id: int, episode_id: str) -> Program | None:
    log.debug(f"Fetching episode: program_id={program_id}, episode_id={episode_id}")
    get_serie_url = construct_serie_url(episode_id, program_id)
    log.debug(get_serie_url)
    response = await client.get(get_serie_url)
    response.raise_for_status()
    json_response = response.json()
    if "error" in json_response:
        log.warning("Error fetching episode: %s", json_response["error"])
        return None
    if "data" not in json_response:
        log.warning("No data in response: %s", json_response)
        return None
    return json_response["data"]["Program"]


async def get_program_episodes(client, program_id: int) -> Program | None:
    """Fetch a program with all its episodes. The episode's 'file' property will be missing"""
    log.debug(f"Fetching program: program_id={program_id}")
    get_episode_url = construct_episode_url(program_id)
    log.debug(get_episode_url)
    response = await client.get(get_episode_url)
    response.raise_for_status()
    json_response = response.json()
    if "error" in json_response:
        log.warning("Error fetching program: %s", json_response["error"])
        return None
    return json_response["data"]["Program"]


class RUVClient:
    """An HTTP client to gather a program list from ruv.is."""

    def __init__(self) -> None:
        headers = {
            "content-type": "application/json",
            "Referer": "https://www.ruv.is/sjonvarp",
            "Origin": "https://www.ruv.is",
        }

    @staticmethod
    async def _query_all_programs() -> List[Program]:
        """Return a list of all programs without episodes."""
        async with httpx.AsyncClient() as client:
            categories = await get_tv_categories(client)
            log.debug(f"Found {len(categories)} categories")
            programs = await asyncio.gather(*[get_tv_category(client, category["slug"]) for category in categories])
            return [program for program_list in programs for program in program_list]

    @staticmethod
    async def _query_program_episodes(program_id: int) -> Program | None:
        """Return a list of specified programs with episodes."""
        async with httpx.AsyncClient() as client:
            # first we fetch the program - this will give us all the episode ids
            # but we are still missing the file urls
            program = await get_program_episodes(client, program_id)
            if program is None:
                return None
            log.debug(f"Found {len(program['episodes'])} episodes for program {program_id}")
            # then we fetch each episode to get the file urls
            programs_with_single_episode = await asyncio.gather(
                *[get_episode(client, program_id, episode["id"]) for episode in program["episodes"] if episode]
            )
            program["episodes"] = [
                program_with_single_episode["episodes"][0]
                for program_with_single_episode in programs_with_single_episode
                if program_with_single_episode
            ]
            return program

    async def _get_all_programs(self) -> Programs:
        """Return a list of all programs without episodes."""
        programs = await self._query_all_programs()
        log.info(f"Found {len(programs)} programs")
        return {program["id"]: program for program in programs}

    async def _get_program_episodes(self, program_ids: List[int]) -> Dict[str, Program]:
        """Return the programs with all their episodes."""
        list_of_programs = await asyncio.gather(
            *[self._query_program_episodes(program_id) for program_id in program_ids]
        )
        return {program["id"]: program for program in list_of_programs if program}

    def get_all_programs(self) -> Programs:
        """Get all programs from ruv.is. This does not contain all the episodes."""
        return asyncio.run(self._get_all_programs())

    def get_program_episodes(self, program_ids: List[int]) -> Dict[str, Program]:
        """Get all the episodes for a list of programs."""
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
