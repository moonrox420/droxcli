"""Tests for config loading and merging."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from droxcli.config import Config, DEFAULTS, load_config, set_config_value


def _write_config(tmp_path: Path, data: dict) -> Path:
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps(data))
    return cfg


def test_load_defaults(tmp_path):
    cfg_path = tmp_path / "config.json"
    with patch("droxcli.config.CONFIG_PATH", cfg_path):
        cfg = load_config()
    assert cfg.planning_model == DEFAULTS["planning_model"]
    assert cfg.execution_model == DEFAULTS["execution_model"]
    assert cfg.temperature == DEFAULTS["temperature"]


def test_user_overrides_defaults(tmp_path):
    cfg_path = _write_config(tmp_path, {"temperature": 0.5, "ollama_timeout": 60})
    with patch("droxcli.config.CONFIG_PATH", cfg_path):
        cfg = load_config()
    assert cfg.temperature == 0.5
    assert cfg.ollama_timeout == 60
    assert cfg.planning_model == DEFAULTS["planning_model"]  # not overridden


def test_unknown_keys_ignored(tmp_path):
    cfg_path = _write_config(
        tmp_path, {"unknown_future_key": "value", "temperature": 0.1}
    )
    with patch("droxcli.config.CONFIG_PATH", cfg_path):
        cfg = load_config()
    assert cfg.temperature == 0.1
    assert not hasattr(cfg, "unknown_future_key")


def test_malformed_json_uses_defaults(tmp_path, capsys):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text("{ bad json")
    with patch("droxcli.config.CONFIG_PATH", cfg_path):
        cfg = load_config()
    assert cfg.temperature == DEFAULTS["temperature"]
    captured = capsys.readouterr()
    assert "malformed" in captured.out


def test_endpoint_auto_adds_http(tmp_path):
    cfg_path = _write_config(tmp_path, {"ollama_endpoint": "127.0.0.1:11434"})
    with patch("droxcli.config.CONFIG_PATH", cfg_path):
        cfg = load_config()
    assert cfg.ollama_endpoint.startswith("http://")


def test_set_config_value(tmp_path):
    cfg_path = _write_config(tmp_path, {})
    with patch("droxcli.config.CONFIG_PATH", cfg_path):
        set_config_value("temperature", "0.7")
        cfg = load_config()
    assert cfg.temperature == 0.7


def test_set_config_value_bool(tmp_path):
    cfg_path = _write_config(tmp_path, {})
    with patch("droxcli.config.CONFIG_PATH", cfg_path):
        set_config_value("debug_mode", "true")
        cfg = load_config()
    assert cfg.debug_mode is True


def test_set_config_value_unknown_key(tmp_path):
    cfg_path = _write_config(tmp_path, {})
    with patch("droxcli.config.CONFIG_PATH", cfg_path):
        with pytest.raises(ValueError, match="Unknown config key"):
            set_config_value("nonexistent_key", "value")
