"""
SQLite wrapper for conversation history and file snapshots.

Schema:
  turns          — one row per DroxCLI interaction
  file_snapshots — pre-change file contents for rollback
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Tuple

DB_PATH = Path.home() / ".droxcli" / "conversation.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db() -> None:
    with _connect() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS turns (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp     TEXT    NOT NULL,
            user_input    TEXT    NOT NULL,
            intent_json   TEXT,
            plan_json     TEXT,
            patches_json  TEXT,
            result        TEXT
        );

        CREATE TABLE IF NOT EXISTS file_snapshots (
            turn_id  INTEGER NOT NULL,
            path     TEXT    NOT NULL,
            content  TEXT    NOT NULL,
            PRIMARY KEY (turn_id, path),
            FOREIGN KEY (turn_id) REFERENCES turns(id) ON DELETE CASCADE
        );
        """)
        con.commit()


def record_turn(
    timestamp: str,
    user_input: str,
    intent: dict,
    plan: dict,
    patches: list,
    result: str,
    file_snapshots: List[Tuple[str, str]],
) -> int:
    with _connect() as con:
        cur = con.cursor()
        cur.execute(
            """INSERT INTO turns
               (timestamp, user_input, intent_json, plan_json, patches_json, result)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                timestamp,
                user_input,
                json.dumps(intent),
                json.dumps(plan),
                json.dumps(patches),
                result,
            ),
        )
        turn_id = cur.lastrowid
        cur.executemany(
            "INSERT INTO file_snapshots (turn_id, path, content) VALUES (?, ?, ?)",
            [(turn_id, path, content) for path, content in file_snapshots],
        )
        con.commit()
    return turn_id


def fetch_turn(turn_id: int) -> Dict[str, Any]:
    with _connect() as con:
        cur = con.cursor()
        cur.execute("SELECT * FROM turns WHERE id = ?", (turn_id,))
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"Turn {turn_id} not found in history.")
        cur.execute(
            "SELECT path, content FROM file_snapshots WHERE turn_id = ?",
            (turn_id,),
        )
        snapshots = {r["path"]: r["content"] for r in cur.fetchall()}
    return {"turn": dict(row), "snapshots": snapshots}


def list_turns(limit: int = 20) -> List[Dict[str, Any]]:
    with _connect() as con:
        cur = con.cursor()
        cur.execute(
            "SELECT id, timestamp, user_input, result FROM turns "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return [dict(r) for r in cur.fetchall()]


def delete_turn(turn_id: int) -> None:
    with _connect() as con:
        con.execute("DELETE FROM turns WHERE id = ?", (turn_id,))
        con.commit()


init_db()
