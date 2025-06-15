import asyncio
import json
import logging
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, TypedDict

import httpx

log = logging.getLogger(__name__)


class RUVAPIError(Exception):
    """Raised when RÚV API returns an error"""

    pass


class PersistedQueryNotFoundError(RUVAPIError):
    """Raised when RÚV API returns PersistedQueryNotFound error"""

    def __init__(self, operation_name: str, url: str, response_data: dict):
        self.operation_name = operation_name
        self.url = url
        self.response_data = response_data
        super().__init__(
            f"PersistedQueryNotFound for operation '{operation_name}'. "
            f"The GraphQL query hash may be outdated. URL: {url}"
        )


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


class RUVClient:
    """A simple HTTP client for RÚV's GraphQL API"""

    BASE_URL = "https://spilari.nyr.ruv.is/gql/"

    # GraphQL query hashes (these may need updating when RÚV changes their API)
    QUERY_HASHES = {
        "getCategories": "7d5f9d18d22e7820e095abdce0d97f0bd516e14e0925748cd75ac937d98703db",
        "getCategory": "6ef244edfc897f95aabd1f915d58264329bb64ee498ae8df359ca0fa14c2278a",
        # "getSerie": "afd9cf0c67f1ebed0a981b72ee127a5a152eb90f4adb2b3bd3e6c1ec185a2dd3", # Operation removed
        "getEpisode": "3c1f5cfa93253b4aabd0f1023be91a30d36ef0acc0d3356aac445d9e005b97f8",
    }

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

    def _build_persisted_query_url(self, operation: str, variables: dict) -> str:
        """Build a GET URL for persisted GraphQL queries"""
        # Use separators to remove spaces and manually encode to match browser format
        variables_json = json.dumps(variables, separators=(",", ":"))
        extensions_json = json.dumps(
            {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": self.QUERY_HASHES[operation],
                }
            },
            separators=(",", ":"),
        )

        # Manually build query string to avoid unwanted encoding
        encoded_variables = urllib.parse.quote(variables_json)
        encoded_extensions = urllib.parse.quote(extensions_json)

        return (
            f"{self.BASE_URL}?operationName={operation}&variables={encoded_variables}&extensions={encoded_extensions}"
        )

    def _handle_response(self, response_data: dict, operation: str, url: str) -> dict:
        """Handle GraphQL response errors"""
        if "errors" in response_data:
            for error in response_data["errors"]:
                if error.get("extensions", {}).get("code") == "PERSISTED_QUERY_NOT_FOUND":
                    raise PersistedQueryNotFoundError(operation, url, response_data)
            raise RUVAPIError(f"GraphQL error in {operation}: {response_data['errors']}")

        if "data" not in response_data:
            raise RUVAPIError(f"No data in {operation} response: {response_data}")

        return response_data["data"]

    async def _query_get(self, operation: str, variables: dict) -> dict:
        """Execute a GET request with persisted query"""
        url = self._build_persisted_query_url(operation, variables)
        log.debug(f"GET {operation}: {url}")

        response = await self.client.get(url)
        response.raise_for_status()
        response_data = response.json()

        return self._handle_response(response_data, operation, url)

    async def _query_post(self, operation: str, variables: dict, query: str) -> dict:
        """Execute a POST request with full GraphQL query"""
        payload = {"operationName": operation, "variables": variables, "query": query}

        log.debug(f"POST {operation}: {variables}")
        response = await self.client.post(self.BASE_URL, json=payload)
        response.raise_for_status()
        response_data = response.json()

        return self._handle_response(response_data, operation, self.BASE_URL)

    async def _query_with_fallback(self, operation: str, variables: dict, fallback_query: str) -> dict:
        """Try GET first, fallback to POST if persisted query fails"""
        try:
            return await self._query_get(operation, variables)
        except PersistedQueryNotFoundError:
            log.info(f"Persisted query failed for {operation}, trying POST fallback")
            return await self._query_post(operation, variables, fallback_query)

    async def get_categories(self, category_type: str = "tv") -> List[Category]:
        """Get all categories for the given type"""
        data = await self._query_get("getCategories", {"type": category_type})
        return data["Category"]["categories"]

    async def get_category_programs(self, slug: str, category_type: str = "tv") -> List[Program]:
        """Get all programs in a category"""
        variables = {"category": slug, "station": category_type}
        data = await self._query_get("getCategory", variables)
        return data["Category"]["categories"][0]["programs"]

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
            }
          }
        }
        """

        variables = {"programID": program_id}
        # Use _query_post directly to ensure we use the updated query structure
        # and get all required fields, bypassing potential GET cache with old structure.
        data = await self._query_post("getEpisode", variables, query)
        return data["Program"]

    async def get_all_programs(self) -> Programs:
        """Get all programs from RÚV (without detailed episode info)"""
        log.info("Fetching all categories...")
        categories = await self.get_categories()
        log.debug(f"Found {len(categories)} categories")

        log.info("Fetching programs from all categories...")
        category_programs = await asyncio.gather(
            *[self.get_category_programs(category["slug"]) for category in categories]
        )

        # Flatten the list of lists and convert to dict
        all_programs = [program for programs in category_programs for program in programs]
        log.info(f"Found {len(all_programs)} total programs")

        return {program["id"]: program for program in all_programs}

    async def get_programs_with_episodes(self, program_ids: List[int]) -> Programs:
        """Get detailed program info with file URLs for episodes"""
        log.info(f"Fetching detailed program and episode info for {len(program_ids)} programs...")

        fetched_programs: list[Program] = []
        for program_id in program_ids:
            # get_program_episodes now fetches all required details, including file URLs
            program = await self.get_program_episodes(program_id)
            if program:
                log.debug(f"Successfully fetched program ID {program_id} with its episodes.")
                fetched_programs.append(program)
            else:
                log.warning(f"Could not fetch program ID {program_id}.")

        # Ensure 'id' exists in program objects before creating the dictionary
        return {prog["id"]: prog for prog in fetched_programs if prog and "id" in prog}


# Utility functions for caching
def save_programs_cache(file_path: Path, programs: Programs):
    """Save programs to cache file"""
    with file_path.open("w", encoding="utf-8") as f:
        json.dump(programs, f, ensure_ascii=False)


def load_programs_cache(file_path: Path) -> Programs:
    """Load programs from cache file"""
    with file_path.open("r") as f:
        return json.load(f)


def load_last_fetched(file_path: Path) -> Optional[datetime]:
    """Load the timestamp of last fetch"""
    if file_path.exists():
        with file_path.open() as f:
            date_time_str = f.read().strip()
            return datetime.fromisoformat(date_time_str)
    return None


def save_last_fetched(file_path: Path):
    """Save the current timestamp"""
    with file_path.open("w") as f:
        f.write(datetime.now().isoformat())


async def load_programs(
    force_reload: bool, programs_cache: Path, last_fetched_file: Path, refresh_interval_sec: int = 10 * 60
) -> Programs:
    """Load programs from cache or fetch from API if needed"""
    last_fetched = load_last_fetched(last_fetched_file)
    should_fetch = force_reload

    if not should_fetch and last_fetched is None:
        log.info("No previous fetch timestamp found")
        should_fetch = True
    elif not should_fetch and last_fetched + timedelta(seconds=refresh_interval_sec) < datetime.now():
        log.info("Cache is stale, refreshing...")
        should_fetch = True

    if should_fetch:
        async with RUVClient() as client:
            programs = await client.get_all_programs()
        save_programs_cache(programs_cache, programs)
        save_last_fetched(last_fetched_file)
        log.info(f"Fetched and cached {len(programs)} programs")
    else:
        try:
            programs = load_programs_cache(programs_cache)
            log.info(f"Loaded {len(programs)} programs from cache")
        except FileNotFoundError:
            async with RUVClient() as client:
                programs = await client.get_all_programs()
            save_programs_cache(programs_cache, programs)
            save_last_fetched(last_fetched_file)
            log.info(f"Cache not found, fetched {len(programs)} programs")

    return programs
