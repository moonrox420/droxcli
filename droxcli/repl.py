"""
Interactive REPL — the Aider/Claude-Code experience for DroxCLI.

Just type. No quotes. No flags. No droxcli prefix.

  > the login function is broken, fix it
  > now add tests for that
  > /undo
  > /status
  > /exit
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

from droxcli.session import Session
from droxcli.ui.formatter import bold, dim, divider, error, info, success, warning

# ---------------------------------------------------------------------------
# Readline setup (history + basic editing on all platforms)
# ---------------------------------------------------------------------------
try:
    import readline

    _HISTFILE = Path.home() / ".droxcli" / ".repl_history"
    _HISTFILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        readline.read_history_file(str(_HISTFILE))
    except FileNotFoundError:
        pass
    readline.set_history_length(500)
    import atexit

    atexit.register(readline.write_history_file, str(_HISTFILE))
    HAS_READLINE = True
except ImportError:
    HAS_READLINE = False


# ---------------------------------------------------------------------------
# Slash command registry
# ---------------------------------------------------------------------------

_SLASH_HELP = """
Slash commands (no quotes needed):

  /help               Show this message
  /status             Check Ollama connectivity + active models
  /models             List all available Ollama models
  /history [N]        Show last N turns (default 20)
  /undo               Undo the last turn
  /undo <id>          Undo a specific turn by ID
  /config show        Show current configuration
  /config set <k> <v> Change a config value
  /rag add <file>     Index a file for RAG
  /rag index          Bulk-index the datasets folder
  /rag datasets       Show datasets directory path
  /rag list           List indexed sources
  /rag stats          Show RAG store info
  /rag clear          Wipe the RAG store
  /eval               Run the benchmark suite
  /eval stier         Run S-tier benchmarks
  /eval <id>          Run a single benchmark problem
  /clear              Clear session context
  /exit  /quit  /q    Exit DroxCLI
