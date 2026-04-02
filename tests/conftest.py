"""
Centralized pytest configuration and fixtures.

This module imports all fixtures from the fixtures package and makes them
available to all tests. It also configures pytest markers and session-level
settings.
"""

import pytest

# Import all settings classes for test use
from fixtures.settings_classes import (
    MockBaseSettings,
    MockSettings,
    TestSettings,
    TemplateTestSettings,
    MultiFieldTestSettings,
    MinimalSettings
)

# Import all fixtures from fixture modules
# Pytest automatically discovers fixtures when imported
from fixtures.config_files import *
from fixtures.parameters import *
from fixtures.instances import *


# Configure custom pytest markers
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line("markers", "unit: marks tests as unit tests")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "performance: marks tests as performance tests")
    config.addinivalue_line("markers", "slow: marks tests as slow running")
    config.addinivalue_line("markers", "edge_case: marks tests covering edge cases")
    config.addinivalue_line("markers", "parametrize: marks parametrized tests")


# Session-level configuration
@pytest.fixture(scope="session", autouse=True)
def session_setup():
    """
    Session-level setup and teardown.

    This runs once at the start of the test session and once at the end.
    """
    # Setup: runs before all tests
    print("\n=== Starting test session ===")

    yield

    # Teardown: runs after all tests
    print("\n=== Test session complete ===")


# Additional helper fixtures
@pytest.fixture
def isolated_cache():
    """
    Provides an isolated cache environment for tests.

    Note: This doesn't fully clear the global LRU cache, but uses
    unique parameter combinations to ensure test isolation.
    """
    from mountainash_settings import SettingsManager

    # Create a fresh manager instance
    manager = SettingsManager()
    yield manager

    # Cleanup: clear the cache for this manager
    manager.settings_object_cache.clear()
