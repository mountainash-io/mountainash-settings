# tests/unit/profiles/test_registry.py
"""Unit tests for the Registry class."""

import warnings

import pytest

from fixtures.auth_stubs import StubNoAuth as NoAuth
from mountainash_settings.profiles.descriptor import ProfileDescriptor
from mountainash_settings.profiles.registry import Registry


def _make_desc(name: str) -> ProfileDescriptor:
    return ProfileDescriptor(
        name=name, provider_type=name, parameters=[], auth_modes=[NoAuth],
    )


@pytest.mark.unit
class TestRegistry:
    def test_register_inserts(self):
        reg = Registry("test")
        desc = _make_desc("foo")

        register = reg.decorator()

        @register(desc)
        class Foo:
            pass

        assert "foo" in reg
        assert reg.get_descriptor("foo") is desc
        assert reg.get_settings_class("foo") is Foo

    def test_duplicate_raises(self):
        reg = Registry("test")
        desc1 = _make_desc("dup")
        desc2 = _make_desc("dup")
        register = reg.decorator()

        @register(desc1)
        class First:
            pass

        with pytest.raises(ValueError, match="already registered"):
            @register(desc2)
            class Second:
                pass

    def test_get_descriptor_unknown_hints(self):
        reg = Registry("storage")
        desc = _make_desc("s3")
        register = reg.decorator()

        @register(desc)
        class S3:
            pass

        with pytest.raises(KeyError, match="Known: s3"):
            reg.get_descriptor("not_a_real_one")

    def test_get_settings_class_unknown_hints(self):
        reg = Registry("storage")
        with pytest.raises(KeyError, match="Known: <none>"):
            reg.get_settings_class("nope")

    def test_duplicate_does_not_pollute_classes(self):
        reg = Registry("test")
        desc1 = _make_desc("inv")
        desc2 = _make_desc("inv")
        register = reg.decorator()

        @register(desc1)
        class First:
            pass

        with pytest.raises(ValueError):
            @register(desc2)
            class Second:
                pass

        assert reg.get_settings_class("inv") is First
        assert reg.get_descriptor("inv") is desc1

    def test_snapshot_and_reset(self):
        reg = Registry("t")
        desc = _make_desc("x")
        reg.decorator()(desc)(type("X", (), {}))
        snap = reg._snapshot_for_tests()

        reg.decorator()(_make_desc("y"))(type("Y", (), {}))
        assert "y" in reg

        reg._reset_for_tests(*snap)
        assert "y" not in reg
        assert "x" in reg

    def test_descriptors_view_is_copy(self):
        reg = Registry("t")
        desc = _make_desc("a")
        reg.decorator()(desc)(type("A", (), {}))

        view = reg.descriptors
        view["fake"] = desc  # mutating the view does not affect the registry
        assert "fake" not in reg


from mountainash_settings.profiles import Profile, ProfileSpec, ParameterSpec


class _CustomSpec(ProfileSpec):
    pass


class _CustomProfile(Profile):
    pass


@pytest.mark.unit
class TestRegistryConstraints:
    def test_default_construction_unchanged(self):
        """Registry() with no constraints still works (backwards compatible)."""
        reg = Registry("default_test")
        assert reg.name == "default_test"

    def test_spec_type_accepts_matching(self):
        """spec_type=_CustomSpec accepts _CustomSpec instances."""
        reg = Registry("custom_spec_test", spec_type=_CustomSpec)
        spec = _CustomSpec(
            name="custom", provider_type="custom",
            parameters=[ParameterSpec(name="HOST", type=str, tier="core", driver_key="host")],
            auth_modes=[NoAuth],
        )
        class P(Profile):
            __spec__ = spec
        reg.register(spec, P)  # should not raise
        assert "custom" in reg

    def test_spec_type_rejects_plain_profilespec(self):
        """spec_type=_CustomSpec rejects a plain ProfileSpec instance."""
        reg = Registry("reject_test", spec_type=_CustomSpec)
        plain = ProfileSpec(
            name="plain", provider_type="plain",
            parameters=[ParameterSpec(name="HOST", type=str, tier="core", driver_key="host")],
            auth_modes=[NoAuth],
        )
        class P(Profile):
            __spec__ = plain
        with pytest.raises(TypeError, match="spec_type"):
            reg.register(plain, P)

    def test_profile_type_accepts_matching(self):
        """profile_type=_CustomProfile accepts _CustomProfile subclasses."""
        reg = Registry("profile_match", profile_type=_CustomProfile)
        spec = ProfileSpec(
            name="cm", provider_type="cm",
            parameters=[ParameterSpec(name="HOST", type=str, tier="core", driver_key="host")],
            auth_modes=[NoAuth],
        )
        class P(_CustomProfile):
            __spec__ = spec
        reg.register(spec, P)
        assert "cm" in reg

    def test_profile_type_rejects_non_subclass(self):
        """profile_type=_CustomProfile rejects a plain Profile subclass."""
        reg = Registry("profile_reject", profile_type=_CustomProfile)
        spec = ProfileSpec(
            name="pr", provider_type="pr",
            parameters=[ParameterSpec(name="HOST", type=str, tier="core", driver_key="host")],
            auth_modes=[NoAuth],
        )
        class P(Profile):
            __spec__ = spec
        with pytest.raises(TypeError, match="profile_type"):
            reg.register(spec, P)


