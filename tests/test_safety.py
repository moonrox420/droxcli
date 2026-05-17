"""Tests for the safety layer."""

from pathlib import Path
from droxcli.safety import Result
from droxcli.safety.security import analyse_code
from droxcli.safety.linter import run_black, run_ruff


def test_result_namedtuple():
    r = Result(ok=True, message="all good", detail=None)
    assert r.ok is True
    assert r.message == "all good"
    assert r.detail is None


def test_analyse_code_clean():
    patches = [{"file": "utils.py", "new": "def add(a, b):\n    return a + b\n"}]
    result = analyse_code(patches)
    assert result.ok is True


def test_analyse_code_hardcoded_aws_key():
    patches = [{"file": "config.py", "new": "AWS_KEY = 'AKIAIOSFODNN7EXAMPLE'\n"}]
    result = analyse_code(patches)
    assert result.ok is False
    assert "CRITICAL" in (result.detail or "")


def test_analyse_code_shell_injection():
    patches = [
        {
            "file": "run.py",
            "new": "import subprocess\nsubprocess.run(cmd, shell=True)\n",
        }
    ]
    result = analyse_code(patches)
    assert result.ok is False


def test_analyse_code_empty_patches():
    result = analyse_code([])
    assert result.ok is True


def test_run_black_no_files():
    result = run_black([])
    assert result.ok is True


def test_run_ruff_no_files():
    result = run_ruff([])
    assert result.ok is True
