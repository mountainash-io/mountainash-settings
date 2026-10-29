"""AppSettings-specific declarations and deterministic clock setup."""

from datetime import datetime

import pytest
from pydantic import Field

from mountainash_settings.settings.app.app_settings import AppSettings


class PandasAppSettings(AppSettings):
    """Application settings with the additional dataframe framework field."""

    PANDERA_DATAFRAME_FRAMEWORK: str = Field(default="pandas")


@pytest.fixture
def pandas_app_settings():
    return PandasAppSettings()


@pytest.fixture
def app_clock(monkeypatch):
    """Control the live clock; each construction samples its current instant."""
    from mountainash_settings.settings.app import _timestamps

    moments = [datetime(2031, 12, 31, 23, 59, 59)]
    monkeypatch.setattr(_timestamps, "_now", lambda: moments.pop(0) if len(moments) > 1 else moments[0])
    return moments
