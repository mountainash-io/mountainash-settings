# src/mountainash_settings/profiles/invariants.py
"""Parametric descriptor invariants runnable against any Registry.

Each consumer domain drops this helper into its test suite::

    from mountainash_settings.profiles import descriptor_invariants_for
    from my_package.settings import MY_REGISTRY

    TestMyInvariants = descriptor_invariants_for(MY_REGISTRY)

Every descriptor registered in ``MY_REGISTRY`` is then checked against the
invariants below. New registrations get coverage for free.
"""

from __future__ import annotations

import typing as t

import pytest

from mountainash_settings.auth.base import AuthSpec

from .registry import Registry

__all__ = ["descriptor_invariants_for"]


def descriptor_invariants_for(registry: Registry) -> type:
    """Return a pytest class parameterised over every descriptor in ``registry``.

    The returned class is named ``TestDescriptorInvariants_<registry_name>``.
    """

    entries = list(registry.descriptors.items())
    ids = list(registry.descriptors.keys()) or [""]

    @pytest.mark.unit
    @pytest.mark.parametrize("name,descriptor", entries, ids=ids)
    class TestDescriptorInvariants:  # noqa: D401
        """Invariants every registered descriptor must satisfy."""

        def test_name_matches_registry_key(self, name: str, descriptor: t.Any) -> None:
            assert descriptor.name == name

        def test_name_lowercase_nonempty(self, name: str, descriptor: t.Any) -> None:
            assert descriptor.name, f"{name}: descriptor.name is empty"
            assert descriptor.name == descriptor.name.lower(), (
                f"{name}: descriptor.name must be lowercase"
            )

        def test_parameter_names_unique(self, name: str, descriptor: t.Any) -> None:
            names = [p.name for p in descriptor.parameters]
            assert len(names) == len(set(names)), f"duplicate param in {name}"

        def test_parameter_names_uppercase(self, name: str, descriptor: t.Any) -> None:
            for p in descriptor.parameters:
                assert p.name == p.name.upper(), (
                    f"{name}.{p.name}: ParameterSpec.name must be UPPERCASE"
                )
                assert p.name, f"{name}: ParameterSpec.name is empty"

        def test_driver_keys_unique(self, name: str, descriptor: t.Any) -> None:
            keys = [p.driver_key for p in descriptor.parameters if p.driver_key]
            assert len(keys) == len(set(keys)), f"duplicate driver_key in {name}"

        def test_parameter_tiers_valid(self, name: str, descriptor: t.Any) -> None:
            for p in descriptor.parameters:
                assert p.tier in {"core", "advanced"}, (
                    f"{name}.{p.name} has invalid tier {p.tier!r}"
                )

        def test_auth_modes_nonempty(self, name: str, descriptor: t.Any) -> None:
            assert descriptor.auth_modes, (
                f"{name}: auth_modes is empty — use [NoAuth] for no-auth profiles"
            )

        def test_auth_modes_are_authspec(self, name: str, descriptor: t.Any) -> None:
            for mode in descriptor.auth_modes:
                assert issubclass(mode, AuthSpec), (
                    f"{name}.auth_modes contains non-AuthSpec: {mode}"
                )

        def test_provider_type_not_none(self, name: str, descriptor: t.Any) -> None:
            assert descriptor.provider_type is not None, (
                f"{name} has no provider_type"
            )

    TestDescriptorInvariants.__name__ = f"TestDescriptorInvariants_{registry.name}"
    TestDescriptorInvariants.__qualname__ = TestDescriptorInvariants.__name__
    return TestDescriptorInvariants
