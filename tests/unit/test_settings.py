"""Unit tests for configuration."""

import pytest

from little_warren.config import get_settings

pytestmark = pytest.mark.unit


def test_defaults():
    settings = get_settings()
    assert settings.env == "dev"
    assert settings.default_interval == "1d"


def test_env_override(monkeypatch):
    monkeypatch.setenv("LW_DEFAULT_INTERVAL", "1wk")
    settings = get_settings()
    assert settings.default_interval == "1wk"
