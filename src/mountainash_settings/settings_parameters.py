
from ast import Set
from pydoc import resolve
from typing import Optional, Union, Any, Tuple, Type, List, Dict
from dataclasses import dataclass
# from mountainash_settings.base import MountainAshBaseSettings
from pydantic_settings import BaseSettings
# from .settings_utils import SettingsUtils
from .settings_filehandler import SettingsFileHandler
from .settings_kwargshandler import SettingsKwargsHandler
from importlib import import_module

from upath import UPath

@dataclass(frozen=True)
class SettingsParameters():

    """
    SettingsParameters is a dataclass that holds the parameters needed to create a settings object.
    
    Parameters:
        namespace:      The namespace of the settings object. This is used to group settings together, and make the settings findable.
        config_files:   The configuration files that the settings object will use to load settings.
        kwargs:         Additional keyword arguments that will be passed to the settings object.
        settings_class: The class/type that will be used to create the settings object.

    """
    namespace:      Optional[str] = None
    config_files:   Optional[Union[Any, str, Tuple[Any|str]]] = None
    kwargs:         Optional[Tuple[str,Any]] = None
    settings_class: Optional[Type[BaseSettings]] = None
    env_prefix:     Optional[str] = None
    secrets_dir:    Optional[str] = None    

    _reserved_kwargs = ["_env_file", "_env_file_encoding", "_env_prefix", "_dummy"]

    def __hash__(self):
        return hash((self.namespace, self.config_files, self.kwargs, self.settings_class, self.env_prefix, self.secrets_dir))


    # Creation methods
    @classmethod
    def create(cls, 
               namespace: Optional[str] = None,
               config_files: Optional[Union[UPath, str, List[Union[UPath, str]]]] = None,
               kwargs: Optional[Dict[str, Any]] = None,
               settings_class: Optional[Type[BaseSettings]] = None,
               env_prefix: Optional[str] = None,
               secrets_dir: Optional[str] = None) -> 'SettingsParameters':
        

        #Combine the parameters into a single object
        # resolved_namespace =     cls._init_namespace(namespace)
        resolved_config_files =  SettingsFileHandler.format_config_file_tuple(config_files)
        resolved_kwargs =        SettingsKwargsHandler.format_kwargs_tuple(kwargs)

        return cls(
            namespace=namespace,
            config_files=resolved_config_files,
            kwargs=resolved_kwargs,
            settings_class=settings_class,
            env_prefix=env_prefix,
            secrets_dir=secrets_dir
        )

    # Move Merge methods to utils class
    # Resolve the settings parameters for creation
   



    #Move statics to utils class!

    @staticmethod
    def _init_namespace(namespace: Optional[str]) -> str:
        return namespace or "DEFAULT"





    #Export / retrieve values
    def to_dict(self) -> Dict[str, Any]:
        return {
            'namespace': self.namespace,
            'config_files': list(self.config_files) if self.config_files else None,
            'kwargs': dict(self.kwargs) if self.kwargs else None,
            'settings_class': self.settings_class,
            'env_prefix': self.env_prefix,
            'secrets_dir': self.secrets_dir
        }


    def _get_settings_kwargs(self, 
                             settings_class: Optional[Type[BaseSettings]] = None
                             ) -> Set:

        if settings_class is None:
            settings_class = self.settings_class
        if settings_class is None:
            return set()

        settings_class_mod: Type[BaseSettings] = getattr(import_module(name=settings_class.__module__), settings_class.__name__)       
        obj_dummy_settings: BaseSettings = settings_class_mod(_dummy=True)
        settings_kwarg_names = set(obj_dummy_settings.model_fields)

        return settings_kwarg_names

    def _get_valid_kwargs(self, 
                          settings_class:    Optional[Type[BaseSettings]] = None
                          ) -> Set:

        if settings_class is None:
            settings_class = self.settings_class
        if settings_class is None:
            return set()

        settings_kwarg_names = self._get_settings_kwargs(settings_class)
        valid_kwarg_names = settings_kwarg_names.union(self._reserved_kwargs)

        return valid_kwarg_names


    #Export a .env file from the settings parameters and class
    # def export_env_file(self, 
    #                     env_file: UPath,
    #                     encoding: Optional[str] = "utf-8") -> None:
        
    #     valid_kwarg_names = self._get_settings_kwargs(self.settings_class)

    #     with env_file.open(mode="w", encoding=encoding) as f:
    #         for k, v in self.kwargs:
    #             if k in valid_kwarg_names:
    #                 f.write(f"{k}={v}\n")