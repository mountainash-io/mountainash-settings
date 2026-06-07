"""SecretsBackend protocol — pluggable credential storage with read/write."""
from __future__ import annotations

import typing as t

if t.TYPE_CHECKING:
    from contextlib import AbstractContextManager

__all__ = ["SecretsBackend", "ClearableBackend"]


@t.runtime_checkable
class SecretsBackend(t.Protocol):
    """Protocol for credential storage backends.

    Values are structured dicts — one key maps to one credential set.
    Backends handle locking internally.
    """

    def get(self, key: str) -> dict[str, t.Any] | None: ...
    def set(self, key: str, data: dict[str, t.Any]) -> None: ...
    def delete(self, key: str) -> None: ...
    def transaction(self, key: str) -> AbstractContextManager[None]: ...


@t.runtime_checkable
class ClearableBackend(SecretsBackend, t.Protocol):
    """Extension for backends that track intentional deletion."""

    def is_cleared(self, key: str) -> bool: ...
