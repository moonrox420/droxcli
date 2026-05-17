"""
Session state for the interactive REPL.

Tracks the current conversation so follow-up requests have context:
  "now add tests for that"   → knows what 'that' is
  "undo"                     → knows the last turn ID
  "fix the error"            → knows which files were just changed
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class Turn:
    """One exchange in the session."""

    user_input: str
    turn_id: Optional[int]
    files_changed: List[str]
    summary: str  # one-liner describing what happened


@dataclass
class Session:
    """Mutable state for the current REPL session."""

    cwd: Path = field(default_factory=Path.cwd)
    history: List[Turn] = field(default_factory=list)
    last_turn_id: Optional[int] = None
    last_files: List[str] = field(default_factory=list)

    # ── convenience ──────────────────────────────────────────────────────

    def record(
        self,
        user_input: str,
        turn_id: Optional[int],
        files_changed: List[str],
        summary: str = "",
    ) -> None:
        self.history.append(Turn(user_input, turn_id, files_changed, summary))
        if turn_id is not None:
            self.last_turn_id = turn_id
        if files_changed:
            self.last_files = files_changed

    def last_context_block(self) -> str:
        """
        Return a short natural-language summary of the last N turns
        so the model understands follow-up requests like "now add tests for that".
        """
        if not self.history:
            return ""
        recent = self.history[-3:]
        lines = ["Recent session context:"]
        for t in recent:
            files = ", ".join(t.files_changed) if t.files_changed else "no files"
            lines.append(f"  • {t.user_input!r} → changed: {files}")
        return "\n".join(lines)

    def enrich(self, user_input: str) -> str:
        """
        Inject session context into the user's input so follow-ups work.
        Only adds context if the input looks like a follow-up.
        """
        follow_up_signals = {
            "that",
            "it",
            "this",
            "them",
            "those",
            "the same",
            "also",
            "now",
            "next",
            "again",
            "undo",
            "revert",
        }
        words = set(user_input.lower().split())
        is_follow_up = bool(words & follow_up_signals) and len(user_input.split()) < 10

        ctx = self.last_context_block()
        if ctx and (is_follow_up or not user_input.strip()):
            return f"{ctx}\n\nNew request: {user_input}"
        return user_input

    def clear(self) -> None:
        self.history.clear()
        self.last_turn_id = None
        self.last_files = []
