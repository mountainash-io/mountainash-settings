"""Tests for SecretsBackend and ClearableBackend protocols."""
from __future__ import annotations

import typing as t
from contextlib import contextmanager

import pytest

from mountainash_settings.secrets.backend import ClearableBackend, SecretsBackend


class _MinimalBackend:
    def get(self, key: str) -> dict[str, t.Any] | None:
        return None

    def set(self, key: str, data: dict[str, t.Any]) -> None:
        pass

    def delete(self, key: str) -> None:
        pass

    @contextmanager
    def transaction(self, key: str):
        yield


class _ClearableImpl(_MinimalBackend):
    def is_cleared(self, key: str) -> bool:
        return False


@pytest.mark.unit
class TestSecretsBackendProtocol:
    def test_minimal_backend_satisfies_protocol(self):
        backend = _MinimalBackend()
        assert isinstance(backend, SecretsBackend)

    def test_clearable_satisfies_both_protocols(self):
        backend = _ClearableImpl()
        assert isinstance(backend, SecretsBackend)
        assert isinstance(backend, ClearableBackend)

    def test_minimal_backend_is_not_clearable(self):
        backend = _MinimalBackend()
        assert not isinstance(backend, ClearableBackend)
