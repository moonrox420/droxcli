"""
RAG store — index code, docs, and datasets so the model sees relevant
examples in every prompt.

Supported file types:
  Code:    .py .js .ts .go .rs .java .cpp .c .h .sh
  Config:  .yaml .yml .toml .json
  Docs:    .md .txt
  Data:    .arrow .parquet .csv  ← dataset formats the AI can read

Arrow/Parquet files are converted to a readable text schema + sample rows
so the AI understands the data structure without seeing raw binary.

Chunking:
  Python files → AST-aware (split at function/class boundaries)
  All others   → 50-line chunks

Scoring:
  BM25 with in-memory cache (zero disk hits per query once loaded)
"""

from __future__ import annotations

import ast
import json
import math
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

RAG_DIR = Path.home() / ".droxcli" / "rag"
RAG_DIR.mkdir(parents=True, exist_ok=True)
INDEX_FILE = RAG_DIR / "index.json"

DATASETS_DIR = RAG_DIR / "datasets"
DATASETS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Supported extensions
# ---------------------------------------------------------------------------
CODE_EXTENSIONS: set = {
    ".py",
    ".js",
    ".ts",
    ".go",
    ".rs",
    ".java",
    ".cpp",
    ".c",
    ".h",
    ".sh",
    ".bash",
}
CONFIG_EXTENSIONS: set = {
    ".yaml",
    ".yml",
    ".toml",
    ".json",
}
DOC_EXTENSIONS: set = {
    ".md",
    ".txt",
    ".rst",
}
DATA_EXTENSIONS: set = {
    ".arrow",
    ".parquet",
    ".csv",
    ".tsv",
}
SUPPORTED_EXTENSIONS: set = (
    CODE_EXTENSIONS | CONFIG_EXTENSIONS | DOC_EXTENSIONS | DATA_EXTENSIONS
)


# ---------------------------------------------------------------------------
# In-memory cache — zero disk hits per query when index is unchanged
# ---------------------------------------------------------------------------
_INDEX_CACHE: Optional[Dict] = None
_INDEX_MTIME: float = 0.0


def _load_index() -> Dict:
    global _INDEX_CACHE, _INDEX_MTIME
    if INDEX_FILE.is_file():
        mtime = INDEX_FILE.stat().st_mtime
        if _INDEX_CACHE is not None and mtime == _INDEX_MTIME:
            return _INDEX_CACHE
        try:
            _INDEX_CACHE = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
            _INDEX_MTIME = mtime
            return _INDEX_CACHE
        except Exception:
            pass
    _INDEX_CACHE = {"chunks": []}
    return _INDEX_CACHE


def _save_index(index: Dict) -> None:
    global _INDEX_CACHE, _INDEX_MTIME
    INDEX_FILE.write_text(json.dumps(index, indent=2), encoding="utf-8")
    _INDEX_CACHE = index
    _INDEX_MTIME = INDEX_FILE.stat().st_mtime


# ---------------------------------------------------------------------------
# Tokenisation
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{2,}", text.lower())


# ---------------------------------------------------------------------------
# Arrow / Parquet / CSV → human-readable text
# ---------------------------------------------------------------------------


def _read_arrow(path: Path) -> str:
    """
    Convert an Arrow IPC file into a readable schema + sample.
    Returns a text block the AI can parse and reason about.
    """
    try:
        import pyarrow as pa
        import pyarrow.ipc as ipc

        with pa.memory_map(str(path), "r") as src:
            reader = ipc.open_file(src)
            table = reader.read_all()

        return _table_to_text(table, path.name, "Apache Arrow")
    except ImportError:
        return f"# {path.name} (Apache Arrow — install pyarrow to read contents)\n"
    except Exception as exc:
        return f"# {path.name} (Arrow read error: {exc})\n"


def _read_parquet(path: Path) -> str:
    try:
        import pyarrow.parquet as pq

        table = pq.read_table(str(path))
        return _table_to_text(table, path.name, "Parquet")
    except ImportError:
        return f"# {path.name} (Parquet — install pyarrow to read contents)\n"
    except Exception as exc:
        return f"# {path.name} (Parquet read error: {exc})\n"


def _read_csv(path: Path) -> str:
    """Read CSV/TSV and return schema + sample rows as readable text."""
    import csv as csv_mod

    sep = "\t" if path.suffix.lower() == ".tsv" else ","
    lines: List[str] = []
    try:
        with path.open(encoding="utf-8", errors="replace", newline="") as f:
            reader = csv_mod.reader(f, delimiter=sep)
            headers = next(reader, [])
            rows = [row for _, row in zip(range(10), reader)]  # first 10 rows

        total_cols = len(headers)
        lines.append(f"# {path.name} ({path.suffix.upper().lstrip('.')} dataset)")
        lines.append(f"# Columns ({total_cols}): {', '.join(headers)}")
        lines.append(
            f"# Sample rows (up to 10 of {path.stat().st_size // 1024} KB file):"
        )
        lines.append("")
        lines.append(sep.join(headers))
        lines.append("─" * min(80, total_cols * 15))
        for row in rows:
            lines.append(sep.join(str(v) for v in row))
    except Exception as exc:
        lines.append(f"# {path.name} (CSV read error: {exc})")
    return "\n".join(lines)


