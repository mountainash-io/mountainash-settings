# tests/unit/profiles/test_deprecation.py
"""Tests for all deprecation paths added in mountainash-settings 26.5.0.

Every test here will be DELETED in 26.6.0 along with the deprecation
shims it covers.
"""

from __future__ import annotations

import warnings

import pytest


@pytest.mark.unit
class TestModuleLevelDeprecations:
    """PEP 562 __getattr__ deprecation shims."""

    def test_profiles_profiledescriptor_warns_and_resolves(self):
        from mountainash_settings.profiles import ProfileSpec
        with pytest.warns(DeprecationWarning, match="ProfileDescriptor.*renamed.*ProfileSpec"):
            from mountainash_settings.profiles import ProfileDescriptor
        assert ProfileDescriptor is ProfileSpec

    def test_profiles_descriptorprofile_warns_and_resolves(self):
        from mountainash_settings.profiles import Profile
        with pytest.warns(DeprecationWarning, match="DescriptorProfile.*renamed.*Profile"):
            from mountainash_settings.profiles import DescriptorProfile
        assert DescriptorProfile is Profile

    def test_profiles_descriptor_invariants_for_warns_and_resolves(self):
        from mountainash_settings.profiles import spec_invariants_for
        with pytest.warns(DeprecationWarning, match="descriptor_invariants_for.*renamed.*spec_invariants_for"):
            from mountainash_settings.profiles import descriptor_invariants_for
        assert descriptor_invariants_for is spec_invariants_for

    def test_descriptor_module_profiledescriptor_warns(self):
        from mountainash_settings.profiles.spec import ProfileSpec
        with pytest.warns(DeprecationWarning, match="ProfileDescriptor.*renamed.*ProfileSpec"):
            from mountainash_settings.profiles.descriptor import ProfileDescriptor
        assert ProfileDescriptor is ProfileSpec

    def test_descriptor_module_missing_warns(self):
        from mountainash_settings.profiles.spec import Missing
        with pytest.warns(DeprecationWarning, match="_Missing.*renamed.*Missing"):
            from mountainash_settings.profiles.descriptor import _Missing
        assert _Missing is Missing

    def test_top_level_old_names_warn(self):
        from mountainash_settings import Profile, ProfileSpec, spec_invariants_for
        with pytest.warns(DeprecationWarning):
            from mountainash_settings import ProfileDescriptor
        with pytest.warns(DeprecationWarning):
            from mountainash_settings import DescriptorProfile
        with pytest.warns(DeprecationWarning):
            from mountainash_settings import descriptor_invariants_for
        assert ProfileDescriptor is ProfileSpec
        assert DescriptorProfile is Profile
        assert descriptor_invariants_for is spec_invariants_for

    def test_unknown_attribute_still_raises(self):
        from mountainash_settings import profiles
        with pytest.raises(AttributeError, match="no attribute 'NotARealName'"):
            profiles.NotARealName


@pytest.mark.unit
class TestRegisterMirrorOnNewForm:
    """The bare @register form still mirrors __spec__ to __descriptor__ during 26.5.x."""

    def test_new_form_class_has_descriptor_attribute(self):
        from mountainash_settings.profiles import (
            ParameterSpec, Profile, ProfileSpec, Registry,
        )

        reg = Registry("mirror_new_form_test")
        register = reg.decorator()

        spec = ProfileSpec(
            name="newform", provider_type="newform",
            parameters=[ParameterSpec(name="HOST", type=str, tier="core", driver_key="host")],
        )

        @register
        class NewFormProfile(Profile):
            __spec__ = spec

        # The class declared only __spec__, but the mirror sets __descriptor__ too
        assert NewFormProfile.__spec__ is spec
        assert NewFormProfile.__descriptor__ is spec

        # And instances see both
        instance = NewFormProfile(HOST="h")
        assert instance.__descriptor__ is spec
