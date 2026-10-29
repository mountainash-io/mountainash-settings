"""Subprocess setup shared by executable documentation tests."""

import os

import pytest


@pytest.fixture
def example_environment() -> dict[str, str]:
    """Keep host configuration out of examples; retain subprocess coverage settings."""
    environment = {
        key: value for key, value in os.environ.items()
        if key.upper() not in {
            "APP_NAME", "ENV", "DEBUG", "DATABASE", "BATCH_SIZE", "OPTIONS",
            "LOG_PATH", "LOG_PATH_TEMPLATE", "HOST", "PORT", "USERNAME",
            "PASSWORD", "LOCAL_NOTE", "CONNECT_TIMEOUT", "URL", "TAGS",
            "PYTHONPATH", "PYTHONHOME", "PYTHONOPTIMIZE", "PYTEST_ADDOPTS",
            "PYTEST_PLUGINS",
        } and not key.upper().startswith("REPORT_")
    }
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    return environment