def _table_to_text(table, name: str, fmt: str) -> str:
    """Render a PyArrow Table as readable schema + sample text."""
    schema = table.schema
    n_rows = table.num_rows
    n_cols = table.num_columns

    lines = [
        f"# {name} ({fmt} dataset)",
        f"# Shape: {n_rows:,} rows × {n_cols} columns",
        f"# Schema:",
    ]
    for field in schema:
        nullable = "" if field.nullable else " [required]"
        lines.append(f"#   {field.name}: {field.type}{nullable}")

    lines.append("")
    lines.append("# Sample rows (up to 5):")

    sample_size = min(5, n_rows)
    if sample_size > 0:
        sample = table.slice(0, sample_size).to_pydict()
        col_names = list(sample.keys())
        lines.append("  " + " | ".join(f"{c:<18}" for c in col_names))
        lines.append("  " + "-" * (21 * len(col_names)))
        for i in range(sample_size):
            row = " | ".join(f"{str(sample[c][i]):<18}" for c in col_names)
            lines.append(f"  {row}")

    # Basic stats for numeric columns
    numeric_stats = []
    for field in schema:
        if str(field.type) in {
            "int8",
            "int16",
            "int32",
            "int64",
            "uint8",
            "uint16",
            "uint32",
            "uint64",
            "float32",
            "float64",
            "double",
        }:
            col = table.column(field.name)
            try:
                import pyarrow.compute as pc

                mn = pc.min(col).as_py()
                mx = pc.max(col).as_py()
                avg = round(pc.mean(col).as_py(), 4) if n_rows > 0 else None
                numeric_stats.append(
                    f"#   {field.name}: min={mn}, max={mx}, mean={avg}"
                )
            except Exception:
                pass

    if numeric_stats:
        lines.append("")
        lines.append("# Numeric column stats:")
        lines.extend(numeric_stats)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------


