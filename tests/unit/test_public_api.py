"""Smoke test: the new profiles/auth surface is importable from the package root."""

import pytest


@pytest.mark.unit
def test_profiles_surface_imports():
    from mountainash_settings import (
        MISSING,
        Missing,
        ParameterSpec,
        Profile,
        ProfileSpec,
        Registry,
        lookup_class_var,
        spec_invariants_for,
    )
    assert all(obj is not None for obj in (
        MISSING, Missing, ParameterSpec,
        Profile, ProfileSpec, Registry, lookup_class_var, spec_invariants_for,
    ))



@pytest.mark.unit
def test_secrets_surface_imports():
    from mountainash_settings import (
        ClearableBackend,
        FilesystemBackend,
        SecretsBackend,
        register_secrets_backend,
        get_secrets_backend,
        replace_secrets_backend,
        clear_secrets_registry,
    )
    assert callable(register_secrets_backend)
    assert callable(get_secrets_backend)
    assert callable(replace_secrets_backend)
    assert callable(clear_secrets_registry)
    assert ClearableBackend is not None
    assert FilesystemBackend is not None
    assert SecretsBackend is not None
