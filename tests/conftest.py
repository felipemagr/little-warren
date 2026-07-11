"""Shared test configuration."""

import pytest

from little_warren.config import get_settings


@pytest.fixture(autouse=True)
def reset_settings_cache():
    """Clear the settings cache so env-var overrides in tests take effect."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
