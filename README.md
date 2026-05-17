# DroxCLI

An agentic coding tool that lives in your terminal and edits your code using local Ollama models. You describe what you want in plain English — it reads your project, plans the changes, generates the code, runs safety checks, and writes the files atomically with a full undo history.

No cloud. No API keys. No subscriptions. Runs entirely on your machine.

---

## Requirements

- Python 3.11+
- [Ollama](https://ollama.com) running locally (`ollama serve`)
- At least one code model pulled (`ollama pull <model>`)

---

## Installation

```powershell
git clone https://github.com/yourname/droxcli
cd droxcli
python -m venv .venv
.venv\Scripts\Activate.ps1          # Windows
# source .venv/bin/activate          # macOS / Linux
pip install -r requirements.txt
pip install -e .
```

Verify:

```powershell
droxcli status
```

---

## Quick Start

```powershell
# Just describe what you want — no flags, no syntax
droxcli "the login function is broken, fix it"
droxcli "make quicksort faster in utils.py"
droxcli "add type hints and docstrings to every function in db.py"
droxcli "there's a memory leak somewhere in scanner.py, find and fix it"
droxcli "refactor the config loader to use pydantic"
```

DroxCLI will:
1. Parse your intent
2. Scan your project files
3. Show you a plan and ask for confirmation
4. Generate the code and preview it
5. Run safety checks (black, ruff, mypy, pytest, security scan)
6. Write files atomically with a SHA256 snapshot for rollback
7. Save the turn to history

---

## Recommended Model Setup

DroxCLI uses a two-model split: a fast **planner** and a capable **executor**.

| Role | Recommended Model | Why |
|------|------------------|-----|
| Planner | `qwen2.5-coder:7b-instruct-q8_0` | Fast, cheap, just needs to output a JSON plan |
| Executor | `nemotron-cascade-2:30b` | NVIDIA mixture-of-depths 30B, strong reasoning |

```powershell
ollama pull qwen2.5-coder:7b-instruct-q8_0
ollama pull nemotron-cascade-2:30b
```

These are the defaults. Change them any time:

```powershell
droxcli config set execution_model nemotron-cascade-2:30b
droxcli config set planning_model qwen2.5-coder:7b-instruct-q8_0
```

---

## Configuration

Config lives at `~/.droxcli/config.json`. Edit it directly or use the CLI:

```powershell
droxcli config show
droxcli config set <key> <value>
```

| Key | Default | Description |
|-----|---------|-------------|
| `ollama_endpoint` | `http://127.0.0.1:11434` | Ollama server URL |
| `planning_model` | qwen2.5-coder:7b-instruct-q8_0 | Model for generating plans |
| `execution_model` | nemotron-cascade-2:30b | Model for generating code |
| `ollama_timeout` | `600` | Seconds before giving up on a model call |
| `max_context_tokens` | `32768` | Max tokens sent to the model |
| `temperature` | `0.0` | Lower = more deterministic code |
| `system_prompt` | `""` | Custom personality injected into every prompt |
| `rollback_depth` | `10` | Snapshots kept in `~/.droxcli/snapshots/` |

### Tuning the system prompt for specific models

Some models respond dramatically better with a personality set:

```powershell
# For Dolphin or other instruction-tuned models
droxcli config set system_prompt "You are an expert competitive programmer who implements every standard algorithm correctly from scratch on the first attempt. You never forget imports."

# Clear it
droxcli config set system_prompt ""
```

---

## Commands

### Natural language (primary usage)

```powershell
droxcli "<anything you want>"
```

Examples:

```powershell
droxcli "utils.py is returning wrong results for negative inputs"
droxcli "add rate limiting to the API endpoints in routes.py"
droxcli "the tests in test_auth.py are all failing after the refactor"
droxcli "extract the database logic from app.py into its own module"
droxcli "dry-run: show me what you'd change in config.py"   # preview only
```

### History and undo

```powershell
droxcli history          # last 20 turns
droxcli history 50       # last 50 turns
droxcli undo 7           # revert all files to their state before turn 7
```

Every turn creates a SHA256-verified snapshot before touching disk. Undo is always safe.

### Models and status

```powershell
droxcli status           # connectivity check + current config
droxcli models           # list all models in Ollama, highlight active ones
```

---

## RAG — Making the Model Smarter

RAG (Retrieval Augmented Generation) indexes your code and injects relevant examples into every prompt. The model writes better code because it sees *your* patterns, not generic ones.

```powershell
# See where to drop files
droxcli rag datasets

# Index a single file
droxcli rag add droxcli/state/db.py

# Drop files into the datasets folder and bulk-index
# (any .py, .md, .json, .txt, .yaml, .sh, .go, .rs, .ts files)
droxcli rag index

# Inspect the store
droxcli rag list
droxcli rag stats

# Wipe and re-index
droxcli rag clear
droxcli rag index
```

**What to put in the datasets folder:**

| File | What it teaches |
|------|----------------|
| Your best existing code | Your personal style and conventions |
| `patterns.md` | Rules like "always use pathlib, never os.path" |
| API docs as `.txt` | How to call specific libraries correctly |
| Reference implementations | Algorithms you want it to follow |
| `typing_examples.py` | Type hint patterns |

Python files are chunked at **function and class boundaries** (AST-aware), so every RAG chunk is a complete, callable unit — not an arbitrary 50-line slice.

---

## Benchmarking Your Model

DroxCLI has a built-in eval harness to measure how smart your model actually is.

```powershell
droxcli eval              # standard suite: 12 problems
droxcli eval stier        # S-tier: 11 harder problems
droxcli eval all          # all 23 problems
droxcli eval easy         # filter by difficulty
droxcli eval --id H01     # single problem
droxcli eval --verbose    # show generated code + failure details
```

**Standard suite** (12 problems):

| Tier | Problems | What it tests |
|------|----------|--------------|
| 🟢 Easy | E01–E03 | FizzBuzz, palindrome, flatten |
| 🟡 Medium | M01–M05 | Two-sum, LRU cache, anagrams, config parser, merge intervals |
| 🔴 Hard | H01–H03 | Levenshtein distance, tree serialization, word break |
| 🔵 Self | S01 | Filesystem traversal |

**S-tier suite** (11 problems — designed to expose capability limits):

| ID | Problem | Algorithm |
|----|---------|-----------|
| X01 | Skyline | Sweep line + max-heap |
| X02 | Alien dictionary | Topological sort + cycle detection |
| X03 | Stock cooldown | 3-state DP |
| X04 | Trap water | O(1) space two-pointer |
| X05 | MedianFinder | Two-heap design |
| X06 | WordDictionary | Trie + wildcard DFS |
| X07 | RangeSum | Fenwick tree |
| X08 | JSON path parser | Recursive traversal |
| X09 | Expression tokenizer | Lexer |
| X10 | RateLimiter | Sliding window |
| XS1 | Diff summary | LCS-based diff |

**Grading:**

| Score | Grade |
|-------|-------|
| 100% | S — Perfect |
| ≥ 90% | A+ — Exceptional |
| ≥ 75% | A — Strong |
| ≥ 60% | B — Competent |
| ≥ 45% | C — Developing |
| < 45% | D — Needs work |

`qwen2.5-coder:7b-instruct-q8_0` scores **12/12 (100%)** on the standard suite and **7/11 (~64%)** on S-tier. The 20B executor is expected to pass all 23.

---

## How It Works

### The 8-step pipeline

```
1. Parse intent      Natural language → structured action + file targets
2. Scan project      Read all source files, build dependency graph
3. Generate plan     Planning model produces a JSON step list → you confirm
4. Generate code     Execution model writes complete new file contents → you confirm
5. Safety checks     black, ruff, mypy, pytest, security scan (parallel)
   └─ Self-correct   If checks fail, errors fed back to model for auto-fix
6. Create snapshot   SHA256 hash of every file before touching disk
7. Apply patches     Atomic writes via tempfile + os.replace() — no corruption
8. Save history      SQLite turn record with snapshot ID for undo
```

### Five hardened systems

| System | What it does |
|--------|-------------|
| **SYSTEM 1** | Atomic writes — `tempfile` + `os.replace()`, zero corruption windows |
| **SYSTEM 2** | SHA256 snapshot hashing — integrity verified before every restore |
| **SYSTEM 3** | SQLite WAL mode — concurrent-safe conversation history |
| **SYSTEM 4** | ThreadPoolExecutor Ollama timeout — requests never hang forever |
| **SYSTEM 5** | Crash isolation — all unhandled exceptions logged to `~/.droxcli/debug.log` |

### Self-correction loop

When black/mypy/ruff fail on generated code, DroxCLI doesn't just ask "apply anyway?" — it feeds the exact error messages back to the model:

```
"Here's the code you wrote. Here's what broke. Fix it."
```

The model sees its own mistakes and corrects them before you ever see the result. Two correction attempts before falling back to asking you.

---

## Project Structure

```
droxcli/
├── __init__.py
├── __main__.py          Crash isolation (SYSTEM 5)
├── cli.py               Command dispatch
├── config.py            ~/.droxcli/config.json management
├── orchestrator.py      8-step pipeline
│
├── context/
│   └── scanner.py       Parallel file scanner with dependency graph
│
├── core/
│   ├── logger.py        Structured JSON logging (structlog or fallback)
│   ├── telemetry.py     trace_performance + atomic_operation contexts
│   └── executor.py      PipelineExecutor for parallel safety checks
│
├── eval/
│   ├── problems.py      Standard 12 benchmark problems
│   ├── problems_stier.py  S-tier 11 hard problems
│   └── runner.py        Eval harness with import auto-repair
│
├── intent/
│   ├── models.py        Intent pydantic model
│   └── parser.py        Conversational NL parser
│
├── ollama/
│   ├── models.py        Plan / DiffPatch pydantic models
│   └── client.py        HTTP client with few-shot prompts + self_correct()
│
├── rag/
│   └── store.py         BM25 retrieval, AST-aware chunking, memory cache
│
├── safety/
│   ├── linter.py        black + ruff wrappers
│   ├── type_checker.py  mypy wrapper
│   ├── test_runner.py   pytest discovery + execution
│   └── security.py      Regex-based security pattern scanner
│
├── state/
│   ├── db.py            SQLite WAL conversation history
│   ├── file_tracker.py  SHA256 snapshots + atomic writes (SYSTEM 1+2)
│   └── conversation.py  CRUD helpers + undo
│
└── ui/
    ├── banner.py        ASCII art banner
    └── formatter.py     Colorized output helpers
```

---

## Data stored locally

| Path | Contents |
|------|----------|
| `~/.droxcli/config.json` | Your configuration |
| `~/.droxcli/conversation.db` | Full turn history (SQLite) |
| `~/.droxcli/snapshots/` | Pre-change file snapshots for undo |
| `~/.droxcli/rag/index.json` | RAG chunk index |
| `~/.droxcli/rag/datasets/` | Drop files here for bulk indexing |
| `~/.droxcli/debug.log` | Crash logs |

Everything stays on your machine. Nothing is sent anywhere except to your local Ollama instance.

---

## Troubleshooting

**Ollama not reachable**
```powershell
ollama serve          # start the server
droxcli status        # verify connectivity
```

**Model times out**
```powershell
droxcli config set ollama_timeout 900    # increase to 15 minutes
```

**Generated code has errors**
DroxCLI will attempt to self-correct automatically. If it fails, run with verbose for details, or use `droxcli undo <turn-id>` to revert.

**Check crash logs**
```powershell
Get-Content ~\.droxcli\debug.log | Select-Object -Last 50
```

---

## License

MIT
