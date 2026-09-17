from __future__ import annotations


from typing import Any, List, Optional, Type, Union

from pydantic_settings import BaseSettings
from upath import UPath

from ..settings_parameters.settings_parameters import SettingsParameters
from .settings_manager import SettingsManager

_SETTINGS_MANAGER = SettingsManager()


def get_settings_manager() -> SettingsManager:
    """Retrieve the sole process-wide structural-context owner."""
    return _SETTINGS_MANAGER


def get_settings(
    settings_parameters: Optional[SettingsParameters] = None,
    settings_class: Optional[Type[BaseSettings]] = None,
    config_files: Optional[Union[UPath, str, List[UPath | str]]] = None,
    env_prefix: Optional[str] = None,
    *,
    reinitialise: bool = False,
    **kwargs: Any,
) -> BaseSettings:
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
