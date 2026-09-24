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
    from mountainash_settings import FilesystemBackend, SecretReader, SecretWriter, ClearableSecretStore
    import mountainash_settings as pkg
    assert FilesystemBackend is not None
    assert SecretReader is not None
    assert SecretWriter is not None
    assert ClearableSecretStore is not None
    for removed in (
        "register_secrets_backend", "get_secrets_backend", "replace_secrets_backend",
        "clear_secrets_registry", "SecretsBackend", "ClearableBackend",
    ):
        assert not hasattr(pkg, removed)