@pytest.mark.unit
class TestBareRegisterDecorator:
    """Tests for the new argument-free @register form."""

    def test_bare_register_reads_spec_from_class(self):
        reg = Registry("bare_test")
        register = reg.decorator()

        spec = ProfileSpec(
            name="bare", provider_type="bare",
            parameters=[ParameterSpec(name="HOST", type=str, tier="core", driver_key="host")],
            auth_modes=[NoAuth],
        )

        @register
        class BareProfile(Profile):
            __spec__ = spec

        assert "bare" in reg
        assert reg.get_settings_class("bare") is BareProfile

    def test_bare_register_raises_when_spec_missing(self):
        reg = Registry("bare_missing")
        register = reg.decorator()

        with pytest.raises(TypeError, match="__spec__"):
            @register
            class NoSpecProfile(Profile):
                pass  # no __spec__ declared

    def test_old_form_emits_deprecation_warning(self):
        reg = Registry("old_form")
        register = reg.decorator()

        spec = ProfileSpec(
            name="old", provider_type="old",
            parameters=[ParameterSpec(name="HOST", type=str, tier="core", driver_key="host")],
            auth_modes=[NoAuth],
        )

        with pytest.warns(DeprecationWarning, match="@register\\(spec\\).*deprecated"):
            @register(spec)
            class OldFormProfile(Profile):
                __spec__ = spec

        assert "old" in reg

    def test_old_form_drift_catch(self):
        """@register(SPEC_A) on a class with __spec__ = SPEC_B raises."""
        reg = Registry("drift_test")
        register = reg.decorator()

        spec_a = ProfileSpec(
            name="a", provider_type="a",
            parameters=[ParameterSpec(name="HOST", type=str, tier="core", driver_key="host")],
            auth_modes=[NoAuth],
        )
        spec_b = ProfileSpec(
            name="b", provider_type="b",
            parameters=[ParameterSpec(name="HOST", type=str, tier="core", driver_key="host")],
            auth_modes=[NoAuth],
        )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            with pytest.raises(TypeError, match="disagree"):
                @register(spec_a)
                class DriftProfile(Profile):
                    __spec__ = spec_b


@pytest.mark.unit
class TestSpecDescriptorMirror:
    """Tests for the __spec__ → __descriptor__ deprecation mirror.

    During 26.5.x, Registry.register() sets both attributes to the same
    object so downstream code reading cls.__descriptor__ keeps working.
    This whole class is deleted in 26.6.0.
    """

    def test_bare_register_mirrors_spec_to_descriptor(self):
        reg = Registry("mirror_test")
        register = reg.decorator()

        spec = ProfileSpec(
            name="mirror", provider_type="mirror",
            parameters=[ParameterSpec(name="HOST", type=str, tier="core", driver_key="host")],
            auth_modes=[NoAuth],
        )

        @register
        class MirrorProfile(Profile):
            __spec__ = spec

        # Both class-level attributes resolve to the same object
        assert MirrorProfile.__spec__ is spec
        assert MirrorProfile.__descriptor__ is spec
        assert MirrorProfile.__descriptor__ is MirrorProfile.__spec__

        # And on instances too
        instance = MirrorProfile(HOST="h", auth=NoAuth())
        assert instance.__descriptor__ is spec
        assert instance.__spec__ is spec
