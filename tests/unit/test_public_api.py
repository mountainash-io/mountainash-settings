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
        descriptor_invariants_for,
    )
    assert all(obj is not None for obj in (
        MISSING, DescriptorProfile, ParameterSpec,
        ProfileDescriptor, Registry, descriptor_invariants_for,
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
