# src/mountainash_settings/profiles/__init__.py
"""Declarative settings profiles — descriptor + registry + generic base.

Lifted and generalized from mountainash-data's 2026-04-15 settings-registry
refactor. See design spec:
``docs/superpowers/specs/2026-04-16-profiles-promotion-design.md``.
"""

from __future__ import annotations

from .descriptor import MISSING, ParameterSpec, ProfileDescriptor

__all__ = ["MISSING", "ParameterSpec", "ProfileDescriptor"]
