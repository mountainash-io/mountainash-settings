"""Public MRO-walking helper for class-level attribute lookup.

Used by Profile to resolve __spec__ (and __descriptor__ during deprecation)
and __adapter__. Exposed as public API so downstream consumers can use it
for their own class-level dunder lookups without depending on private symbols.
"""

from __future__ import annotations

import typing as t

__all__ = ["lookup_class_var"]


def lookup_class_var(cls: type, name: str) -> t.Any | None:
    """Walk cls.__mro__ and return the first __dict__ value for `name`.

    Returns None when the attribute is not found anywhere in the MRO.

    Args:
        cls: The class to start from.
        name: The attribute name to look up.

    Returns:
        The first value found in any class's __dict__ along the MRO,
        or None if no class in the MRO defines `name`.
    """
    for klass in cls.__mro__:
        if name in klass.__dict__:
            return klass.__dict__[name]
    return None
