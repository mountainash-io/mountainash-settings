# tests/unit/profiles/test_profile.py
"""Unit tests for the generic Profile base."""

from __future__ import annotations

import warnings
from enum import Enum

import pytest
from pydantic import SecretStr, ValidationError

from mountainash_settings import SettingsManager, SettingsParameters
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
)


class DummyProfile(Profile):
    __spec__ = DUMMY_SPEC


@pytest.mark.unit
class TestProfile:
    def test_required_field_enforced(self):
        with pytest.raises(ValidationError):
            DummyProfile()  # HOST missing

    def test_default_used(self):
        p = DummyProfile(HOST="localhost")
        assert p.PORT == 9999

    def test_default_kwargs(self):
        p = DummyProfile(HOST="h", PORT=1234)
        assert p._default_kwargs() == {"host": "h", "port": 1234}

    def test_secret_field_unwrapped(self):
        p = DummyProfile(HOST="h", PASSWORD="literal-secret")
        kwargs = p._default_kwargs()
        assert kwargs["password"] == "literal-secret"

    def test_none_values_skipped(self):
        p = DummyProfile(HOST="h")
        kwargs = p._default_kwargs()
        assert "password" not in kwargs

    def test_backend_and_profile_name(self):
        p = DummyProfile(HOST="h")
        assert p.backend == "dummy"
        assert p.profile_name == "dummy"

    def test_provider_type_property(self):
        p = DummyProfile(HOST="h")
        assert p.provider_type == "dummy"

    def test_transform_applied(self):
        desc = ProfileSpec(
            name="tf", provider_type="tf",
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

        assert P()._default_kwargs() == {"flag": 1}
        assert P(FLAG=False)._default_kwargs() == {"flag": 0}

    def test_validator_rejects_bad_input(self):
        def _positive(v: int) -> int:
            if v <= 0:
                raise ValueError("must be positive")
            return v

        desc = ProfileSpec(
            name="val", provider_type="val",
            parameters=[
                ParameterSpec(name="N", type=int, tier="core",
                              validator=_positive),
            ],
        )

        class P(Profile):
            __spec__ = desc

        assert P(N=5).N == 5
        with pytest.raises(ValidationError, match="must be positive"):
            P(N=-1)

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
        p = Adapted(HOST="h")
        assert type(p).__dict__.get("__adapter__") is not None

    def test_template_populates_derived_field(self):
        """ParameterSpec(template=...) auto-populates field in post_init."""
        desc = ProfileSpec(
            name="tmpl", provider_type="tmpl",
            parameters=[
                ParameterSpec(name="HOST", type=str, tier="core"),
                ParameterSpec(name="URL", type=str, tier="core",
                              default="",
                              template="https://{HOST}/api"),
            ],
        )

        class P(Profile):
            __spec__ = desc

        p = P(HOST="example.com")
        assert p.URL == "https://example.com/api"

    def test_template_respects_explicit_value(self):
        """If caller sets URL explicitly, the template does not overwrite."""
        desc = ProfileSpec(
            name="tmpl2", provider_type="tmpl2",
            parameters=[
                ParameterSpec(name="HOST", type=str, tier="core"),
                ParameterSpec(name="URL", type=str, tier="core",
                              default="",
                              template="https://{HOST}/api"),
            ],
        )

        class P(Profile):
            __spec__ = desc

        p = P(HOST="a.b", URL="https://override.example/")
        assert p.URL == "https://override.example/"


@pytest.mark.unit
class TestValidatedTemplateDerivation:
    """MAS-SEC-005 (M6): a template-derived value must obey the same
    declared Pydantic assignment contract as an equivalent explicit value --
    coercion, validators, and SecretStr wrapping all apply. Today's
    ``Profile.post_init`` assigns the formatted string via
    ``object.__setattr__``, bypassing validation entirely, so these are red
    until Task 2's rewrite lands (see the M6 plan's decision checkpoint,
    2026-09-25)."""

    def test_invalid_derived_value_is_rejected_like_an_explicit_one(self):
        def _even(v: int) -> int:
            if v % 2:
                raise ValueError("must be even")
            return v

        spec = ProfileSpec(
            name="derived-validator", provider_type="derived-validator",
            parameters=[
                ParameterSpec(name="BASE", type=int, tier="core", default=3),
                ParameterSpec(
                    name="DOUBLED", type=int, tier="core", default=0,
                    validator=_even, template="{BASE}",
                ),
            ],
        )

        class P(Profile):
            __spec__ = spec

        # An equivalent explicit assignment is already rejected today.
        with pytest.raises(ValidationError, match="must be even"):
            P(DOUBLED=3)

        # The template-derived value must be rejected the same way, not
        # silently stored raw and unvalidated.
        with pytest.raises(ValidationError, match="must be even"):
            P(BASE=3)

    def test_derived_value_is_coerced_and_transformed_like_an_explicit_one(self):
        spec = ProfileSpec(
            name="derived-transform", provider_type="derived-transform",
            parameters=[
                ParameterSpec(name="COUNT", type=int, tier="core", default=2),
                ParameterSpec(
                    name="DOUBLED", type=int, tier="core", default=0,
                    driver_key="doubled", template="{COUNT}",
                    transform=lambda v: v * 2,
                ),
            ],
        )

        class P(Profile):
            __spec__ = spec

        p = P(COUNT=4)
        assert p.DOUBLED == 4
        assert isinstance(p.DOUBLED, int)
        assert p.emit() == {"doubled": 8}

    def test_derived_bool_and_enum_are_coerced_like_explicit_values(self):
        class Mode(str, Enum):
            DEV = "development"
            PROD = "production"

        spec = ProfileSpec(
            name="derived-bool-enum", provider_type="derived-bool-enum",
            parameters=[
                ParameterSpec(name="FLAG_SOURCE", type=str, tier="core", default="true"),
                ParameterSpec(name="ENABLED", type=bool, tier="core", default=False,
                              driver_key="enabled", template="{FLAG_SOURCE}"),
                ParameterSpec(name="MODE_SOURCE", type=str, tier="core", default="production"),
                ParameterSpec(name="MODE", type=Mode, tier="core", default=Mode.DEV,
                              driver_key="mode", template="{MODE_SOURCE}"),
            ],
        )

        class P(Profile):
            __spec__ = spec

        p = P()
        assert p.ENABLED is True
        assert isinstance(p.ENABLED, bool)
        assert p.MODE is Mode.PROD
        assert p.emit() == {"enabled": True, "mode": Mode.PROD}

    def test_derived_secret_is_wrapped_and_unwrapped_only_at_emission(self):
        spec = ProfileSpec(
            name="derived-secret", provider_type="derived-secret",
            parameters=[
                ParameterSpec(name="RAW", type=str, tier="core", default="s3cr3t-canary"),
                ParameterSpec(
                    name="TOKEN", type=str, tier="core", default="",
                    secret=True, driver_key="token", template="{RAW}",
                ),
            ],
        )

        class P(Profile):
            __spec__ = spec

        p = P()
        assert isinstance(p.TOKEN, SecretStr)
        assert p.TOKEN.get_secret_value() == "s3cr3t-canary"
        assert "s3cr3t-canary" not in str(p.TOKEN)
        assert p.emit() == {"token": "s3cr3t-canary"}


@pytest.mark.unit
class TestExplicitOriginPrecedence:
    """Explicit values win regardless of whether they equal the declared
    default, None, or empty string -- MAS-SEC-005 checkpoint 1's value-free
    origin rule. Today's guard compares values, so an explicit value equal
    to the default/None/"" is misclassified as template-eligible and
    silently overwritten; red until Task 2's rewrite lands."""

    def _make_spec(self, url_default):
        return ProfileSpec(
            name="explicit-origin", provider_type="explicit-origin",
            parameters=[
                ParameterSpec(name="HOST", type=str, tier="core", default="host.example"),
                ParameterSpec(
                    name="URL", type=str | None, tier="core",
                    default=url_default, template="https://{HOST}/api",
                ),
            ],
        )

    def test_explicit_value_equal_to_default_is_not_overwritten(self):
        spec = self._make_spec("https://default.example/")

        class P(Profile):
            __spec__ = spec

        p = P(URL="https://default.example/")
        assert p.URL == "https://default.example/"

    def test_explicit_none_is_not_overwritten(self):
        spec = self._make_spec(None)

        class P(Profile):
            __spec__ = spec

        p = P(URL=None)
        assert p.URL is None

    def test_explicit_empty_string_is_not_overwritten(self):
        spec = self._make_spec("")

        class P(Profile):
            __spec__ = spec

        p = P(URL="")
        assert p.URL == ""


@pytest.mark.unit
class TestReinitialiseCacheRoute:
    """MAS-SEC-005 + MAS-SEC-002 joint gate (M6 Task 1 checklist item 5):
    flag-off leaves a stale derived value even as its dependency changes;
    flag-on rederives only previously template-derived fields from the new
    effective inputs; a final explicit runtime value always wins; the
    complete invocation validates atomically. Red until Task 3 wires
    ``_settings_carried_field_names``/``_settings_runtime_field_names`` into
    ``_initialise_from_cache_frame`` and Task 2 consumes them."""

    def _spec(self):
        return ProfileSpec(
            name="reinit", provider_type="reinit",
            parameters=[
                ParameterSpec(name="HOST", type=str, tier="core", default="a.example"),
                ParameterSpec(name="URL", type=str, tier="core", default="",
                              template="https://{HOST}/api"),
            ],
        )

    def test_baseline_derives_url_from_host(self):
        spec = self._spec()

        class P(Profile):
            __spec__ = spec

        manager = SettingsManager()
        # Zero-kwarg baseline: MAS-SEC-002's _source_carry only publishes
        # from a materialize() call with no runtime overrides at all
        # (_context.py:524-535), so every "previously derived" case below
        # seeds it this way before applying a runtime override.
        p = manager.get_or_create_settings(SettingsParameters.create(settings_class=P))
        assert p.URL == "https://a.example/api"

    def test_flag_off_host_override_leaves_url_stale(self):
        spec = self._spec()

        class P(Profile):
            __spec__ = spec

        manager = SettingsManager()
        manager.get_or_create_settings(SettingsParameters.create(settings_class=P))
        p = manager.get_or_create_settings(
            SettingsParameters.create(settings_class=P, HOST="b.example"),
        )
        assert p.HOST == "b.example"
        assert p.URL == "https://a.example/api"  # intentionally stale, flag is off

    def test_flag_on_host_override_rederives_url(self):
        spec = self._spec()

        class P(Profile):
            __spec__ = spec

        manager = SettingsManager()
        manager.get_or_create_settings(SettingsParameters.create(settings_class=P))
        p = manager.get_or_create_settings(
            SettingsParameters.create(settings_class=P, HOST="b.example"),
            reinitialise=True,
        )
        assert p.URL == "https://b.example/api"

    def test_flag_on_explicit_url_override_wins(self):
        spec = self._spec()

        class P(Profile):
            __spec__ = spec

        manager = SettingsManager()
        manager.get_or_create_settings(SettingsParameters.create(settings_class=P))
        p = manager.get_or_create_settings(
            SettingsParameters.create(
                settings_class=P, HOST="b.example", URL="https://custom.example/",
            ),
            reinitialise=True,
        )
        assert p.URL == "https://custom.example/"

    def test_non_idempotent_validator_runs_once_per_materialization(self):
        calls: list[int] = []

        def _count_and_return(v: str) -> str:
            calls.append(1)
            return v

        spec = ProfileSpec(
            name="reinit-validator", provider_type="reinit-validator",
            parameters=[
                ParameterSpec(name="HOST", type=str, tier="core", default="a.example"),
                ParameterSpec(
                    name="URL", type=str, tier="core", default="",
                    template="https://{HOST}/api", validator=_count_and_return,
                ),
            ],
        )

        class P(Profile):
            __spec__ = spec

        manager = SettingsManager()
        manager.get_or_create_settings(SettingsParameters.create(settings_class=P))
        calls.clear()
        p = manager.get_or_create_settings(
            SettingsParameters.create(settings_class=P, HOST="b.example"),
            reinitialise=True,
        )
        assert p.URL == "https://b.example/api"
        assert calls == [1]  # validated once for this materialization, not per field/source

    def test_atomic_multi_field_override_validates_together(self):
        spec = ProfileSpec(
            name="reinit-atomic", provider_type="reinit-atomic",
            parameters=[
                ParameterSpec(name="HOST", type=str, tier="core", default="a.example"),
                ParameterSpec(name="PORT", type=int, tier="core", default=80),
                ParameterSpec(name="URL", type=str, tier="core", default="",
                              template="https://{HOST}:{PORT}/api"),
            ],
        )

        class P(Profile):
            __spec__ = spec

        manager = SettingsManager()
        manager.get_or_create_settings(SettingsParameters.create(settings_class=P))
        p = manager.get_or_create_settings(
            SettingsParameters.create(settings_class=P, HOST="b.example", PORT=8443),
            reinitialise=True,
        )
        # Both explicit overrides land in the same validated candidate before
        # URL rederives from them -- not a stale intermediate from key-by-key
        # assignment.
        assert p.URL == "https://b.example:8443/api"


@pytest.mark.unit
class TestSensitiveDerivedFailureBoundary:
    """MAS-SEC-005 + MAS-SEC-006 gate: a secret-bearing derived field's
    validation failure goes through the existing chain-free
    ``resolve._raise_sanitized_resolution_error`` boundary -- no raw value,
    no retained cause/context -- while an ordinary literal-only derived
    field keeps its normal useful ``ValidationError``. Approved 2026-09-25
    as available now (``resolve.py`` already ships this helper); red until
    Task 2 wraps the ``setattr`` call for secret=True derived fields."""

    def test_derived_secret_validation_failure_is_sanitized(self):
        def _reject(v: str) -> str:
            raise ValueError("upstream-secret-value-should-not-leak")

        spec = ProfileSpec(
            name="derived-secret-fail", provider_type="derived-secret-fail",
            parameters=[
                ParameterSpec(name="RAW", type=str, tier="core", default="super-secret-canary"),
                ParameterSpec(
                    name="TOKEN", type=str, tier="core", default="",
                    secret=True, template="{RAW}", validator=_reject,
                ),
            ],
        )

        class P(Profile):
            __spec__ = spec

        with pytest.raises(ValueError, match="TOKEN") as excinfo:
            P()

        message = str(excinfo.value)
        assert "super-secret-canary" not in message
        assert "upstream-secret-value-should-not-leak" not in message
        assert excinfo.value.__cause__ is None
        assert excinfo.value.__suppress_context__ is True

    def test_derived_non_secret_failure_keeps_useful_diagnostic(self):
        def _reject(v: str) -> str:
            raise ValueError("must not be empty")

        spec = ProfileSpec(
            name="derived-plain-fail", provider_type="derived-plain-fail",
            parameters=[
                ParameterSpec(name="RAW", type=str, tier="core", default="value"),
                ParameterSpec(
                    name="PLAIN", type=str, tier="core", default="",
                    template="{RAW}", validator=_reject,
                ),
            ],
        )

        class P(Profile):
            __spec__ = spec

        with pytest.raises(ValidationError, match="must not be empty"):
            P()


@pytest.mark.unit
class TestSpecAttributeFallback:
    """Tests for the __spec__ / __descriptor__ deprecation fallback."""

    def test_old_descriptor_attribute_emits_warning(self):
        """A class declaring only __descriptor__ (no __spec__) still works
        but emits DeprecationWarning at class creation.

        Methods that read self.__spec__ (profile_name, backend,
        provider_type, _default_kwargs) must keep working — _resolve_spec
        installs cls.__spec__ as an alias for cls.__descriptor__ when
        falling back to the old attribute.
        """
        with pytest.warns(DeprecationWarning, match="__descriptor__.*deprecated"):
            class OldStyleProfile(Profile):
                __descriptor__ = DUMMY_SPEC

        # Field installation still works from the old attribute
        instance = OldStyleProfile(HOST="h")
        assert instance.HOST == "h"

        # Methods that read self.__spec__ must work too — these previously
        # raised AttributeError on __descriptor__-only classes.
        assert instance.profile_name == "dummy"
        assert instance.backend == "dummy"
        assert instance.provider_type == "dummy"
        kwargs = instance._default_kwargs()
        assert kwargs == {"host": "h", "port": 9999}

    def test_conflicting_spec_and_descriptor_raises(self):
        """Declaring both __spec__ and __descriptor__ with different values raises."""
        OTHER_SPEC = ProfileSpec(
            name="other", provider_type="other",
            parameters=[ParameterSpec(name="HOST", type=str, tier="core", driver_key="host")],
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
