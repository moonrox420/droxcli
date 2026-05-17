"""
Conversational intent parser — no verb syntax required.

  "the login is broken"          → fix
  "make quicksort faster"        → refactor
  "i need a config parser"       → create
  "add type hints to utils.py"   → refactor
"""

from __future__ import annotations

import re
from pathlib import Path
from .models import Intent

_FILE_RE = re.compile(
    r"(?:(?:in|to|for|on|at|file|update|edit|fix|check)\s+)?"
    r"(?P<file>[\w./\\-]+"
    r"\.(?:py|js|ts|go|yaml|yml|toml|json|md|txt|sh|bash|rs|rb|java|cpp|c|h))",
    re.IGNORECASE,
)

_LANG_MAP = {
    ".py": "python",
    ".js": "js",
    ".ts": "js",
    ".go": "go",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".json": "json",
}

_ACTIONS = {
    "create": "create",
    "make": "create",
    "add": "create",
    "write": "create",
    "build": "create",
    "generate": "create",
    "implement": "create",
    "new": "create",
    "fix": "fix",
    "repair": "fix",
    "debug": "fix",
    "solve": "fix",
    "resolve": "fix",
    "patch": "fix",
    "correct": "fix",
    "broken": "fix",
    "error": "fix",
    "bug": "fix",
    "issue": "fix",
    "failing": "fix",
    "fails": "fix",
    "refactor": "refactor",
    "improve": "refactor",
    "clean": "refactor",
    "update": "refactor",
    "edit": "refactor",
    "modify": "refactor",
    "optimize": "refactor",
    "optimise": "refactor",
    "rewrite": "refactor",
    "restructure": "refactor",
    "simplify": "refactor",
    "mess": "refactor",
    "delete": "delete",
    "remove": "delete",
    "drop": "delete",
    "rename": "rename",
    "move": "rename",
    "complete": "complete",
    "finish": "complete",
    "continue": "complete",
}

_BROKEN_RE = re.compile(
    r"\b(broken|doesn'?t work|not working|crash(es|ing)?|fail(s|ing)?|"
    r"throws?|exception|traceback|wrong|incorrect|invalid)\b",
    re.IGNORECASE,
)
_TEST_RE = re.compile(r"\b(tests?\b|spec\b|unit.?test)", re.IGNORECASE)
_DRY_RE = re.compile(r"\b(dry.?run|preview|no.?apply|don'?t\s+apply)\b", re.IGNORECASE)


def _infer_action(text: str) -> str:
    for word in re.findall(r"\b\w+\b", text.lower()):
        if word in _ACTIONS:
            return _ACTIONS[word]
    if _BROKEN_RE.search(text):
        return "fix"
    return "complete"


def parse_natural_language(text: str) -> Intent:
    """Parse any natural language into a structured Intent. Never raises."""
    action = _infer_action(text)
    files: list[str] = []
    seen: set[str] = set()
    for m in _FILE_RE.finditer(text):
        f = Path(m.group("file")).as_posix()
        if f not in seen:
            files.append(f)
            seen.add(f)

    language = "any"
    if files:
        language = _LANG_MAP.get(Path(files[0]).suffix.lower(), "any")

    return Intent(
        action=action,
        target_files=files,
        description=text,
        language=language,
        tests_needed=bool(_TEST_RE.search(text)),
        dry_run=bool(_DRY_RE.search(text)),
    )