"""


def _prompt_string(session: Session) -> str:
    """Build the input prompt showing cwd and last turn."""
    cwd = Path.cwd()
    short = cwd.name or str(cwd)
    turn = f" #{session.last_turn_id}" if session.last_turn_id else ""
    return f"\n\033[1;32m drox\033[0m \033[90m{short}{turn}\033[0m \033[1;32m›\033[0m "


def _handle_slash(cmd: str, session: Session) -> bool:
    """
    Handle a slash command. Returns True to continue the loop, False to exit.
    Commands are case-insensitive and parsed without flags.
    """
    parts = cmd.strip().lstrip("/").split()
    if not parts:
        return True
    sub = parts[0].lower()
    rest = parts[1:]

    # ── exit ──────────────────────────────────────────────────────────────
    if sub in {"exit", "quit", "q", "bye"}:
        print(info("Bye."))
        return False

    # ── help ──────────────────────────────────────────────────────────────
    elif sub == "help":
        print(_SLASH_HELP)

    # ── clear ─────────────────────────────────────────────────────────────
    elif sub == "clear":
        session.clear()
        print(success("Session context cleared."))

    # ── status ────────────────────────────────────────────────────────────
    elif sub == "status":
        from droxcli.orchestrator import check_status

        check_status()

    # ── models ────────────────────────────────────────────────────────────
    elif sub == "models":
        from droxcli.orchestrator import show_models

        show_models()

    # ── history ───────────────────────────────────────────────────────────
    elif sub == "history":
        from droxcli.orchestrator import show_history

        limit = int(rest[0]) if rest and rest[0].isdigit() else 20
        show_history(limit)

    # ── undo ──────────────────────────────────────────────────────────────
    elif sub == "undo":
        from droxcli.orchestrator import perform_undo

        if rest and rest[0].isdigit():
            turn_id = int(rest[0])
        elif session.last_turn_id:
            turn_id = session.last_turn_id
        else:
            print(warning("No turn to undo. Use /undo <turn-id>."))
            return True
        try:
            perform_undo(turn_id)
            if session.last_turn_id == turn_id:
                session.last_turn_id = None
                session.last_files = []
        except ValueError as exc:
            print(error(str(exc)))

    # ── config ────────────────────────────────────────────────────────────
    elif sub == "config":
        from droxcli.config import load_config, set_config_value, show_config

        action = rest[0].lower() if rest else "show"
        if action == "show" or not rest:
            show_config(load_config())
        elif action == "set":
            if len(rest) < 3:
                print(error("Usage: /config set <key> <value>"))
            else:
                try:
                    set_config_value(rest[1], rest[2])
                    print(success(f"Set {rest[1]} = {rest[2]}"))
                except ValueError as exc:
                    print(error(str(exc)))
        else:
            print(error(f"Unknown: /config {action}"))

    # ── rag ───────────────────────────────────────────────────────────────
    elif sub == "rag":
        action = rest[0].lower() if rest else ""
        if action == "add":
            if len(rest) < 2:
                print(error("Usage: /rag add <file>"))
            else:
                from droxcli.rag.store import add_file

                try:
                    n = add_file(Path(rest[1]), description=Path(rest[1]).name)
                    print(success(f"Indexed {rest[1]} — {n} chunk(s)."))
                except FileNotFoundError:
                    print(error(f"File not found: {rest[1]}"))
        elif action in {"index", "scan"}:
            from droxcli.rag.store import index_datasets_dir, get_datasets_dir

            print(info(f"Scanning {get_datasets_dir()} …"))
            r = index_datasets_dir(verbose=True)
            note = f"  ({r['skipped']} skipped)" if r["skipped"] else ""
            print(
                success(
                    f"Indexed {r['files_indexed']} file(s) → {r['chunks_added']} chunk(s){note}"
                )
            )
        elif action in {"datasets", "dir"}:
            from droxcli.rag.store import get_datasets_dir

            print(info(f"Datasets directory: {get_datasets_dir()}"))
        elif action == "list":
            from droxcli.rag.store import list_sources

            sources = list_sources()
            if not sources:
                print(info("RAG store is empty."))
            else:
                for s in sources:
                    print(f"  • {s}")
        elif action == "stats":
            from droxcli.rag.store import stats

            s = stats()
            print(
                info(
                    f"{s['total_chunks']} chunks / {s['total_sources']} sources / {s['index_size_kb']} KB"
                )
            )
        elif action == "clear":
            from droxcli.rag.store import clear

            clear()
            print(success("RAG store cleared."))
        else:
            print(info("Usage: /rag add|index|datasets|list|stats|clear"))

    # ── eval ──────────────────────────────────────────────────────────────
    elif sub == "eval":
        from droxcli.eval.runner import run_eval, print_report
        from droxcli.ui.banner import print_banner

        print_banner()
        tier = None
        difficulty = None
        problem_id = None
        if rest:
            word = rest[0].lower()
            if word in {"stier", "s-tier"}:
                tier = "stier"
            elif word == "all":
                tier = "all"
            elif word in {"easy", "medium", "hard"}:
                difficulty = word
            elif len(word) <= 4 and word[0].upper() in "EMHSX":
                problem_id = word.upper()
        results = run_eval(
            difficulty=difficulty,
            tier=tier,
            problem_id=problem_id,
            verbose="--verbose" in rest or "-v" in rest,
        )
        print_report(results)

    else:
        print(warning(f"Unknown command: /{sub}  —  type /help for a list"))

    return True


# ---------------------------------------------------------------------------
# Main REPL loop
# ---------------------------------------------------------------------------


def run_repl() -> None:
    """Enter the interactive DroxCLI session."""
    from droxcli.config import load_config
    from droxcli.ui.banner import print_banner

    print_banner()
    cfg = load_config()

    print(info(f"Planner:  {cfg.planning_model}"))
    print(info(f"Executor: {cfg.execution_model}"))
    print(info(f"CWD:      {Path.cwd()}"))
    print(
        dim(
            "Type your request, a /command, or /help.  Ctrl-C to cancel a run.  /exit to quit.\n"
        )
    )

    session = Session(cwd=Path.cwd())

    while True:
        # ── read input ────────────────────────────────────────────────────
        try:
            raw = input(_prompt_string(session)).strip()
        except KeyboardInterrupt:
            print()
            continue
        except EOFError:
            print()
            break

        if not raw:
            continue

        # ── slash commands ────────────────────────────────────────────────
        if raw.startswith("/"):
            if not _handle_slash(raw, session):
                break
            continue

        # ── bare keywords (convenience aliases without slash) ─────────────
        lower = raw.lower()
        if lower in {"exit", "quit", "q"}:
            print(info("Bye."))
            break
        if lower == "undo":
            _handle_slash("/undo", session)
            continue
        if lower in {"help", "?"}:
            print(_SLASH_HELP)
            continue
        if lower == "status":
            _handle_slash("/status", session)
            continue
        if lower == "history":
            _handle_slash("/history", session)
            continue

        # ── natural language → orchestrator ───────────────────────────────
        enriched = session.enrich(raw)
        try:
            _run_command(enriched, session)
        except KeyboardInterrupt:
            print(f"\n{warning('Run cancelled.')}")
        except SystemExit:
            # orchestrator calls sys.exit(0) on abort — catch it so REPL survives
            pass
        except Exception as exc:
            print(error(f"Unexpected error: {exc}"))
            from droxcli.__main__ import DEBUG_LOG

            print(dim(f"  Details: {DEBUG_LOG}"))


def _run_command(user_input: str, session: Session) -> None:
    """Run the orchestrator pipeline and update session state on success."""
    from droxcli import orchestrator

    # Monkey-patch log_turn to capture the turn_id and changed files
    # without modifying orchestrator's internal structure
    from droxcli.state import conversation as conv

    _original_log = conv.log_turn
    captured: dict = {}

    def _capturing_log(**kwargs):
        turn_id = _original_log(**kwargs)
        captured["turn_id"] = turn_id
        captured["files"] = [p["file"] for p in kwargs.get("patches", [])]
        return turn_id

    conv.log_turn = _capturing_log
    try:
        orchestrator.run_user_command(user_input)
    finally:
        conv.log_turn = _original_log

    if "turn_id" in captured:
        session.record(
            user_input=user_input,
            turn_id=captured["turn_id"],
            files_changed=captured.get("files", []),
            summary=f"Turn #{captured['turn_id']}",
        )
