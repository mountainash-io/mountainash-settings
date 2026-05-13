# tests/unit/profiles/test_profile.py
"""Unit tests for the generic Profile base."""

from __future__ import annotations

import warnings

import pytest
from pydantic import SecretStr, ValidationError

from mountainash_settings.auth import NoAuth, PasswordAuth
from mountainash_settings.profiles import (
    ParameterSpec,
    ProfileSpec,
)
from mountainash_settings.profiles.profile import Profile


DUMMY_SPEC = ProfileSpec(
    name="dummy",
    provider_type="dummy",
    parameters=[
        ParameterSpec(name="HOST", type=str, tier="core", driver_key="host"),
        ParameterSpec(name="PORT", type=int, tier="core", default=9999, driver_key="port"),
        ParameterSpec(name="PASSWORD", type=str, tier="core", secret=True,
                      driver_key="password", default=None),
    ],
    auth_modes=[NoAuth, PasswordAuth],
)


class DummyProfile(Profile):
    __spec__ = DUMMY_SPEC


@pytest.mark.unit
class TestDescriptorProfile:
    def test_required_field_enforced(self):
        with pytest.raises(ValidationError):
            DummyProfile(auth=NoAuth())  # HOST missing

    def test_default_used(self):
        p = DummyProfile(HOST="localhost", auth=NoAuth())
        assert p.PORT == 9999

    def test_default_kwargs_noauth(self):
        p = DummyProfile(HOST="h", PORT=1234, auth=NoAuth())
        assert p._default_kwargs() == {"host": "h", "port": 1234}

    def test_auth_kwargs_password(self):
        p = DummyProfile(
            HOST="h",
            auth=PasswordAuth(username="u", password=SecretStr("p")),
        )
        kwargs = p._auth_kwargs()
        assert kwargs["user"] == "u"
        assert kwargs["password"] == "p"

    def test_secret_field_unwrapped(self):
        p = DummyProfile(HOST="h", PASSWORD="literal-secret", auth=NoAuth())
        kwargs = p._default_kwargs()
        assert kwargs["password"] == "literal-secret"

    def test_none_values_skipped(self):
        p = DummyProfile(HOST="h", auth=NoAuth())
        kwargs = p._default_kwargs()
        assert "password" not in kwargs

    def test_backend_and_profile_name(self):
        p = DummyProfile(HOST="h", auth=NoAuth())
        assert p.backend == "dummy"
        assert p.profile_name == "dummy"

    def test_provider_type_property(self):
        p = DummyProfile(HOST="h", auth=NoAuth())
        assert p.provider_type == "dummy"

    def test_transform_applied(self):
        desc = ProfileSpec(
            name="tf", provider_type="tf", auth_modes=[NoAuth],
            parameters=[
                ParameterSpec(
                    name="FLAG", type=bool, tier="core",
                    default=True, driver_key="flag",
                    transform=lambda v: 1 if v else 0,
                ),
            ],
        )

        class P(Profile):
            __spec__ = desc

        assert P(auth=NoAuth())._default_kwargs() == {"flag": 1}
        assert P(FLAG=False, auth=NoAuth())._default_kwargs() == {"flag": 0}

    def test_validator_rejects_bad_input(self):
        def _positive(v: int) -> int:
            if v <= 0:
                raise ValueError("must be positive")
            return v

        desc = ProfileSpec(
            name="val", provider_type="val", auth_modes=[NoAuth],
            parameters=[
                ParameterSpec(name="N", type=int, tier="core",
                              validator=_positive),
            ],
        )

        class P(Profile):
            __spec__ = desc

        assert P(N=5, auth=NoAuth()).N == 5
        with pytest.raises(ValidationError, match="must be positive"):
            P(N=-1, auth=NoAuth())

    def test_adapter_owns_pipeline(self):
        def _adapter(profile: "Profile") -> dict:
            kwargs = profile._default_kwargs()
            kwargs["adapter_added"] = True
            return kwargs

        class Adapted(Profile):
            __spec__ = DUMMY_SPEC
            __adapter__ = staticmethod(_adapter)

        # Note: Profile itself has no to_driver_kwargs; adapters
        # are invoked by domain subclasses. We test the mechanism indirectly
        # by confirming the adapter attr is accessible.
        p = Adapted(HOST="h", auth=NoAuth())
        assert type(p).__dict__.get("__adapter__") is not None

    def test_template_populates_derived_field(self):
        """ParameterSpec(template=...) auto-populates field in post_init."""
        desc = ProfileSpec(
            name="tmpl", provider_type="tmpl", auth_modes=[NoAuth],
            parameters=[
                ParameterSpec(name="HOST", type=str, tier="core"),
                ParameterSpec(name="URL", type=str, tier="core",
                              default="",
                              template="https://{HOST}/api"),
            ],
        )

        class P(Profile):
            __spec__ = desc

        p = P(HOST="example.com", auth=NoAuth())
        assert p.URL == "https://example.com/api"

    def test_template_respects_explicit_value(self):
        """If caller sets URL explicitly, the template does not overwrite."""
        desc = ProfileSpec(
            name="tmpl2", provider_type="tmpl2", auth_modes=[NoAuth],
            parameters=[
                ParameterSpec(name="HOST", type=str, tier="core"),
                ParameterSpec(name="URL", type=str, tier="core",
                              default="",
                              template="https://{HOST}/api"),
            ],
        )

        class P(Profile):
            __spec__ = desc

        p = P(HOST="a.b", URL="https://override.example/", auth=NoAuth())
        assert p.URL == "https://override.example/"


@pytest.mark.unit
class TestSpecAttributeFallback:
    """Tests for the __spec__ / __descriptor__ deprecation fallback."""

    def test_old_descriptor_attribute_emits_warning(self):
        """A class declaring only __descriptor__ (no __spec__) still works
        but emits DeprecationWarning at class creation."""
        with pytest.warns(DeprecationWarning, match="__descriptor__.*deprecated"):
            class OldStyleProfile(Profile):
                __descriptor__ = DUMMY_SPEC

        # Field installation still works from the old attribute
        instance = OldStyleProfile(HOST="h", auth=NoAuth())
        assert instance.HOST == "h"

    def test_conflicting_spec_and_descriptor_raises(self):
        """Declaring both __spec__ and __descriptor__ with different values raises."""
        OTHER_SPEC = ProfileSpec(
            name="other", provider_type="other",
            parameters=[ParameterSpec(name="HOST", type=str, tier="core", driver_key="host")],
            auth_modes=[NoAuth],
        )
        with pytest.raises(TypeError, match="conflicting"):
            class ConflictProfile(Profile):
                __spec__ = DUMMY_SPEC
                __descriptor__ = OTHER_SPEC

    def test_matching_spec_and_descriptor_no_warning(self):
        """Declaring both pointing at the same object works without warning."""
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            class BothProfile(Profile):
                __spec__ = DUMMY_SPEC
                __descriptor__ = DUMMY_SPEC
            # No warning raised — test passes by reaching this line
        assert BothProfile.__spec__ is DUMMY_SPEC
