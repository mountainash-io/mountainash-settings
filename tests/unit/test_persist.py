"""Tests for MountainAshBaseSettings.persist() and persist_key()."""
from __future__ import annotations

import typing as t
from contextlib import contextmanager

import pytest
from pydantic import Field

from mountainash_settings import MountainAshBaseSettings
from mountainash_settings.secrets.registry import (
    clear_secrets_registry,
    register_secrets_backend,
)


class _InMemoryBackend:
    def __init__(self):
        self._store: dict[str, dict[str, t.Any]] = {}
        self._cleared: set[str] = set()

    def get(self, key: str) -> dict[str, t.Any] | None:
        return self._store.get(key)

    def set(self, key: str, data: dict[str, t.Any]) -> None:
        self._store[key] = data
        self._cleared.discard(key)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)
        self._cleared.add(key)

    def is_cleared(self, key: str) -> bool:
        return key in self._cleared

    @contextmanager
    def transaction(self, key: str):
        yield


class _TestSettings(MountainAshBaseSettings):
    TOKEN: str = Field(default=None)
    REFRESH: str = Field(default=None)


@pytest.fixture(autouse=True)
def clean():
    clear_secrets_registry()
    yield
    clear_secrets_registry()


@pytest.mark.unit
class TestPersistKey:
    def test_key_from_class_name_only(self):
        instance = _TestSettings()
        key = instance.persist_key()
        assert key == "_testsettings"

    def test_key_from_env_prefix_and_class(self):
        instance = _TestSettings(env_prefix="STRAVA_")
        key = instance.persist_key()
        assert key == "strava._testsettings"


@pytest.mark.unit
class TestPersist:
    def test_persist_writes_to_backend(self):
        backend = _InMemoryBackend()
        register_secrets_backend("memory", backend)
        instance = _TestSettings(
            TOKEN="old",
            env_prefix="APP_",
            secrets_provider="memory",
        )
        instance.persist({"TOKEN": "new_token", "REFRESH": "new_refresh"})
        stored = backend.get("app._testsettings")
        assert stored["TOKEN"] == "new_token"
        assert stored["REFRESH"] == "new_refresh"

    def test_persist_updates_in_memory(self):
        backend = _InMemoryBackend()
        register_secrets_backend("memory", backend)
        instance = _TestSettings(
            TOKEN="old",
            env_prefix="APP_",
            secrets_provider="memory",
        )
        instance.persist({"TOKEN": "updated"})
        assert instance.TOKEN == "updated"

    def test_persist_with_explicit_key(self):
        backend = _InMemoryBackend()
        register_secrets_backend("memory", backend)
        instance = _TestSettings(
            TOKEN="old",
            secrets_provider="memory",
        )
        instance.persist({"TOKEN": "val"}, key="custom.key")
        assert backend.get("custom.key") == {"TOKEN": "val"}

    def test_persist_raises_without_secrets_provider(self):
        instance = _TestSettings(TOKEN="old")
        with pytest.raises(ValueError, match="secrets_provider"):
            instance.persist({"TOKEN": "new"})
