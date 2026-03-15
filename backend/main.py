from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

from flowback import database
from flowback import capture
from flowback import gemini
from flowback.models import (
    BriefingResponse,
    SnapshotListItem,
    SnapshotRequest,
    SnapshotResponse,
    TagCount,
    TagHistoryItem,
)


def _pick_folder_native():
    """Open a native macOS folder picker via osascript and return the POSIX path."""
    import subprocess
    try:
        result = subprocess.run(
            ["osascript", "-e", "POSIX path of (choose folder with prompt \"Select project folder\")"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        path = result.stdout.strip().rstrip("/")
        return path if path else None
    except Exception:
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    yield


app = FastAPI(title="FlowBack API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/pick-folder")
async def pick_folder():
    path = await run_in_threadpool(_pick_folder_native)
    if not path:
        raise HTTPException(status_code=404, detail="No folder selected")
    return {"path": path}


@app.post("/snapshot", response_model=SnapshotResponse)
def create_snapshot(req: SnapshotRequest):
    watch_paths = [p.strip() for p in req.watch_paths if p.strip()]
    files_changed, file_contents = capture.take_snapshot(watch_paths)

    snapshot_id = database.insert_snapshot(
        watch_paths=watch_paths,
        user_note=req.user_note,
        files_changed=files_changed,
        file_contents=file_contents,
    )

    snapshot = database.get_snapshot(snapshot_id)
    return SnapshotResponse(
        snapshot_id=snapshot_id,
        files_changed=files_changed,
        created_at=snapshot["created_at"],
    )


@app.post("/briefing/{snapshot_id}", response_model=list[BriefingResponse])
def create_briefing(snapshot_id: int):
    snapshot = database.get_snapshot(snapshot_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    all_files: list[str] = snapshot["files_changed"]
    all_contents: dict = snapshot["file_contents"]
    watch_paths: list[str] = snapshot["watch_paths"]

    results = []
    for project_path in watch_paths:
        # Filter files belonging to this project
        project_files = [f for f in all_files if f.startswith(project_path)]
        project_contents = {k: v for k, v in all_contents.items() if k.startswith(project_path)}

        if not project_files:
            continue

        try:
            briefing_data, raw = gemini.generate_briefing(
                user_note=snapshot["user_note"],
                file_contents=project_contents,
                files_changed=project_files,
            )
        except RuntimeError as e:
            raise HTTPException(status_code=502, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

        briefing_id = database.insert_briefing(
            snapshot_id=snapshot_id,
            goal=briefing_data.get("goal"),
            stuck_point=briefing_data.get("stuck_point"),
            next_steps=briefing_data.get("next_steps", []),
            files_changed=project_files,
            raw_response=raw,
            project_path=project_path,
            tags=briefing_data.get("tags", []),
        )

        briefing = database.get_briefing(briefing_id)
        results.append(BriefingResponse(
            briefing_id=briefing_id,
            snapshot_id=snapshot_id,
            project_path=project_path,
            goal=briefing["goal"] or "",
            stuck_point=briefing["stuck_point"] or "",
            next_steps=briefing["next_steps"],
            files_changed=briefing["files_changed"],
            tags=briefing["tags"],
            created_at=briefing["created_at"],
        ))

    if not results:
        raise HTTPException(status_code=422, detail="No files found in any project folder")

    return results


@app.get("/briefing/latest", response_model=BriefingResponse)
def get_latest_briefing():
    briefing = database.get_latest_briefing()
    if not briefing:
        raise HTTPException(status_code=404, detail="No briefings yet")
    return BriefingResponse(
        briefing_id=briefing["id"],
        snapshot_id=briefing["snapshot_id"],
        project_path=briefing.get("project_path"),
        goal=briefing["goal"] or "",
        stuck_point=briefing["stuck_point"] or "",
        next_steps=briefing["next_steps"],
        files_changed=briefing["files_changed"],
        tags=briefing["tags"],
        created_at=briefing["created_at"],
    )


@app.get("/briefings", response_model=list[BriefingResponse])
def list_briefings():
    rows = database.list_briefings()
    return [
        BriefingResponse(
            briefing_id=row["id"],
            snapshot_id=row["snapshot_id"],
            project_path=row.get("project_path"),
            goal=row["goal"] or "",
            stuck_point=row["stuck_point"] or "",
            next_steps=row["next_steps"],
            files_changed=row["files_changed"],
            tags=row["tags"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


@app.get("/tags", response_model=list[TagCount])
def list_tags():
    return [TagCount(**t) for t in database.get_all_tag_counts()]


@app.get("/tags/{tag}", response_model=list[TagHistoryItem])
def get_tag_history(tag: str):
    rows = database.get_tag_history(tag)
    return [
        TagHistoryItem(
            briefing_id=row["id"],
            snapshot_id=row["snapshot_id"],
            project_path=row.get("project_path"),
            goal=row["goal"] or "",
            stuck_point=row["stuck_point"] or "",
            created_at=row["created_at"],
        )
        for row in rows
    ]


@app.get("/snapshots", response_model=list[SnapshotListItem])
def list_snapshots():
    rows = database.list_snapshots()
    return [SnapshotListItem(**row) for row in rows]


@app.get("/error-graph")
def get_error_graph():
    return database.get_error_graph_data()
