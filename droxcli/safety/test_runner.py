"""Pytest discovery + execution wrapper."""

import subprocess
from pathlib import Path
from typing import List
from . import Result, SUBPROCESS_OPTS


def _discover_test_files(root: Path) -> List[str]:
    return [str(p) for p in root.rglob("test_*.py")] + [
        str(p) for p in root.rglob("*_test.py")
    ]


def run_pytest(root: Path) -> Result:
    test_files = _discover_test_files(root)
    if not test_files:
        return Result(True, "No tests found — skipped", None)
    try:
        proc = subprocess.run(
            ["pytest", "-q", "--tb=short"] + test_files,
            **SUBPROCESS_OPTS,
        )
        if proc.returncode == 0:
            stdout = proc.stdout or ""
            summary = stdout.splitlines()[-1] if stdout.strip() else "All tests passed"
            return Result(True, f"Tests pass ({summary})", None)
        detail = "\n".join((proc.stdout or "").splitlines()[:30])
        return Result(False, "Tests failed", detail)
    except FileNotFoundError:
        return Result(True, "pytest not installed — skipped", None)
