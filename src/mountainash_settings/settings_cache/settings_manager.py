"""Sole public owner for private structural settings contexts."""
from __future__ import annotations

from dataclasses import dataclass, field
from threading import Event, Lock, get_ident
from typing import Any

from pydantic_settings import BaseSettings

from ..settings_parameters import SettingsParameters
from ._context import _SettingsContext, _StructuralKey


@dataclass
class _InitializationCell:
    context: _SettingsContext
    initializer_thread: int
    completed: bool = False
    event: Event = field(default_factory=Event)


class SettingsManager:
    """Materialize isolated settings from one owned source context per key."""

    def __init__(self) -> None:
        self._contexts: dict[_StructuralKey, _InitializationCell] = {}
        self._lock = Lock()

    @staticmethod
    def _request(
        settings_parameters: SettingsParameters, reinitialise: bool,
    ) -> tuple[_StructuralKey, dict[str, Any], bool]:
        if not isinstance(settings_parameters, SettingsParameters):
            raise ValueError("settings_parameters must be an instance of SettingsParameters.")
        key = _StructuralKey.from_parameters(settings_parameters)
        from ..settings.base_settings import MountainAshBaseSettings
        if (
            not issubclass(key.settings_class, MountainAshBaseSettings)
            and key.settings_class.__init__ is not BaseSettings.__init__
        ):
            raise ValueError("Cached retrieval requires BaseSettings.__init__ for plain settings classes")
        return key, settings_parameters.get_cache_runtime_kwargs(key.settings_class), reinitialise

    def _get_completed_context(self, key: _StructuralKey) -> _SettingsContext:
        with self._lock:
            cell = self._contexts.get(key)
            if cell is None or not cell.completed:
                raise ValueError("Cached settings context is not initialised.")
            return cell.context

    def get_settings_object(
        self, settings_parameters: SettingsParameters, *, reinitialise: bool = False,
    ) -> BaseSettings:
        """Materialize only from an already-complete structural source capture."""
        key, runtime, reinitialise = self._request(settings_parameters, reinitialise)
        return self._get_completed_context(key).materialize(runtime, reinitialise=reinitialise)

    def is_initialised(self, settings_parameters: SettingsParameters) -> bool:
        """Whether source capture, rather than a particular result, is complete."""
        if not isinstance(settings_parameters, SettingsParameters):
            return False
        try:
            key = _StructuralKey.from_parameters(settings_parameters)
        except ValueError:
            return False
        with self._lock:
            cell = self._contexts.get(key)
            return cell is not None and cell.completed

    def get_or_create_settings(
        self, settings_parameters: SettingsParameters, *, reinitialise: bool = False,
    ) -> BaseSettings:
        """Capture sources once, then validate one complete isolated invocation."""
        key, runtime, reinitialise = self._request(settings_parameters, reinitialise)
        owner = False
        with self._lock:
            cell = self._contexts.get(key)
            if cell is None:
                cell = _InitializationCell(_SettingsContext(key), get_ident(), event=Event())
                self._contexts[key] = cell
                owner = True
            elif not cell.completed:
                if cell.initializer_thread == get_ident():
                    raise ValueError("Cached settings source capture is reentrant.")
                waiter = cell.event
            else:
                waiter = None
        if not owner and waiter is not None:
            waiter.wait()
            with self._lock:
                current = self._contexts.get(key)
                if current is not cell or current is None or not current.completed:
                    raise ValueError("Cached settings source capture failed.")
                cell = current
        if owner:
            try:
                cell.context.capture()
            except BaseException:
                with self._lock:
                    if self._contexts.get(key) is cell:
                        self._contexts.pop(key, None)
                    cell.event.set()
                raise
            with self._lock:
                cell.completed = True
                cell.event.set()
        return cell.context.materialize(runtime, reinitialise=reinitialise)
