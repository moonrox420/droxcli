"""
Project-wide file scanner.

Walks the working directory, excludes noisy folders, and returns
a JSON-serialisable context dict for the planning and execution models.

Optimisations:
  - Parallel file reads via ThreadPoolExecutor
  - Token-budget guard: switches to relevance-reduced view on large repos
  - Dependency graph extracted from imports for smarter context selection
"""

from __future__ import annotations

import fnmatch
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Set

DEFAULT_IGNORE: Set[str] = {
    ".venv",
    "venv",
    "__pycache__",
    ".git",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    "dist",
    "build",
    "*.egg-info",
    "*.lock",
    "*.sqlite3",
    "*.db",
    "*.env",
    "*.pem",
    "*.key",
    "*.crt",
    "*.log",
    ".DS_Store",
    "Thumbs.db",
}

SOURCE_EXTENSIONS: Set[str] = {
    ".py",
    ".js",
    ".ts",
    ".go",
    ".yaml",
    ".yml",
    ".toml",
    ".json",
    ".md",
    ".sh",
    ".bash",
}

MAX_PAYLOAD_BYTES = 2 * 1024 * 1024  # 2 MiB — switch to reduced view above this


def _should_ignore(path: Path, rules: Set[str]) -> bool:
    path_str = str(path).lower()
    parts = {p.lower() for p in path.parts}
    for rule in rules:
        if fnmatch.fnmatch(path_str, rule.lower()):
            return True
        if rule.lower() in parts:
            return True
    return False


def _read_file(p: Path) -> str:
    with p.open("r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _extract_imports(fname: str, text: str) -> List[str]:
    """Extract top-level module names from import statements."""
    imports: List[str] = []
    if fname.endswith(".py"):
        for line in text.splitlines():
            m = re.match(r"^\s*(?:import|from)\s+([\w.]+)", line)
            if m:
                imports.append(m.group(1).split(".")[0])
    elif fname.endswith((".js", ".ts")):
        for line in text.splitlines():
            m = re.search(r'require\(["\']([^"\']+)["\']\)', line) or re.search(
                r'from\s+["\']([^"\']+)["\']', line
            )
            if m:
                imports.append(m.group(1).split("/")[0].lstrip("@"))
    return imports


def _build_dep_graph(contents: Dict[str, str]) -> Dict[str, List[str]]:
    return {fname: _extract_imports(fname, text) for fname, text in contents.items()}


def _reduce_context(
    contents: Dict[str, str],
    target_files: List[str],
    dep_graph: Dict[str, List[str]],
) -> Dict[str, str]:
    """
    When the repo is too large, keep only:
      1. Target files (always)
      2. Files that import any target module
      3. Files that are imported by any target file
    """
    reduced: Dict[str, str] = {}
    targets = set(target_files)

    # Target module names (without extension/path)
    target_mods = {Path(t).stem for t in targets}

    for fname, text in contents.items():
        if fname in targets:
            reduced[fname] = text
            continue
        # This file imports something from a target → include it
        if any(mod in dep_graph.get(fname, []) for mod in target_mods):
            reduced[fname] = text
            continue
        # A target file imports this file → include it
        fname_mod = Path(fname).stem
        for t in targets:
            if fname_mod in dep_graph.get(t, []):
                reduced[fname] = text
                break

    return reduced


def count_files(root_path: Path) -> int:
    """Return number of source files under root_path, excluding ignored dirs."""
    count = 0
    for dirpath, dirnames, filenames in os.walk(root_path):
        dirnames[:] = [
            d
            for d in dirnames
            if not _should_ignore(
                Path(dirpath, d).relative_to(root_path), DEFAULT_IGNORE
            )
        ]
        for fname in filenames:
            full = Path(dirpath, fname)
            rel = full.relative_to(root_path)
            if not _should_ignore(rel, DEFAULT_IGNORE):
                if full.suffix.lower() in SOURCE_EXTENSIONS:
                    count += 1
    return count


def scan_project(
    root: Optional[Path] = None,
    extra_ignore: Optional[List[str]] = None,
    max_workers: Optional[int] = None,
    target_files: Optional[List[str]] = None,
) -> Dict:
    """
    Walk *root* and return a JSON-serialisable context dict.

    Returns:
        files    – sorted list of relative file paths
        contents – {relative_path: file_text}
        imports  – {relative_path: [imported_module_names]}
        root     – str(root)
        reduced  – True if payload was trimmed to fit the token budget
    """
    if root is None:
        root = Path.cwd()
    if max_workers is None:
        max_workers = min(os.cpu_count() or 4, 8)  # cap at 8 for safety

    ignore_rules: Set[str] = set(DEFAULT_IGNORE)
    if extra_ignore:
        ignore_rules.update(extra_ignore)

    # Collect candidates
    candidates: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d
            for d in dirnames
            if not _should_ignore(Path(dirpath, d).relative_to(root), ignore_rules)
        ]
        for fname in filenames:
            full = Path(dirpath, fname)
            rel = full.relative_to(root)
            if not _should_ignore(rel, ignore_rules):
                if full.suffix.lower() in SOURCE_EXTENSIONS:
                    candidates.append(full)

    # Parallel read
    content_map: Dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_read_file, p): p for p in candidates}
        for fut in as_completed(futures):
            p = futures[fut]
            try:
                rel = str(p.relative_to(root)).replace("\\", "/")
                content_map[rel] = fut.result()
            except Exception as exc:
                print(f"⚠  Could not read {p}: {exc}")

    dep_graph = _build_dep_graph(content_map)

    # Token-budget guard
    total_bytes = sum(len(v.encode()) for v in content_map.values())
    reduced = False
    if total_bytes > MAX_PAYLOAD_BYTES:
        reduced = True
        content_map = _reduce_context(content_map, target_files or [], dep_graph)
        dep_graph = _build_dep_graph(content_map)

    return {
        "files": sorted(content_map.keys()),
        "contents": content_map,
        "imports": dep_graph,
        "root": str(root),
        "reduced": reduced,
    }
