"""Function-scoped ownership for public and direct settings retrieval."""

import pytest

from mountainash_settings import SettingsManager


@pytest.fixture
def isolated_settings_manager(monkeypatch) -> SettingsManager:
    """Route public retrieval through the same fresh manager supplied to the test."""
    manager = SettingsManager()
    monkeypatch.setattr(
        "mountainash_settings.settings_cache.settings_functions.get_settings_manager",
        lambda: manager,
    )
    return manager
