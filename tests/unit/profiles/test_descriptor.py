# tests/unit/profiles/test_descriptor.py
"""Unit tests for ProfileDescriptor, ParameterSpec, and MISSING."""

import pytest

from mountainash_settings.auth import NoAuth
from mountainash_settings.profiles.descriptor import (
    MISSING,
    ParameterSpec,
    ProfileDescriptor,
)


@pytest.mark.unit
class TestMissing:
    def test_missing_is_singleton(self):
        from mountainash_settings.profiles.descriptor import _Missing
        assert _Missing() is MISSING

    def test_missing_is_falsy(self):
        assert not MISSING

    def test_missing_repr(self):
        assert repr(MISSING) == "MISSING"


@pytest.mark.unit
class TestParameterSpec:
    def test_minimal(self):
        p = ParameterSpec(name="X", type=str, tier="core")
        assert p.name == "X"
        assert p.default is MISSING
        assert p.template is None

    def test_frozen(self):
        p = ParameterSpec(name="X", type=str, tier="core")
        with pytest.raises(Exception):
            p.name = "Y"  # type: ignore

    def test_template_field(self):
        p = ParameterSpec(name="URL", type=str, tier="core",
                          template="https://{HOST}/api")
        assert p.template == "https://{HOST}/api"


@pytest.mark.unit
class TestProfileDescriptor:
    def test_minimal(self):
        d = ProfileDescriptor(
            name="x", provider_type="x",
            parameters=[], auth_modes=[NoAuth],
        )
        assert d.name == "x"
        assert d.metadata == {}

    def test_metadata(self):
        d = ProfileDescriptor(
            name="x", provider_type="x",
            parameters=[], auth_modes=[NoAuth],
            metadata={"port": 5432, "scheme": "x://"},
        )
        assert d.metadata["port"] == 5432

    def test_frozen(self):
        d = ProfileDescriptor(
            name="x", provider_type="x",
            parameters=[], auth_modes=[NoAuth],
        )
        with pytest.raises(Exception):
            d.name = "y"  # type: ignore
