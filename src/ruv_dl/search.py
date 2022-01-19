"""A module for searching for programs."""
import logging
from typing import List, Tuple

from ruv_dl.ruv_client import Programs

log = logging.getLogger(__name__)


def get_all_programs_by_pattern(programs: Programs, pattern: str, ignore_case: bool) -> Programs:
    """Get all programs that match the pattern.
    Can be multiple.
    """
    if ignore_case:
        pattern = pattern.lower()
    found_programs = {}
    for program in programs.values():
        foreign_title = program.get("foreign_title", None)
        title = program.get("title", "")
        if ignore_case:
            foreign_title = foreign_title.lower() if foreign_title else None
            title = title.lower()
        if pattern in title or (foreign_title is not None and pattern in foreign_title):
            found_programs[program["id"]] = program
    return found_programs