def _chunk_python(source: str) -> List[Tuple[int, str]]:
    """Split Python at function/class boundaries (AST-aware)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return _chunk_lines(source)

    lines = source.splitlines()
    nodes = [
        n
        for n in ast.iter_child_nodes(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]
    if not nodes:
        return _chunk_lines(source)

    chunks: List[Tuple[int, str]] = []
    first = nodes[0].lineno - 1
    if first > 0:
        pre = "\n".join(lines[:first]).strip()
        if pre:
            chunks.append((1, pre))

    for i, node in enumerate(nodes):
        start = node.lineno - 1
        end = nodes[i + 1].lineno - 1 if i + 1 < len(nodes) else len(lines)
        text = "\n".join(lines[start:end]).strip()
        if text:
            chunks.append((node.lineno, text))

    return chunks or _chunk_lines(source)


def _chunk_lines(source: str, size: int = 50) -> List[Tuple[int, str]]:
    lines = source.splitlines()
    chunks = []
    for i in range(0, len(lines), size):
        text = "\n".join(lines[i : i + size]).strip()
        if text:
            chunks.append((i + 1, text))
    return chunks


def _read_file_text(path: Path) -> str:
    """Read a file and return its content as clean, AI-readable text."""
    suffix = path.suffix.lower()

    if suffix == ".arrow":
        return _read_arrow(path)
    if suffix == ".parquet":
        return _read_parquet(path)
    if suffix in {".csv", ".tsv"}:
        return _read_csv(path)

    # All text-based formats
    return path.read_text(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# BM25 scoring
# ---------------------------------------------------------------------------


def _compute_idf(all_chunks: List[Dict]) -> Dict[str, float]:
    n = len(all_chunks)
    if n == 0:
        return {}
    df: Dict[str, int] = {}
    for chunk in all_chunks:
        for tok in set(chunk.get("tokens", [])):
            df[tok] = df.get(tok, 0) + 1
    return {
        tok: math.log((n - freq + 0.5) / (freq + 0.5) + 1.0) for tok, freq in df.items()
    }


def _bm25(
    query_tokens: List[str],
    doc_tokens: List[str],
    idf: Dict[str, float],
    k1: float = 1.5,
    b: float = 0.75,
    avg_l: float = 200.0,
) -> float:
    if not query_tokens or not doc_tokens:
        return 0.0
    dl = len(doc_tokens)
    tf: Dict[str, int] = {}
    for tok in doc_tokens:
        tf[tok] = tf.get(tok, 0) + 1
    score = 0.0
    for tok in query_tokens:
        if tok not in idf:
            continue
        f = tf.get(tok, 0)
        score += idf[tok] * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / avg_l))
    return score


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def add_file(path: Path, description: str = "") -> int:
    """
    Add a file to the RAG store.
    Returns number of chunks indexed.

    Supported formats:
      Code files   → AST-aware or line-based chunking
      Arrow/Parquet → schema + sample rows as text chunks
      CSV/TSV       → header + sample rows as text chunks
    """
    if not path.is_file():
        raise FileNotFoundError(f"{path} not found")

    text = _read_file_text(path)
    index = _load_index()

    # Remove stale chunks from this file
    index["chunks"] = [c for c in index["chunks"] if c.get("source") != str(path)]

    suffix = path.suffix.lower()

    if suffix == ".py":
        raw_chunks = _chunk_python(text)
    elif suffix in DATA_EXTENSIONS:
        # Data files: one chunk per logical section (schema, sample, stats)
        # Already formatted as sections by the reader — split on blank lines
        sections = re.split(r"\n{2,}", text)
        raw_chunks = [
            (i * 10 + 1, s.strip()) for i, s in enumerate(sections) if s.strip()
        ]
    else:
        raw_chunks = _chunk_lines(text)

    added = 0
    for start_line, chunk_text in raw_chunks:
        if not chunk_text.strip():
            continue
        index["chunks"].append(
            {
                "source": str(path),
                "start_line": start_line,
                "text": chunk_text,
                "tokens": _tokenize(chunk_text),
                "description": description or path.name,
                "file_type": suffix.lstrip("."),
            }
        )
        added += 1

    _save_index(index)
    return added


def add_snippet(text: str, description: str, tags: List[str] = None) -> None:
    """Add a raw text snippet directly to the store."""
    index = _load_index()
    index["chunks"].append(
        {
            "source": f"snippet:{description}",
            "start_line": 0,
            "text": text,
            "tokens": _tokenize(text),
            "description": description,
            "tags": tags or [],
            "file_type": "snippet",
        }
    )
    _save_index(index)


def query(request: str, top_k: int = 3) -> List[Dict]:
    """Return top_k most relevant chunks using BM25."""
    index = _load_index()
    chunks = index.get("chunks", [])
    if not chunks:
        return []

    query_tokens = _tokenize(request)
    idf = _compute_idf(chunks)
    avg_len = sum(len(c.get("tokens", [])) for c in chunks) / len(chunks)

    scored: List[Tuple[float, Dict]] = []
    for chunk in chunks:
        score = _bm25(query_tokens, chunk.get("tokens", []), idf, avg_l=avg_len)
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:top_k]]


def format_for_prompt(chunks: List[Dict]) -> str:
    """Format RAG chunks for injection into the Ollama prompt."""
    if not chunks:
        return ""
    lines = ["\n--- REFERENCE CONTEXT (from your indexed files) ---"]
    for chunk in chunks:
        ftype = chunk.get("file_type", "")
        label = f"[{ftype.upper()}] " if ftype and ftype != "snippet" else ""
        lines.append(
            f"\n# {label}{chunk['description']} "
            f"({chunk['source']}, line {chunk.get('start_line', '?')})"
        )
        lines.append(chunk["text"])
    lines.append("--- END REFERENCE CONTEXT ---\n")
    return "\n".join(lines)


def list_sources() -> List[str]:
    index = _load_index()
    seen: set = set()
    sources = []
    for chunk in index.get("chunks", []):
        src = chunk.get("source", "")
        if src not in seen:
            seen.add(src)
            sources.append(src)
    return sources


def clear() -> None:
    _save_index({"chunks": []})


def stats() -> Dict:
    index = _load_index()
    chunks = index.get("chunks", [])
    sources = {c.get("source") for c in chunks}
    by_type: Dict[str, int] = {}
    for c in chunks:
        ft = c.get("file_type", "unknown")
        by_type[ft] = by_type.get(ft, 0) + 1
    return {
        "total_chunks": len(chunks),
        "total_sources": len(sources),
        "index_size_kb": (
            round(INDEX_FILE.stat().st_size / 1024, 1) if INDEX_FILE.exists() else 0
        ),
        "by_type": by_type,
    }


def get_datasets_dir() -> Path:
    DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    return DATASETS_DIR


def index_datasets_dir(verbose: bool = False) -> Dict:
    """Scan ~/.droxcli/rag/datasets/ and index all supported files."""
    DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    files_indexed = chunks_added = skipped = 0

    for path in sorted(DATASETS_DIR.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            skipped += 1
            continue
        try:
            n = add_file(path, description=str(path.relative_to(DATASETS_DIR)))
            files_indexed += 1
            chunks_added += n
            if verbose:
                ftype = path.suffix.upper().lstrip(".")
                print(f"  ✓ [{ftype}] {path.relative_to(DATASETS_DIR)} ({n} chunks)")
        except Exception as exc:
            if verbose:
                print(f"  ✗ {path.name}: {exc}")
            skipped += 1

    return {
        "files_indexed": files_indexed,
        "chunks_added": chunks_added,
        "skipped": skipped,
        "datasets_dir": str(DATASETS_DIR),
    }
