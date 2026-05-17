"""Black + Ruff linting wrappers."""

import json
import subprocess
from typing import List
from . import Result, SUBPROCESS_OPTS


def run_black(files: List[str], fix: bool = True) -> Result:
    if not files:
        return Result(True, "No files to check", None)
    try:
        cmd = ["black", "--quiet"] + ([] if fix else ["--check"]) + files
        proc = subprocess.run(cmd, **SUBPROCESS_OPTS)
        if proc.returncode == 0:
            return Result(True, "Black auto-formatted OK" if fix else "Black OK", None)
        return Result(
            False, "Black formatting violations", (proc.stdout + proc.stderr)[:500]
        )
    except FileNotFoundError:
        return Result(True, "black not installed — skipped", None)


def run_ruff(files: List[str]) -> Result:
    if not files:
        return Result(True, "No files to check", None)
    try:
        proc = subprocess.run(["ruff", "check"] + files, **SUBPROCESS_OPTS)
        if proc.returncode == 0:
            return Result(True, "Ruff lint OK", None)
        lines = (proc.stdout or "").strip().splitlines()
        return Result(False, f"Ruff found {len(lines)} issue(s)", "\n".join(lines[:20]))
    except FileNotFoundError:
        return Result(True, "ruff not installed — skipped", None)


def run_pylint(files: List[str]) -> Result:
    if not files:
        return Result(True, "No files to check", None)
    try:
        proc = subprocess.run(
            ["pylint", "--output-format", "json"] + files, **SUBPROCESS_OPTS
        )
        if proc.returncode == 0:
            return Result(True, "Pylint OK", None)
        try:
            issues = json.loads(proc.stdout or "[]")
            detail = "\n".join(
                f"{i.get('type','?')}:{i.get('line','?')}:{i.get('symbol','?')}"
                for i in issues[:15]
            )
        except Exception:
            detail = (proc.stdout or "")[:500]
        return Result(False, "Pylint found issues", detail)
    except FileNotFoundError:
        return Result(True, "pylint not installed — skipped", None)
