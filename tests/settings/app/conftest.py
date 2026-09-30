"""AppSettings-specific declarations and deterministic clock setup."""

from datetime import datetime
from unittest.mock import patch

import pytest
from pydantic import Field

from mountainash_settings.settings.app.app_settings import AppSettings


class PandasAppSettings(AppSettings):
    """Application settings with the additional dataframe framework field."""

    PANDERA_DATAFRAME_FRAMEWORK: str = Field(default="pandas")


@pytest.fixture
def pandas_app_settings():
    return PandasAppSettings()


@pytest.fixture(autouse=True)
def fixed_app_datetime():
    """Keep AppSettings clock fields predictable within this directory."""
    with patch("mountainash_settings.settings.app.app_settings.datetime") as clock:
        clock.now.return_value = datetime(2024, 1, 15, 14, 30, 45)
        yield clock
