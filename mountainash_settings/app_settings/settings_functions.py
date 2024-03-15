from typing import Optional, Union, List, Any, Dict, Type, Tuple
from functools import lru_cache
from upath import UPath

from mountainash_settings.settings.settings_functions import get_settings
from mountainash_settings.settings.settings_utils import  SettingsParameters, SettingsUtils
from mountainash_settings.settings.base_settings import MountainAshBaseSettings

from .app_settings import AppSettings

def get_app_settings(app_settings_parameters: SettingsParameters,
                     settings_class:     Optional[Type[AppSettings]] = AppSettings, 
                     settings_namespace: Optional[str] = None,
                     config_files: Optional[Union[UPath, str, List[UPath|str]]]  = None,
                     **kwargs
                     ) -> AppSettings:
    """
    The main function to be called to retrieve the application settings for a given namespace.
    This function is exported from the module!

    Args:
        namespace (str, optional): The namespace for the configuration. Defaults to None, which retrieves the default namespace.

    Returns:
        AppSettings: The AppSettings object for the given namespace.
    """
    
    settings_class = AppSettings
    
    app_settings: MountainAshBaseSettings = get_settings(settings_parameters=app_settings_parameters, settings_class=settings_class, settings_namespace=settings_namespace, config_files=config_files, **kwargs)

    if isinstance(app_settings, AppSettings):
        return app_settings
    else:
        raise ValueError("The settings object retrieved is not of type AppSettings.")


def prepare_app_settings_parameters(
        settings_namespace: str,
        config_files:       Optional[Union[UPath, str, List[UPath|str], Tuple[UPath|str]]]  = None,
        p_kwargs:           Optional[Dict[Any,Any]] = None,
        **kwargs
        ) -> SettingsParameters:
    
    return SettingsUtils.prepare_settings_parameters(
        settings_namespace=settings_namespace,
        settings_class=AppSettings,
        config_files=config_files,
        p_kwargs=p_kwargs,
        **kwargs
    )