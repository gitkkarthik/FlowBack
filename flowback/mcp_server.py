"""
FlowBack MCP Server

Exposes FlowBack as a set of Claude tools so your coding context,
error history, and skill gaps are available directly inside Claude Code.

Setup:
  claude mcp add flowback flowback-mcp

Tools:
  pause        — scan project folders and save your context
  resume       — get your last saved briefing(s) as context
  track_error  — analyze an error and see if you're in a loop
  skill_gaps   — see recurring error patterns and skill areas to strengthen
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# Load API key before importing gemini
load_dotenv(Path.home() / ".flowback" / ".env")
load_dotenv()

from flowback import capture, database, gemini  # noqa: E402

database.init_db()

mcp = FastMCP(
    "flowback",
    instructions="Developer context tool — save your coding context, track errors, and identify skill gaps.",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_briefing(b: dict) -> str:
    project = Path(b["project_path"]).name if b.get("project_path") else "Project"
    lines = [f"### {project}"]
    if b.get("goal"):
        lines.append(f"**Goal:** {b['goal']}")
    if b.get("stuck_point"):
        lines.append(f"**Stuck point:** {b['stuck_point']}")
    if b.get("next_steps"):
        steps = "\n".join(f"{i+1}. {s}" for i, s in enumerate(b["next_steps"]))
        lines.append(f"**Next steps:**\n{steps}")
    if b.get("files_changed"):
        lines.append(f"**Files changed:** {', '.join(Path(f).name for f in b['files_changed'])}")
    if b.get("tags"):
        lines.append(f"**Tags:** {' '.join('#' + t for t in b['tags'])}")
    return "\n".join(lines)


def _format_error_analysis(analysis: dict, occurrences: int) -> str:
    lines = []
    if occurrences == 1:
        lines.append("**First time seeing this error.**")
    elif occurrences == 2:
        lines.append(f"**⚠ Seen {occurrences} times — watch this pattern.**")
    else:
        lines.append(f"**🔁 Hit {occurrences} times — you're in a loop!**")

    if analysis.get("error_type"):
        lines.append(f"**Type:** {analysis['error_type']}")
    if analysis.get("root_cause"):
        lines.append(f"**Root cause:** {analysis['root_cause']}")
    if analysis.get("solution"):
        steps = "\n".join(f"{i+1}. {s}" for i, s in enumerate(analysis["solution"]))
        lines.append(f"**How to fix it:**\n{steps}")
    if analysis.get("prevention"):
        label = "**Break the loop:**" if occurrences >= 3 else "**Prevention:**"
        lines.append(f"{label} {analysis['prevention']}")
    if analysis.get("tags"):
        lines.append(f"**Tags:** {' '.join('#' + t for t in analysis['tags'])}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def pause(paths: list[str], note: Optional[str] = None) -> str:
    """
    Scan one or more project folders and save your coding context as an AI briefing.
    Call this before stepping away from your work.

    Args:
        paths: List of absolute paths to project directories to scan.
        note:  Optional note about what you were doing (e.g. "debugging auth middleware").
    """
    resolved = [str(Path(p).expanduser().resolve()) for p in paths]
    bad = [p for p in resolved if not Path(p).is_dir()]
    if bad:
        return f"Error: not a directory: {', '.join(bad)}"

    files_changed, file_contents = capture.take_snapshot(resolved)
    if not files_changed:
        return (
            "No recently modified files found in the last 2 hours. "
            "Make sure the paths are correct and you have recent changes."
        )

    snapshot_id = database.insert_snapshot(
        watch_paths=resolved,
        user_note=note,
        files_changed=files_changed,
        file_contents=file_contents,
    )

    results = []
    for project_path in resolved:
        project_files = [f for f in files_changed if f.startswith(project_path)]
        project_contents = {k: v for k, v in file_contents.items() if k.startswith(project_path)}
        if not project_files:
            continue

        try:
            briefing_data, raw = gemini.generate_briefing(
                user_note=note,
                file_contents=project_contents,
                files_changed=project_files,
            )
        except (RuntimeError, ValueError) as e:
            results.append(f"### {Path(project_path).name}\nError generating briefing: {e}")
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
        results.append(_format_briefing({**briefing_data, "project_path": project_path}))

    if not results:
        return "No briefings generated."

    header = f"## FlowBack — Context Saved (snapshot #{snapshot_id})\n"
    footer = "\n\nRun `flowback resume` or call the `resume` tool when you're back."
    return header + "\n\n".join(results) + footer


@mcp.tool()
def resume() -> str:
    """
    Return your last saved coding context — what you were working on,
    where you were stuck, and what to do next.
    Call this at the start of a session to get back up to speed instantly.
    """
    all_briefings = database.list_briefings()
    if not all_briefings:
        return (
            "No saved context found. "
            "Run `flowback pause <path>` or call the `pause` tool before stepping away next time."
        )

    # Group by snapshot — get the most recent session
    sessions: dict[int, list[dict]] = {}
    for b in all_briefings:
        sessions.setdefault(b["snapshot_id"], []).append(b)

    latest_id = max(sessions.keys())
    latest = sessions[latest_id]
    ts = latest[0]["created_at"]

    lines = [f"## FlowBack — Last Session ({ts})"]
    for b in reversed(latest):
        lines.append("")
        lines.append(_format_briefing(b))

    if len(sessions) > 1:
        lines.append(f"\n---\n*{len(sessions) - 1} older session(s) available. Call `resume_all` for full history.*")

    return "\n".join(lines)


@mcp.tool()
def track_error(error: str, project: Optional[str] = None) -> str:
    """
    Track an error message, get AI root cause analysis and fix steps,
    and see whether you're caught in a recurring loop.

    Args:
        error:   The full error message or stack trace.
        project: Optional path to the project where the error occurred.
                 Defaults to the current working directory.
    """
    import os
    project_path = str(Path(project).expanduser().resolve()) if project else os.getcwd()

    existing = database.list_errors()

    try:
        analysis, raw = gemini.analyze_error(error, occurrence_count=0)
    except (RuntimeError, ValueError) as e:
        return f"Error analyzing with Gemini: {e}"

    fingerprint = analysis["fingerprint"]
    prior = [e for e in existing if e["fingerprint"] == fingerprint]
    occurrence_count = len(prior)

    if occurrence_count >= 2:
        try:
            analysis, raw = gemini.analyze_error(error, occurrence_count=occurrence_count)
        except (RuntimeError, ValueError):
            pass

    database.insert_error(
        raw_error=error,
        fingerprint=fingerprint,
        error_type=analysis.get("error_type"),
        root_cause=analysis.get("root_cause"),
        solution=analysis.get("solution", []),
        prevention=analysis.get("prevention"),
        tags=analysis.get("tags", []),
        project_path=project_path,
    )

    return _format_error_analysis(analysis, occurrence_count + 1)


@mcp.tool()
def skill_gaps() -> str:
    """
    Return a summary of your recurring error patterns and skill areas to strengthen,
    based on all tracked errors across all projects.
    """
    summary = database.get_error_summary()
    tag_counts = database.get_all_tag_counts()

    if not summary:
        return (
            "No errors tracked yet. "
            "Use `track_error` or run `flowback error` in your terminal to start building your error history."
        )

    lines = ["## FlowBack — Skill Gaps & Recurring Patterns", ""]

    # Recurring errors (2+)
    recurring = [e for e in summary if e["count"] >= 2]
    if recurring:
        lines.append("### Recurring errors (fix these first)")
        for e in recurring:
            marker = "🔁" if e["count"] >= 3 else "⚠"
            lines.append(f"- {marker} **{e.get('error_type', 'Unknown')}** — hit {e['count']} times")
            if e.get("root_cause"):
                lines.append(f"  _{e['root_cause']}_")
        lines.append("")

    # Top skill tags
    if tag_counts:
        lines.append("### Skill areas to strengthen (by frequency)")
        for t in tag_counts[:8]:
            bar = "█" * min(t["count"], 10)
            lines.append(f"- **#{t['tag']}** {bar} ({t['count']})")
        lines.append("")

    # One-off errors
    oneoffs = [e for e in summary if e["count"] == 1]
    if oneoffs:
        lines.append(f"*{len(oneoffs)} one-off error(s) — less of a concern.*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
