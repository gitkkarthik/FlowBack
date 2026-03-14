from typing import Optional
from pydantic import BaseModel


class SnapshotRequest(BaseModel):
    watch_paths: list[str] = []
    user_note: Optional[str] = None


class SnapshotResponse(BaseModel):
    snapshot_id: int
    files_changed: list[str]
    created_at: str


class BriefingResponse(BaseModel):
    briefing_id: int
    snapshot_id: int
    project_path: Optional[str] = None
    goal: str
    stuck_point: str
    next_steps: list[str]
    files_changed: list[str]
    tags: list[str] = []
    created_at: str


class TagCount(BaseModel):
    tag: str
    count: int


class TagHistoryItem(BaseModel):
    briefing_id: int
    snapshot_id: int
    project_path: Optional[str] = None
    goal: str
    stuck_point: str
    created_at: str


class SnapshotListItem(BaseModel):
    id: int
    created_at: str
    watch_paths: list[str]
    user_note: Optional[str]
    files_changed: list[str]
