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
