"""Total normalization of settings keyword arguments."""

from collections.abc import Iterable, Mapping
from typing import Any

KwargItems = tuple[tuple[str, Any], ...]
KwargInput = Mapping[str, Any] | Iterable[tuple[str, Any]] | None


class SettingsKwargsHandler:
    """Normalize kwargs and unwrap the optional ``kwargs`` mapping."""

    @classmethod
    def format_kwargs_dict(cls, p_kwargs: KwargInput = None) -> dict[str, Any]:
        """Return a fresh mapping; malformed inputs raise a value-free TypeError."""
        data = None
        try:
            data = {} if p_kwargs is None else dict(p_kwargs)
        except (TypeError, ValueError):
            pass
        if data is None:
            raise TypeError("Invalid kwargs mapping")
        nested = data.get("kwargs", data)
        if not isinstance(nested, Mapping) or any(not isinstance(key, str) for key in nested):
            raise TypeError("Invalid kwargs mapping")
        return dict(nested)

    @classmethod
    def format_kwargs_tuple(cls, p_kwargs: KwargInput = None) -> KwargItems:
        """Return normalized items in deterministic key order."""
        return tuple(sorted(cls.format_kwargs_dict(p_kwargs).items()))

    @staticmethod
    def merge_kwargs(kwargs1: KwargInput = None, kwargs2: KwargInput = None) -> dict[str, Any]:
        """Merge normalized inputs with the second input taking precedence."""
        return {
            **SettingsKwargsHandler.format_kwargs_dict(kwargs1),
            **SettingsKwargsHandler.format_kwargs_dict(kwargs2),
        }
