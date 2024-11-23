
from typing import Optional, Union, List, Any, Tuple, Dict, Type
from unittest.mock import Base
from upath import UPath
from importlib import import_module
import platform

from .settings_parameters import SettingsParameters
from pydantic_settings import BaseSettings
# from .base import MountainAshBaseSettings
from .settings_filehandler import SettingsFileHandler
from .settings_kwargshandler import SettingsKwargsHandler

class SettingsUtils:

    """
    Utility class for handling settings parameters.
    """

    #Hashable format for settings parameters
    default_namespace: str = "DEFAULT"

    ############################################################################################################
    # SettingsParameters combination

    @classmethod
    def merge_settings_parameter_objects(cls,
                        base: SettingsParameters, 
                        other: SettingsParameters,
                        prioritise_self: Optional[bool] = False
                   ) -> SettingsParameters:


        if base.settings_class and other.settings_class:
            if other.settings_class != base.settings_class:
                raise ValueError(f"Settings class must match for merging. bsse: {base.settings_class} != other: {other.settings_class}")



        #Merge values based on precedence
        if not prioritise_self:
            resolved_namespace =    other.namespace or base._init_namespace(base.namespace)
            resolved_config_files = SettingsFileHandler.merge_config_files(other.config_files, base.config_files)
            resolved_kwargs =       SettingsKwargsHandler.merge_kwargs(other.kwargs, base.kwargs)
            resolved_env_prefix=    other.env_prefix or base.env_prefix
            resolved_settings_class = other.settings_class or base.settings_class or BaseSettings


        else:
            resolved_namespace =    base.namespace or base._init_namespace(other.namespace)
            resolved_config_files = SettingsFileHandler.merge_config_files( base.config_files, other.config_files,)
            resolved_kwargs =       SettingsKwargsHandler.merge_kwargs(base.kwargs, other.kwargs)
            resolved_env_prefix=    base.env_prefix or other.env_prefix
            resolved_settings_class = base.settings_class or other.settings_class or BaseSettings


        return SettingsParameters.create(
            namespace=      resolved_namespace,
            config_files=   resolved_config_files,
            kwargs=         resolved_kwargs,
            settings_class= resolved_settings_class,
            env_prefix=     resolved_env_prefix,
            secrets_dir=    other.secrets_dir or base.secrets_dir
        )

    @classmethod
    def merge_settings_parameters(cls,
                            base: SettingsParameters, 
                            namespace: Optional[str] = None,
                            config_files: Optional[Union[UPath, str, List[Union[UPath, str]]]] = None,
                            kwargs: Optional[Dict[str, Any]] = None,
                            env_prefix: Optional[str] = None,
                            secrets_dir: Optional[str] = None,
                            prioritise_self: Optional[bool] = False
               ) -> 'SettingsParameters':
        

        if not prioritise_self:
            resolved_namespace =    namespace or base._init_namespace(base.namespace)
            resolved_config_files = SettingsFileHandler.merge_config_files(config_files, base.config_files)
            resolved_kwargs =       SettingsKwargsHandler.merge_kwargs(kwargs, base.kwargs)
            resolved_env_prefix=    cls.merge_env_prefix(env_prefix, base.env_prefix)
        else:
            resolved_namespace =    base.namespace or base._init_namespace(namespace)
            resolved_config_files = SettingsFileHandler.merge_config_files( base.config_files, config_files,)
            resolved_kwargs =       SettingsKwargsHandler.merge_kwargs(base.kwargs, kwargs)
            resolved_env_prefix=    cls.merge_env_prefix(base.env_prefix, env_prefix)


        return SettingsParameters.create(
            namespace=      resolved_namespace,
            config_files=   resolved_config_files,
            kwargs=         resolved_kwargs,
            settings_class= base.settings_class,
            env_prefix=     resolved_env_prefix,
            secrets_dir=    secrets_dir or base.secrets_dir
        )



    #Translation functions between mutable and immutable

    ############################################################################################################
    # Parameter formatting

    @classmethod
    def format_kwargs_dict(cls, 
                            p_kwargs: None | Dict[str,Any] | Tuple[Any,Any] = None
                            ) -> Optional[Dict[str,Any]]:
        
        return SettingsKwargsHandler.format_kwargs_dict(p_kwargs=p_kwargs)


    @classmethod
    def format_kwargs_tuple(cls, 
                            p_kwargs: None | Dict[str,Any] | Tuple[Any,Any]  = None
                            ) -> Optional[Tuple[Any,Any]]:
        
        return SettingsKwargsHandler.format_kwargs_tuple(p_kwargs=p_kwargs)



    @classmethod
    def format_config_file_list(cls, 
                                 config_files: Optional[Union[UPath, str, List[UPath|str], Tuple[UPath|str]]]  = None
                                 ) -> Optional[List[UPath|str]]:
        
        return SettingsFileHandler.format_config_file_list(config_files=config_files)


    @classmethod
    def format_config_file_tuple(cls, 
                                config_files: Optional[Union[UPath, str, List[UPath|str], Tuple[UPath|str]]]  = None
                                ) -> Optional[Tuple[UPath|str]]:
        
        return SettingsFileHandler.format_config_file_tuple(config_files=config_files)


    #Resolve / Merge values 
    @staticmethod
    def merge_namspaces(namespace1: Optional[str] = None,
                         namespace2: Optional[str] = None) -> str:
        return namespace1 or namespace2 or "DEFAULT"

    @staticmethod
    def merge_env_prefix(env_prefix1: Optional[str] = None,
                         env_prefix2: Optional[str] = None) -> Optional[str]:
        return env_prefix1 or env_prefix2 or None



    @staticmethod
    def merge_config_files(config_files1: Optional[Tuple[Union[UPath, str], ...]] = None,
                            config_files2: Optional[Tuple[Union[UPath, str], ...]] = None) -> Optional[Tuple[Union[UPath, str], ...]]:
    
        return SettingsFileHandler.merge_config_files(config_files1=config_files1, config_files2=config_files2)

    @staticmethod
    def merge_kwargs(kwargs1: Optional[Tuple[Tuple[str, Any], ...]] = None,
                      kwargs2: Optional[Tuple[Tuple[str, Any], ...]] = None) -> Optional[Tuple[Tuple[str, Any], ...]]:
        
        return SettingsKwargsHandler.merge_kwargs(kwargs1=kwargs1, kwargs2=kwargs2)



    ############################################################################################################
    # SettingsParameters extraction

    @classmethod
    def extract_namespace_from_settings_parameters(cls, 
                                                   settings_parameters: SettingsParameters) -> Optional[str]:

        """
        Extracts the namespace from the SettingsParameters object.
        
        Args:
            settings_parameters (SettingsParameters): The settings parameters object.

        Returns:
            str: The namespace.        
        """

        mutable_parameters: dict[str, Any] = cls.extract_settings_parameters(settings_parameters=settings_parameters)

        return settings_parameters.namespace

    @classmethod
    def extract_config_files_from_settings_parameters(cls, 
                                                      settings_parameters: SettingsParameters) -> Optional[List[UPath|str]]:
        """
        Extracts the config_files from the SettingsParameters object.

        Args:
            settings_parameters (SettingsParameters): The settings parameters object.

        Returns:
            List[UPath|str]: The configuration files.
        """


        mutable_parameters: dict[str, Any] = cls.extract_settings_parameters(settings_parameters=settings_parameters)

        return mutable_parameters["config_files"]

    @classmethod
    def extract_kwargs_from_settings_parameters(cls, settings_parameters: SettingsParameters) -> Optional[dict[str, Any]]:

        """
        Extracts the keyword arguments from the SettingsParameters object.

        Args:
            settings_parameters (SettingsParameters): The settings parameters object.

        Returns:
            dict: The keyword arguments.
        """

        mutable_parameters: dict[str, Any] = cls.extract_settings_parameters(settings_parameters=settings_parameters)

        return mutable_parameters["kwargs"]

    @classmethod
    def get_platform_slash(cls) -> str:

        """
        Returns the platform-specific slash.

        Returns:
            str: The platform-specific slash.
        """

        if platform.system() == "Windows":
            return "\\"
        else:
            return "/"

