"""Tests for the REPL session state."""

from droxcli.session import Session, Turn


def test_initial_state():
    s = Session()
    assert s.history == []
    assert s.last_turn_id is None
    assert s.last_files == []


def test_record_turn():
    s = Session()
    s.record("fix the bug", turn_id=1, files_changed=["auth.py"], summary="Turn #1")
    assert len(s.history) == 1
    assert s.last_turn_id == 1
    assert s.last_files == ["auth.py"]


def test_record_multiple_turns():
    s = Session()
    s.record("fix login", turn_id=1, files_changed=["auth.py"])
    s.record("add tests", turn_id=2, files_changed=["test_auth.py"])
    assert s.last_turn_id == 2
    assert s.last_files == ["test_auth.py"]
    assert len(s.history) == 2


def test_last_context_block_empty():
    s = Session()
    assert s.last_context_block() == ""


def test_last_context_block_with_history():
    s = Session()
    s.record("fix login", turn_id=1, files_changed=["auth.py"])
    ctx = s.last_context_block()
    assert "fix login" in ctx
    assert "auth.py" in ctx


def test_enrich_followup():
    s = Session()
    s.record("fix the bug", turn_id=1, files_changed=["utils.py"])
    # "that" is a follow-up signal
    enriched = s.enrich("add tests for that")
    assert "utils.py" in enriched
    assert "add tests for that" in enriched


def test_enrich_standalone():
    s = Session()
    s.record("fix the bug", turn_id=1, files_changed=["utils.py"])
    # Long specific request — not a follow-up
    enriched = s.enrich("refactor the entire database layer in db.py to use async")
    assert enriched == "refactor the entire database layer in db.py to use async"


def test_clear():
    s = Session()
    s.record("fix login", turn_id=1, files_changed=["auth.py"])
    s.clear()
    assert s.history == []
    assert s.last_turn_id is None
    assert s.last_files == []
