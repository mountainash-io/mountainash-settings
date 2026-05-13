# src/mountainash_settings/profiles/__init__.py
"""Declarative settings profiles — spec + registry + generic base."""

from __future__ import annotations

import typing as t
import warnings

from .lookup import lookup_class_var
from .invariants import spec_invariants_for
from .profile import Profile
from .registry import Registry
from .spec import MISSING, Missing, ParameterSpec, ProfileSpec

__all__ = [
    "MISSING",
    "Missing",
    "ParameterSpec",
    "Profile",
    "ProfileSpec",
    "Registry",
    "lookup_class_var",
    "spec_invariants_for",
]


_DEPRECATED: dict[str, tuple[str, t.Any]] = {
    "ProfileDescriptor":         ("ProfileSpec", ProfileSpec),
    "DescriptorProfile":         ("Profile", Profile),
    "descriptor_invariants_for": ("spec_invariants_for", spec_invariants_for),
}


def __getattr__(name: str) -> t.Any:
    """PEP 562 module __getattr__ for deprecated top-level names.

    Resolves the pre-26.5.0 names to their renamed equivalents and emits a
    ``DeprecationWarning`` per access. Removed in 26.6.0.
    """
    if name in _DEPRECATED:
        new_name, obj = _DEPRECATED[name]
        warnings.warn(
            f"{name!r} is renamed to {new_name!r} in mountainash-settings "
            f"26.5.0. The old name will be removed in 26.6.0.",
            DeprecationWarning, stacklevel=2,
        )
        return obj
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
