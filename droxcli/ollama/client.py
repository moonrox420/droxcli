"""
Ollama HTTP client — optimized for qwen2.5-coder:7b-instruct-q8_0 (planner) + nemotron-cascade-2:30b (executor).

Design notes:
  Qwen2.5-Coder-7B (planner):
    - Short, direct prompts — concise is better than verbose
    - Temperature 0.0 for deterministic JSON plans
    - 2k tokens is enough for any plan
  Nemotron-Cascade-2-30B (executor):
    - NVIDIA mixture-of-depths — strong at multi-step reasoning
    - Benefits from structured prompts with explicit output schema
    - 32k context, 16k output ceiling — handles large files cleanly
"""

from __future__ import annotations

import concurrent.futures
import json
from typing import Dict, List, Optional

import httpx

from droxcli.config import Config
from droxcli.ollama.models import DiffPatch, Plan


class OllamaTimeoutError(RuntimeError):
    pass


class OllamaConnectionError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# System prompts — concise for Qwen planner, structured for Nemotron executor
# ---------------------------------------------------------------------------

_PLAN_SYSTEM = """\
You are a precise software engineering planner.
Given a user request and project file contents, output a JSON plan.
Rules: minimal steps, one file per step, no unnecessary changes.
Output ONLY valid JSON — no markdown, no prose."""

_EXEC_SYSTEM = """\
You are a precise code generator.
Implement the plan exactly. Output complete file contents, never diffs.
Include all imports. No TODOs. No placeholders.
Output ONLY a valid JSON array — no markdown, no prose."""

_CORRECT_SYSTEM = """\
You are a code debugger. Fix the errors in the code below.
Output the complete corrected Python file — nothing else."""


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


