"""Explicit source capability required by cached settings retrieval."""
from __future__ import annotations

from abc import abstractmethod
from typing import Any

from pydantic_settings import PydanticBaseSettingsSource


class CacheableSettingsSource(PydanticBaseSettingsSource):
    """A source whose captured state can be projected without source I/O.

    Cached retrieval invokes :meth:`capture` once during structural-context
    initialization.  Every subsequent invocation calls :meth:`project` with
    detached value trees and must return terminal candidate values; projectors
    must not read external state or synthesize unresolved references.
    """

    @abstractmethod
    def capture(self) -> dict[str, Any]:
        """Capture this source's structural source-form values once."""

    @staticmethod
    @abstractmethod
    def project(
        owned_resolved_snapshot: dict[str, Any],
        owned_current_state: dict[str, Any],
        owned_sources_data: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """Project terminal values for one materialization without I/O."""
