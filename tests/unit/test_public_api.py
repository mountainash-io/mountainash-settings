"""Smoke test: the new profiles/auth surface is importable from the package root."""

import pytest


@pytest.mark.unit
def test_profiles_surface_imports():
    from mountainash_settings import (
        MISSING,
        DescriptorProfile,
        ParameterSpec,
        ProfileDescriptor,
        Registry,
        spec_invariants_for,
    )
    assert all(obj is not None for obj in (
        MISSING, DescriptorProfile, ParameterSpec,
        ProfileDescriptor, Registry, spec_invariants_for,
    ))


@pytest.mark.unit
def test_auth_surface_imports():
    from mountainash_settings import (
        AuthSpec, NoAuth, PasswordAuth, TokenAuth, JWTAuth, OAuth2Auth,
        ServiceAccountAuth, IAMAuth, WindowsAuth, AzureADAuth, KerberosAuth,
        CertificateAuth, auth_to_driver_kwargs, AUTH_TO_DRIVER_KWARGS,
    )
    assert issubclass(PasswordAuth, AuthSpec)
    assert callable(auth_to_driver_kwargs)


@pytest.mark.unit
def test_secrets_surface_imports():
    from mountainash_settings import (
        SecretsResolver,
        register_secrets_resolver,
        get_secrets_resolver,
        replace_secrets_resolver,
        clear_secrets_registry,
    )
    assert callable(register_secrets_resolver)
    assert callable(get_secrets_resolver)
    assert callable(replace_secrets_resolver)
    assert callable(clear_secrets_registry)
