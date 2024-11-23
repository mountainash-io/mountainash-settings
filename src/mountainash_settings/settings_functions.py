from logging import warn
from typing import Optional, Union, List, Any, Dict, Type, Tuple, final
from functools import lru_cache
import warnings
from upath import UPath

from pydantic_settings import BaseSettings

from mountainash_settings.settings_utils import SettingsUtils, SettingsParameters
from mountainash_settings.settings_manager import SettingsManager
from mountainash_settings.base import BaseSettings
from mountainash_settings.app.app_settings import AppSettings


@lru_cache(maxsize=None)
def get_settings_manager(
        settings_class: Optional[Type[BaseSettings]]=None
    ) -> SettingsManager:
    """
    Retrieves the SettingsManager instance.

    Returns:
        SettingsManager: The singleton instance of SettingsManager - per settings_class
    """
    return SettingsManager(
            settings_class=settings_class
        )


@lru_cache(maxsize=None)
def _get_settings(settings_parameters: SettingsParameters,
                  settings_class:     Optional[Type[BaseSettings]] = BaseSettings, 
                    ) -> BaseSettings:
    """
    Retrieves the AppSettings object for a given namespace.

    Args:
        namespace (str): The namespace for the configuration.

    Returns:
        AppSettings: The AppSettings object for the given namespace.
    """

    # mutable_params = SettingsUtils.extract_settings_parameters(settings_parameters=settings_parameters)

    # namespace: str =                            mutable_params["namespace"]
    # config_files: Optional[List[UPath|str]] =   mutable_params["config_files"]
    # kwargs: Optional[Dict[str,str]] =           mutable_params["kwargs"]

    objSettingsManager: SettingsManager = get_settings_manager(settings_class=settings_class)
    settings =  objSettingsManager.get_or_create_settings(settings_parameters=settings_parameters)

    # if kwargs:
    #     settings: BaseSettings =  objSettingsManager.get_settings(settings_namespace=namespace, 
    #                                                                        config_files=config_files, 
    #                                                                        settings_class=settings_class, 
    #                                                                        **kwargs)
    # else:
    #     settings =  objSettingsManager.get_settings(settings_namespace=namespace, 
    #                                               config_files=config_files, 
    #                                               settings_class=settings_class)

    return settings






def get_settings(    settings_parameters: Optional[SettingsParameters] = None,
                     settings_class:        Optional[Type[BaseSettings]] = None, 
                     settings_namespace:    Optional[str] = None,
                     config_files:          Optional[Union[UPath, str, List[UPath|str]]]  = None,
                     env_prefix:            Optional[str] = None,
                     **kwargs
                     ) -> BaseSettings:
    """
    The main function to be called to retrieve the application settings for a given namespace.
    This function is exported from the module!

    Args:
        settings_parameters (SettingsParameters): The settings parameters for the settings object.
        settings_class (Type[BaseSettings]): The class of the settings object to be retrieved.
        settings_namespace (str, optional): The namespace for the configuration. Defaults to None, which retrieves the default namespace.
        config_files (Optional[Union[UPath, str, List[UPath|str]]]): The configuration files that the settings object will use to load settings.
        kwargs (Dict[Any,Any]): Additional keyword arguments that will be passed to the settings object.

    Returns:
        AppSettings: The AppSettings object for the given namespace.
    """

    # We will need to be clever and careful here.
    # It makes sense to separate initialisation vs getting of settings.
    # Getting a non-initialised should throw a warning, but not halt play!
    # Initialisation should be done once ( *per thread/process!), and then the settings retrieved. If re-initing and existing, an error should be thrown.
    # getting, however should be by namespace, with validation.

    #Is it possible to retrieve an existing settings, and then augment with kwargs, just for this instance?
    #We should remain as close to the priority described here as possible: https://docs.pydantic.dev/latest/concepts/pydantic_settings/#field-value-priority

    if settings_parameters:
        if not isinstance(settings_parameters, SettingsParameters):
            raise ValueError("The settings_parameters parameter must be an instance of SettingsParameters.")

        local_settings_parameters = SettingsParameters.create(
            namespace=settings_namespace,
            config_files=config_files,
            kwargs=kwargs,
            settings_class=settings_class,
            env_prefix=env_prefix
        )


        final_settings_params = SettingsUtils.merge_settings_parameter_objects(settings_parameters, local_settings_parameters)

    else:

        final_settings_parameters = SettingsParameters.create(
            namespace=settings_namespace,
            config_files=config_files,
            kwargs=kwargs,
            settings_class=settings_class,
            env_prefix=env_prefix
        )

    return _get_settings(settings_parameters=final_settings_params, settings_class=settings_class)


def get_app_settings(  settings_parameters: SettingsParameters,
                        settings_namespace: Optional[str] = None,
                        config_files:       Optional[Union[UPath, str, List[UPath|str]]]  = None,
                        env_prefix:         Optional[str] = None,
                        **kwargs
                     ) -> AppSettings:
  
    """
    The main function to be called to retrieve the application settings for a given namespace.

    
    Args:
        settings_namespace (str, optional): The namespace for the configuration. Defaults to None, which retrieves the default namespace.
        config_files (Optional[Union[UPath, str, List[UPath|str]]]): The configuration files that the settings object will use to load settings.
        kwargs (Dict[Any,Any]): Additional keyword arguments that will be passed to the settings object.

    Returns:
        AppSettings: The AppSettings object for the given namespace.

    Raises:
        ValueError: If the settings object retrieved is not of type AppSettings.
    """

    settings_class = AppSettings

    auth_settings: BaseSettings = get_settings(settings_parameters=settings_parameters, 
                                               settings_class=settings_class, 
                                               settings_namespace=settings_namespace, 
                                               config_files=config_files,
                                               env_prefix=env_prefix
                                                 **kwargs)

    if isinstance(auth_settings, AppSettings):
        return auth_settings
    else:
        raise ValueError("The settings object retrieved is not of type AppSettings.")
    
