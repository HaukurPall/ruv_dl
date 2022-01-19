import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional, Tuple

import click

from ruv_dl import main

logger = logging.getLogger("ruvsarpur")

config = main.Config()


@click.group()
@click.option(
    "--work-dir",
    help="""The working directory of the program, the current working directory by default.
For example downloaded content is placed in the folder "$WORK_DIR/downloads".
The program list is cached as "$WORK_DIR/programs.json".
The downloaded episode list is stored in "$WORK_DIR/downloaded.log".
""",
    default=Path.cwd(),
    type=Path,
)
@click.option("--log-level", default="WARNING", help="The log level of the stdout.")
def cli(work_dir: Path, log_level):
    global config
    # Create the config and save as a global variable
    config = main.Config(work_dir)
    config.initialize_dirs()

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s: %(message)s", "%Y-%m-%d %H:%M:%S")

    stdout_handler = logging.StreamHandler(sys.stderr)
    stdout_handler.setLevel(log_level)
    stdout_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(config.run_log, maxBytes=10000, backupCount=1)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stdout_handler)
    # Increase the log level of gql - otherwise we are spammed
    logging.getLogger("gql").setLevel(logging.WARN)


@cli.command()
@click.argument("patterns", type=str, nargs=-1, required=True)
@click.option(
    "--ignore-case/--no-ignore-case", default=config.ignore_case, help="Should we ignore casing when searching?"
)
@click.option("--only-ids/--no-only-ids", default=config.only_ids, help="Should we only return the found program ids?")
@click.option(
    "--force-reload-programs/--no-force-reload-programs",
    default=config.force_reload_programs,
    help="Should we force reloading the program list?",
)
def search(patterns: Tuple[str, ...], ignore_case: bool, only_ids: bool, force_reload_programs: bool):
    """Search for a program based on the patterns provided.
    Make sure that each pattern is separated by a space by surrounding each pattern with quotation marks:
    "pattern one" "pattern two"."""
    global config
    config.ignore_case = ignore_case
    config.only_ids = only_ids
    config.force_reload_programs = force_reload_programs
    # TODO: Add support for checking date of last programs fetch.
    click.echo(main.search(patterns=patterns, config=config))


def maybe_read_stdin(ctx, param, value):
    if not value and not click.get_text_stream("stdin").isatty():
        return click.get_text_stream("stdin").read().strip().split(" ")
    else:
        return value


@cli.command()
@click.argument("program-ids", nargs=-1, type=str, callback=maybe_read_stdin)
@click.option(
    "--quality",
    help="""The quality of the file to download.
The default value, when not supplied, is the highest quality.
Usually ranges from 0-4, where 0 is the worst quality (426x240) and 4 is the best (1920x1080) = Full HD or 1080p.
3 tends to be 1280x720 = HD or 720p.
""",
    type=int,
    default=config.quality,
)
@click.option(
    "--force-reload-programs/--no-force-reload-programs",
    default=config.force_reload_programs,
    help="Should we force reloading the program list?",
)
def download_program(program_ids: Tuple[str, ...], quality: Optional[int], force_reload_programs):
    """Download the supplied program ids. Can be multiple.
    Use the 'search' functionality with --only-ids to get them and pipe them to this command."""
    global config
    config.quality = quality
    config.force_reload_programs = force_reload_programs
    click.echo(main.download_program(program_ids=program_ids, config=config))


@cli.command()
@click.option(
    "--dry-run/--no-dry-run",
    default=config.dry_run,
    help="Only mimic the organization of shows - do not actually move them.",
)
def organize(dry_run: bool):
    """Organizes **TV shows** from the 'downloads' directory to the 'organized' directory.
    This is a 'best effort' approach as many TV shows do not contain enough information for correct organization.
    The show format is understood by plex and other tools such as tvrenamer.
    Please note that the show number is from RÚV and is often wrong.
    """
    global config
    config.dry_run = dry_run
    click.echo(main.organize(config=config))


@cli.command()
@click.argument("program-ids", nargs=-1, type=str, callback=maybe_read_stdin)
@click.option(
    "--force-reload-programs/--no-force-reload-programs",
    default=config.force_reload_programs,
    help="Should we force reloading the program list?",
)
def details(program_ids: Tuple[str, ...], force_reload_programs: bool):
    """Get the details of all the episodes of the supplied program ids. Can be multiple."""
    global config
    config.force_reload_programs = force_reload_programs
    click.echo(main.details(program_ids, config=config))


if __name__ == "__main__":
    cli()
