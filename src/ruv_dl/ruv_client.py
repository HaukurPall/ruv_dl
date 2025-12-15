import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import httpx
from tqdm import tqdm

log = logging.getLogger(__name__)


class RUVAPIError(Exception):
    """Raised when RÚV API returns an error"""

    pass


@dataclass(frozen=True)
class Subtitle:
    """A subtitle with language and URL"""

    name: str  # This is actually the language extension (is)
    value: str  # This is a URL to the subtitle file

    @classmethod
    def from_dict(cls, data: dict) -> "Subtitle":
        return cls(name=data["name"], value=data["value"])


@dataclass(frozen=True)
class Episode:
    """A single episode"""

    id: str
    title: str
    file: str
    firstrun: str  # 2009-01-01 22:10:00
    subtitles: List[Subtitle] = field(default_factory=list)
    open_subtitles: bool = False
    closed_subtitles: bool = False
    auto_subtitles: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> "Episode":
        subtitles = [Subtitle.from_dict(s) for s in data.get("subtitles", [])]
        return cls(
            id=data["id"],
            title=data.get("title", ""),
            file=data.get("file", ""),
            firstrun=data.get("firstrun", ""),
            subtitles=subtitles,
            open_subtitles=data.get("open_subtitles", False),
            closed_subtitles=data.get("closed_subtitles", False),
            auto_subtitles=data.get("auto_subtitles", False),
        )


@dataclass(frozen=True)
class Program:
    """A single program"""

    programID: int
    id: str
    title: str
    foreign_title: Optional[str] = None
    short_description: Optional[str] = None
    episodes: List[Episode] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "Program":
        episodes = [Episode.from_dict(e) for e in data.get("episodes", [])]
        episodes.sort(key=lambda e: (e.firstrun or "", e.id))
        return cls(
            programID=data.get("programID", 0),
            id=data["id"],
            title=data["title"],
            foreign_title=data.get("foreign_title"),
            short_description=data.get("short_description"),
            episodes=episodes,
        )


@dataclass(frozen=True)
class Category:
    """A single category"""

    title: str
    slug: str

    @classmethod
    def from_dict(cls, data: dict) -> "Category":
        return cls(title=data["title"], slug=data["slug"])


Programs = Dict[str, Program]


class RUVClient:
    """A simple HTTP client for RÚV's GraphQL API"""

    BASE_URL = "https://spilari.nyr.ruv.is/gql/"

    def __init__(self) -> None:
        self.headers = {
            "content-type": "application/json",
            "Referer": "https://www.ruv.is/sjonvarp",
            "Origin": "https://www.ruv.is",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
        }
        self.client = None

    async def __aenter__(self):
        self.client = httpx.AsyncClient(headers=self.headers)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()

    def _handle_response(self, response_data: dict, operation: str) -> dict:
        """Handle GraphQL response errors"""
        if "errors" in response_data:
            raise RUVAPIError(f"GraphQL error in {operation}: {response_data['errors']}")

        if "data" not in response_data:
            raise RUVAPIError(f"No data in {operation} response: {response_data}")

        return response_data["data"]

    async def _query_post(self, operation: str, variables: dict, query: str) -> dict:
        """Execute a POST request with full GraphQL query"""
        payload = {"operationName": operation, "variables": variables, "query": query}

        log.debug(f"POST {operation}: {variables}")
        response = await self.client.post(self.BASE_URL, json=payload)
        response.raise_for_status()
        response_data = response.json()

        return self._handle_response(response_data, operation)

    async def get_categories(self, category_type: str = "tv") -> List[Category]:
        """Get all categories for the given type"""
        query = """
        query getCategories($station: StationSearch!) {
          Category(station: $station) {
            categories {
              title
              slug
            }
          }
        }
        """
        variables = {"station": category_type}
        data = await self._query_post("getCategories", variables, query)
        return [Category.from_dict(cat) for cat in data["Category"]["categories"]]

    async def get_category_programs(self, slug: str, category_type: str = "tv") -> List[Program]:
        """Get all programs in a category"""
        query = """
        query getCategory($category: String!, $station: StationSearch!) {
          Category(category: $category, station: $station) {
            categories {
              programs {
                programID
                id
                title
                foreign_title
                short_description
                episodes {
                  id
                }
              }
            }
          }
        }
        """
        variables = {"category": slug, "station": category_type}
        data = await self._query_post("getCategory", variables, query)
        return [Program.from_dict(prog) for prog in data["Category"]["categories"][0]["programs"]]

    async def get_program_episodes(self, program_id: int) -> Optional[Program]:
        """Get a program with detailed episode info including file URLs"""
        query = """
        query getEpisode($programID: Int!) {
          Program(id: $programID) {
            # slug # Removed
            title
            description
            short_description
            foreign_title
            id
            # image # Removed
            episodes {
              title
              id
              firstrun
              description
              # image # Removed
              file # Added
              file_expires # Added
              open_subtitles
              closed_subtitles
              auto_subtitles
              subtitles {
                __typename
                name
                value
              }
            }
          }
        }
        """

        variables = {"programID": program_id}
        data = await self._query_post("getEpisode", variables, query)
        program_data = data["Program"]
        return Program.from_dict(program_data) if program_data else None

    async def get_all_programs(self) -> Programs:
        """Get all programs from RÚV (without detailed episode info)"""
        log.info("Fetching all categories...")
        categories = await self.get_categories()
        log.debug(f"Found {len(categories)} categories")

        log.info("Fetching programs from all categories...")
        category_programs = await asyncio.gather(
            *[self.get_category_programs(category.slug) for category in categories]
        )

        # Flatten the list of lists and convert to dict
        all_programs = [program for programs in category_programs for program in programs]
        all_programs.sort(key=lambda p: p.title)
        log.info(f"Found {len(all_programs)} total programs")

        return {program.id: program for program in all_programs}

    async def get_programs_with_episodes(self, program_ids: List[int], limit: int = 10) -> Programs:
        """Get detailed program info with file URLs for episodes"""
        log.info(f"Fetching detailed program and episode info for {len(program_ids)} programs...")

        semaphore = asyncio.Semaphore(limit)

        async def _fetch(pid: int) -> tuple[int, Optional[Program]]:
            async with semaphore:
                try:
                    return pid, await self.get_program_episodes(pid)
                except Exception as e:
                    log.warning(f"Error fetching program ID {pid}: {e}")
                    return pid, None

        fetched_programs: list[Program] = []
        tasks = [_fetch(pid) for pid in program_ids]

        for coro in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="Fetching programs details"):
            pid, program = await coro
            if program:
                log.debug(f"Successfully fetched program ID {pid} with its episodes.")
                fetched_programs.append(program)
            else:
                log.warning(f"Could not fetch program ID {pid}.")

        fetched_programs.sort(key=lambda p: p.title)

        # Ensure 'id' exists in program objects before creating the dictionary
        return {prog.id: prog for prog in fetched_programs if prog}
