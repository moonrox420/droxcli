"""Load and manage ~/.droxcli/config.json."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

# ---------------------------------------------------------------------------
# Defaults — tuned for qwen2.5-coder:7b-instruct-q8_0 (planner) + nemotron-cascade-2:30b (executor)
# ---------------------------------------------------------------------------
DEFAULTS: dict = {
    "ollama_endpoint": "http://127.0.0.1:11434",
    # Fast 7B planner — cheap, deterministic JSON plans
    "planning_model": "qwen2.5-coder:7b-instruct-q8_0",
    # Nemotron Cascade 30B executor — NVIDIA's mixture-of-depths architecture,
    # strong reasoning, handles complex multi-file changes cleanly.
    "execution_model": "nemotron-cascade-2:30b",
    "ollama_timeout": 600,  # 30B needs time — 10 min ceiling
    "auto_apply_safe": True,
    "rollback_depth": 10,
    "max_context_tokens": 32768,  # Nemotron supports large context windows
    "temperature": 0.0,  # fully deterministic — best for code
    "debug_mode": False,
    "enable_git": False,
    "git_auto_commit": False,
    # Custom personality injected before every system prompt.
    # Leave empty to use built-in prompts as-is.
    # Example: "Always use type hints. Prefer pathlib over os.path."
    "system_prompt": "",
}

CONFIG_PATH = Path.home() / ".droxcli" / "config.json"
CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class Config:
    ollama_endpoint: str
    planning_model: str
    execution_model: str
    ollama_timeout: int
    auto_apply_safe: bool
    rollback_depth: int
    max_context_tokens: int
    temperature: float
    debug_mode: bool
    enable_git: bool
    git_auto_commit: bool
    system_prompt: str


def load_config() -> Config:
    """Merge ~/.droxcli/config.json with defaults. Unknown keys are ignored."""
    data: dict = {}
    if CONFIG_PATH.is_file():
        try:
            with CONFIG_PATH.open(encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            print(f"⚠  Config at {CONFIG_PATH} is malformed — using defaults.")

    merged = {**DEFAULTS, **data}
    known = {f.name for f in fields(Config)}
    filtered = {k: v for k, v in merged.items() if k in known}

    # Auto-fix missing scheme on endpoint
    ep = filtered.get("ollama_endpoint", "")
    if ep and not ep.startswith("http"):
        filtered["ollama_endpoint"] = f"http://{ep}"

    return Config(**filtered)


def save_config(cfg: Config) -> None:
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(asdict(cfg), f, indent=2)


def set_config_value(key: str, value: str) -> None:
    """Set a single key and persist. Coerces to the correct type automatically."""
    cfg = load_config()
    known = {f.name for f in fields(Config)}
    if key not in known:
        raise ValueError(
            f"Unknown config key: '{key}'\nValid keys: {', '.join(sorted(known))}"
        )
    current = getattr(cfg, key)
    if isinstance(current, bool):
        coerced = value.lower() in {"true", "1", "yes"}
    elif isinstance(current, int):
        coerced = int(value)
    elif isinstance(current, float):
        coerced = float(value)
    else:
        coerced = value
    setattr(cfg, key, coerced)
    save_config(cfg)


def show_config(cfg: Config) -> None:
    from droxcli.ui.formatter import info

    print(info("Current DroxCLI configuration:"))
    for k, v in asdict(cfg).items():
        tag = ""
        if k == "planning_model":
            tag = "  ← planner"
        elif k == "execution_model":
            tag = "  ← executor"
        print(f"  {k}: {v}{tag}")
