"""Deterministic local records; callers coordinate compound operations explicitly."""
from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager

from .keys import _segments
from .records import SecretRecord, _own_record


class MemorySecretStore:
    def __init__(self) -> None:
        self._data: dict[str, SecretRecord] = {}
        self._cleared: set[str] = set()
        self._locks: dict[str, threading.RLock] = {}
        self._guard = threading.Lock()

    def get(self, key: str) -> SecretRecord | None:
        _segments(key)
        record = self._data.get(key)
        return None if record is None else _own_record(record)

    def set(self, key: str, data: SecretRecord) -> None:
        _segments(key)
        owned = _own_record(data)
        self._data[key] = owned
        self._cleared.discard(key)

    def delete(self, key: str) -> None:
        _segments(key)
        self._cleared.add(key)
        self._data.pop(key, None)

    def is_cleared(self, key: str) -> bool:
        _segments(key)
        return key in self._cleared

    @contextmanager
    def transaction(self, key: str) -> Iterator[None]:
        _segments(key)
        with self._guard:
            lock = self._locks.get(key)
            if lock is None:
                lock = threading.RLock()
                self._locks[key] = lock
        with lock:
            yield
