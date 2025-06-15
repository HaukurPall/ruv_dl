import asyncio
import logging
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import typer
from rich.console import Console
from rich.table import Table

from ruv_dl import main
from ruv_dl.ffmpeg import QUALITIES_STR
from ruv_dl.hls_downloader import load_m3u8_available_resolutions
from ruv_dl.ruv_client import Programs

log = logging.getLogger("ruv_dl")
app = typer.Typer()
console = Console()
CONFIG: main.Config  # Global config, to be initialized in callback


@app.callback()
def main_callback(
    ctx: typer.Context,
    work_dir: Path = typer.Option(
        Path.cwd(),
        "--work-dir",
        help="""The working directory of the program.
For example downloaded content is placed in the folder "$WORK_DIR/downloads",
the program list is cached as "$WORK_DIR/programs.json", etc..
""",
        resolve_path=True,
    ),
    log_level: str = typer.Option(
        "WARNING",
        "--log-level",
        help="The log level of the stdout. WARNING by default.",
        case_sensitive=False,
    ),
):
    """
    RÚV Downloader: A CLI tool to download content from RÚV.
    """
    global CONFIG
    CONFIG = main.Config(work_dir)
    CONFIG.initialize_dirs()

    # Ensure log_level is uppercase for consistent comparison
    effective_log_level = log_level.upper()
    log.setLevel(effective_log_level)  # Set level on the logger itself

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Stdout handler (using stderr for logs is common for CLIs)
    stdout_handler = logging.StreamHandler(sys.stderr)
    stdout_handler.setLevel(effective_log_level)
    stdout_handler.setFormatter(formatter)

    # Clear existing handlers to avoid duplication if callback is invoked multiple times (e.g. in tests)
    if log.hasHandlers():
        log.handlers.clear()

    log.addHandler(stdout_handler)

    # Set level for other loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)


@app.command()
def search(
    patterns: List[str] = typer.Argument(..., help="Pattern(s) to search for in program titles."),
    ignore_case: bool = typer.Option(True, "--ignore-case/--no-ignore-case", help="Ignore casing when searching."),
    only_ids: bool = typer.Option(
        False, "--only-ids/--no-only-ids", help="Only return the found program IDs (space separated)."
    ),
    force_reload_programs: bool = typer.Option(
        False,
        "--force-reload-programs/--no-force-reload-programs",
        help="Force reloading the program list from RUV.",
    ),
):
    """Search for programs based on the supplied PATTERNS."""
    CONFIG.ignore_case = ignore_case
    CONFIG.only_ids = only_ids
    CONFIG.force_reload_programs = force_reload_programs
    found_programs = asyncio.run(main.search(tuple(patterns), config=CONFIG))

    if not found_programs:
        console.print("[yellow]No programs found matching your criteria.[/yellow]")
        return

    if CONFIG.only_ids:
        # found_programs is of type Programs (Dict[int, ProgramDict])
        # We should print the keys (program IDs) or the 'id' field from the values.
        # Using program['id'] from values is consistent with program_results
        console.print(" ".join([str(p_data["id"]) for p_data in found_programs.values()]))
    else:
        headers, rows = program_results(found_programs)
        table = Table(title="Search Results", show_header=True, header_style="bold magenta")
        for header in headers:
            table.add_column(header)
        for row in rows:
            table.add_row(*[str(item) for item in row])
        console.print(table)


