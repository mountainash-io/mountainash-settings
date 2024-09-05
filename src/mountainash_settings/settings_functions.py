from typing import Optional, Union, List, Any, Dict, Type, Tuple
from functools import lru_cache
from upath import UPath

from mountainash_settings.settings_utils import SettingsUtils, SettingsParameters
from mountainash_settings.settings_manager import SettingsManager
from mountainash_settings.base_settings import MountainAshBaseSettings
from mountainash_settings.app_settings import AppSettings


@lru_cache(maxsize=None)
def get_settings_manager(auth_parameters: Optional[SettingsParameters]=None) -> SettingsManager:
    """
    Retrieves the SettingsManager instance.

    Returns:
        SettingsManager: The singleton instance of SettingsManager.
    """
    return SettingsManager(auth_parameters=auth_parameters)
    # return _get_settings_manager(auth_parameters=auth_parameters)


@lru_cache(maxsize=None)
def _get_settings(settings_parameters: SettingsParameters,
                  settings_class:     Optional[Type[MountainAshBaseSettings]] = MountainAshBaseSettings, 
                    ) -> MountainAshBaseSettings:
    """
    Retrieves the AppSettings object for a given namespace.

    Args:
        namespace (str): The namespace for the configuration.

    Returns:
        AppSettings: The AppSettings object for the given namespace.
    """

    mutable_params = SettingsUtils.extract_settings_parameters(settings_parameters=settings_parameters)

    namespace: str =                            mutable_params["namespace"]
    config_files: Optional[List[UPath|str]] =   mutable_params["config_files"]
    kwargs: Optional[Dict[str,str]] =           mutable_params["kwargs"]

    objSettingsManager: SettingsManager = get_settings_manager()

    if kwargs:
        settings: MountainAshBaseSettings =  objSettingsManager.get_config(settings_namespace=namespace, config_files=config_files, settings_class=settings_class, **kwargs)
    else:
        settings =  objSettingsManager.get_config(settings_namespace=namespace, config_files=config_files, settings_class=settings_class)

    return settings






def get_settings(    settings_parameters: SettingsParameters,
                     settings_class:     Type[MountainAshBaseSettings] = MountainAshBaseSettings, 
                     settings_namespace: Optional[str] = None,
                     config_files: Optional[Union[UPath, str, List[UPath|str]]]  = None,
                     **kwargs
                     ) -> MountainAshBaseSettings:
    """
    The main function to be called to retrieve the application settings for a given namespace.
    This function is exported from the module!

    Args:
        settings_parameters (SettingsParameters): The settings parameters for the settings object.
        settings_class (Type[MountainAshBaseSettings]): The class of the settings object to be retrieved.
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

    if settings_parameters is None:
        raise ValueError("The settings_parameters parameter must be provided.")

    if settings_class is None:
        raise ValueError("The settings_class parameter must be provided.")

    if not issubclass(settings_class, MountainAshBaseSettings):
        raise ValueError("The settings_class parameter must be a subclass of MountainAshBaseSettings")
    
    if settings_class != settings_parameters.settings_class:
        raise ValueError("The settings_class parameter does not match the settings_parameters.settings_class parameter.")

    # Get the attributes from the settings_parameters
    params_namespace = settings_parameters.namespace
    params_config_files = settings_parameters.config_files
    params_kwargs = settings_parameters.kwargs


    #Resolve the settings parameters - from the passed in parameters, or from the structured parameters
    final_namespace: str = SettingsUtils.resolve_namespace(new_namespace=settings_namespace, original_namespace=params_namespace)

    final_config_files: Optional[List[UPath | str]] = SettingsUtils.resolve_config_files(new_config_files=config_files, original_config_files=params_config_files)

    final_kwargs: Optional[Dict[str, Any]] = SettingsUtils.resolve_kwargs(new_kwargs=kwargs, original_kwargs=params_kwargs)

    #Build the final settings parameters
    settings_parameters = SettingsUtils.prepare_settings_parameters(settings_namespace=final_namespace, 
                                                                    settings_class=settings_class, 
                                                                    config_files=final_config_files, 
                                                                    p_kwargs=final_kwargs)

    return _get_settings(settings_parameters=settings_parameters, settings_class=settings_class)


def prepare_settings_parameters(
        settings_namespace: str,
        settings_class:    Type[MountainAshBaseSettings],
        config_files:       Optional[Union[UPath, str, List[UPath|str], Tuple[UPath|str]]]  = None,
        p_kwargs:           Optional[Dict[Any,Any]] = None,
        **kwargs
        ) -> SettingsParameters:
    
    """
    Construct the settings parameters for the AppSettings object.

    Args:
        settings_namespace (str): The namespace for the configuration.
        config_files (Optional[Union[UPath, str, List[UPath|str], Tuple[UPath|str]]]): The configuration files that the settings object will use to load settings.
        p_kwargs (Optional[Dict[Any,Any]]): Additional keyword arguments that will be passed to the settings object.
        kwargs (Dict[Any,Any]): Additional keyword arguments that will be passed to the settings object.

    Returns:
        SettingsParameters: The settings parameters for the AppSettings object.
        
    """


    return SettingsUtils.prepare_settings_parameters(
        settings_namespace=settings_namespace,
        settings_class=settings_class,
        config_files=config_files,
        p_kwargs=p_kwargs,
        **kwargs
    )



def get_app_settings(  app_settings_parameters: SettingsParameters,
                        settings_namespace: Optional[str] = None,
                        config_files: Optional[Union[UPath, str, List[UPath|str]]]  = None,
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

    auth_settings: MountainAshBaseSettings = get_settings(settings_parameters=app_settings_parameters, settings_class=settings_class, settings_namespace=settings_namespace, config_files=config_files, **kwargs)

    if isinstance(auth_settings, AppSettings):
        return auth_settings
    else:
        raise ValueError("The settings object retrieved is not of type AppSettings.")