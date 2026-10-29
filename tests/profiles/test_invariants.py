# tests/profiles/test_invariants.py
"""Exercise spec_invariants_for against a fake registry."""

import pytest
from types import SimpleNamespace

from mountainash_settings.profiles import (
    ParameterSpec,
    ProfileSpec,
    Profile,
    Registry,
)
from mountainash_settings.profiles.invariants import spec_invariants_for


FAKE_REGISTRY = Registry("fake_tests")
FAKE_DESC = ProfileSpec(
    name="fake",
    provider_type="fake",
    parameters=[
        ParameterSpec(name="HOST", type=str, tier="core", driver_key="host"),
    ],
)


class _FakeProfile(Profile):
    __spec__ = FAKE_DESC


FAKE_REGISTRY.register(FAKE_DESC, _FakeProfile)


# Dynamic class — pytest collects its parameterized methods:
TestFakeInvariants = spec_invariants_for(FAKE_REGISTRY)


@pytest.mark.unit
def test_invariants_class_is_renamed():
    """Sanity check on the name-mangling helper."""
    cls = spec_invariants_for(Registry("empty"))
    assert cls.__name__ == "TestSpecInvariants_empty"


@pytest.mark.parametrize("method, invalid", [
    ("test_name_matches_registry_key", {"name": "other"}),
    ("test_name_lowercase_nonempty", {"name": "Example"}),
    ("test_name_lowercase_nonempty", {"name": ""}),
    ("test_parameter_names_unique", {"parameters": [("HOST", "core"), ("HOST", "advanced")]}),
    ("test_parameter_names_uppercase", {"parameters": [("host", "core")]}),
    ("test_parameter_names_uppercase", {"parameters": [("", "core")]}),
    ("test_parameter_tiers_valid", {"parameters": [("HOST", "expert")]}),
    ("test_provider_type_not_none", {"provider_type": None}),
])
def test_generated_invariants_reject_invalid_specs(method, invalid):
    # Bypass registration's own validation: these controls must reach the
    # generated consumer check, rather than pass because an earlier guard rejects.
    def record(**changes):
        values = {"name": "example", "provider_type": "sdk",
                  "parameters": [("HOST", "core"), ("PORT", "advanced")]}
        values.update(changes)
        values["parameters"] = [SimpleNamespace(name=name, tier=tier)
                                for name, tier in values["parameters"]]
        return SimpleNamespace(**values)

    check = getattr(spec_invariants_for(Registry("enforcement"))(), method)
    check("example", record())
    with pytest.raises(AssertionError):
        check("example", record(**invalid))
