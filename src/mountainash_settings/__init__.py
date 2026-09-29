from .__version__ import __version__

from .settings_parameters.settings_parameters import SettingsParameters
from .settings.base_settings import MountainAshBaseSettings
from .settings_cache.settings_functions import get_settings, get_settings_manager
from .settings_cache.settings_manager import SettingsManager
from .settings_cache.sources import CacheableSettingsSource

# --- Profiles + auth (2026-04-16 promotion) ---------------------------------

from .profiles import (
    Adapter,
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
from .secrets import (
    ClearableSecretStore,
    FilesystemBackend,
    SecretReader,
    SecretWriter,
    SecretCapabilityError,
    SecretStoreError,
    SecretStoreUnavailableError,
)

__all__ = [
    "__version__",

    "SettingsParameters",

    "MountainAshBaseSettings",
    "SettingsManager",

    "CacheableSettingsSource",
    "get_settings",
    "get_settings_manager",

    # Profiles
    "Adapter",
    "FACTORY_DEFAULT",
    "FactoryDefault",
    "ProfileField",
    "MISSING",
    "Missing",
    "ParameterSpec",
    "Profile",
    "ProfileSpec",
    "Registry",
    "lookup_class_var",
    "spec_invariants_for",

    # Secrets
    "ClearableSecretStore",
    "FilesystemBackend",
    "SecretReader",
    "SecretWriter",
    "SecretCapabilityError",
    "SecretStoreError",
    "SecretStoreUnavailableError",
]
