"""Canonical registry registration, isolation and domain constraints."""
import pytest

from mountainash_settings.profiles import Profile, ProfileSpec, Registry


def make_profile(name, *, spec_type=ProfileSpec, profile_type=Profile):
    spec = spec_type(name=name, provider_type=name, parameters=[])
    return type(name.title(), (profile_type,), {"__spec__": spec})


def test_registration_lookup_and_duplicate_isolation():
    registry = Registry("test")
    first = make_profile("foo")
    assert registry.decorator()(first) is first
    assert len(registry) == 1
    assert "foo" in registry
    assert registry.get_spec("foo") is first.__spec__
    assert registry.get_settings_class("foo") is first
    with pytest.raises(ValueError, match="already registered"):
        registry.decorator()(make_profile("foo"))
    assert registry.get_settings_class("foo") is first
    assert registry.get_spec("foo") is first.__spec__


def test_unknown_lookup_lists_known_names():
    registry = Registry("storage")
    with pytest.raises(KeyError, match="Known: <none>"):
        registry.get_settings_class("missing")
    registry.decorator()(make_profile("s3"))
    with pytest.raises(KeyError, match="Known: s3"):
        registry.get_spec("missing")
    with pytest.raises(KeyError, match="Known: s3"):
        registry.get_settings_class("missing")


def test_snapshot_and_defensive_view():
    registry = Registry("snapshot")
    registry.decorator()(make_profile("x"))
    snapshot = registry._snapshot_for_tests()
    registry.decorator()(make_profile("y"))
    assert "y" in registry
    registry._reset_for_tests(*snapshot)
    assert "y" not in registry
    assert "x" in registry
    registry.specs.clear()
    assert len(registry) == 1


class CustomSpec(ProfileSpec):
    pass


class CustomProfile(Profile):
    pass


def test_spec_constraint_accepts_matching_and_rejects_plain():
    registry = Registry("custom", spec_type=CustomSpec)
    custom = make_profile("custom", spec_type=CustomSpec)
    registry.register(custom.__spec__, custom)
    assert "custom" in registry
    plain = make_profile("plain")
    with pytest.raises(TypeError, match="spec_type"):
        registry.register(plain.__spec__, plain)
    assert "plain" not in registry


def test_profile_constraint_accepts_matching_and_rejects_plain():
    registry = Registry("custom", profile_type=CustomProfile)
    custom = make_profile("custom", profile_type=CustomProfile)
    registry.register(custom.__spec__, custom)
    assert "custom" in registry
    plain = make_profile("plain")
    with pytest.raises(TypeError, match="profile_type"):
        registry.register(plain.__spec__, plain)
    assert "plain" not in registry


def test_missing_spec_and_old_decorator_form_fail():
    registry = Registry("missing")
    with pytest.raises(TypeError, match="__spec__"):
        registry.decorator()(CustomProfile)
    with pytest.raises(TypeError, match="Profile subclass"):
        registry.decorator()(ProfileSpec(name="old", provider_type="old", parameters=[]))
