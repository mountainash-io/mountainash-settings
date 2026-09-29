"""Native Pydantic fields carrying profile emission options."""

from __future__ import annotations

import typing as t
from dataclasses import dataclass
from enum import Enum

from pydantic import Field
from pydantic_core import PydanticUndefined

__all__ = ["ProfileField"]


class _Omitted(Enum):
    VALUE = 0


_OMITTED = _Omitted.VALUE


@dataclass(frozen=True)
class _ProfileOptions:
    driver_key: str | tuple[tuple[t.Hashable, str], ...] | None | _Omitted
    tier: t.Literal["core", "advanced"]
    transform: t.Callable[[t.Any], t.Any] | None
    template: str | None
    supplied: frozenset[str]


def _profile_options(
    *, driver_key: t.Any = _OMITTED, tier: t.Any = _OMITTED,
    transform: t.Any = _OMITTED, template: t.Any = _OMITTED,
) -> _ProfileOptions:
    supplied = frozenset(
        key for key, value in locals().items() if value is not _OMITTED
    )
    if tier is _OMITTED:
        tier = "core"
    if tier not in ("core", "advanced"):
        raise TypeError("ProfileField tier must be core or advanced")
    if transform is _OMITTED:
        transform = None
    if transform is not None and not callable(transform):
        raise TypeError("ProfileField transform must be callable or None")
    if template is _OMITTED:
        template = None
    if template is not None and not isinstance(template, str):
        raise TypeError("ProfileField template must be a string or None")
    if isinstance(driver_key, dict):
        if not all(isinstance(key, str) for key in driver_key.values()):
            raise TypeError("ProfileField driver_key mapping values must be strings")
        driver_key = tuple(driver_key.items())
    elif driver_key is not _OMITTED and driver_key is not None and not isinstance(driver_key, str):
        raise TypeError("ProfileField driver_key must be a string, target mapping or None")
    return _ProfileOptions(driver_key, tier, transform, template, supplied)


def ProfileField(
    default: t.Any = PydanticUndefined, *,
    driver_key: t.Any = _OMITTED, tier: t.Any = _OMITTED,
    transform: t.Any = _OMITTED, template: t.Any = _OMITTED,
    **field_kwargs: t.Any,
) -> t.Any:
    """Declare a Pydantic field with optional profile emission/derivation rules.

    Omitted ``driver_key`` follows the class convention; explicit ``None``
    excludes the field. Other keyword arguments are passed to Pydantic's Field.
    Native inheritance/redeclaration governs all field metadata.
    """
    options = _profile_options(
        driver_key=driver_key, tier=tier, transform=transform, template=template,
    )
    info = Field(default=default, **field_kwargs)
    info.metadata.append(options)
    return info
