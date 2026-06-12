from .__version__ import __version__

from .settings_parameters.settings_parameters import SettingsParameters
from .settings.base_settings import MountainAshBaseSettings
from .settings_cache.settings_functions import get_settings, get_settings_manager
from .settings_cache.settings_manager import SettingsManager

# --- Profiles + auth (2026-04-16 promotion) ---------------------------------

from .profiles import (
    Adapter,
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
    ClearableBackend,
    FilesystemBackend,
    SecretsBackend,
    register_secrets_backend,
    get_secrets_backend,
    replace_secrets_backend,
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
    "Adapter",
    "MISSING",
    "Missing",
    "ParameterSpec",
    "Profile",
    "ProfileSpec",
    "Registry",
    "lookup_class_var",
    "spec_invariants_for",

    # Secrets
    "ClearableBackend",
    "FilesystemBackend",
    "SecretsBackend",
    "register_secrets_backend",
    "get_secrets_backend",
    "replace_secrets_backend",
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
