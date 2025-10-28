from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from main import store, TagState
from db import init_db, register_tag, list_tags as db_list_tags, get_tag as db_get_tag, touch_last_seen


class TagCreate(BaseModel):
    id: str = Field(..., description="Tag ID")
    description: str = Field("", description="Human description")


class TagOut(BaseModel):
    id: str
    description: str
    last_cnt: int
    last_seen: Optional[datetime]


app = FastAPI(title="Tag Status API", version="1.0.0")


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.post("/tags", response_model=TagOut)
def register_tag_api(tag: TagCreate) -> TagOut:
    register_tag(tag.id, tag.description)
    # Keep in-memory store aligned if registered during this process
    state = store.register(tag.id, tag.description)
    db_row = db_get_tag(tag.id)
    return TagOut(
        id=tag.id,
        description=state.description,
        last_cnt=(db_row["last_cnt"] if db_row else state.last_cnt),
        last_seen=(db_row["last_seen"] if db_row else state.last_seen),
    )


@app.get("/tags", response_model=list[TagOut])
def list_tags_api() -> list[TagOut]:
    rows = db_list_tags()
    return [
        TagOut(
            id=r["id"],
            description=r["description"],
            last_cnt=r["last_cnt"],
            last_seen=r["last_seen"],
        )
        for r in rows
    ]


@app.get("/tag/{tag_id}", response_model=TagOut)
def get_tag_api(tag_id: str) -> TagOut:
    row = db_get_tag(tag_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    # touch last_seen to now
    now_iso = datetime.now(tz=timezone.utc).isoformat()
    updated = touch_last_seen(tag_id, now_iso)
    if updated is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    return TagOut(
        id=updated["id"],
        description=updated["description"],
        last_cnt=updated["last_cnt"],
        last_seen=updated["last_seen"],
    )


