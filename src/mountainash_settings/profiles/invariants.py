# src/mountainash_settings/profiles/invariants.py
"""Parametric spec invariants runnable against any Registry.

Each consumer domain drops this helper into its test suite::

    from mountainash_settings.profiles import spec_invariants_for
    from my_package.settings import MY_REGISTRY

    TestMyInvariants = spec_invariants_for(MY_REGISTRY)

Every spec registered in ``MY_REGISTRY`` is then checked against the
invariants below. New registrations get coverage for free.

Public from 26.5.0. Previously named ``descriptor_invariants_for``.
"""

from __future__ import annotations

import typing as t

from mountainash_auth_client import AuthSpec

from .registry import Registry

__all__ = ["spec_invariants_for"]


def spec_invariants_for(registry: Registry) -> type:
    """Return a pytest class parameterised over every spec in ``registry``.

    The returned class is named ``TestSpecInvariants_<registry_name>``.
    """

    # Lazy import: keeps ``mountainash_settings`` importable in non-test envs.
    import pytest

    entries = list(registry.descriptors.items())
    ids = list(registry.descriptors.keys()) or [""]

    @pytest.mark.unit
    @pytest.mark.parametrize("name,spec", entries, ids=ids)
    class TestSpecInvariants:  # noqa: D401
        """Invariants every registered spec must satisfy."""

        def test_name_matches_registry_key(self, name: str, spec: t.Any) -> None:
            assert spec.name == name

        def test_name_lowercase_nonempty(self, name: str, spec: t.Any) -> None:
            assert spec.name, f"{name}: spec.name is empty"
            assert spec.name == spec.name.lower(), (
                f"{name}: spec.name must be lowercase"
            )

        def test_parameter_names_unique(self, name: str, spec: t.Any) -> None:
            names = [p.name for p in spec.parameters]
            assert len(names) == len(set(names)), f"duplicate param in {name}"

        def test_parameter_names_uppercase(self, name: str, spec: t.Any) -> None:
            for p in spec.parameters:
                assert p.name == p.name.upper(), (
                    f"{name}.{p.name}: ParameterSpec.name must be UPPERCASE"
                )
                assert p.name, f"{name}: ParameterSpec.name is empty"

        def test_driver_keys_unique(self, name: str, spec: t.Any) -> None:
            keys = [p.driver_key for p in spec.parameters if p.driver_key]
            assert len(keys) == len(set(keys)), f"duplicate driver_key in {name}"

        def test_parameter_tiers_valid(self, name: str, spec: t.Any) -> None:
            for p in spec.parameters:
                assert p.tier in {"core", "advanced"}, (
                    f"{name}.{p.name} has invalid tier {p.tier!r}"
                )

        def test_auth_modes_nonempty(self, name: str, spec: t.Any) -> None:
            assert spec.auth_modes, (
                f"{name}: auth_modes is empty — use [NoAuth] for no-auth profiles"
            )

        def test_auth_modes_are_authspec(self, name: str, spec: t.Any) -> None:
            for mode in spec.auth_modes:
                assert issubclass(mode, AuthSpec), (
                    f"{name}.auth_modes contains non-AuthSpec: {mode}"
                )

        def test_provider_type_not_none(self, name: str, spec: t.Any) -> None:
            assert spec.provider_type is not None, (
                f"{name} has no provider_type"
            )

    TestSpecInvariants.__name__ = f"TestSpecInvariants_{registry.name}"
    TestSpecInvariants.__qualname__ = TestSpecInvariants.__name__
    return TestSpecInvariants
