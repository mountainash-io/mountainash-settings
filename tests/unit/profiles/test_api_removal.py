"""The 0.1 profile API has no deprecation fallback paths."""
import importlib

import pytest

from mountainash_settings.profiles import Profile, ProfileSpec, Registry


@pytest.mark.parametrize("module", ["mountainash_settings", "mountainash_settings.profiles"])
@pytest.mark.parametrize("name", ["ProfileDescriptor", "DescriptorProfile", "descriptor_invariants_for", "_Missing"])
def test_removed_exports(module, name):
    assert not hasattr(importlib.import_module(module), name)


def test_descriptor_module_is_removed():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("mountainash_settings.profiles.descriptor")


def test_registration_has_only_canonical_surface():
    registry = Registry("canonical")
    spec = ProfileSpec(name="example", provider_type="example", parameters=[])

    @registry.decorator()
    class Example(Profile):
        __spec__ = spec

    assert registry.get_spec("example") is spec
    registry.specs.clear()
    assert registry.get_settings_class("example") is Example
    assert not hasattr(Example, "__descriptor__")
    assert not hasattr(Example, "backend")
    assert not hasattr(Profile, "__adapter__")
    assert not hasattr(registry, "descriptors")
    assert not hasattr(registry, "get_descriptor")
    with pytest.raises(TypeError):
        registry.decorator()(spec)

    class Child(Example):
        pass

    with pytest.raises(TypeError):
        registry.decorator()(Child)


def test_invalid_spec_fails_directly():
    with pytest.raises(TypeError):
        class Invalid(Profile):
            __spec__ = object()


def test_non_profile_registration_is_rejected():
    registry = Registry("canonical")
    with pytest.raises(TypeError):
        registry.register(ProfileSpec(name="x", provider_type="x", parameters=[]), object)
