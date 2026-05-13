# tests/unit/profiles/test_spec.py
"""Unit tests for ProfileSpec, ParameterSpec, Missing, and MISSING."""

import pytest

from mountainash_settings.auth import NoAuth
from mountainash_settings.profiles.spec import (
    MISSING,
    Missing,
    ParameterSpec,
    ProfileSpec,
)


@pytest.mark.unit
class TestMissing:
    def test_missing_is_singleton(self):
        assert Missing() is MISSING

    def test_missing_is_falsy(self):
        assert not MISSING

    def test_missing_repr(self):
        assert repr(MISSING) == "MISSING"


@pytest.mark.unit
class TestParameterSpec:
    def test_minimal(self):
        p = ParameterSpec(name="X", type=str, tier="core")
        assert p.name == "X"
        assert p.type is str
        assert p.tier == "core"
        assert p.default is MISSING
        assert p.driver_key is None
        assert p.secret is False
        assert p.transform is None
        assert p.validator is None
        assert p.template is None

    def test_with_default(self):
        p = ParameterSpec(name="X", type=int, tier="core", default=42)
        assert p.default == 42

    def test_secret_flag(self):
        p = ParameterSpec(name="PWD", type=str, tier="core", secret=True)
        assert p.secret is True

    def test_frozen(self):
        p = ParameterSpec(name="X", type=str, tier="core")
        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            p.name = "Y"


@pytest.mark.unit
class TestProfileSpec:
    def test_minimal(self):
        spec = ProfileSpec(
            name="test",
            provider_type="test",
            parameters=[],
            auth_modes=[NoAuth],
        )
        assert spec.name == "test"
        assert spec.provider_type == "test"
        assert spec.parameters == []
        assert spec.auth_modes == [NoAuth]
        assert spec.metadata == {}

    def test_with_parameters(self):
        params = [ParameterSpec(name="HOST", type=str, tier="core", driver_key="host")]
        spec = ProfileSpec(
            name="test",
            provider_type="test",
            parameters=params,
            auth_modes=[NoAuth],
        )
        assert spec.parameters == params

    def test_frozen(self):
        spec = ProfileSpec(
            name="test",
            provider_type="test",
            parameters=[],
            auth_modes=[NoAuth],
        )
        with pytest.raises(Exception):  # FrozenInstanceError
            spec.name = "other"

    def test_metadata(self):
        spec = ProfileSpec(
            name="test",
            provider_type="test",
            parameters=[],
            auth_modes=[NoAuth],
            metadata={"port": 5432},
        )
        assert spec.metadata == {"port": 5432}
