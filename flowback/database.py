import sqlite3
import json
from pathlib import Path
from typing import Optional

DB_PATH = Path.home() / ".flowback" / "history.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            watch_path TEXT,
            user_note TEXT,
            files_changed TEXT NOT NULL DEFAULT '[]',
            file_contents TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS briefings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            project_path TEXT,
            goal TEXT,
            stuck_point TEXT,
            next_steps TEXT NOT NULL DEFAULT '[]',
            files_changed TEXT NOT NULL DEFAULT '[]',
            tags TEXT NOT NULL DEFAULT '[]',
            raw_response TEXT
        );

        CREATE TABLE IF NOT EXISTS errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            raw_error TEXT NOT NULL,
            fingerprint TEXT NOT NULL,
            error_type TEXT,
            root_cause TEXT,
            solution TEXT NOT NULL DEFAULT '[]',
            prevention TEXT,
            tags TEXT NOT NULL DEFAULT '[]',
            project_path TEXT
        );
    """)

    # Migrations for existing databases
    for migration in [
        "ALTER TABLE briefings ADD COLUMN project_path TEXT",
        "ALTER TABLE briefings ADD COLUMN tags TEXT NOT NULL DEFAULT '[]'",
        "ALTER TABLE errors ADD COLUMN project_path TEXT",
    ]:
        try:
            cursor.execute(migration)
            conn.commit()
        except Exception:
            pass  # column already exists

    conn.commit()
    conn.close()


def insert_snapshot(
    watch_paths: list[str],
    user_note: Optional[str],
    files_changed: list[str],
    file_contents: dict[str, str],
) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO snapshots (watch_path, user_note, files_changed, file_contents)
        VALUES (?, ?, ?, ?)
        """,
        (
            json.dumps(watch_paths),
            user_note,
            json.dumps(files_changed),
            json.dumps(file_contents),
        ),
    )
    conn.commit()
    snapshot_id = cursor.lastrowid
    conn.close()
    return snapshot_id


def get_snapshot(snapshot_id: int) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM snapshots WHERE id = ?", (snapshot_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    result = dict(row)
    result["watch_paths"] = _parse_watch_paths(result.pop("watch_path", None))
    result["files_changed"] = json.loads(result["files_changed"])
    result["file_contents"] = json.loads(result["file_contents"])
    return result


def _parse_watch_paths(raw: Optional[str]) -> list[str]:
    """Handle both old single-string and new JSON-array formats."""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else [parsed]
    except (json.JSONDecodeError, TypeError):
        return [raw]


def list_snapshots() -> list[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, created_at, watch_path, user_note, files_changed FROM snapshots ORDER BY id DESC"
    )
    rows = cursor.fetchall()
    conn.close()
    result = []
    for row in rows:
        item = dict(row)
        item["watch_paths"] = _parse_watch_paths(item.pop("watch_path", None))
        item["files_changed"] = json.loads(item["files_changed"])
        result.append(item)
    return result


def insert_briefing(
    snapshot_id: int,
    goal: Optional[str],
    stuck_point: Optional[str],
    next_steps: list[str],
    files_changed: list[str],
    raw_response: Optional[str],
    project_path: Optional[str] = None,
    tags: Optional[list[str]] = None,
) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO briefings (snapshot_id, project_path, goal, stuck_point, next_steps, files_changed, tags, raw_response)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            snapshot_id,
            project_path,
            goal,
            stuck_point,
            json.dumps(next_steps),
            json.dumps(files_changed),
            json.dumps(tags or []),
            raw_response,
        ),
    )
    conn.commit()
    briefing_id = cursor.lastrowid
    conn.close()
    return briefing_id


def _parse_briefing_row(row) -> dict:
    result = dict(row)
    result["next_steps"] = json.loads(result["next_steps"])
    result["files_changed"] = json.loads(result["files_changed"])
    result["tags"] = json.loads(result.get("tags") or "[]")
    return result


def get_briefing(briefing_id: int) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM briefings WHERE id = ?", (briefing_id,))
    row = cursor.fetchone()
    conn.close()
    return _parse_briefing_row(row) if row else None


