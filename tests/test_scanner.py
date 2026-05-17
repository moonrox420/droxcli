"""Tests for the project file scanner."""

import tempfile
from pathlib import Path

from droxcli.context.scanner import count_files, scan_project


def _make_tree(root: Path) -> None:
    (root / "main.py").write_text("print('hello')")
    (root / "utils.py").write_text("def add(a, b): return a + b")
    sub = root / "subpkg"
    sub.mkdir()
    (sub / "__init__.py").write_text("")
    (sub / "helper.py").write_text("pass")
    venv = root / ".venv"
    venv.mkdir()
    (venv / "site.py").write_text("# venv")
    pycache = root / "__pycache__"
    pycache.mkdir()
    (pycache / "main.cpython-311.pyc").write_bytes(b"")


def test_scan_returns_dict():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_tree(root)
        result = scan_project(root=root)
    assert "files" in result
    assert "contents" in result
    assert "imports" in result
    assert "root" in result


def test_scan_excludes_venv():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_tree(root)
        result = scan_project(root=root)
    assert not any(".venv" in f for f in result["files"])


def test_scan_excludes_pycache():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_tree(root)
        result = scan_project(root=root)
    assert not any("__pycache__" in f for f in result["files"])


def test_scan_finds_python_files():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_tree(root)
        result = scan_project(root=root)
    py_files = [f for f in result["files"] if f.endswith(".py")]
    assert len(py_files) >= 4  # main, utils, subpkg/__init__, subpkg/helper


def test_scan_contents_not_empty():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "app.py").write_text("x = 1")
        result = scan_project(root=root)
    assert result["contents"]["app.py"] == "x = 1"


def test_count_files_excludes_venv():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_tree(root)
        count = count_files(root)
    assert count == 4  # main, utils, subpkg/__init__, subpkg/helper (not .venv/site.py)


def test_scan_target_files_prioritised():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_tree(root)
        result = scan_project(root=root, target_files=["main.py"])
    assert "main.py" in result["contents"]


def test_scan_uses_forward_slashes():
    """File paths in results use / even on Windows."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        sub = root / "pkg"
        sub.mkdir()
        (sub / "mod.py").write_text("pass")
        result = scan_project(root=root)
    assert all("\\" not in f for f in result["files"])
