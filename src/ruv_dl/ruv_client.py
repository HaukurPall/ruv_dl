import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, TypedDict

from .ruv_urls import construct_categories_url, construct_category_url, construct_serie_url, construct_episode_url

import httpx

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
    episodes: List[Episode]


class Category(TypedDict):
    """A single category"""

    title: str
    slug: str


Programs = Dict[str, Program]


async def get_tv_categories(client) -> list[Category]:
    response = await client.get()
    response.raise_for_status()
    return response.json()["data"]["Category"]["categories"]


async def get_tv_category(client, slug: str) -> list[Program]:
    get_category_url = f"https://spilari.nyr.ruv.is/gql/?operationName=getCategory&variables=%7B%22category%22%3A%22{slug}%22%2C%22station%22%3A%22tv%22%7D&extensions=%7B%22persistedQuery%22%3A%7B%22version%22%3A1%2C%22sha256Hash%22%3A%224d04a20dcfe37d6ec064299abb82895802d51bfa8bdd1ff283b64478cb2a2328%22%7D%7D"
    # Returns a Category with a list of programs, each program has little information and a single episode.
    # Example:
    # {
    #     "data": {
    #         "Category": {
    #             "categories": [
    #                 {
    #                     "title": "Fréttatengt efni",
    #                     "slug": "frettatengt-efni",
    #                     "programs": [
    #                         {
    #                             "short_description": null,
    #                             "episodes": [
    #                                 {
    #                                     "id": "ahptvh",
    #                                     "title": "05.02.2024",
    #                                     "rating": 0,
    #                                     "__typename": "Episode"
    #                                 }
    #                             ],
    #                             "title": "Kastljós",
    #                             "portrait_image": "https://myndir.ruv.is/eyJidWNrZXQiOiAicnV2LXByb2QtcnV2aXMtcHVibGljIiwgImtleSI6ICJtZWRpYS9wdWJsaWMvS3JpbmdsdW15bmRpci9wb3J0cmFpdF9wb3N0ZXJzL2FocHR2MC0yMG1hMDAuanBnIiwgImVkaXRzIjogeyJyZXNpemUiOiB7IndpZHRoIjogMTAwMCwgImhlaWdodCI6IDE1MDB9fX0=",
    #                             "id": 35422,
    #                             "slug": "kastljos",
    #                             "image": "https://myndir.ruv.is/eyJidWNrZXQiOiAicnV2LXByb2QtcnV2aXMtcHVibGljIiwgImtleSI6ICJtZWRpYS9wdWJsaWMvS3JpbmdsdW15bmRpci9oZF9wb3N0ZXJzL2FocHR2MC1namdyNmcuanBnIiwgImVkaXRzIjogeyJyZXNpemUiOiB7IndpZHRoIjogMTkyMCwgImhlaWdodCI6IDEwODB9fX0=",
    #                             "__typename": "Program"
    #                         },
    #                         ...
    response = await client.get(get_category_url)
    response.raise_for_status()
    return response.json()["data"]["Category"]["categories"][0]["programs"]


async def get_episode(client, program_id: str, episode_id: str) -> Program:
    def construct_serie_url(episode_id, program_id):
        operation_name = "getSerie"

        variables = json.dumps({"episodeID": [episode_id], "programID": program_id})
        extensions = json.dumps(
            {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": "afd9cf0c67f1ebed0a981b72ee127a5a152eb90f4adb2b3bd3e6c1ec185a2dd3",
                }
            }
        )

        query_params = {"operationName": operation_name, "variables": variables, "extensions": extensions}

        encoded_query_params = urllib.parse.urlencode(query_params)
        full_url = f"{base_url}?{encoded_query_params}"

        return full_url

    # Returns a Program with a single episode, each episode detailed information and file url.
    # Example:
    # {
    #     "data": {
    #         "Program": {
    #             "slug": "aevintyri-halldors-gylfasonar",
    #             "title": "Ævintýri Halldórs Gylfasonar",
    #             "description": "Halldór Gylfason segir sígild ævintýri og leikur jafnframt öll hlutverkin.",
    #             "short_description": null,
    #             "foreign_title": null,
    #             "format": "tv",
    #             "id": 26322,
    #             "image": "https://myndir.ruv.is/eyJidWNrZXQiOiAicnV2LXByb2QtcnV2aXMtcHVibGljIiwgImtleSI6ICJtZWRpYS9wdWJsaWMvS3JpbmdsdW15bmRpci9oZF9wb3N0ZXJzLzdyMHFwMC1ub2JyNGcuanBnIiwgImVkaXRzIjogeyJyZXNpemUiOiB7IndpZHRoIjogMTkyMCwgImhlaWdodCI6IDEwODB9fX0=",
    #             "episodes": [
    #                 {
    #                     "title": "Garðabrúða - seinni hluti",
    #                     "id": "7r0qq7",
    #                     "description": "Halldór Gylfason leikur öll hlutverk í þessu sígilda ævintýri um stúlkuna sem var með svo sítt hár að hún gat notað það sem reipi til að fá draumaprinsinn sinn í heimsókn upp í turnherbergið sem hún var fangi í.",
    #                     "duration": 300,
    #                     "firstrun": "2018-01-18T17:29:00",
    #                     "scope": "Global",
    #                     "file": "https://ruv-vod.akamaized.net/opid/5228824A1/5228824A1.m3u8",
    #                     "rating": 0,
    #                     "file_expires": "2025-12-31",
    #                     "cards": [],
    #                     "clips": [],
    #                     "image": "https://myndir.ruv.is/eyJidWNrZXQiOiAicnV2LXByb2QtcnV2aXMtcHVibGljIiwgImtleSI6ICJtZWRpYS9wdWJsaWMvS3JpbmdsdW15bmRpci9oZF9wb3N0ZXJzLzdyMHFxNy1kZDRrYW8uanBnIiwgImVkaXRzIjogeyJyZXNpemUiOiB7IndpZHRoIjogMTkyMCwgImhlaWdodCI6IDEwODB9fX0=",
    #                     "subtitles": [],
    #                     "__typename": "Episode"
    #                 }
    #             ],
    #             "__typename": "Program"
    #         }
    #     }
    # }
    response = await client.get(construct_serie_url(episode_id, program_id))
    response.raise_for_status()
    return response.json()["data"]["Program"]


