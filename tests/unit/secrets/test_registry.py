"""Unit tests for the secrets backend registry."""
from __future__ import annotations

import typing as t
from contextlib import contextmanager

import pytest

from mountainash_settings.secrets.registry import (
    register_secrets_backend,
    get_secrets_backend,
    replace_secrets_backend,
    clear_secrets_registry,
)


class _DummyBackend:
    def get(self, key: str) -> dict[str, t.Any] | None:
        return {"value": f"resolved_{key}"}

    def set(self, key: str, data: dict[str, t.Any]) -> None:
        pass

    def delete(self, key: str) -> None:
        pass

    @contextmanager
    def transaction(self, key: str):
        yield


class _OtherBackend(_DummyBackend):
    pass


@pytest.fixture(autouse=True)
def clean_registry():
    clear_secrets_registry()
    yield
    clear_secrets_registry()


@pytest.mark.unit
class TestSecretsRegistry:
    def test_register_and_retrieve(self):
        backend = _DummyBackend()
        register_secrets_backend("local", backend)
        assert get_secrets_backend("local") is backend

    def test_get_unregistered_raises_keyerror(self):
        with pytest.raises(KeyError):
            get_secrets_backend("nonexistent")

    def test_duplicate_registration_raises_valueerror(self):
        register_secrets_backend("local", _DummyBackend())
        with pytest.raises(ValueError):
            register_secrets_backend("local", _OtherBackend())

    def test_replace_overwrites_existing(self):
        register_secrets_backend("local", _DummyBackend())
        other = _OtherBackend()
        replace_secrets_backend("local", other)
        assert get_secrets_backend("local") is other

    def test_replace_unregistered_registers(self):
        backend = _DummyBackend()
        replace_secrets_backend("new_provider", backend)
        assert get_secrets_backend("new_provider") is backend

    def test_clear_removes_all(self):
        register_secrets_backend("a", _DummyBackend())
        register_secrets_backend("b", _OtherBackend())
        clear_secrets_registry()
        with pytest.raises(KeyError):
            get_secrets_backend("a")
        with pytest.raises(KeyError):
            get_secrets_backend("b")
