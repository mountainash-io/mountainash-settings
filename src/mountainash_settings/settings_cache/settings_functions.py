from typing import Optional, Union, List, Type
from functools import lru_cache

from pydantic_settings import BaseSettings
from upath import UPath

from ..settings_parameters.settings_parameters import SettingsParameters
from .settings_manager import SettingsManager
from ..settings import MountainAshBaseSettings


@lru_cache(maxsize=None)
def get_settings_manager() -> SettingsManager:
    """
    Retrieves the SettingsManager singleton instance.

    Returns:
        SettingsManager: The singleton instance of SettingsManager
    """
    return SettingsManager()


@lru_cache(maxsize=None)
def _get_settings(settings_parameters: SettingsParameters) -> MountainAshBaseSettings:
    """
    Retrieves or creates a settings object for the given parameters.

    Uses lru_cache for efficient caching based on SettingsParameters hash.

    Args:
        settings_parameters: The structural parameters identifying the settings.

    Returns:
        MountainAshBaseSettings: The cached or newly created settings object.
    """
    objSettingsManager: SettingsManager = get_settings_manager()
    settings: MountainAshBaseSettings = objSettingsManager.get_or_create_settings(settings_parameters=settings_parameters)

    return settings


def get_settings(settings_parameters: Optional[SettingsParameters] = None,
                 settings_class: Optional[Type[MountainAshBaseSettings]] = None,
                 config_files: Optional[Union[UPath, str, List[UPath|str]]] = None,
                 env_prefix: Optional[str] = None,
                 **kwargs
                 ) -> BaseSettings:
    """
    The main function to retrieve application settings.

    Args:
        settings_parameters: Pre-built settings parameters object.
        settings_class: The class of settings to create.
        config_files: Configuration files to load.
        env_prefix: Environment variable prefix.
        **kwargs: Additional keyword arguments passed as runtime overrides.

    Returns:
        BaseSettings: The settings instance.
    """
    if settings_parameters:
        if not isinstance(settings_parameters, SettingsParameters):
            raise ValueError("The settings_parameters parameter must be an instance of SettingsParameters.")

        local_settings_parameters = SettingsParameters.create(
            settings_class=settings_class,
            config_files=config_files,
            env_prefix=env_prefix,
            **kwargs
        )

        final_settings_parameters = SettingsParameters.merge(settings_parameters, local_settings_parameters)

    else:
        final_settings_parameters = SettingsParameters.create(
            settings_class=settings_class,
            config_files=config_files,
            env_prefix=env_prefix,
            **kwargs
        )

    # Get cached settings based on structural parameters only
    cached_settings = _get_settings(settings_parameters=final_settings_parameters)

    # Apply runtime overrides to the cached instance
    return final_settings_parameters.apply_runtime_overrides(cached_settings)
