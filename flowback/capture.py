import time
from pathlib import Path

MAX_FILES_PER_FOLDER = 5
MAX_LINES = 500
LOOKBACK_SECONDS = 2 * 60 * 60  # 2 hours

BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg",
    ".pdf", ".zip", ".tar", ".gz", ".rar",
    ".exe", ".dll", ".so", ".dylib",
    ".pyc", ".pyo", ".class",
    ".mp3", ".mp4", ".avi", ".mov",
    ".db", ".sqlite", ".sqlite3",
    ".bak",
}

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "env", ".env", "dist", "build", ".next", ".cache",
}


def _scan_folder(path: str, cutoff: float, seen: set[str]) -> list[tuple[str, float]]:
    """Return up to MAX_FILES_PER_FOLDER files from a single folder, newest first."""
    root = Path(path)
    if not root.exists() or not root.is_dir():
        return []

    candidates: list[tuple[str, float]] = []
    for f in root.rglob("*"):
        if f.is_dir():
            continue
        if any(part in SKIP_DIRS for part in f.parts):
            continue
        if any(s.lower() in BINARY_EXTENSIONS for s in f.suffixes):
            continue
        key = str(f.resolve())
        if key in seen:
            continue
        seen.add(key)
        try:
            mtime = f.stat().st_mtime
        except OSError:
            continue
        if mtime >= cutoff:
            candidates.append((str(f), mtime))

    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[:MAX_FILES_PER_FOLDER]


def read_file_contents(paths: list[str]) -> dict[str, str]:
    """Read up to MAX_LINES lines from each file. Skip binary/unreadable files."""
    contents: dict[str, str] = {}
    for path_str in paths:
        path = Path(path_str)
        if not path.exists() or not path.is_file():
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="strict") as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= MAX_LINES:
                        lines.append(f"... (truncated at {MAX_LINES} lines)")
                        break
                    lines.append(line)
            contents[path_str] = "".join(lines)
        except (UnicodeDecodeError, PermissionError, OSError):
            continue
    return contents


def take_snapshot(watch_paths: list[str]) -> tuple[list[str], dict[str, str]]:
    """
    Scan each folder independently (up to MAX_FILES_PER_FOLDER each),
    then combine. Returns (files_changed, file_contents).
    """
    if not watch_paths:
        return [], {}

    seen: set[str] = set()
    cutoff = time.time() - LOOKBACK_SECONDS
    all_files: list[str] = []

    for path in watch_paths:
        folder_files = _scan_folder(path, cutoff, seen)
        all_files.extend(f for f, _ in folder_files)

    file_contents = read_file_contents(all_files)
    return all_files, file_contents
