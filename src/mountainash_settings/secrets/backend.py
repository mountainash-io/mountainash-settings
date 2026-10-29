"""Local record store protocols."""
from __future__ import annotations

from contextlib import AbstractContextManager

import typing as t

from .records import SecretRecord

__all__ = ["SecretReader", "SecretWriter", "ClearableSecretStore"]

@t.runtime_checkable
class SecretReader(t.Protocol):
    def get(self, key: str) -> SecretRecord | None: ...


@t.runtime_checkable
class SecretWriter(SecretReader, t.Protocol):
    def set(self, key: str, data: SecretRecord) -> None: ...
    def delete(self, key: str) -> None: ...
    def transaction(self, key: str) -> AbstractContextManager[None]: ...


@t.runtime_checkable
class ClearableSecretStore(SecretWriter, t.Protocol):
    def is_cleared(self, key: str) -> bool: ...
