"""Borrowed clearable-store view; lifetime remains with the application."""
from __future__ import annotations

from contextlib import AbstractContextManager

from .backend import ClearableSecretStore
from .errors import SecretCapabilityError, _raise_clean
from .keys import _segments
from .records import SecretRecord


class NamespacedSecretStore:
    def __init__(self, inner: ClearableSecretStore, prefix: str) -> None:
        _segments(prefix)
        if not isinstance(inner, ClearableSecretStore):
            _raise_clean(SecretCapabilityError("Clearable local storage is required"))
        self._inner = inner
        self._prefix = prefix

    def _key(self, key: str) -> str:
        _segments(key)
        return f"{self._prefix}.{key}"

    def get(self, key: str) -> SecretRecord | None:
        return self._inner.get(self._key(key))

    def set(self, key: str, data: SecretRecord) -> None:
        self._inner.set(self._key(key), data)

    def delete(self, key: str) -> None:
        self._inner.delete(self._key(key))

    def is_cleared(self, key: str) -> bool:
        return self._inner.is_cleared(self._key(key))

    def transaction(self, key: str) -> AbstractContextManager[None]:
        return self._inner.transaction(self._key(key))
