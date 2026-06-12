# tests/unit/profiles/test_emit.py
"""Unit tests for target-aware driver_key, __adapters__, and Profile.emit()."""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from mountainash_settings.profiles import ParameterSpec, ProfileSpec
from mountainash_settings.profiles.profile import Profile


# A bare-string spec — behaves exactly as before this change.
BARE_SPEC = ProfileSpec(
    name="bare",
    provider_type="bare",
    parameters=[
        ParameterSpec(name="HOST", type=str, tier="core", driver_key="host"),
        ParameterSpec(name="PASSWORD", type=str, tier="core", secret=True,
                      driver_key="password", default=None),
    ],
)


class BareProfile(Profile):
    __spec__ = BARE_SPEC


# A target-scoped spec — driver_key is a {target: key} dict.
SCOPED_SPEC = ProfileSpec(
    name="scoped",
    provider_type="scoped",
    parameters=[
        ParameterSpec(name="USERNAME", type=str, tier="core",
                      driver_key={"paramiko": "username"}),
        ParameterSpec(name="PASSWORD", type=str, tier="core", secret=True,
                      driver_key={"paramiko": "password"}),
    ],
)


class ScopedProfile(Profile):
    __spec__ = SCOPED_SPEC


@pytest.mark.unit
class TestTargetAwareDriverKey:
    def test_bare_driver_key_unchanged_no_target(self):
        p = BareProfile(HOST="h", PASSWORD="s")
        assert p._default_kwargs() == {"host": "h", "password": "s"}

    def test_bare_driver_key_ignores_target(self):
        p = BareProfile(HOST="h", PASSWORD="s")
        # A bare string means "all targets" — passing a target changes nothing.
        assert p._default_kwargs("anything") == {"host": "h", "password": "s"}

    def test_scoped_emits_for_matching_target(self):
        p = ScopedProfile(USERNAME="u", PASSWORD="s")
        assert p._default_kwargs("paramiko") == {"username": "u", "password": "s"}

    def test_scoped_skips_for_other_target(self):
        p = ScopedProfile(USERNAME="u", PASSWORD="s")
        assert p._default_kwargs("http") == {}

    def test_scoped_skips_for_none_target(self):
        p = ScopedProfile(USERNAME="u", PASSWORD="s")
        assert p._default_kwargs(None) == {}

    def test_spec_with_dict_driver_key_is_hashable(self):
        # ParameterSpec is a frozen dataclass; its auto-generated __hash__ must
        # not choke on a dict driver_key. driver_key is excluded from the hash
        # (field(hash=False)) but stays in __eq__.
        param = ParameterSpec(name="X", type=str, tier="core",
                              driver_key={"paramiko": "x"})
        assert isinstance(hash(param), int)


@pytest.mark.unit
class TestAdaptersMap:
    def test_adapters_default_empty(self):
        # A profile that declares no adapters has an empty map.
        assert BareProfile.__adapters__ == {}

    def test_adapters_declarable(self):
        def _http(profile, kw):
            return {**kw, "marker": "http"}

        class Adapted(Profile):
            __spec__ = BARE_SPEC
            __adapters__ = {"http": _http}

        assert "http" in Adapted.__adapters__
        # Base Profile is unaffected (no leakage across classes).
        assert BareProfile.__adapters__ == {}


def _http_basic(profile, kw):
    # Copy-on-write nested container; sole producer of the Authorization key.
    token = f"{profile.USERNAME}:{profile.PASSWORD.get_secret_value()}"
    return {**kw, "headers": {**kw.get("headers", {}), "Authorization": token}}


# Profile that is target-scoped via an adapter only (no dict driver_keys).
class HttpAdaptedProfile(Profile):
    __spec__ = SCOPED_SPEC
    __adapters__ = {"http": _http_basic}


# Legacy owns-the-pipeline adapter (1-arg).
def _legacy_adapter(profile):
    kw = profile._default_kwargs()
    kw["legacy"] = True
    return kw


class LegacyAdaptedProfile(Profile):
    __spec__ = BARE_SPEC
    __adapter__ = staticmethod(_legacy_adapter)


