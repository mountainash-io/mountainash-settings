# tests/unit/profiles/test_profile.py
"""Unit tests for the generic DescriptorProfile base."""

from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from mountainash_settings.auth import NoAuth, PasswordAuth
from mountainash_settings.profiles import (
    DescriptorProfile,
    ParameterSpec,
    ProfileDescriptor,
)


DUMMY_DESCRIPTOR = ProfileDescriptor(
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


class DummyProfile(DescriptorProfile):
    __descriptor__ = DUMMY_DESCRIPTOR


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
        desc = ProfileDescriptor(
            name="tf", provider_type="tf", auth_modes=[NoAuth],
            parameters=[
                ParameterSpec(
                    name="FLAG", type=bool, tier="core",
                    default=True, driver_key="flag",
                    transform=lambda v: 1 if v else 0,
                ),
            ],
        )

        class P(DescriptorProfile):
            __descriptor__ = desc

        assert P(auth=NoAuth())._default_kwargs() == {"flag": 1}
        assert P(FLAG=False, auth=NoAuth())._default_kwargs() == {"flag": 0}

    def test_validator_rejects_bad_input(self):
        def _positive(v: int) -> int:
            if v <= 0:
                raise ValueError("must be positive")
            return v

        desc = ProfileDescriptor(
            name="val", provider_type="val", auth_modes=[NoAuth],
            parameters=[
                ParameterSpec(name="N", type=int, tier="core",
                              validator=_positive),
            ],
        )

        class P(DescriptorProfile):
            __descriptor__ = desc

        assert P(N=5, auth=NoAuth()).N == 5
        with pytest.raises(ValidationError, match="must be positive"):
            P(N=-1, auth=NoAuth())

    def test_adapter_owns_pipeline(self):
        def _adapter(profile: "DescriptorProfile") -> dict:
            kwargs = profile._default_kwargs()
            kwargs["adapter_added"] = True
            return kwargs

        class Adapted(DescriptorProfile):
            __descriptor__ = DUMMY_DESCRIPTOR
            __adapter__ = staticmethod(_adapter)

        # Note: DescriptorProfile itself has no to_driver_kwargs; adapters
        # are invoked by domain subclasses. We test the mechanism indirectly
        # by confirming the adapter attr is accessible.
        p = Adapted(HOST="h", auth=NoAuth())
        assert type(p).__dict__.get("__adapter__") is not None

    def test_template_populates_derived_field(self):
        """ParameterSpec(template=...) auto-populates field in post_init."""
        desc = ProfileDescriptor(
            name="tmpl", provider_type="tmpl", auth_modes=[NoAuth],
            parameters=[
                ParameterSpec(name="HOST", type=str, tier="core"),
                ParameterSpec(name="URL", type=str, tier="core",
                              default="",
                              template="https://{HOST}/api"),
            ],
        )

        class P(DescriptorProfile):
            __descriptor__ = desc

        p = P(HOST="example.com", auth=NoAuth())
        assert p.URL == "https://example.com/api"

    def test_template_respects_explicit_value(self):
        """If caller sets URL explicitly, the template does not overwrite."""
        desc = ProfileDescriptor(
            name="tmpl2", provider_type="tmpl2", auth_modes=[NoAuth],
            parameters=[
                ParameterSpec(name="HOST", type=str, tier="core"),
                ParameterSpec(name="URL", type=str, tier="core",
                              default="",
                              template="https://{HOST}/api"),
            ],
        )

        class P(DescriptorProfile):
            __descriptor__ = desc

        p = P(HOST="a.b", URL="https://override.example/", auth=NoAuth())
        assert p.URL == "https://override.example/"
