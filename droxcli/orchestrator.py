"""
Orchestrator — the main 8-step pipeline.

SYSTEM 1: Atomic file writes (tempfile + os.replace)
SYSTEM 2: SHA256 snapshot hashing
SYSTEM 3: SQLite WAL conversation memory
SYSTEM 4: ThreadPoolExecutor Ollama timeout
SYSTEM 5: Crash isolation to ~/.droxcli/debug.log
"""

from __future__ import annotations

import pathlib
import sys
import time
from typing import Any, Dict, List, Optional, Tuple, cast

from droxcli.config import load_config, show_config
from droxcli.context.scanner import scan_project
from droxcli.core.executor import PipelineExecutor, Task
from droxcli.core.logger import logger
from droxcli.intent.parser import parse_natural_language
from droxcli.ollama.client import (
    OllamaClient,
    OllamaConnectionError,
    OllamaTimeoutError,
)
from droxcli.ollama.models import DiffPatch, Plan
from droxcli.safety.linter import run_black, run_ruff
from droxcli.safety.security import analyse_code
from droxcli.safety.test_runner import run_pytest
from droxcli.safety.type_checker import run_mypy
from droxcli.state.conversation import log_turn, print_history, undo
from droxcli.state.file_tracker import (
    apply_patches,
    capture_snapshots,
    create_snapshot,
    restore_snapshot,
)
from droxcli.ui.banner import print_banner
from droxcli.ui.formatter import (
    divider,
    error,
    info,
    print_patch_preview,
    step,
    success,
    warning,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _confirm(prompt: str, default: bool = False) -> bool:
    hint = "[Y/n]" if default else "[y/N]"
    try:
        answer = input(f"\n{prompt} {hint} ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in {"y", "yes"}


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------


def _generate_plan_with_rag(
    client: OllamaClient,
    cfg: Any,
    raw_input: str,
    intent: Any,
    context: Dict[str, Any],
) -> Optional[Plan]:
    from droxcli.rag.store import (
        format_for_prompt,
        get_datasets_dir,
        index_datasets_dir,
        query as rag_query,
    )

    datasets_dir = get_datasets_dir()
    if any(datasets_dir.rglob("*.*")):
        index_datasets_dir(verbose=False)

    rag_chunks = rag_query(raw_input, top_k=3)
    if rag_chunks:
        print(info(f"RAG: injecting {len(rag_chunks)} reference example(s)"))
        logger.info("rag_injected", count=len(rag_chunks))
        enriched = raw_input + "\n" + format_for_prompt(rag_chunks)
    else:
        enriched = raw_input

    try:
        plan = client.generate_plan(
            {**intent.model_dump(), "description": enriched},
            context,
        )
        logger.info("plan_ok", steps=len(plan.steps))
        return plan
    except (OllamaConnectionError, OllamaTimeoutError) as exc:
        print(error(str(exc)))
        logger.error("ollama_error", error=str(exc))
    except Exception as exc:
        print(error(f"Planning failed: {exc}"))
        logger.error("plan_fail", error=str(exc))
    return None


def _generate_patches(
    client: OllamaClient,
    plan: Plan,
    context: Dict[str, Any],
) -> Optional[List[DiffPatch]]:
    try:
        patches = client.generate_code(plan, context)
        logger.info("patches_ok", count=len(patches))
        return patches
    except OllamaTimeoutError as exc:
        print(error(str(exc)))
        logger.error("codegen_timeout", error=str(exc))
    except Exception as exc:
        print(error(f"Code generation failed: {exc}"))
        logger.error("codegen_fail", error=str(exc))
    return None


def _run_safety_checks(
    root: pathlib.Path,
    patches: List[Any],
) -> Tuple[List[tuple], List[Dict[str, Any]]]:
    print(step(5, 8, "Running safety checks …"))
    patch_files = [p.file for p in patches]
    patch_dicts = [p.model_dump() for p in patches]

    tasks = [
        Task(name="black", func=run_black, args=(patch_files,)),
        Task(name="ruff", func=run_ruff, args=(patch_files,)),
        Task(name="mypy", func=run_mypy, args=(patch_files,)),
        Task(name="pytest", func=run_pytest, args=(root,)),
        Task(name="security", func=analyse_code, args=(patch_dicts,)),
    ]

    executor = PipelineExecutor(max_workers=5, timeout=120.0)
    batch = executor.execute_batch(tasks)

    failed: List[tuple] = []
    for name, result, exc in batch:
        if exc is not None:
            print(warning(f"  ⚠ {name}: exception — {exc}"))
            failed.append((name, str(exc)))
        elif result is not None:
            icon = "✓" if result.ok else "✗"
            fn = success if result.ok else warning
            print(fn(f"  {icon} {name}: {result.message}"))
            if not result.ok:
                failed.append((name, result.message))

    if failed:
        print(error(f"\n{len(failed)} safety check(s) failed."))

    return failed, patch_dicts


def _self_correct_patches(
    client: OllamaClient,
    patch_dicts: List[Dict[str, Any]],
    failed_checks: List[tuple],
) -> List[Dict[str, Any]]:
    """Feed error messages back to the model and ask it to fix the code."""
    error_map: Dict[str, List[str]] = {}
    for check_name, message in failed_checks:
        for patch in patch_dicts:
            error_map.setdefault(patch["file"], []).append(f"[{check_name}] {message}")

    corrected = []
    for patch in patch_dicts:
        fname = patch["file"]
        errors = error_map.get(fname)
        if errors and fname.endswith(".py"):
            print(info(f"  Correcting {fname}…"))
            try:
                fixed = client.self_correct(
                    file=fname,
                    broken_code=patch["new"],
                    errors="\n".join(errors),
                )
                corrected.append({**patch, "new": fixed})
                logger.info("self_correction_applied", file=fname)
            except Exception as exc:
                logger.warning("self_correction_failed", file=fname, error=str(exc))
                print(warning(f"  Could not auto-correct {fname}: {exc}"))
                corrected.append(patch)
        else:
            corrected.append(patch)
    return corrected


def _snapshot_and_apply(
    patch_dicts: List[Dict[str, Any]],
    root: pathlib.Path,
) -> Tuple[str, List]:
    print(step(6, 8, "Creating integrity snapshot …"))
    snap_id = create_snapshot(patch_dicts, root)
    snapshots = capture_snapshots(patch_dicts, root)
    print(info(f"Snapshot: {snap_id}"))

    print(step(7, 8, "Applying patches …"))
    try:
        apply_patches(patch_dicts, root, snap_id=snap_id)
    except Exception as exc:
        print(error(f"Write failed: {exc}"))
        print(warning("Attempting to restore from snapshot …"))
        try:
            restore_snapshot(snap_id, root)
            print(success("Restored successfully."))
        except Exception as re_exc:
            print(error(f"Restore also failed: {re_exc}"))
        sys.exit(1)

    return snap_id, snapshots


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def run_user_command(raw_input: str) -> None:
    cfg = load_config()
    root = pathlib.Path.cwd()
    print_banner()
    logger.info("pipeline_start", input=raw_input[:80])
    _t0 = time.perf_counter()

    # 1. Parse intent
    print(step(1, 8, "Understanding your request …"))
    intent = parse_natural_language(raw_input)
    target_display = (
        ", ".join(intent.target_files) if intent.target_files else "TBD by model"
    )
    print(info(f"Intent: {intent.action}  |  Files: {target_display}"))
    logger.info("intent_ok", action=intent.action, files=target_display)

    # 2. Scan project
    print(step(2, 8, "Scanning project …"))
    context = scan_project(root=root, target_files=intent.target_files)
    reduced = "  ⚠ Context reduced (large repo)" if context.get("reduced") else ""
    print(info(f"{len(context['files'])} file(s) loaded.{reduced}"))
    logger.info("scan_ok", files=len(context["files"]))

    # 3. Generate plan
    print(step(3, 8, "Generating plan …"))
    client = OllamaClient(cfg)
    plan = _generate_plan_with_rag(client, cfg, raw_input, intent, context)
    if plan is None:
        sys.exit(1)

    print(f"\n{divider()}")
    for s in plan.steps:
        marker = (
            "✚" if s.operation == "add" else ("✎" if s.operation == "edit" else "✖")
        )
        conf = f"  ({int(s.confidence * 100)}%)" if s.confidence < 1.0 else ""
        print(f"  {s.step_id}. {marker} {s.file}  —  {s.description}{conf}")
    print(divider())

    if not _confirm("Apply this plan?"):
        print(warning("Aborted."))
        sys.exit(0)

    # 4. Generate code
    print(step(4, 8, "Generating code …"))
    patches = _generate_patches(client, plan, context)
    if patches is None:
        sys.exit(1)

    print()
    for p in patches:
        print_patch_preview(p.file, p.new)

    if getattr(intent, "dry_run", False):
        print(warning("Dry-run mode — nothing written."))
        sys.exit(0)

    if not _confirm("Write these changes to disk?"):
        print(warning("Changes discarded."))
        sys.exit(0)

    # 5. Safety checks + self-correction loop
    failed, patch_dicts = _run_safety_checks(root, patches)

    if failed:
        correctable = [f for f in failed if f[0] in {"black", "mypy", "ruff"}]
        if correctable:
            print(info(f"Attempting self-correction on {len(correctable)} issue(s)…"))
            patch_dicts = _self_correct_patches(client, patch_dicts, correctable)

            class _Proxy:
                def __init__(self, d: Dict[str, Any]) -> None:
                    self.file = d["file"]
                    self.new = d["new"]

                def model_dump(self) -> Dict[str, Any]:
                    return {"file": self.file, "new": self.new}

            proxies = [_Proxy(p) for p in patch_dicts]
            failed2, patch_dicts = _run_safety_checks(
                root, cast(List[DiffPatch], proxies)
            )
            if not failed2:
                print(success("Self-correction resolved all issues."))
                failed = []
            else:
                failed = failed2

    if failed and not _confirm("Apply anyway?"):
        print(warning("Aborting."))
        sys.exit(1)

    # 6 + 7. Snapshot and apply
    snap_id, snapshots = _snapshot_and_apply(patch_dicts, root)

    # 8. Persist turn
    print(step(8, 8, "Saving to history …"))
    turn_id = log_turn(
        user_input=raw_input,
        intent=intent.model_dump(),
        plan=plan.model_dump(),
        patches=patch_dicts,
        result="✅ applied",
        snapshots=snapshots,
    )

    # Prune old snapshots to stay within rollback_depth
    try:
        from droxcli.state.file_tracker import prune_snapshots

        pruned = prune_snapshots(keep=cfg.rollback_depth)
        if pruned:
            logger.debug("snapshots_pruned", count=pruned)
    except Exception:
        pass  # pruning is best-effort

    duration_ms = round((time.perf_counter() - _t0) * 1000, 2)
    print(f"\n{success(f'Done! Turn #{turn_id} recorded.')}")
    print(info(f"Snapshot: {snap_id}"))
    print(info(f"To revert: droxcli undo {turn_id}"))
    logger.info(
        "pipeline_done", turn_id=turn_id, ms=duration_ms, patches=len(patch_dicts)
    )


# ---------------------------------------------------------------------------
# Auxiliary commands
# ---------------------------------------------------------------------------


def show_history(limit: int = 20) -> None:
    print_history(limit)


def perform_undo(turn_id: int) -> None:
    undo(turn_id)


def show_models() -> None:
    cfg = load_config()
    client = OllamaClient(cfg)
    try:
        models = client.list_models()
    except Exception as exc:
        print(error(f"Cannot reach Ollama: {exc}"))
        return
    print(info(f"Models in Ollama ({cfg.ollama_endpoint}):"))
    for m in models:
        tag = ""
        if m == cfg.planning_model:
            tag = "  ← planning model"
        elif m == cfg.execution_model:
            tag = "  ← execution model"
        print(f"  • {m}{tag}")


def check_status() -> None:
    cfg = load_config()
    client = OllamaClient(cfg)
    if client.check_connection():
        print(success(f"Ollama is reachable at {cfg.ollama_endpoint}"))
        show_models()
        print(info(f"Timeout:      {cfg.ollama_timeout}s"))
        print(info(f"Context:      {cfg.max_context_tokens} tokens"))
        print(info(f"Temperature:  {cfg.temperature}"))
        if cfg.system_prompt:
            preview = (
                cfg.system_prompt[:60] + "…"
                if len(cfg.system_prompt) > 60
                else cfg.system_prompt
            )
            print(info(f"System prompt: {preview}"))
    else:
        print(error(f"Cannot reach Ollama at {cfg.ollama_endpoint}"))
        print(info("Start it with: ollama serve"))
    show_config(cfg)