async def get_program_episodes(client, program_id: str) -> Program:
    get_episode_url = f"https://spilari.nyr.ruv.is/gql/?operationName=getEpisode&variables=%7B%22programID%22%3A{program_id}%7D&extensions=%7B%22persistedQuery%22%3A%7B%22version%22%3A1%2C%22sha256Hash%22%3A%22f3f957a3a577be001eccf93a76cf2ae1b6d10c95e67305c56e4273279115bb93%22%7D%7D"
    # Returns a Program with a list of episodes, each episode has basic information and no file url.
    # Example:
    # {
    #     "data": {
    #         "Program": {
    #             "slug": "aevintyri-halldors-gylfasonar",
    #             "title": "Ævintýri Halldórs Gylfasonar",
    #             "description": "Halldór Gylfason segir sígild ævintýri og leikur jafnframt öll hlutverkin.",
    #             "short_description": null,
    #             "foreign_title": null,
    #             "id": 26322,
    #             "image": "https://myndir.ruv.is/eyJidWNrZXQiOiAicnV2LXByb2QtcnV2aXMtcHVibGljIiwgImtleSI6ICJtZWRpYS9wdWJsaWMvS3JpbmdsdW15bmRpci9oZF9wb3N0ZXJzLzdyMHFwMC1ub2JyNGcuanBnIiwgImVkaXRzIjogeyJyZXNpemUiOiB7IndpZHRoIjogMTkyMCwgImhlaWdodCI6IDEwODB9fX0=",
    #             "episodes": [
    #                 {
    #                     "title": "Garðabrúða - seinni hluti",
    #                     "id": "7r0qq7",
    #                     "firstrun": "2018-01-18T17:29:00",
    #                     "description": "Halldór Gylfason leikur öll hlutverk í þessu sígilda ævintýri um stúlkuna sem var með svo sítt hár að hún gat notað það sem reipi til að fá draumaprinsinn sinn í heimsókn upp í turnherbergið sem hún var fangi í.",
    #                     "image": "https://myndir.ruv.is/eyJidWNrZXQiOiAicnV2LXByb2QtcnV2aXMtcHVibGljIiwgImtleSI6ICJtZWRpYS9wdWJsaWMvS3JpbmdsdW15bmRpci9oZF9wb3N0ZXJzLzdyMHFxNy1kZDRrYW8uanBnIiwgImVkaXRzIjogeyJyZXNpemUiOiB7IndpZHRoIjogMTkyMCwgImhlaWdodCI6IDEwODB9fX0=",
    #                     "__typename": "Episode"
    #                 },
    #                 ...,
    #             ],
    #             "__typename": "Program"
    #         }
    #     }
    # }
    response = await client.get(get_episode_url)
    response.raise_for_status()
    return response.json()["data"]["Program"]


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
            programs = await asyncio.gather(*[get_tv_category(client, category["slug"]) for category in categories])
            return [program for program_list in programs for program in program_list]

    @staticmethod
    async def _query_program_episodes(program_id: str) -> Program:
        """Return a list of specified programs with episodes."""
        async with httpx.AsyncClient() as client:
            # first we fetch the program - this will give us all the episode ids
            # but we are still missing the file urls
            program = await get_program_episodes(client, program_id)
            # then we fetch each episode to get the file urls
            programs_with_single_episode = await asyncio.gather(
                *[get_episode(client, program_id, episode["id"]) for episode in program["episodes"]]
            )
            program["episodes"] = [
                program_with_single_episode["episodes"][0]
                for program_with_single_episode in programs_with_single_episode
            ]
            return program

    async def _get_all_programs(self) -> Programs:
        """Return a list of all programs without episodes."""
        programs = await self._query_all_programs()
        return {program["id"]: program for program in programs}

    async def _get_program_episodes(self, program_ids: List[str]) -> Dict[str, Program]:
        """Return a list of specified programs with episodes."""
        list_of_programs = await asyncio.gather(
            *[self._query_program_episodes(program_id) for program_id in program_ids]
        )
        return {program["id"]: program for program in list_of_programs}

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
