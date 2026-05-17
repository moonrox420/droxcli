"""Tests for the RAG store."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from droxcli.rag.store import (
    _chunk_python,
    _chunk_lines,
    _tokenize,
    add_file,
    clear,
    query,
    stats,
)


def _patch_rag_dir(tmp_path: Path):
    """Context manager that redirects RAG storage to a temp directory."""
    import droxcli.rag.store as store

    return (
        patch.object(store, "INDEX_FILE", tmp_path / "index.json"),
        patch.object(store, "_INDEX_CACHE", None),
        patch.object(store, "_INDEX_MTIME", 0.0),
    )


def test_tokenize_basic():
    tokens = _tokenize("def my_function(x, y):")
    assert "def" in tokens
    assert "my_function" in tokens


def test_tokenize_filters_short():
    tokens = _tokenize("a b x = 1")
    assert "a" not in tokens
    assert "b" not in tokens


def test_chunk_lines_basic():
    source = "\n".join(f"line{i}" for i in range(100))
    chunks = _chunk_lines(source, size=50)
    assert len(chunks) == 2
    assert chunks[0][0] == 1  # start line


def test_chunk_python_splits_at_functions():
    source = "x = 1\n\ndef foo():\n    pass\n\ndef bar():\n    return 1\n"
    chunks = _chunk_python(source)
    texts = [c[1] for c in chunks]
    assert any("def foo" in t for t in texts)
    assert any("def bar" in t for t in texts)


def test_chunk_python_fallback_on_syntax_error():
    bad_source = "def broken(\n    pass"
    chunks = _chunk_python(bad_source)
    assert len(chunks) >= 1


def test_add_and_query(tmp_path):
    idx_file = tmp_path / "index.json"
    import droxcli.rag.store as store

    original_index = store.INDEX_FILE
    original_cache = store._INDEX_CACHE
    store.INDEX_FILE = idx_file
    store._INDEX_CACHE = None

    try:
        py_file = tmp_path / "utils.py"
        py_file.write_text(
            "def quicksort(arr):\n    if len(arr) <= 1:\n        return arr\n"
        )
        n = add_file(py_file, description="utils")
        assert n >= 1
        results = query("quicksort sorting algorithm")
        assert len(results) >= 1
        assert any("quicksort" in r["text"] for r in results)
    finally:
        store.INDEX_FILE = original_index
        store._INDEX_CACHE = original_cache


def test_stats_empty(tmp_path):
    import droxcli.rag.store as store

    original = store.INDEX_FILE
    store.INDEX_FILE = tmp_path / "index.json"
    store._INDEX_CACHE = None
    try:
        s = stats()
        assert s["total_chunks"] == 0
        assert s["total_sources"] == 0
    finally:
        store.INDEX_FILE = original


def test_read_csv(tmp_path):
    from droxcli.rag.store import _read_csv

    csv_file = tmp_path / "data.csv"
    csv_file.write_text("name,age,city\nAlice,30,NYC\nBob,25,LA\n")
    text = _read_csv(csv_file)
    assert "name" in text
    assert "Alice" in text
    assert "Columns" in text


def test_supported_extensions_includes_arrow():
    from droxcli.rag.store import SUPPORTED_EXTENSIONS

    assert ".arrow" in SUPPORTED_EXTENSIONS
    assert ".parquet" in SUPPORTED_EXTENSIONS
    assert ".csv" in SUPPORTED_EXTENSIONS


def test_add_csv_file(tmp_path):
    import droxcli.rag.store as store

    original = store.INDEX_FILE
    store.INDEX_FILE = tmp_path / "index.json"
    store._INDEX_CACHE = None

    csv_file = tmp_path / "sales.csv"
    csv_file.write_text("product,revenue,units\nWidgetA,1000,50\nWidgetB,2000,80\n")
    try:
        n = store.add_file(csv_file, description="sales data")
        assert n >= 1
        results = store.query("revenue sales product")
        assert len(results) >= 1
    finally:
        store.INDEX_FILE = original
        store._INDEX_CACHE = None


def test_stats_shows_by_type(tmp_path):
    import droxcli.rag.store as store

    original = store.INDEX_FILE
    store.INDEX_FILE = tmp_path / "index.json"
    store._INDEX_CACHE = None

    py_file = tmp_path / "utils.py"
    csv_file = tmp_path / "data.csv"
    py_file.write_text("def foo(): pass\n")
    csv_file.write_text("a,b\n1,2\n")
    try:
        store.add_file(py_file)
        store.add_file(csv_file)
        s = store.stats()
        assert "by_type" in s
        assert s["by_type"].get("py", 0) >= 1
        assert s["by_type"].get("csv", 0) >= 1
    finally:
        store.INDEX_FILE = original
        store._INDEX_CACHE = None
