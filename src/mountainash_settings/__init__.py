from .__version__ import __version__

from .settings_parameters.settings_parameters import SettingsParameters
from .settings.base_settings import MountainAshBaseSettings
from .settings_cache.settings_functions import get_settings, get_settings_manager
from .settings_cache.settings_manager import SettingsManager

# --- Profiles + auth (2026-04-16 promotion) ---------------------------------

from .profiles import (
    MISSING,
    Missing,
    ParameterSpec,
    Profile,
    ProfileSpec,
    Registry,
    lookup_class_var,
    spec_invariants_for,
)
from .auth import (
    AUTH_TO_DRIVER_KWARGS,
    AuthSpec,
    AzureADAuth,
    CertificateAuth,
    IAMAuth,
    JWTAuth,
    KerberosAuth,
    NoAuth,
    OAuth1Auth,
    OAuth2Auth,
    OAuth2AuthCodeAuth,
    PasswordAuth,
    ServiceAccountAuth,
    TokenAuth,
    WindowsAuth,
    auth_to_driver_kwargs,
)
from .secrets import (
    SecretsResolver,
    register_secrets_resolver,
    get_secrets_resolver,
    replace_secrets_resolver,
    clear_secrets_registry,
)

__all__ = [
    "__version__",

    "SettingsParameters",

    "MountainAshBaseSettings",
    "SettingsManager",

    "get_settings",
    "get_settings_manager",

    # Profiles
    "MISSING",
    "Missing",
    "ParameterSpec",
    "Profile",
    "ProfileSpec",
    "Registry",
    "lookup_class_var",
    "spec_invariants_for",

    # Auth
    "AUTH_TO_DRIVER_KWARGS",
    "AuthSpec",
    "AzureADAuth",
    "CertificateAuth",
    "IAMAuth",
    "JWTAuth",
    "KerberosAuth",
    "NoAuth",
    "OAuth1Auth",
    "OAuth2Auth",
    "OAuth2AuthCodeAuth",
    "PasswordAuth",
    "ServiceAccountAuth",
    "TokenAuth",
    "WindowsAuth",
    "auth_to_driver_kwargs",

    # Secrets
    "SecretsResolver",
    "register_secrets_resolver",
    "get_secrets_resolver",
    "replace_secrets_resolver",
    "clear_secrets_registry",
]


# --- Deprecation aliases (PEP 562) ------------------------------------------
# Resolves pre-26.5.0 names with DeprecationWarning. Removed in 26.6.0.

import typing as _t
import warnings as _warnings

_DEPRECATED: dict[str, tuple[str, _t.Any]] = {
    "ProfileDescriptor":         ("ProfileSpec", ProfileSpec),
    "DescriptorProfile":         ("Profile", Profile),
    "descriptor_invariants_for": ("spec_invariants_for", spec_invariants_for),
}


def __getattr__(name: str) -> _t.Any:
    if name in _DEPRECATED:
        new_name, obj = _DEPRECATED[name]
        _warnings.warn(
            f"{name!r} is renamed to {new_name!r} in mountainash-settings "
            f"26.5.0. The old name will be removed in 26.6.0.",
            DeprecationWarning, stacklevel=2,
        )
        return obj
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
