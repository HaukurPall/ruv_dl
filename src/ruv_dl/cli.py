import logging
import sys
from itertools import chain
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import List, Tuple

import click
from tabulate import tabulate

from ruv_dl import main
from ruv_dl.ffmpeg import QUALITIES_STR_TO_INT
from ruv_dl.ruv_client import Programs

log = logging.getLogger("ruvsarpur")

CONFIG = main.Config()


@click.group()
@click.option(
    "--work-dir",
    help="""The working directory of the program, the current working directory by default.
For example downloaded content is placed in the folder "$WORK_DIR/downloads",
the program list is cached as "$WORK_DIR/programs.json", etc..
""",
    default=Path.cwd(),
    type=Path,
)
@click.option("--log-level", default="WARNING", help="The log level of the stdout. WARNING by default.")
def cli(work_dir: Path, log_level):
    global CONFIG
    # Create the config and save as a global variable
    CONFIG = main.Config(work_dir)
    CONFIG.initialize_dirs()

    log.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s: %(message)s", "%Y-%m-%d %H:%M:%S")

    stdout_handler = logging.StreamHandler(sys.stderr)
    stdout_handler.setLevel(log_level)
    stdout_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(CONFIG.run_log, maxBytes=10000, backupCount=1)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    log.addHandler(file_handler)
    log.addHandler(stdout_handler)
    # Increase the log level of gql - otherwise we are spammed
    logging.getLogger("gql").setLevel(logging.WARN)


@cli.command()
@click.argument("patterns", type=str, nargs=-1, required=True)
@click.option(
    "--ignore-case/--no-ignore-case", default=CONFIG.ignore_case, help="Should we ignore casing when searching?"
)
@click.option("--only-ids/--no-only-ids", default=CONFIG.only_ids, help="Should we only return the found program ids?")
@click.option(
    "--force-reload-programs/--no-force-reload-programs",
    default=CONFIG.force_reload_programs,
    help="Should we force reloading the program list?",
)
def search(patterns: Tuple[str, ...], ignore_case: bool, only_ids: bool, force_reload_programs: bool):
    """Search for a program based on the patterns provided.
    Make sure that each pattern is separated by a space by surrounding each pattern with quotation marks:
    "pattern one" "pattern two"."""
    CONFIG.ignore_case = ignore_case
    CONFIG.only_ids = only_ids
    CONFIG.force_reload_programs = force_reload_programs
    found_programs = main.search(patterns=patterns, config=CONFIG)
    if CONFIG.only_ids:
        return click.echo(" ".join([str(id) for id in found_programs]))
    headers, rows = program_results(found_programs)
    return click.echo(tabulate(tabular_data=rows, headers=headers, tablefmt="github"))


def maybe_read_stdin(_ctx, _param, value):
    """Read the stdin if no value is provided"""
    if not value and not click.get_text_stream("stdin").isatty():
        return click.get_text_stream("stdin").read().strip().split(" ")
    else:
        return value


@cli.command()
@click.argument("program-ids", nargs=-1, type=str, callback=maybe_read_stdin)
@click.option(
    "--quality",
    help="""The quality of the file to download.
The default value, when not supplied, is 1080p.
""",
    type=click.Choice(list(QUALITIES_STR_TO_INT.keys())),
    default=CONFIG.quality,
)
@click.option(
    "--force-reload-programs/--no-force-reload-programs",
    default=CONFIG.force_reload_programs,
    help="Should we force reloading the program list?",
)
def download_program(program_ids: Tuple[str, ...], quality: str, force_reload_programs):
    """Download the supplied program ids. Can be multiple.
    Use the 'search' functionality with --only-ids to get them and pipe them to this command."""
    CONFIG.quality = quality
    CONFIG.force_reload_programs = force_reload_programs
    downloaded_episodes, skipped_episodes = main.download_program(program_ids=program_ids, config=CONFIG)
    if len(downloaded_episodes) == 0 and len(skipped_episodes) == 0:
        click.echo("No episodes downloaded.")
    click.echo("\n".join(episode.file_name() for episode in chain(downloaded_episodes, skipped_episodes)))


@cli.command()
@click.argument("shows", nargs=-1, type=str)
@click.option(
    "--dry-run/--no-dry-run",
    default=CONFIG.dry_run,
    help="Only mimic the organization of shows - do not actually move them.",
)
def organize(shows: List[str], dry_run: bool):
    """Organizes **TV shows** from the 'downloads' directory to the 'organized' directory.
    This is a 'best effort' approach as many TV shows do not contain enough information for correct organization.
    The show format is understood by plex and other tools such as tvrenamer.
    Please note that the show number is from RÚV and is often wrong.
    """
    CONFIG.dry_run = dry_run
    click.echo(main.organize([Path(show) for show in shows], config=CONFIG))


@cli.command()
@click.argument("program-ids", nargs=-1, type=str, callback=maybe_read_stdin)
@click.option(
    "--force-reload-programs/--no-force-reload-programs",
    default=CONFIG.force_reload_programs,
    help="Should we force reloading the program list?",
)
def details(program_ids: Tuple[str, ...], force_reload_programs: bool):
    """Get the details of all the episodes of the supplied program ids. Can be multiple."""
    CONFIG.force_reload_programs = force_reload_programs
    click.echo(main.details(program_ids, config=CONFIG))


@cli.command()
@click.argument("file_path", type=Path)
@click.argument("timestamp", type=str)
def split_episode(file_path: Path, timestamp: str):
    """Split an episode into two episodes based on the timestamp provided [-][<HH>:]<MM>:<SS>[.<m>...]."""
    result = main.split_episode(file_path, timestamp)
    if result:
        click.echo("\n".join((str(path) for path in result)))
    else:
        click.echo("Unable to split file.")


ProgramRow = Tuple[str, str, int, str, str]
ProgramHeader = Tuple[str, str, str, str, str]


def program_results(programs: Programs) -> Tuple[ProgramHeader, List[ProgramRow]]:
    """Format the program results for printing."""
    header = ("Program title", "Foreign title", "Episode count", "Program ID", "Short description")
    rows = []
    for program in programs.values():
        try:
            rows.append(
                (
                    program["title"],
                    program["foreign_title"],
                    len(program["episodes"]),
                    program["id"],
                    program["short_description"][:40] if program["short_description"] is not None else "",
                )
            )
        except KeyError:
            log.warning("Malformed program: %s", program)
        except AttributeError:
            log.warning("Malformed program: %s", program)
    return header, rows


if __name__ == "__main__":
    cli()
