from typing import Optional, Union, List, Any, Dict, Tuple
from functools import lru_cache
from upath import UPath

from ..settings_functions import get_settings
from ..settings import  SettingsParameters, SettingsUtils
from ..settings import MountainAshBaseSettings
from .auth_settings import AuthSettings



def get_auth_settings(  auth_settings_parameters: SettingsParameters,
                        settings_namespace: Optional[str] = None,
                        config_files: Optional[Union[UPath, str, List[UPath|str]]]  = None,
                        **kwargs
                     ) -> AuthSettings:
    """
    The main function to be called to retrieve the application settings for a given namespace.
    This function is exported from the module!

    Args:
        namespace (str, optional): The namespace for the configuration. Defaults to None, which retrieves the default namespace.

    Returns:
        AppSettings: The AppSettings object for the given namespace.
    """

    settings_class = AuthSettings

    auth_settings: MountainAshBaseSettings = get_settings(settings_parameters=auth_settings_parameters, settings_class=settings_class, settings_namespace=settings_namespace, config_files=config_files, **kwargs)


    if isinstance(auth_settings, AuthSettings):
        return auth_settings
    else:
        raise ValueError("The settings object retrieved is not of type AppSettings.")


def prepare_auth_settings_parameters(
        settings_namespace: str,
        config_files:       Optional[Union[UPath, str, List[UPath|str], Tuple[UPath|str]]]  = None,
        p_kwargs:           Optional[Dict[Any,Any]] = None,
        **kwargs
        ) -> SettingsParameters:
    
    return SettingsUtils.prepare_settings_parameters(
        settings_namespace=settings_namespace,
        settings_class=AuthSettings,
        config_files=config_files,
        p_kwargs=p_kwargs,
        **kwargs
    )