@app.command()
def download_program(
    program_ids: Optional[List[str]] = typer.Argument(
        None, help="Program IDs to download. Reads from stdin if not provided."
    ),
    quality: str = typer.Option(
        "1080p",  # Default from main.Config
        "--quality",
        help=f"The quality of the file to download. Choices: {', '.join(QUALITIES_STR)}.",
        case_sensitive=False,
    ),
    force_reload_programs: bool = typer.Option(
        False,  # Default from main.Config
        "--force-reload-programs/--no-force-reload-programs",
        help="Force reloading the program list.",
    ),
):
    """Download all episodes of the supplied program IDs."""
    actual_program_ids: List[str] = []
    if program_ids:
        actual_program_ids.extend(program_ids)
    elif not sys.stdin.isatty():  # Check if not a TTY and program_ids is empty
        stdin_data = sys.stdin.read().strip()
        if stdin_data:
            actual_program_ids.extend(stdin_data.split())

    if not actual_program_ids:
        console.print("[bold red]Error: No program IDs provided via arguments or stdin.[/bold red]")
        raise typer.Exit(code=1)

    if quality.lower() not in [q.lower() for q in QUALITIES_STR]:  # Case-insensitive check
        console.print(
            f"[bold red]Error: Invalid quality '{quality}'. Choose from: {', '.join(QUALITIES_STR)}[/bold red]"
        )
        raise typer.Exit(code=1)

    CONFIG.quality = quality
    CONFIG.force_reload_programs = force_reload_programs

    console.print(f"Attempting to download programs: {', '.join(actual_program_ids)} with quality: {quality}")

    downloaded_episodes, skipped_episodes = asyncio.run(main.download_program(tuple(actual_program_ids), config=CONFIG))

    if not downloaded_episodes and not skipped_episodes:
        console.print("[yellow]No episodes were downloaded or skipped. Check program IDs and availability.[/yellow]")
    else:
        if downloaded_episodes:
            console.print("\n[bold green]Successfully downloaded episodes:[/bold green]")
            for episode in downloaded_episodes:
                console.print(f"- {episode.file_name()}")
        if skipped_episodes:
            console.print("\n[bold yellow]Skipped episodes (already exist or other reasons):[/bold yellow]")
            for episode in skipped_episodes:
                console.print(f"- {episode.file_name()}")


@app.command()
def organize(
    shows_paths: List[Path] = typer.Argument(
        ...,  # Ellipsis means it's required
        help="Paths to show directories or files to organize.",
        exists=True,  # Typer will check if path exists
        file_okay=True,
        dir_okay=True,
        resolve_path=True,  # Converts to absolute path
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run/--no-dry-run",
        help="Mimic organization without moving files.",  # Default from main.Config
    ),
):
    """Organize SHOWS into a 'Title/Season X/filename' structure."""
    CONFIG.dry_run = dry_run

    console.print(f"Organizing shows/files: {[str(p) for p in shows_paths]}")
    if dry_run:
        console.print("[yellow]Dry run enabled. No files will be moved.[/yellow]")

    organized_items = main.organize(shows_paths, config=CONFIG)

    if not organized_items:
        console.print("[yellow]No files were organized.[/yellow]")
        return

    table = Table(title="File Organization Summary", show_header=True, header_style="bold blue")
    table.add_column("Original Path", style="dim cyan")
    table.add_column("New Path", style="green")

    for path_old, path_new in organized_items.items():
        table.add_row(str(path_old), str(path_new))
    console.print(table)


