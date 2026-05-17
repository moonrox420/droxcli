"""High-level conversation helpers — CRUD, history display, undo."""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Dict, List

from droxcli.state import db
from droxcli.state.file_tracker import rollback_from_snapshots


def log_turn(
    user_input: str,
    intent: dict,
    plan: dict,
    patches: List[Dict],
    result: str,
    snapshots: List,
) -> int:
    return db.record_turn(
        timestamp=datetime.datetime.utcnow().isoformat(),
        user_input=user_input,
        intent=intent,
        plan=plan,
        patches=patches,
        result=result,
        file_snapshots=snapshots,
    )


def list_history(limit: int = 20) -> List[Dict]:
    return db.list_turns(limit)


def print_history(limit: int = 20) -> None:
    from droxcli.ui.formatter import info, success, warning

    rows = list_history(limit)
    if not rows:
        print(info("No history yet."))
        return
    print(info(f"Last {len(rows)} DroxCLI turn(s):\n"))
    for row in rows:
        status_fn = success if "✅" in (row["result"] or "") else warning
        print(
            f"  [{row['id']:>4}]  {row['timestamp'][:19]}  {status_fn(row['result'] or '?')}"
        )
        print(f"         {row['user_input'][:80]}")
        print()


def undo(turn_id: int, root: Path = None) -> None:
    if root is None:
        root = Path.cwd()
    data = db.fetch_turn(turn_id)
    rollback_from_snapshots(data["snapshots"], root)
    from droxcli.ui.formatter import success

    print(success(f"Rolled back to pre-turn-{turn_id} state."))
