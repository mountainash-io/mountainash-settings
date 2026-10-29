"""AppSettings clock and initialization-local timestamp defaults."""

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
import os
from threading import Lock
from typing import Iterator, Literal

_DEFAULTS: ContextVar[dict[str, str] | None] = ContextVar("app_timestamp_defaults", default=None)
_process_lock = Lock()
_process_pid = os.getpid()
_process_value: tuple[int, datetime] | None = None


def _now() -> datetime:
    return datetime.now()


def _after_fork() -> None:
    """A child owns a new clock and must never acquire an inherited lock."""
    global _process_lock, _process_pid, _process_value
    _process_lock = Lock()
    _process_pid = os.getpid()
    _process_value = None


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_after_fork)


def _process_instant() -> datetime:
    global _process_value
    pid = os.getpid()
    if pid != _process_pid:
        _after_fork()
    with _process_lock:
        if _process_value is None or _process_value[0] != pid:
            _process_value = (pid, _now())
        return _process_value[1]


def capture(scope: Literal["context", "process"]) -> dict[str, str]:
    if scope not in ("context", "process"):
        raise ValueError("Invalid RUN_TIMESTAMP_SCOPE: expected 'context' or 'process'")
    instant = _now() if scope == "context" else _process_instant()
    return {"RUNDATE": instant.strftime("%Y%m%d"), "RUNTIME": instant.strftime("%H%M%S")}


@contextmanager
def default_scope(values: dict[str, str]) -> Iterator[None]:
    token = _DEFAULTS.set(values)
    try:
        yield
    finally:
        _DEFAULTS.reset(token)


def _default(name: str) -> str:
    values = _DEFAULTS.get()
    if values is None:
        raise RuntimeError("AppSettings timestamp defaults require construction scope")
    return values[name]


def run_date() -> str:
    return _default("RUNDATE")


def run_time() -> str:
    return _default("RUNTIME")
