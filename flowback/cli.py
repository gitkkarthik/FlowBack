"""
flowback CLI — pick up exactly where you left off.

Commands:
  flowback pause <path1> <path2> ... [--note "optional note"]
  flowback resume [--all]
  flowback tags
"""

from __future__ import annotations

import sys
from itertools import groupby
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from flowback import capture, database, gemini

app = typer.Typer(
    name="flowback",
    help="Pick up exactly where you left off.",
    add_completion=False,
    pretty_exceptions_enable=False,
)

console = Console()
err_console = Console(stderr=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tag_pills(tags: list[str]) -> Text:
    """Return a Rich Text object with tags rendered as coloured pills."""
    text = Text()
    for i, tag in enumerate(tags):
        if i:
            text.append("  ")
        text.append(f"#{tag}", style="bold magenta")
    return text


def _project_label(project_path: Optional[str]) -> str:
    if not project_path:
        return "project"
    return Path(project_path).name or project_path


def _resolve_path(p: str) -> str:
    """Expand ~ and resolve to absolute path string."""
    return str(Path(p).expanduser().resolve())


def _briefings_for_snapshot(snapshot_id: int) -> list[dict]:
    """Return all briefings linked to a snapshot, ordered by id asc."""
    all_briefings = database.list_briefings()
    return [b for b in reversed(all_briefings) if b["snapshot_id"] == snapshot_id]


def _all_snapshots_with_briefings() -> list[tuple[dict, list[dict]]]:
    """
    Return [(snapshot, [briefings])] ordered newest-first,
    skipping snapshots with no briefings.
    """
    snapshots = database.list_snapshots()  # newest first
    all_briefings = database.list_briefings()  # newest first

    briefings_by_snap: dict[int, list[dict]] = {}
    for b in reversed(all_briefings):  # oldest first so append order is asc
        briefings_by_snap.setdefault(b["snapshot_id"], []).append(b)

    result = []
    for snap in snapshots:
        bs = briefings_by_snap.get(snap["id"], [])
        if bs:
            result.append((snap, bs))
    return result


def _print_session(
    snap: dict,
    briefings: list[dict],
    *,
    is_latest: bool,
    show_dim: bool = False,
) -> None:
    """Render one session (snapshot + its briefings) to the console."""
    dim = not is_latest and show_dim

    # Session header
    ts = snap["created_at"]
    paths = snap.get("watch_paths", [])
    paths_str = "  ".join(f"[dim]{p}[/dim]" if dim else f"[bold]{p}[/bold]" for p in paths)

    if is_latest:
        header = f"[bold cyan]Session #{snap['id']}[/bold cyan]  [dim]{ts}[/dim]  {paths_str}"
        console.rule(header, style="cyan")
    else:
        header = f"[dim]Session #{snap['id']}  {ts}  {', '.join(paths)}[/dim]"
        console.rule(header, style="dim")

    note = snap.get("user_note")
    if note:
        console.print(f"  [italic dim]Note: {note}[/italic dim]")

    for briefing in briefings:
        label = _project_label(briefing.get("project_path"))
        style_prefix = "" if is_latest else "dim"

        # Goal panel
        goal_text = briefing.get("goal") or "[dim]—[/dim]"
        console.print(
            Panel(
                f"[{'bold ' if is_latest else 'dim'}]{goal_text}[/{'bold ' if is_latest else 'dim'}]",
                title=f"[bold]{label}[/bold] — Goal",
                border_style="cyan" if is_latest else "dim",
                padding=(0, 2),
            )
        )

        stuck = briefing.get("stuck_point") or ""
        if stuck:
            console.print(
                Panel(
                    f"[{'yellow' if is_latest else 'dim'}]{stuck}[/{'yellow' if is_latest else 'dim'}]",
                    title="Stuck point",
                    border_style="yellow" if is_latest else "dim",
                    padding=(0, 2),
                )
            )

        steps = briefing.get("next_steps", [])
        if steps:
            steps_text = Text()
            for i, step in enumerate(steps, 1):
                steps_text.append(f"{i}. ", style="bold green" if is_latest else "dim")
                steps_text.append(step + "\n", style="green" if is_latest else "dim")
            console.print(
                Panel(
                    steps_text,
                    title="Next steps",
                    border_style="green" if is_latest else "dim",
                    padding=(0, 2),
                )
            )

        tags = briefing.get("tags", [])
        if tags:
            console.print("  " + ("  " if is_latest else "") + _tag_pills(tags).markup if is_latest else "  " + " ".join(f"[dim]#{t}[/dim]" for t in tags))

    console.print()


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command()
def pause(
    paths: Annotated[list[str], typer.Argument(help="Project directories to snapshot")],
    note: Annotated[Optional[str], typer.Option("--note", "-n", help="Optional developer note")] = None,
) -> None:
    """Snapshot project folders and generate an AI briefing for each."""
    if not paths:
        err_console.print("[red]Error:[/red] Provide at least one project path.")
        raise typer.Exit(1)

    resolved = [_resolve_path(p) for p in paths]

    # Validate paths exist
    bad = [p for p in resolved if not Path(p).is_dir()]
    if bad:
        for b in bad:
            err_console.print(f"[red]Not a directory:[/red] {b}")
        raise typer.Exit(1)

    database.init_db()

    console.print()
    console.rule("[bold cyan]flowback pause[/bold cyan]", style="cyan")

    with console.status("[cyan]Scanning files…[/cyan]"):
        files_changed, file_contents = capture.take_snapshot(resolved)

    if not files_changed:
        console.print(
            Panel(
                "[yellow]No recently modified files found in the last 2 hours.[/yellow]\n"
                "Try touching a file or check that the paths are correct.",
                border_style="yellow",
                title="Nothing to snapshot",
            )
        )
        raise typer.Exit(0)

    console.print(f"  Found [bold]{len(files_changed)}[/bold] recently modified file(s).\n")

    # Insert one snapshot for all paths combined
    snapshot_id = database.insert_snapshot(
        watch_paths=resolved,
        user_note=note,
        files_changed=files_changed,
        file_contents=file_contents,
    )

    # Generate one briefing per project
    saved_count = 0
    for project_path in resolved:
        project_files = [f for f in files_changed if f.startswith(project_path)]
        project_contents = {k: v for k, v in file_contents.items() if k.startswith(project_path)}

        if not project_files:
            console.print(f"  [dim]No recent files in {project_path} — skipping.[/dim]")
            continue

        label = _project_label(project_path)

        with console.status(f"[cyan]Generating briefing for [bold]{label}[/bold]…[/cyan]"):
            try:
                briefing_data, raw = gemini.generate_briefing(
                    user_note=note,
                    file_contents=project_contents,
                    files_changed=project_files,
                )
            except (RuntimeError, ValueError) as e:
                err_console.print(f"[red]Gemini error for {label}:[/red] {e}")
                continue

        database.insert_briefing(
            snapshot_id=snapshot_id,
            goal=briefing_data.get("goal"),
            stuck_point=briefing_data.get("stuck_point"),
            next_steps=briefing_data.get("next_steps", []),
            files_changed=project_files,
            raw_response=raw,
            project_path=project_path,
            tags=briefing_data.get("tags", []),
        )
        saved_count += 1

        # Print confirmation panel for this project
        goal = briefing_data.get("goal") or "—"
        tags = briefing_data.get("tags", [])

        tag_line = ("  " + _tag_pills(tags).markup) if tags else ""

        console.print(
            Panel(
                f"[bold]{goal}[/bold]" + (f"\n\n{tag_line}" if tag_line else ""),
                title=f"[bold cyan]{label}[/bold cyan] — captured",
                border_style="cyan",
                padding=(1, 2),
            )
        )

    if saved_count == 0:
        console.print("[yellow]No briefings were saved.[/yellow]")
        raise typer.Exit(1)

    console.print(
        f"\n[bold green]Done![/bold green] Saved [bold]{saved_count}[/bold] briefing(s) "
        f"(snapshot #{snapshot_id}). Run [bold]flowback resume[/bold] to pick up later.\n"
    )


@app.command()
def resume(
    all_sessions: Annotated[bool, typer.Option("--all", "-a", help="Show all sessions, not just the latest")] = False,
) -> None:
    """Resume where you left off — show the last saved briefing(s)."""
    database.init_db()

    sessions = _all_snapshots_with_briefings()

    if not sessions:
        console.print(
            Panel(
                "No sessions found. Run [bold]flowback pause <path>[/bold] first.",
                border_style="yellow",
                title="Nothing here yet",
            )
        )
        raise typer.Exit(0)

    console.print()

    if all_sessions:
        for i, (snap, briefings) in enumerate(sessions):
            _print_session(snap, briefings, is_latest=(i == 0), show_dim=True)
    else:
        snap, briefings = sessions[0]
        _print_session(snap, briefings, is_latest=True)
        if len(sessions) > 1:
            console.print(
                f"[dim]  {len(sessions) - 1} older session(s) available. "
                f"Run [bold]flowback resume --all[/bold] to see them.[/dim]\n"
            )


@app.command()
def tags() -> None:
    """List all tags with their occurrence counts."""
    database.init_db()

    tag_counts = database.get_all_tag_counts()

    if not tag_counts:
        console.print(
            Panel(
                "No tags yet. Run [bold]flowback pause <path>[/bold] to generate briefings.",
                border_style="yellow",
                title="No tags found",
            )
        )
        raise typer.Exit(0)

    table = Table(
        box=box.ROUNDED,
        border_style="magenta",
        header_style="bold magenta",
        title="[bold magenta]FlowBack Tags[/bold magenta]",
        title_justify="left",
        show_lines=False,
        padding=(0, 1),
    )
    table.add_column("Tag", style="bold magenta", no_wrap=True)
    table.add_column("Count", justify="right", style="bold white")
    table.add_column("Last seen", style="dim")

    for entry in tag_counts:
        tag = entry["tag"]
        count = str(entry["count"])
        last_seen = entry.get("last_seen", "")
        # Trim datetime to date only for readability
        last_seen_display = last_seen[:10] if last_seen else "—"
        table.add_row(f"#{tag}", count, last_seen_display)

    console.print()
    console.print(table)
    console.print()
