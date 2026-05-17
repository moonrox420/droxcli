"""Mypy type-checking wrapper."""

import subprocess
from typing import List
from . import Result, SUBPROCESS_OPTS


def run_mypy(files: List[str]) -> Result:
    if not files:
        return Result(True, "No files to type-check", None)
    try:
        proc = subprocess.run(
            ["mypy", "--ignore-missing-imports", "--show-error-codes"] + files,
            **SUBPROCESS_OPTS,
        )
        if proc.returncode == 0:
            return Result(True, "Mypy passes ✓", None)
        detail = "\n".join((proc.stdout + proc.stderr).splitlines()[:20])
        return Result(False, "Mypy type errors detected", detail)
    except FileNotFoundError:
        return Result(True, "mypy not installed — skipped", None)
