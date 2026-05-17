#!/usr/bin/env python3
"""
DroxCLI entry point.

  droxcli               → interactive REPL (Aider/Claude-Code style)
  droxcli <anything>    → one-shot command (backward compatible)
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

from droxcli.ui.formatter import error, info, success, warning

_HELP = """
DroxCLI — Agentic coding assistant powered by Ollama

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 INTERACTIVE MODE  (recommended)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  droxcli                   Start the interactive REPL

  Inside the REPL just type naturally:
    the login is broken, fix it
    add type hints to utils.py
    now write tests for that
    undo
    /status
    /help

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 ONE-SHOT MODE  (scripts / CI)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  droxcli "the login is broken, fix it"
  droxcli eval stier
  droxcli rag index
  droxcli status
  droxcli history 20
  droxcli undo 7
  droxcli config set execution_model nemotron-cascade-2:30b
  droxcli models
  droxcli help
"""


# ---------------------------------------------------------------------------
# Arg helpers
# ---------------------------------------------------------------------------


def _flag(args: List[str], name: str) -> bool:
    return f"--{name}" in args or f"-{name[0]}" in args


def _flag_value(args: List[str], name: str) -> Optional[str]:
    try:
        idx = args.index(f"--{name}")
        return args[idx + 1] if idx + 1 < len(args) else None
    except ValueError:
        return None


def _positional(args: List[str]) -> List[str]:
    return [a for a in args if not a.startswith("-")]


# ---------------------------------------------------------------------------
# Command handlers (one-shot mode)
# ---------------------------------------------------------------------------


def _cmd_eval(args: List[str]) -> None:
    from droxcli.eval.runner import print_report, run_eval
    from droxcli.ui.banner import print_banner

    print_banner()

    verbose = _flag(args, "verbose")
    problem_id = (_flag_value(args, "id") or "").upper() or None
    difficulty = _flag_value(args, "difficulty")
    tier = None
    category = None

    if "--id" in args:
        idx = args.index("--id")
        if idx + 1 < len(args):
            problem_id = args[idx + 1].upper()

    pos = _positional(args)
    if pos:
        word = pos[0].lower()
        if word in {"stier", "s-tier", "xtier"}:
            tier = "stier"
        elif word == "all":
            tier = "all"
        elif word in {"easy", "medium", "hard"}:
            difficulty = word
        elif word in {"algorithm", "string", "data-structures", "real-world", "self"}:
            category = word
        elif not problem_id and len(word) <= 4 and word[0].upper() in "EMHSX":
            problem_id = word.upper()

    results = run_eval(
        difficulty=difficulty,
        category=category,
        problem_id=problem_id,
        tier=tier,
        verbose=verbose,
    )
    print_report(results)


def _cmd_rag(args: List[str]) -> None:
    if not args:
        print(
            info(
                "Usage: droxcli rag add <file> | index | datasets | list | stats | clear"
            )
        )
        return

    from droxcli.rag.store import (
        add_file,
        clear,
        get_datasets_dir,
        index_datasets_dir,
        list_sources,
        stats,
    )

    subcmd = args[0].lower()
    verbose = _flag(args, "verbose")

    if subcmd == "add":
        if len(args) < 2:
            print(error("Usage: droxcli rag add <file>"))
            sys.exit(1)
        path = Path(args[1])
        try:
            n = add_file(path, description=path.name)
            print(success(f"Indexed {path.name} — {n} chunk(s) added."))
        except FileNotFoundError:
            print(error(f"File not found: {args[1]}"))
            sys.exit(1)

    elif subcmd in {"index", "scan", "reindex"}:
        d = get_datasets_dir()
        print(info(f"Scanning {d} …"))
        r = index_datasets_dir(verbose=verbose)
        note = f"  ({r['skipped']} skipped)" if r["skipped"] else ""
        print(
            success(
                f"Indexed {r['files_indexed']} file(s) → {r['chunks_added']} chunk(s){note}"
            )
        )

    elif subcmd in {"datasets", "dir", "where"}:
        d = get_datasets_dir()
        print(info(f"Datasets directory: {d}"))
        print(info("Drop files here then run: droxcli rag index"))

    elif subcmd == "list":
        sources = list_sources()
        if not sources:
            print(info("RAG store is empty. Use: droxcli rag add <file>"))
        else:
            print(info(f"{len(sources)} indexed source(s):"))
            for s in sources:
                print(f"  • {s}")

    elif subcmd == "stats":
        s = stats()
        print(
            info(
                f"RAG store: {s['total_chunks']} chunks from "
                f"{s['total_sources']} source(s) ({s['index_size_kb']} KB)"
            )
        )

    elif subcmd == "clear":
        clear()
        print(success("RAG store cleared."))

    else:
        print(error(f"Unknown rag subcommand: {subcmd!r}"))
        print(info("Valid: add | index | datasets | list | stats | clear"))
        sys.exit(1)


def _cmd_config(args: List[str]) -> None:
    from droxcli.config import load_config, set_config_value, show_config

    if not args or args[0].lower() == "show":
        show_config(load_config())
        return
    subcmd = args[0].lower()
    if subcmd == "set":
        if len(args) < 3:
            print(error("Usage: droxcli config set <key> <value>"))
            sys.exit(1)
        key, value = args[1], args[2]
        try:
            set_config_value(key, value)
            print(success(f"Set {key} = {value}"))
        except ValueError as exc:
            print(error(str(exc)))
            sys.exit(1)
    else:
        print(error(f"Unknown config subcommand: {subcmd!r}"))
        sys.exit(1)


def _cmd_history(args: List[str]) -> None:
    from droxcli.orchestrator import show_history

    limit = int(args[0]) if args and args[0].isdigit() else 20
    show_history(limit)


def _cmd_undo(args: List[str]) -> None:
    from droxcli.orchestrator import perform_undo

    if not args:
        print(error("Usage: droxcli undo <turn-id>"))
        sys.exit(1)
    if not args[0].isdigit():
        print(error(f"Invalid turn ID: {args[0]!r} — must be an integer."))
        sys.exit(1)
    perform_undo(int(args[0]))


def _cmd_status(_args: List[str]) -> None:
    from droxcli.orchestrator import check_status

    check_status()


def _cmd_models(_args: List[str]) -> None:
    from droxcli.orchestrator import show_models

    show_models()


_COMMANDS = {
    "eval": _cmd_eval,
    "rag": _cmd_rag,
    "config": _cmd_config,
    "history": _cmd_history,
    "log": _cmd_history,
    "undo": _cmd_undo,
    "status": _cmd_status,
    "models": _cmd_models,
}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    argv = sys.argv[1:]

    # ── no args → interactive REPL ────────────────────────────────────────
    if not argv:
        from droxcli.repl import run_repl

        run_repl()
        return

    command = argv[0].lower()

    # ── explicit help ─────────────────────────────────────────────────────
    if command in {"help", "--help", "-h"}:
        print(_HELP)
        return

    # ── known sub-commands ────────────────────────────────────────────────
    if command in _COMMANDS:
        _COMMANDS[command](argv[1:])
        return

    # ── everything else → one-shot natural language ───────────────────────
    from droxcli.orchestrator import run_user_command

    run_user_command(" ".join(argv))


if __name__ == "__main__":
    main()
