"""Tests for natural language intent parsing."""

import pytest
from droxcli.intent.parser import parse_natural_language
from droxcli.intent.models import Intent


def test_fix_action_from_broken():
    intent = parse_natural_language("the login is broken, fix it")
    assert intent.action == "fix"


def test_fix_action_from_debug():
    intent = parse_natural_language("debug utils.py")
    assert intent.action == "fix"


def test_create_action():
    intent = parse_natural_language("create a new config parser in config.py")
    assert intent.action == "create"


def test_refactor_action():
    intent = parse_natural_language("optimize the quicksort in utils.py")
    assert intent.action == "refactor"


def test_file_extraction():
    intent = parse_natural_language("fix the bug in auth/login.py")
    assert "auth/login.py" in intent.target_files


def test_multiple_files():
    intent = parse_natural_language("update models.py and views.py")
    assert len(intent.target_files) == 2


def test_language_detection_python():
    intent = parse_natural_language("add type hints to utils.py")
    assert intent.language == "python"


def test_language_detection_yaml():
    intent = parse_natural_language("fix the config in docker-compose.yml")
    assert intent.language == "yaml"


def test_dry_run_detection():
    intent = parse_natural_language("dry-run: show what would change in db.py")
    assert intent.dry_run is True


def test_tests_needed_detection():
    intent = parse_natural_language("add unit tests to the parser module")
    assert intent.tests_needed is True


def test_no_file_mentioned():
    intent = parse_natural_language("clean up the codebase")
    assert intent.target_files == []


def test_never_raises():
    """Parser must not raise on any input."""
    for text in ["", "   ", "!@#$%", "fix", "create delete rename"]:
        result = parse_natural_language(text)
        assert isinstance(result, Intent)


def test_broken_pattern_fix():
    intent = parse_natural_language(
        "utils.py is returning wrong results for edge cases"
    )
    assert intent.action == "fix"


def test_delete_action():
    intent = parse_natural_language("remove the legacy API endpoints from routes.py")
    assert intent.action == "delete"
