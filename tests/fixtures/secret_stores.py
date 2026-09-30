"""Deterministic secret references shared by settings and resolver tests."""

from contextlib import nullcontext

import pytest


class _ResolvedRecord(dict):
    """Return a recognizable value for any requested record field."""

    def __init__(self, key: str):
        super().__init__()
        self._key = key

    def __contains__(self, field):
        return True

    def __getitem__(self, field):
        return f"resolved_{self._key}/{field}"

    def __len__(self):
        return 2  # Avoid the resolver's single-value extraction path.


class ResolvingSecretStore:
    """Stateless store double; every read returns a new deterministic record."""

    def get(self, key: str) -> dict | None:
        return _ResolvedRecord(key)

    def set(self, key: str, data: dict) -> None:
        pass

    def delete(self, key: str) -> None:
        pass

    def transaction(self, key: str):
        return nullcontext()


@pytest.fixture
def resolving_secret_store():
    return ResolvingSecretStore()
