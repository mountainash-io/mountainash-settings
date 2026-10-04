from __future__ import annotations


from typing import Any, Optional, TYPE_CHECKING, TypeVar, overload

from ..settings_parameters.filehandler import ConfigFilesInput

if TYPE_CHECKING:
    from ..settings.base_settings import MountainAshBaseSettings

from ..settings_parameters.settings_parameters import SettingsParameters
from .settings_manager import SettingsManager

_SETTINGS_MANAGER = SettingsManager()
T = TypeVar("T", bound="MountainAshBaseSettings")


def get_settings_manager() -> SettingsManager:
    """Retrieve the sole process-wide structural-context owner."""
    return _SETTINGS_MANAGER


@overload
def get_settings(
    settings_parameters: Optional[SettingsParameters] = None,
    *,
    settings_class: type[T],
    config_files: ConfigFilesInput = None,
    env_prefix: Optional[str] = None,
    reinitialise: bool = False,
    **kwargs: Any,
) -> T: ...


@overload
def get_settings(
    settings_parameters: Optional[SettingsParameters],
    settings_class: type[T],
    config_files: ConfigFilesInput = None,
    env_prefix: Optional[str] = None,
    *,
    reinitialise: bool = False,
    **kwargs: Any,
) -> T: ...


@overload
def get_settings(
    settings_parameters: Optional[SettingsParameters] = None,
    settings_class: None = None,
    config_files: ConfigFilesInput = None,
    env_prefix: Optional[str] = None,
    *,
    reinitialise: bool = False,
    **kwargs: Any,
) -> MountainAshBaseSettings: ...


def get_settings(
    settings_parameters: Optional[SettingsParameters] = None,
    settings_class: type[MountainAshBaseSettings] | None = None,
    config_files: ConfigFilesInput = None,
    env_prefix: Optional[str] = None,
    *,
    reinitialise: bool = False,
    **kwargs: Any,
) -> MountainAshBaseSettings:
    """Materialize an isolated result from a pinned structural source context."""
    if settings_parameters is not None:
        if not isinstance(settings_parameters, SettingsParameters):
            raise ValueError("The settings_parameters parameter must be an instance of SettingsParameters.")
        local = SettingsParameters.create(
            settings_class=settings_class,
            config_files=config_files,
            env_prefix=env_prefix,
            **kwargs,
        )
        final = SettingsParameters.merge(settings_parameters, local)
    else:
        final = SettingsParameters.create(
            settings_class=settings_class,
            config_files=config_files,
            env_prefix=env_prefix,
            **kwargs,
        )
    return get_settings_manager().get_or_create_settings(final, reinitialise=reinitialise)
