from typing import Optional, Union, List, Type
from functools import lru_cache

from pydantic_settings import BaseSettings
from upath import UPath

from ..settings_parameters.utils import SettingsUtils, SettingsParameters
from .settings_manager import SettingsManager
from ..settings import MountainAshBaseSettings
# from mountainash_settings.app.app_settings import AppSettings


@lru_cache(maxsize=None)
def get_settings_manager(
        # settings_class: Optional[Type[BaseSettings]] = None
    ) -> SettingsManager:
    """
    Retrieves the SettingsManager instance.

    Returns:
        SettingsManager: The singleton instance of SettingsManager - per settings_class
    """


    return SettingsManager(
            # settings_class=settings_class
        )


@lru_cache(maxsize=None)
def _get_settings(settings_parameters: SettingsParameters,
                  #settings_class:     Optional[Type[BaseSettings]] = BaseSettings,
                    ) -> MountainAshBaseSettings:
    """
    Retrieves the AppSettings object for a given namespace.

    Args:
        namespace (str): The namespace for the configuration.

    Returns:
        AppSettings: The AppSettings object for the given namespace.
    """

    objSettingsManager: SettingsManager = get_settings_manager()
    settings: MountainAshBaseSettings =  objSettingsManager.get_or_create_settings(settings_parameters=settings_parameters)

    return settings



def get_settings(    settings_parameters: Optional[SettingsParameters] = None,
                     settings_class:        Optional[Type[MountainAshBaseSettings]] = None,
                     config_files:          Optional[Union[UPath, str, List[UPath|str]]]  = None,
                     env_prefix:            Optional[str] = None,
                     **kwargs
                     ) -> BaseSettings:
    """
    The main function to be called to retrieve the application settings.
    This function is exported from the module!

    Args:
        settings_parameters (SettingsParameters): The settings parameters for the settings object.
        settings_class (Type[MountainAshBaseSettings]): The class of the settings object to be retrieved.
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
            settings_class=settings_class,
            config_files=config_files,
            env_prefix=env_prefix,
            **kwargs
        )


        final_settings_parameters = SettingsUtils.merge_settings_parameter_objects(settings_parameters, local_settings_parameters)

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


    def build_path_template(*parts: str) -> str:
        """Build cross-platform path template from parts."""
        path = UPath(parts[0])
        for part in parts[1:]:
            path = path / part
        return str(path)


# def get_app_settings(  settings_parameters: SettingsParameters,
#                         settings_namespace: Optional[str] = None,
#                         config_files:       Optional[Union[UPath, str, List[UPath|str]]]  = None,
#                         env_prefix:         Optional[str] = None,
#                         **kwargs
#                      ) -> AppSettings:

#     """
#     The main function to be called to retrieve the application settings for a given namespace.


#     Args:
#         settings_namespace (str, optional): The namespace for the configuration. Defaults to None, which retrieves the default namespace.
#         config_files (Optional[Union[UPath, str, List[UPath|str]]]): The configuration files that the settings object will use to load settings.
#         kwargs (Dict[Any,Any]): Additional keyword arguments that will be passed to the settings object.

#     Returns:
#         AppSettings: The AppSettings object for the given namespace.

#     Raises:
#         ValueError: If the settings object retrieved is not of type AppSettings.
#     """

#     settings_class = AppSettings

#     auth_settings: MountainAshBaseSettings = get_settings(settings_parameters=settings_parameters,
#                                                settings_class=settings_class,
#                                                settings_namespace=settings_namespace,
#                                                config_files=config_files,
#                                                env_prefix=env_prefix
#                                                  **kwargs)

#     if isinstance(auth_settings, AppSettings):
#         return auth_settings
#     else:
#         raise ValueError("The settings object retrieved is not of type AppSettings.")
