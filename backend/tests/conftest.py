"""Shared fixtures: every test reads the environment afresh."""

import pytest

from kisan import config


@pytest.fixture(autouse=True)
def fresh_settings():
    """get_settings() is cached for the app's lifetime; a test that changes the environment
    must not see, or leave behind, another test's settings."""
    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()
