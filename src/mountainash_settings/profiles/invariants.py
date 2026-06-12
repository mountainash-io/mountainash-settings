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
            # Per-target output keys must be unique. A bare-string driver_key
            # applies to every target; a dict driver_key applies per named
            # target. (dicts are unhashable, so a set() over raw values would
            # crash — resolve to per-target keys first.)
            from collections import defaultdict

            bare: list[str] = []
            per_target: dict[t.Hashable, list[str]] = defaultdict(list)
            for p in spec.parameters:
                dk = p.driver_key
                if not dk:
                    continue
                if isinstance(dk, str):
                    bare.append(dk)
                else:  # dict[Hashable, str]
                    for target, key in dk.items():
                        per_target[target].append(key)

            assert len(bare) == len(set(bare)), (
                f"duplicate bare driver_key in {name}"
            )
            for target, keys in per_target.items():
                combined = keys + bare  # bare keys apply to every target
                assert len(combined) == len(set(combined)), (
                    f"duplicate driver_key for target {target!r} in {name}"
                )

        def test_parameter_tiers_valid(self, name: str, spec: t.Any) -> None:
            for p in spec.parameters:
                assert p.tier in {"core", "advanced"}, (
                    f"{name}.{p.name} has invalid tier {p.tier!r}"
                )

        def test_provider_type_not_none(self, name: str, spec: t.Any) -> None:
            assert spec.provider_type is not None, (
                f"{name} has no provider_type"
            )

    TestSpecInvariants.__name__ = f"TestSpecInvariants_{registry.name}"
    TestSpecInvariants.__qualname__ = TestSpecInvariants.__name__
    return TestSpecInvariants
