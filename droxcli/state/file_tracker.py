"""
File tracker — SHA256 integrity snapshots + atomic writes (SYSTEM 1 + 2).

Every file write goes through tempfile + os.replace() so there is
no window where a file can be left in a partial/corrupt state.
Every snapshot is SHA256-verified before restore.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Dict, List, Tuple

from droxcli.core.logger import logger
from droxcli.core.telemetry import atomic_operation, trace_performance

SNAPSHOT_DIR = Path.home() / ".droxcli" / "snapshots"
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Atomic write — SYSTEM 1
# ---------------------------------------------------------------------------


def _atomic_write(path: Path, content: str) -> None:
    """Write atomically via tempfile → os.replace(). Zero corruption window."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".drox_tmp_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
        logger.debug("write_ok", path=str(path))
    except Exception as exc:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        logger.error("write_fail", path=str(path), error=str(exc))
        raise


# ---------------------------------------------------------------------------
# Snapshot — SYSTEM 2
# ---------------------------------------------------------------------------


def create_snapshot(patches: List[Dict], root: Path) -> str:
    """
    Capture pre-patch file contents. Returns snapshot ID.
    Each file is SHA256-hashed so restoration can detect corruption.
    """
    snap_id = f"{int(time.time())}-{uuid.uuid4().hex[:8]}"
    snap_path = SNAPSHOT_DIR / snap_id
    snap_path.mkdir(parents=True, exist_ok=True)

    metadata: Dict[str, Dict] = {}
    seen: set[str] = set()

    with trace_performance("create_snapshot"):
        for patch in patches:
            rel = patch["file"]
            if rel in seen:
                continue
            seen.add(rel)
            abs_path = root / rel
            content = abs_path.read_text(encoding="utf-8") if abs_path.is_file() else ""
            dest = snap_path / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write(dest, content)
            metadata[rel] = {
                "sha256": _sha256(content),
                "existed": abs_path.is_file(),
            }

        _atomic_write(
            snap_path / "metadata.json",
            json.dumps({"id": snap_id, "files": metadata}, indent=2),
        )

    logger.info("snapshot_created", snap_id=snap_id, files=len(metadata))
    return snap_id


def restore_snapshot(snap_id: str, root: Path) -> None:
    """
    Restore files from snapshot with SHA256 integrity verification.
    Raises ValueError on missing snapshot or hash mismatch.
    """
    snap_path = SNAPSHOT_DIR / snap_id
    if not snap_path.is_dir():
        raise ValueError(f"Snapshot '{snap_id}' not found in {SNAPSHOT_DIR}")

    meta_file = snap_path / "metadata.json"
    if not meta_file.is_file():
        raise ValueError(f"Snapshot '{snap_id}' is missing metadata.json")

    metadata = json.loads(meta_file.read_text(encoding="utf-8"))

    with trace_performance("restore_snapshot"):
        for rel, info in metadata["files"].items():
            snap_file = snap_path / rel
            if not snap_file.is_file():
                continue
            content = snap_file.read_text(encoding="utf-8")
            if _sha256(content) != info["sha256"]:
                raise ValueError(
                    f"SHA256 mismatch for '{rel}' — snapshot may be corrupt."
                )
            abs_path = root / rel
            if not info["existed"] and not content:
                if abs_path.is_file():
                    abs_path.unlink()
            else:
                _atomic_write(abs_path, content)

    logger.info("snapshot_restored", snap_id=snap_id)


def prune_snapshots(keep: int = 10) -> int:
    """
    Delete oldest snapshots beyond the *keep* limit.
    Returns number of snapshots deleted.
    """
    snapshots = sorted(
        (d for d in SNAPSHOT_DIR.iterdir() if d.is_dir()),
        key=lambda d: d.stat().st_mtime,
    )
    to_delete = snapshots[:-keep] if len(snapshots) > keep else []
    for snap in to_delete:
        try:
            import shutil

            shutil.rmtree(snap)
            logger.debug("snapshot_pruned", snap=snap.name)
        except Exception as exc:
            logger.warning("snapshot_prune_failed", snap=snap.name, error=str(exc))
    return len(to_delete)


# ---------------------------------------------------------------------------
# Patch application with auto-rollback
# ---------------------------------------------------------------------------


def apply_patches(
    patches: List[Dict],
    root: Path,
    snap_id: str | None = None,
) -> None:
    """
    Write all patches atomically.
    If snap_id is provided, auto-rolls back the snapshot on any failure.
    """

    def _rollback() -> None:
        if snap_id:
            try:
                restore_snapshot(snap_id, root)
                logger.info("auto_rollback_ok", snap_id=snap_id)
            except Exception as exc:
                logger.error("auto_rollback_fail", error=str(exc))

    with atomic_operation("apply_patches", rollback=_rollback if snap_id else None):
        with trace_performance("apply_patches"):
            for patch in patches:
                _atomic_write(root / patch["file"], patch["new"])
                logger.debug("patch_applied", file=patch["file"])

    logger.info("patches_applied", count=len(patches))


# ---------------------------------------------------------------------------
# SQLite-compatible helpers (used by conversation.py for undo)
# ---------------------------------------------------------------------------


def capture_snapshots(patches: List[Dict], root: Path) -> List[Tuple[str, str]]:
    """Return (rel_path, original_content) for each patched file."""
    result: List[Tuple[str, str]] = []
    seen: set[str] = set()
    for p in patches:
        rel = p["file"]
        if rel in seen:
            continue
        seen.add(rel)
        abs_path = root / rel
        content = abs_path.read_text(encoding="utf-8") if abs_path.is_file() else ""
        result.append((rel, content))
    return result


def rollback_from_snapshots(snapshots: Dict[str, str], root: Path) -> None:
    """Restore files from a {rel_path: original_content} dict (SQLite undo)."""
    for rel, content in snapshots.items():
        abs_path = root / rel
        if not content:
            if abs_path.is_file():
                abs_path.unlink()
        else:
            _atomic_write(abs_path, content)