@pytest.mark.unit
class TestEmit:
    def test_untargeted_emit_equals_default_kwargs(self):
        p = BareProfile(HOST="h", PASSWORD="s")
        assert p.emit() == p._default_kwargs() == {"host": "h", "password": "s"}

    def test_untargeted_emit_layers_base(self):
        p = BareProfile(HOST="h")
        assert p.emit(base={"region": "x"}) == {"region": "x", "host": "h"}

    def test_targeted_profile_no_target_raises(self):
        p = ScopedProfile(USERNAME="u", PASSWORD="s")
        with pytest.raises(ValueError, match="target-scoped"):
            p.emit()

    def test_targeted_profile_unknown_target_raises(self):
        p = ScopedProfile(USERNAME="u", PASSWORD="s")
        with pytest.raises(ValueError, match="no emission for target"):
            p.emit("ftp")

    def test_targeted_profile_known_target_emits(self):
        p = ScopedProfile(USERNAME="u", PASSWORD="s")
        assert p.emit("paramiko") == {"username": "u", "password": "s"}

    def test_per_target_adapter_composes_onto_base(self):
        p = HttpAdaptedProfile(USERNAME="u", PASSWORD="pw")
        out = p.emit("http", base={"timeout": 5})
        assert out["timeout"] == 5
        assert out["headers"]["Authorization"] == "u:pw"
        # SCOPED_SPEC driver_keys are paramiko-only, so no stray username/password.
        assert "username" not in out and "password" not in out

    def test_legacy_adapter_owns_pipeline(self):
        p = LegacyAdaptedProfile(HOST="h", PASSWORD="s")
        # Not target-scoped (no __adapters__, no dict driver_keys) → emit() allowed.
        out = p.emit()
        assert out == {"host": "h", "password": "s", "legacy": True}


@pytest.mark.unit
class TestEmitSafety:
    def test_emit_does_not_mutate_base_top_level(self):
        p = BareProfile(HOST="h")
        base = {"region": "x"}
        p.emit(base=base)
        # emit() shallow-copies base; caller's dict is untouched.
        assert base == {"region": "x"}

    def test_double_emit_from_shared_base_is_isolated(self):
        # Config emit, then a credential-style adapter emit layered on top,
        # from the same starting base. The first result must not be mutated
        # by the second.
        config = BareProfile(HOST="h")
        first = config.emit(base={"timeout": 5})

        cred = HttpAdaptedProfile(USERNAME="u", PASSWORD="pw")
        second = cred.emit("http", base=first)

        # first still has no Authorization header; the nested header dict the
        # adapter built is its own (copy-on-write), not first's.
        assert "headers" not in first
        assert second["headers"]["Authorization"] == "u:pw"
        assert second["timeout"] == 5 and second["host"] == "h"


@pytest.mark.unit
class TestBackCompat:
    def test_existing_default_kwargs_call_sites_unbroken(self):
        # Domain code calls _default_kwargs() with no args; still valid.
        p = BareProfile(HOST="h", PASSWORD="s")
        assert p._default_kwargs() == {"host": "h", "password": "s"}

    def test_secret_unwrapped_under_target_resolution(self):
        # SecretStr unwrap still happens for a target-scoped secret field.
        p = ScopedProfile(USERNAME="u", PASSWORD="s")
        out = p._default_kwargs("paramiko")
        assert out["password"] == "s"
        assert not isinstance(out["password"], SecretStr)

    def test_dict_driver_key_constructs_and_installs_fields(self):
        # A spec with a dict driver_key builds its pydantic fields normally.
        p = ScopedProfile(USERNAME="u", PASSWORD="s")
        assert p.USERNAME == "u"
        assert isinstance(p.PASSWORD, SecretStr)

    def test_transform_applies_under_target(self):
        spec = ProfileSpec(
            name="tf2", provider_type="tf2",
            parameters=[
                ParameterSpec(name="FLAG", type=bool, tier="core", default=True,
                              driver_key={"boto": "flag"},
                              transform=lambda v: 1 if v else 0),
            ],
        )

        class P(Profile):
            __spec__ = spec

        assert P(FLAG=True).emit("boto") == {"flag": 1}


@pytest.mark.unit
class TestExports:
    def test_adapter_exported_from_profiles(self):
        from mountainash_settings.profiles import Adapter  # noqa: F401

    def test_adapter_exported_from_package_root(self):
        from mountainash_settings import Adapter  # noqa: F401
