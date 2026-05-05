from .__version__ import __version__

from .settings_parameters.settings_parameters import SettingsParameters
from .settings.base_settings import MountainAshBaseSettings
from .settings_cache.settings_functions import get_settings, get_settings_manager
from .settings_cache.settings_manager import SettingsManager

# --- Profiles + auth (2026-04-16 promotion) ---------------------------------

from .profiles import (
    MISSING,
    DescriptorProfile,
    ParameterSpec,
    ProfileDescriptor,
    Registry,
    descriptor_invariants_for,
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

__all__ = [
    "__version__",

    "SettingsParameters",

    "MountainAshBaseSettings",
    "SettingsManager",

    "get_settings",
    "get_settings_manager",

    # Profiles
    "MISSING",
    "DescriptorProfile",
    "ParameterSpec",
    "ProfileDescriptor",
    "Registry",
    "descriptor_invariants_for",

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
]