@app.command()
def details(
    program_ids: Optional[List[str]] = typer.Argument(
        None, help="Program IDs to get details for. Reads from stdin if not provided."
    ),
    force_reload_programs: bool = typer.Option(
        False,  # Default from main.Config
        "--force-reload-programs/--no-force-reload-programs",
        help="Force reloading the program list.",
    ),
):
    """Get and display details for episodes of the supplied program IDs."""
    actual_program_ids: List[str] = []
    if program_ids:
        actual_program_ids.extend(program_ids)
    elif not sys.stdin.isatty():
        stdin_data = sys.stdin.read().strip()
        if stdin_data:
            actual_program_ids.extend(stdin_data.split())

    if not actual_program_ids:
        console.print("[bold red]Error: No program IDs provided via arguments or stdin.[/bold red]")
        raise typer.Exit(code=1)

    CONFIG.force_reload_programs = force_reload_programs

    # main.details now returns Programs (Dict[int, ProgramDict])
    programs_data: Programs = asyncio.run(main.details(tuple(actual_program_ids), config=CONFIG))

    if not programs_data:
        console.print("[yellow]No details found for the provided program IDs.[/yellow]")
        return

    for program_id_key, program_details_dict in programs_data.items():
        console.print(
            f"\n[bold magenta]Program: {program_details_dict.get('title', 'N/A')} (ID: {program_details_dict.get('id', program_id_key)})[/bold magenta]"
        )
        console.print(f"  [cyan]Foreign Title:[/cyan] {program_details_dict.get('foreign_title', 'N/A')}")
        console.print(
            f"  [cyan]Description:[/cyan] {program_details_dict.get('short_description') or program_details_dict.get('description', 'N/A')}"
        )

        episodes = program_details_dict.get("episodes", [])
        if not episodes:
            console.print("  [yellow]No episodes found for this program.[/yellow]")
            continue

        episode_table = Table(
            title=f"Episodes for {program_details_dict.get('title', 'N/A')}", show_header=True, header_style="bold blue"
        )
        episode_table.add_column("Episode Title", style="dim", width=40)
        episode_table.add_column("Episode ID")
        episode_table.add_column("Published")
        episode_table.add_column("Duration (s)")
        episode_table.add_column("Available Qualities")
        episode_table.add_column("File URL", overflow="fold")

        for episode in episodes:
            episode_title = episode.get("title", "N/A")
            episode_id = str(episode.get("id", "N/A"))
            published_date = (
                episode.get("firstrun", {}).get("isl", {}).get("date", "N/A")
                if isinstance(episode.get("firstrun"), dict)
                else episode.get("firstrun", "N/A")
            )
            duration = (
                str(episode.get("duration", {}).get("seconds", "N/A"))
                if isinstance(episode.get("duration"), dict)
                else str(episode.get("duration", "N/A"))
            )

            available_qualities_str = "N/A"
            if episode.get("file"):
                try:
                    resolutions = load_m3u8_available_resolutions(episode["file"])
                    if resolutions:
                        available_qualities_str = "/".join(
                            f"{res_h}p" for _, res_h in sorted(resolutions, key=lambda x: x[1], reverse=True)
                        )
                    else:
                        available_qualities_str = "[yellow]Could not fetch[/yellow]"
                except Exception as e:
                    log.debug(f"Could not load resolutions for {episode.get('file')}: {e}")
                    available_qualities_str = "[red]Error fetching[/red]"

            file_url = episode.get("file", "N/A")

            episode_table.add_row(
                episode_title, episode_id, published_date, duration, available_qualities_str, file_url
            )
        console.print(episode_table)


@app.command()
def split_episode(
    file_path: Path = typer.Argument(
        ...,
        help="Path to the episode file to split.",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
    ),
    timestamp: str = typer.Argument(..., help="Timestamp to split at, e.g., [-][<HH>:]<MM>:<SS>[.<m>...]."),
):
    """Split an episode file into two based on the provided TIMESTAMP."""
    console.print(f"Attempting to split file: '{file_path}' at timestamp: {timestamp}")
    result = main.split_episode(file_path, timestamp)
    if result:
        console.print(f"[bold green]Successfully split '{file_path.name}'. New files created:[/bold green]")
        for path_item in result:
            console.print(f"  - [green]{path_item}[/green]")
    else:
        console.print(f"[bold red]Error: Unable to split file '{file_path}'.[/bold red]")
        console.print(
            "This could be due to an invalid timestamp, file format, or other issues. Check logs for details."
        )


# Moved ProgramRow and ProgramHeader type aliases to be defined before their first use if needed,
# or they can remain here if only program_results uses them.
# For now, assuming program_results is the primary user.
ProgramRow = Tuple[str, str, int, str, str]
ProgramHeader = Tuple[str, str, str, str, str]


def program_results(programs: Programs) -> Tuple[ProgramHeader, List[ProgramRow]]:
    """Format the program results for printing."""
    header = ("Program title", "Foreign title", "Episode count", "Program ID", "Short description")
    rows = []
    for program_id_key, program_content in programs.items():
        try:
            title = program_content.get("title", "N/A")
            foreign_title = program_content.get("foreign_title", "N/A")
            episodes = program_content.get("episodes", [])
            episode_count = len(episodes)
            # Use program_id_key (the dict key) or program_content.get('id')
            # Prefer program_content.get('id') if it's reliably the ID, otherwise program_id_key
            actual_program_id = program_content.get("id", program_id_key)
            short_desc = program_content.get("short_description", "")

            rows.append(
                (
                    title,
                    foreign_title,
                    episode_count,
                    str(actual_program_id),  # Ensure ID is string for table
                    short_desc[:40] if short_desc else "",
                )
            )
        except Exception as e:  # Catching a broader exception for unexpected issues
            log.warning(
                f"Malformed program data (ID: {program_id_key}) or unexpected error processing program: {program_content}, Error: {e}"
            )
    return header, rows


if __name__ == "__main__":
    app()
