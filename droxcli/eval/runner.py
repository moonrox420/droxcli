"""
Eval harness — benchmark your Ollama model against coding problems.

Usage:
  droxcli eval                Run standard suite (12 problems)
  droxcli eval stier          Run S-tier suite (11 hard problems)
  droxcli eval all            Run all 23 problems
  droxcli eval easy
  droxcli eval --id X05       Any ID from either suite
  droxcli eval --verbose
"""

import subprocess
import textwrap
import time
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from droxcli.config import load_config
from droxcli.eval.problems import PROBLEMS, Problem
from droxcli.eval.problems_stier import PROBLEMS_STIER
from droxcli.ollama.client import OllamaClient
from droxcli.ui.formatter import divider, error, info, success, warning

ALL_PROBLEMS = PROBLEMS + PROBLEMS_STIER

# Tuned for GPT-OSS 20B — direct, authoritative, no hedging
_CODEGEN_SYSTEM = """\
You are an expert Python programmer.
Write only the requested function(s) or class(es).
Include all necessary imports at the top.
Handle all edge cases. No explanation. No markdown fences.
Return raw Python source code only."""

# Stdlib modules models commonly use without importing
_COMMON_IMPORTS = {
    "heapq": "import heapq",
    "bisect": "import bisect",
    "functools": "import functools",
    "itertools": "import itertools",
    "math": "import math",
    "re": "import re",
    "sys": "import sys",
    "collections": "from collections import defaultdict, deque, OrderedDict, Counter",
    "typing": "from typing import List, Dict, Tuple, Optional, Set",
}


@dataclass
class EvalResult:
    problem: Problem
    passed: bool
    generated_code: str
    error_msg: str
    elapsed_seconds: float
    tokens_approx: int


def _strip_fences(raw: str) -> str:
    code = raw.strip()
    if code.startswith("```"):
        lines = code.splitlines()
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        code = "\n".join(lines[1:end]).strip()
    return code


def _ensure_imports(code: str) -> str:
    """Inject stdlib imports the model used but forgot to declare."""
    to_add = []
    for module, stmt in _COMMON_IMPORTS.items():
        already = f"import {module}" in code or f"from {module}" in code
        if already:
            continue
        members = {
            "collections": ["defaultdict", "deque", "OrderedDict", "Counter"],
        }.get(module, [])
        used = f"{module}." in code or any(m in code for m in members)
        if used:
            to_add.append(stmt)
    if to_add:
        return "\n".join(to_add) + "\n\n" + code
    return code


