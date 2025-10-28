from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional
import os


_conn: Optional[sqlite3.Connection] = None
_lock = threading.Lock()


def init_db(path: str = "tags.db") -> None:
    global _conn
    if _conn is not None:
        return
    conn = sqlite3.connect(path, check_same_thread=False, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tags (
            id TEXT PRIMARY KEY,
            description TEXT NOT NULL DEFAULT '',
            last_cnt INTEGER NOT NULL DEFAULT 1,
            last_seen TEXT
        )
        """
    )
    conn.commit()
    _conn = conn


def reset_db(path: str = "tags.db") -> None:
    """Delete DB file (if exists) and create a fresh schema."""
    global _conn
    with _lock:
        if _conn is not None:
            try:
                _conn.close()
            except Exception:
                pass
            _conn = None
        if os.path.exists(path):
            os.remove(path)
        init_db(path)


def _get_conn() -> sqlite3.Connection:
    if _conn is None:
        raise RuntimeError("DB not initialized; call init_db() first")
    return _conn


def register_tag(tag_id: str, description: str = "") -> None:
    with _lock:
        conn = _get_conn()
        cur = conn.execute("SELECT last_cnt FROM tags WHERE id = ?", (tag_id,))
        row = cur.fetchone()
        if row is None:
            # New tag: start at 1
            conn.execute(
                "INSERT INTO tags (id, description, last_cnt) VALUES (?, ?, 1)",
                (tag_id, description),
            )
        else:
            # Existing tag: increment from the last recorded value
            last_cnt = int(row[0]) if row[0] is not None else 0
            conn.execute(
                "UPDATE tags SET description = ?, last_cnt = ? WHERE id = ?",
                (description, last_cnt + 1, tag_id),
            )
        conn.commit()


def list_tags() -> list[dict]:
    conn = _get_conn()
    cur = conn.execute("SELECT id, description, last_cnt, last_seen FROM tags ORDER BY id")
    rows = cur.fetchall()
    return [
        {
            "id": r[0],
            "description": r[1],
            "last_cnt": int(r[2]) if r[2] is not None else -1,
            "last_seen": r[3],
        }
        for r in rows
    ]


def get_tag(tag_id: str) -> Optional[dict]:
    conn = _get_conn()
    cur = conn.execute(
        "SELECT id, description, last_cnt, last_seen FROM tags WHERE id = ?",
        (tag_id,),
    )
    r = cur.fetchone()
    if not r:
        return None
    return {
        "id": r[0],
        "description": r[1],
        "last_cnt": int(r[2]) if r[2] is not None else -1,
        "last_seen": r[3],
    }


def touch_last_seen(tag_id: str, timestamp_iso: str) -> Optional[dict]:
    with _lock:
        conn = _get_conn()
        cur = conn.execute(
            "SELECT id, description, last_cnt FROM tags WHERE id = ?",
            (tag_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        conn.execute(
            "UPDATE tags SET last_seen = ? WHERE id = ?",
            (timestamp_iso, tag_id),
        )
        conn.commit()
        return {
            "id": row[0],
            "description": row[1],
            "last_cnt": int(row[2]) if row[2] is not None else -1,
            "last_seen": timestamp_iso,
        }


def update_from_message(tag_id: str, cnt: int, timestamp_iso: str, *, auto_increment: bool = False) -> Optional[dict]:
    """Update state only if tag already registered. Returns updated row or None if not registered.

    If auto_increment=True, the new CNT becomes max(0, last_cnt) + 1 and the
    provided cnt is ignored for storage (still used for logging comparisons if needed).
    """
    with _lock:
        conn = _get_conn()
        cur = conn.execute("SELECT last_cnt FROM tags WHERE id = ?", (tag_id,))
        row = cur.fetchone()
        if not row:
            return None
        last_cnt = int(row[0]) if row[0] is not None else -1
        new_cnt = (max(0, last_cnt) + 1) if auto_increment else cnt
        conn.execute(
            "UPDATE tags SET last_cnt = ?, last_seen = ? WHERE id = ?",
            (new_cnt, timestamp_iso, tag_id),
        )
        conn.commit()
        return {"id": tag_id, "last_cnt": new_cnt, "last_seen": timestamp_iso, "changed": new_cnt != last_cnt}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SQLite DB utilities")
    parser.add_argument("--path", default="tags.db")
    parser.add_argument("--reset", action="store_true", help="Delete existing DB and recreate schema")
    args = parser.parse_args()

    if args.reset:
        reset_db(args.path)
        print(f"Recreated database at {args.path}")
    else:
        init_db(args.path)
        print(f"Initialized database at {args.path}")


