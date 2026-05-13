# src/mountainash_settings/profiles/__init__.py
"""Declarative settings profiles — descriptor + registry + generic base."""

from __future__ import annotations

from .descriptor import ProfileDescriptor
from .invariants import spec_invariants_for
from .profile import Profile
from .registry import Registry
from .spec import MISSING, ParameterSpec, ProfileSpec

# Compatibility alias — removed in Task 9 which adds deprecation __getattr__
DescriptorProfile = Profile

__all__ = [
    "MISSING",
    "DescriptorProfile",
    "ParameterSpec",
    "Profile",
    "ProfileDescriptor",
    "ProfileSpec",
    "Registry",
    "spec_invariants_for",
]