def _run_tests(code: str, test_code: str, tmp_dir: Path) -> tuple[bool, str]:
    """Wrap assertions in def test_solution() and run pytest."""
    (tmp_dir / "eval_target.py").write_text(code, encoding="utf-8")
    indented = textwrap.indent(test_code.strip(), "    ")
    wrapped = (
        f"import sys\n"
        f"sys.path.insert(0, r'{tmp_dir}')\n\n"
        f"def test_solution():\n"
        f"{indented}\n"
    )
    (tmp_dir / "test_eval.py").write_text(wrapped, encoding="utf-8")
    try:
        proc = subprocess.run(
            [
                "pytest",
                str(tmp_dir / "test_eval.py"),
                "-q",
                "--tb=short",
                "--no-header",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=30,
        )
        return proc.returncode == 0, (proc.stdout + proc.stderr).strip()
    except subprocess.TimeoutExpired:
        return False, "Test timed out after 30s"


def run_eval(
    difficulty: Optional[str] = None,
    category: Optional[str] = None,
    problem_id: Optional[str] = None,
    tier: Optional[str] = None,
    verbose: bool = False,
) -> List[EvalResult]:
    cfg = load_config()
    client = OllamaClient(cfg)

    # --id always searches all problems
    if problem_id:
        pool = ALL_PROBLEMS
    elif tier == "stier":
        pool = PROBLEMS_STIER
    elif tier == "all":
        pool = ALL_PROBLEMS
    else:
        pool = PROBLEMS

    problems = pool
    if difficulty:
        problems = [p for p in problems if p.difficulty.lower() == difficulty.lower()]
    if category:
        problems = [p for p in problems if p.category.lower() == category.lower()]
    if problem_id:
        problems = [p for p in problems if p.id.upper() == problem_id.upper()]

    if not problems:
        print(warning("No problems matched the filter."))
        return []

    tier_label = {"stier": "S-Tier", "all": "Full Suite"}.get(tier or "", "Standard")
    print(f"\n{divider()}")
    print(
        info(
            f"Running {len(problems)} {tier_label} problem(s) against {cfg.execution_model}"
        )
    )
    print(divider())

    results: List[EvalResult] = []

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        for i, problem in enumerate(problems, 1):
            icon = {"easy": "🟢", "medium": "🟡", "hard": "🔴", "s-tier": "💀"}.get(
                problem.difficulty, "⚪"
            )
            print(
                f"\n[{i}/{len(problems)}] {icon} {problem.id} — {problem.category}/{problem.difficulty}"
            )

            if verbose:
                print(info(f"  Prompt: {problem.prompt[:100]}…"))

            start = time.time()
            try:
                raw = client._generate(
                    model=cfg.execution_model,
                    system=_CODEGEN_SYSTEM,
                    prompt=problem.prompt,
                    temperature=0.0,  # deterministic for benchmarking
                    max_tokens=2048,  # 7B is concise; 2k covers any benchmark solution
                )
                elapsed = time.time() - start
                tokens_approx = len(raw.split())
                code = _ensure_imports(_strip_fences(raw))

                if verbose:
                    preview = "\n".join(code.splitlines()[:8])
                    print(
                        info(
                            f"  Generated ({tokens_approx} tokens):\n{textwrap.indent(preview, '    ')}"
                        )
                    )

                passed, test_output = _run_tests(code, problem.test_code, tmp_path)

                if passed:
                    print(
                        success(f"  ✓ PASS  ({elapsed:.1f}s, ~{tokens_approx} tokens)")
                    )
                else:
                    print(error(f"  ✗ FAIL  ({elapsed:.1f}s)"))
                    if verbose:
                        for line in test_output.splitlines()[:12]:
                            print(f"    {line}")

                results.append(
                    EvalResult(
                        problem=problem,
                        passed=passed,
                        generated_code=code,
                        error_msg="" if passed else test_output,
                        elapsed_seconds=elapsed,
                        tokens_approx=tokens_approx,
                    )
                )

            except Exception as exc:
                elapsed = time.time() - start
                print(error(f"  ✗ ERROR  ({elapsed:.1f}s): {exc}"))
                results.append(
                    EvalResult(
                        problem=problem,
                        passed=False,
                        generated_code="",
                        error_msg=str(exc),
                        elapsed_seconds=elapsed,
                        tokens_approx=0,
                    )
                )

    return results


def print_report(results: List[EvalResult]) -> None:
    if not results:
        return

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    score_pct = (passed / total) * 100
    avg_time = sum(r.elapsed_seconds for r in results) / total

    print(f"\n{divider('═')}")
    print("  DROXCLI EVAL REPORT")
    print(divider("═"))
    print(f"  Score:    {passed}/{total}  ({score_pct:.0f}%)")
    print(f"  Avg time: {avg_time:.1f}s per problem")
    print(divider())

    for diff in ["easy", "medium", "hard", "s-tier", "self"]:
        subset = [
            r
            for r in results
            if r.problem.difficulty == diff or r.problem.category == diff
        ]
        if not subset:
            continue
        sub_pass = sum(1 for r in subset if r.passed)
        icon = {"easy": "🟢", "medium": "🟡", "hard": "🔴", "s-tier": "💀"}.get(
            diff, "🔵"
        )
        print(f"  {icon} {diff.capitalize():8s}  {sub_pass}/{len(subset)}")

    print(divider())

    if score_pct == 100:
        grade = "S  — Perfect"
    elif score_pct >= 90:
        grade = "A+ — Exceptional"
    elif score_pct >= 75:
        grade = "A  — Strong"
    elif score_pct >= 60:
        grade = "B  — Competent"
    elif score_pct >= 45:
        grade = "C  — Developing"
    else:
        grade = "D  — Needs work"

    print(f"  Grade:  {grade}")
    print(divider("═"))

    failed = [r for r in results if not r.passed]
    if failed:
        print("\n  Failed problems:")
        for r in failed:
            first = r.error_msg.splitlines()[0][:70] if r.error_msg else "unknown"
            print(f"    ✗ {r.problem.id}: {first}")