def list_briefings() -> list[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM briefings ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [_parse_briefing_row(row) for row in rows]


def get_latest_briefing() -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM briefings ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return _parse_briefing_row(row) if row else None


def get_tag_history(tag: str) -> list[dict]:
    """Return all briefings that contain the given tag, newest first."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM briefings ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    results = []
    for row in rows:
        parsed = _parse_briefing_row(row)
        if tag in parsed["tags"]:
            results.append(parsed)
    return results


def insert_error(
    raw_error: str,
    fingerprint: str,
    error_type: Optional[str],
    root_cause: Optional[str],
    solution: list[str],
    prevention: Optional[str],
    tags: Optional[list[str]] = None,
    project_path: Optional[str] = None,
) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO errors (raw_error, fingerprint, error_type, root_cause, solution, prevention, tags, project_path)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            raw_error,
            fingerprint,
            error_type,
            root_cause,
            json.dumps(solution),
            prevention,
            json.dumps(tags or []),
            project_path,
        ),
    )
    conn.commit()
    error_id = cursor.lastrowid
    conn.close()
    return error_id


def get_error_occurrences(fingerprint: str) -> list[dict]:
    """Return all recorded instances of an error fingerprint, newest first."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM errors WHERE fingerprint = ? ORDER BY id DESC",
        (fingerprint,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [_parse_error_row(row) for row in rows]


def list_errors() -> list[dict]:
    """Return all errors newest first."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM errors ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [_parse_error_row(row) for row in rows]


def _parse_error_row(row) -> dict:
    result = dict(row)
    result["solution"] = json.loads(result.get("solution") or "[]")
    result["tags"] = json.loads(result.get("tags") or "[]")
    return result


def get_error_summary() -> list[dict]:
    """Return unique errors grouped by fingerprint with occurrence counts."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM errors ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()

    seen: dict[str, dict] = {}
    for row in rows:
        parsed = _parse_error_row(row)
        fp = parsed["fingerprint"]
        if fp not in seen:
            seen[fp] = {**parsed, "count": 1, "first_seen": parsed["created_at"]}
        else:
            seen[fp]["count"] += 1
            seen[fp]["first_seen"] = parsed["created_at"]  # oldest since we go desc

    return sorted(seen.values(), key=lambda x: -x["count"])


def get_error_graph_data() -> dict:
    """Return nodes and links for a force-directed error graph."""
    errors = list_errors()

    error_nodes: dict[str, dict] = {}
    project_nodes: dict[str, dict] = {}
    tag_nodes: dict[str, dict] = {}
    links: dict[tuple, dict] = {}

    def _add_link(source: str, target: str):
        key = (source, target)
        if key in links:
            links[key]["value"] += 1
        else:
            links[key] = {"source": source, "target": target, "value": 1}

    for error in errors:
        fp = error["fingerprint"]
        node_id = f"error:{fp}"

        if node_id not in error_nodes:
            error_nodes[node_id] = {
                "id": node_id,
                "type": "error",
                "label": error.get("error_type") or "Unknown",
                "fingerprint": fp,
                "count": 1,
                "root_cause": error.get("root_cause") or "",
            }
        else:
            error_nodes[node_id]["count"] += 1

        project_path = error.get("project_path")
        if project_path:
            project_name = Path(project_path).name or project_path
            proj_id = f"project:{project_name}"
            if proj_id not in project_nodes:
                project_nodes[proj_id] = {
                    "id": proj_id,
                    "type": "project",
                    "label": project_name,
                    "count": 1,
                }
            else:
                project_nodes[proj_id]["count"] += 1
            _add_link(node_id, proj_id)

        for tag in error.get("tags", []):
            tag_id = f"tag:{tag}"
            if tag_id not in tag_nodes:
                tag_nodes[tag_id] = {
                    "id": tag_id,
                    "type": "tag",
                    "label": tag,
                    "count": 1,
                }
            else:
                tag_nodes[tag_id]["count"] += 1
            _add_link(node_id, tag_id)

    nodes = list(error_nodes.values()) + list(project_nodes.values()) + list(tag_nodes.values())
    return {"nodes": nodes, "links": list(links.values())}


def get_all_tag_counts() -> list[dict]:
    """Return all tags with their occurrence counts, sorted by count desc."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT tags, created_at FROM briefings ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    counts: dict[str, int] = {}
    last_seen: dict[str, str] = {}
    for row in rows:
        created_at = row["created_at"]
        for tag in json.loads(row["tags"] or "[]"):
            counts[tag] = counts.get(tag, 0) + 1
            if tag not in last_seen:
                last_seen[tag] = created_at
    return [
        {"tag": t, "count": c, "last_seen": last_seen.get(t, "")}
        for t, c in sorted(counts.items(), key=lambda x: -x[1])
    ]
