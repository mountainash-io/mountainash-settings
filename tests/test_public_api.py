"""Smoke test: the new profiles/auth surface is importable from the package root."""

import pytest


def test_clean_break_version():
    from mountainash_settings.__version__ import __version__
    assert __version__ == "0.1.0"


@pytest.mark.unit
def test_profiles_surface_imports():
    from mountainash_settings import (
        FACTORY_DEFAULT,
        FactoryDefault,
        ProfileField,
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
        FACTORY_DEFAULT, FactoryDefault, ProfileField,
        MISSING, Missing, ParameterSpec,
        Profile, ProfileSpec, Registry, lookup_class_var, spec_invariants_for,
    ))
    from mountainash_settings import profiles
    assert profiles.ProfileField is ProfileField
    assert profiles.FactoryDefault is FactoryDefault
    assert profiles.FACTORY_DEFAULT is FACTORY_DEFAULT



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