def _plan_prompt(intent: Dict, context: Dict) -> str:
    """Build planning prompt. Includes file contents for target files."""
    target_files = intent.get("target_files", [])
    contents = context.get("contents", {})
    all_files = context.get("files", [])

    # Always include target files in full; fill remaining budget with others
    relevant: Dict[str, str] = {f: c for f, c in contents.items() if f in target_files}
    budget = 8000 - sum(len(v) for v in relevant.values())
    other = [(f, c) for f, c in contents.items() if f not in relevant]
    per = max(200, budget // max(len(other), 1))
    for f, c in other:
        if budget <= 0:
            break
        chunk = c[: min(len(c), per)]
        relevant[f] = chunk
        budget -= len(chunk)

    file_section = "\n\n".join(
        f"### {fname}\n```\n{src[:3000]}\n```" for fname, src in relevant.items()
    )
    file_list = "\n".join(f"  {f}" for f in all_files[:100])

    return f"""Request: {intent.get("description", "")}

Files in project:
{file_list}

Relevant file contents:
{file_section}

Return this JSON schema (and nothing else):
{{
  "steps": [
    {{"step_id": 1, "description": "...", "operation": "edit|add|remove", "file": "path.py", "confidence": 0.95}}
  ],
  "overall_estimated_tokens": 512,
  "token_budget_ok": true
}}"""


def _exec_prompt(plan: Plan, context: Dict) -> str:
    """Build execution prompt with full contents of all planned files."""
    involved = {s.file for s in plan.steps}
    files_payload = {f: c for f, c in context["contents"].items() if f in involved}
    steps = "\n".join(
        f"  {s.step_id}. [{s.operation.upper()}] {s.file}: {s.description}"
        for s in plan.steps
    )

    return f"""Plan:
{steps}

Current file contents:
{json.dumps(files_payload, indent=2)[:400_000]}

Return this JSON array (and nothing else):
[
  {{"file": "path.py", "original": "...", "new": "complete new file content", "summary": "..."}}
]"""


def _correction_prompt(file: str, code: str, errors: str) -> str:
    return f"""File: {file}

Your code:
```python
{code}
```

Errors to fix:
```
{errors}
```

Output the complete corrected Python file — nothing else."""


# ---------------------------------------------------------------------------
# JSON recovery (3-attempt cascade)
# ---------------------------------------------------------------------------


def _repair_truncated(text: str) -> str:
    """Close unclosed brackets from token-limit cutoffs."""
    if not text:
        return text
    last = text.rfind("}")
    if last == -1:
        return text
    t = text[: last + 1]
    opens = t.count("{") - t.count("}")
    open_ar = t.count("[") - t.count("]")
    result = t + ("}" * max(opens, 0))
    if open_ar > 0:
        result += "]" * open_ar + "}"
    return result


def _recover_json(raw: str, label: str) -> object:
    cleaned = raw.strip()

    # Strip markdown fences
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        end = len(lines) - 1 if lines and lines[-1].strip() == "```" else len(lines)
        cleaned = "\n".join(lines[1:end]).strip()

    # Attempt 1: as-is
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Attempt 2: repair truncation
    repaired = _repair_truncated(cleaned)
    if repaired != cleaned:
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass

    # Attempt 3: extract first valid object/array
    for open_ch, close_ch in [("[", "]"), ("{", "}")]:
        s = cleaned.find(open_ch)
        e = cleaned.rfind(close_ch)
        if s != -1 and e > s:
            try:
                return json.loads(cleaned[s : e + 1])
            except json.JSONDecodeError:
                pass

    raise RuntimeError(
        f"{label} returned malformed JSON.\nRaw (first 600 chars):\n{raw[:600]}"
    )


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class OllamaClient:
    """HTTP client for Ollama with hard-timeout enforcement (SYSTEM 4)."""

    # Class-level executor — shared across all instances, never recreated
    _executor: Optional[concurrent.futures.ThreadPoolExecutor] = None

    def __init__(self, cfg: Config) -> None:
        self.base_url = cfg.ollama_endpoint.rstrip("/")
        self.planning_model = cfg.planning_model
        self.execution_model = cfg.execution_model
        self.timeout = cfg.ollama_timeout
        self.temperature = cfg.temperature
        self.system_prompt = cfg.system_prompt

        if OllamaClient._executor is None:
            OllamaClient._executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=2, thread_name_prefix="ollama"
            )

    def _generate(
        self,
        model: str,
        system: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Call Ollama with a hard wall-clock timeout. Never hangs."""
        # Prepend custom personality if configured
        if self.system_prompt:
            system = self.system_prompt.rstrip() + "\n\n" + system

        def _call() -> str:
            payload = {
                "model": model,
                "system": system,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                    "num_ctx": 32768,  # Nemotron handles full 32k cleanly
                    "repeat_penalty": 1.1,  # standard for 30B models
                    "top_p": 0.95,
                },
            }
            try:
                resp = httpx.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=httpx.Timeout(
                        connect=10.0,
                        read=float(self.timeout),
                        write=30.0,
                        pool=5.0,
                    ),
                )
                resp.raise_for_status()
            except httpx.ConnectError:
                raise OllamaConnectionError(
                    f"Cannot reach Ollama at {self.base_url}. "
                    "Is it running?  Try: ollama serve"
                )
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(
                    f"Ollama HTTP {exc.response.status_code}: {exc.response.text[:300]}"
                )
            return resp.json().get("response", "")

        future = self._executor.submit(_call)
        try:
            return future.result(timeout=self.timeout + 15)
        except concurrent.futures.TimeoutError:
            future.cancel()
            raise OllamaTimeoutError(
                f"Ollama timed out after {self.timeout}s on '{model}'. "
                "Run: droxcli config set ollama_timeout 900"
            )

    def generate_plan(self, intent: Dict, context: Dict) -> Plan:
        raw = self._generate(
            model=self.planning_model,
            system=_PLAN_SYSTEM,
            prompt=_plan_prompt(intent, context),
            temperature=0.0,
            max_tokens=2048,  # plans are short; planner is 7B so keep it tight
        )
        return Plan.model_validate(_recover_json(raw, "Planning model"))

    def generate_code(self, plan: Plan, context: Dict) -> List[DiffPatch]:
        raw = self._generate(
            model=self.execution_model,
            system=_EXEC_SYSTEM,
            prompt=_exec_prompt(plan, context),
            temperature=self.temperature,
            max_tokens=16384,  # 30B can produce larger, well-structured files
        )
        result = _recover_json(raw, "Execution model")
        if not isinstance(result, list):
            raise RuntimeError("Execution model did not return a JSON array.")
        return [DiffPatch.model_validate(p) for p in result]

    def self_correct(
        self,
        file: str,
        broken_code: str,
        errors: str,
        max_attempts: int = 2,
    ) -> str:
        """Feed broken code + errors back to the model. Returns corrected source."""
        code = broken_code
        for _ in range(max_attempts):
            raw = self._generate(
                model=self.execution_model,
                system=_CORRECT_SYSTEM,
                prompt=_correction_prompt(file, code, errors),
                temperature=0.0,
                max_tokens=4096,
            )
            fixed = raw.strip()
            if fixed.startswith("```"):
                lines = fixed.splitlines()
                end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
                fixed = "\n".join(lines[1:end]).strip()
            code = fixed
            # Stop early if output looks complete
            if not any(
                kw in fixed for kw in ["TODO", "raise NotImplementedError", "pass  #"]
            ):
                break
        return code

    def check_connection(self) -> bool:
        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def list_models(self) -> List[str]:
        resp = httpx.get(f"{self.base_url}/api/tags", timeout=10)
        resp.raise_for_status()
        return [m["name"] for m in resp.json().get("models", [])]
