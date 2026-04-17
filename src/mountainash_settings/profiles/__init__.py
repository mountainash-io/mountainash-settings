# src/mountainash_settings/profiles/__init__.py
"""Declarative settings profiles — descriptor + registry + generic base."""

from __future__ import annotations

from .descriptor import MISSING, ParameterSpec, ProfileDescriptor
from .invariants import descriptor_invariants_for
from .profile import DescriptorProfile
from .registry import Registry

__all__ = [
    "MISSING",
    "DescriptorProfile",
    "ParameterSpec",
    "ProfileDescriptor",
    "Registry",
    "descriptor_invariants_for",
]
