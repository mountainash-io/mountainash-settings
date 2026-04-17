# tests/unit/profiles/test_invariants.py
"""Exercise descriptor_invariants_for against a fake registry."""

import pytest

from mountainash_settings.auth import NoAuth
from mountainash_settings.profiles import (
    ParameterSpec,
    ProfileDescriptor,
    Registry,
)
from mountainash_settings.profiles.invariants import descriptor_invariants_for


FAKE_REGISTRY = Registry("fake_tests")
FAKE_DESC = ProfileDescriptor(
    name="fake",
    provider_type="fake",
    parameters=[
        ParameterSpec(name="HOST", type=str, tier="core", driver_key="host"),
    ],
    auth_modes=[NoAuth],
)


class _FakeProfile:
    pass


FAKE_REGISTRY.register(FAKE_DESC, _FakeProfile)  # type: ignore[arg-type]


# Dynamic class — pytest collects its parameterized methods:
TestFakeInvariants = descriptor_invariants_for(FAKE_REGISTRY)


@pytest.mark.unit
def test_invariants_class_is_renamed():
    """Sanity check on the name-mangling helper."""
    cls = descriptor_invariants_for(Registry("empty"))
    assert cls.__name__ == "TestDescriptorInvariants_empty"
