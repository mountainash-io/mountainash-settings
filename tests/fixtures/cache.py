"""Function-scoped ownership for public and direct settings retrieval."""

import pytest
from threading import Event

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


@pytest.fixture
def capture_signals(monkeypatch):
    """Observe the real initialization-cell wait without replacing exclusion."""
    entered, release, waiting = Event(), Event(), Event()

    class ObservedEvent(Event):
        def wait(self, timeout=None):
            waiting.set()
            return super().wait(timeout)

    monkeypatch.setattr("mountainash_settings.settings_cache.settings_manager.Event", ObservedEvent)
    try:
        yield entered, release, waiting
    finally:
        release.set()
