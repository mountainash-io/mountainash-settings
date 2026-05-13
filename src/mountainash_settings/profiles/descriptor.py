# src/mountainash_settings/profiles/descriptor.py
"""Compatibility shim for the pre-26.5.0 module location.

The canonical home for ``ProfileSpec``, ``Missing``, ``MISSING``, and
``ParameterSpec`` is :mod:`mountainash_settings.profiles.spec`. This module
re-exports ``MISSING`` and ``ParameterSpec`` (whose names have not changed)
and intercepts the renamed symbols ``ProfileDescriptor`` and ``_Missing``
via PEP 562 module-level ``__getattr__`` so existing imports keep working
with a ``DeprecationWarning``.

Removed in 26.6.0.

``BackendDescriptor`` is intentionally NOT aliased here — it is owned by
the ``mountainash-data`` package, not by ``mountainash-settings``. Its
compatibility shim lives in ``mountainash-data``'s own ``descriptor.py``.
"""

from __future__ import annotations

import typing as t
import warnings

# Re-export unchanged-name symbols transparently for callers that did
# ``from mountainash_settings.profiles.descriptor import MISSING, ParameterSpec``.
from .spec import MISSING, ParameterSpec  # noqa: F401

__all__ = ["MISSING", "ParameterSpec"]
# Note: ProfileDescriptor and _Missing are NOT in __all__ — they resolve via
# PEP 562 __getattr__ with DeprecationWarning. Excluding them from __all__
# prevents `from mountainash_settings.profiles.descriptor import *` from
# silently pulling in deprecated names.


def __getattr__(name: str) -> t.Any:
    """PEP 562 module __getattr__ for deprecated symbols.

    Resolves ``ProfileDescriptor`` to ``ProfileSpec`` and ``_Missing`` to
    ``Missing``. Each lookup emits a ``DeprecationWarning`` naming the
    new symbol and the 26.6.0 removal version.
    """
    if name == "ProfileDescriptor":
        from .spec import ProfileSpec
        warnings.warn(
            "'ProfileDescriptor' is renamed to 'ProfileSpec' in "
            "mountainash-settings 26.5.0. The old name will be removed "
            "in 26.6.0. Import from mountainash_settings instead.",
            DeprecationWarning, stacklevel=2,
        )
        return ProfileSpec
    if name == "_Missing":
        from .spec import Missing
        warnings.warn(
            "'_Missing' is renamed to 'Missing' (now public) in "
            "mountainash-settings 26.5.0. The old name will be removed "
            "in 26.6.0. Import from mountainash_settings instead.",
            DeprecationWarning, stacklevel=2,
        )
        return Missing
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
