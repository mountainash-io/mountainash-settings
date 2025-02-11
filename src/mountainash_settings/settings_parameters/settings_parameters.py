
from typing import Optional, Any, Tuple, Type, List, Dict
from dataclasses import dataclass

from pydantic_settings import BaseSettings
from upath import UPath

from .filehandler import SettingsFileHandler


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
    config_files:   Optional[List[str|UPath]|Tuple[str|UPath]] = None
    settings_class: Optional[Type[BaseSettings]] = None
    env_prefix:     Optional[str] = None
    secrets_dir:    Optional[str] = None    
    kwargs:         Optional[Dict[str,Any]] = None

    # _reserved_mountainash_kwargs = ["_dummy"]


    _reserved_pydantic_modelconfig_kwargs = [ 
                                 "extra",
                                 "arbitrary_types_allowed",
                                 "validate_default"
    ]


    _reserved_pydantic_kwargs = ["_case_sensitive", 
                                 "_nested_model_default_partial_update", 
                                 "_env_prefix", 
                                 "_env_file", 
                                 "_env_file_encoding", 
                                 "_env_ignore_empty", 
                                 "_env_nested_delimiter", 
                                 "_env_parse_none_str", 
                                 "_env_parse_enums", 
                                 "_cli_prog_name", 
                                 "_cli_parse_args", 
                                 "_cli_settings_source", 
                                 "_cli_parse_none_str", 
                                 "_cli_hide_none_type", 
                                 "_cli_avoid_json", 
                                 "_cli_enforce_required", 
                                 "_cli_use_class_docs_for_groups", 
                                 "_cli_exit_on_error", 
                                 "_cli_prefix", 
                                 "_cli_flag_prefix_char", 
                                 "_cli_implicit_flags", 
                                 "_cli_ignore_unknown_args", 
                                 "_secrets_dir",
                                 ]




    def __hash__(self):

        hashable_config_files = SettingsFileHandler.format_config_file_tuple(self.config_files)

        hashable_attrs = tuple(
                    [self.namespace, 
                      hashable_config_files, 
                      self.settings_class, 
                      self.env_prefix, 
                    #   self.secrets_dir
                      ]
                      )

        return hash(hashable_attrs)


    # Creation methods
    @classmethod
    def create(cls, 
               namespace: Optional[str] = None,
               config_files: Optional[str|UPath|List[str|UPath]|Tuple[str|UPath]] = None,
               settings_class: Optional[Type[BaseSettings]] = None,
               env_prefix: Optional[str] = None,
               secrets_dir: Optional[str] = None,
               **kwargs: Optional[Dict[str, Any]]
               ) -> 'SettingsParameters':
        

        #Combine the parameters into a single object
        # resolved_namespace =     cls._init_namespace(namespace)
        resolved_config_files =  SettingsFileHandler.format_config_file_tuple(config_files)        
        # merged_kwargs =         SettingsKwargsHandler.merge_kwargs(kw_params, kwargs) if kwargs else kw_params
        # resolved_kwargs =        SettingsKwargsHandler.format_kwargs_dict(kwargs) if kwargs else None

        return cls(
            namespace=namespace,
            config_files=resolved_config_files,
            settings_class=settings_class,
            env_prefix=env_prefix,
            secrets_dir=secrets_dir,
            kwargs = kwargs
        )



    @staticmethod
    def _init_namespace(namespace: Optional[str]) -> str:
        return namespace or "DEFAULT"


    #Export / retrieve values
    def to_dict(self) -> Dict[str, Any]:
        return {
            'namespace': self.namespace,
            'config_files': list(self.config_files) if self.config_files else None,
            'kwargs': self.get_all_kwargs() if self.kwargs else None,
            'settings_class': self.settings_class,
            'env_prefix': self.env_prefix,
            'secrets_dir': self.secrets_dir
        }


    def _get_settings_kwarg_names(self, 
                             settings_class: Optional[Type[BaseSettings]] = None
                             ) -> set[str]:

        if settings_class is None:
            settings_class = self.settings_class
        if settings_class is None:
            return set()

        #This relies on the _dummay parameter on MountainAshBaseSettings. If I actuallly use that type (rather than pydantic_settings.BaseSettings) I will get a circular dependency.
        # settings_class_mod: Type[BaseSettings] = getattr(import_module(name=settings_class.__module__), settings_class.__name__)       
        # obj_dummy_settings: BaseSettings = settings_class_mod(_dummy=True)
        # settings_kwarg_names = set(obj_dummy_settings.model_fields)
        settings_kwarg_names = set(settings_class.model_fields.keys())


        return settings_kwarg_names

    def _get_valid_kwarg_names(self, 
                          settings_class:    Optional[Type[BaseSettings]] = None
                          ) -> set[str]:

        if settings_class is None:
            settings_class = self.settings_class
        if settings_class is None:
            return set()

        settings_kwarg_names = self._get_settings_kwarg_names(settings_class)
        valid_kwarg_names = settings_kwarg_names.union(self._reserved_pydantic_kwargs)

        return valid_kwarg_names


    def get_attribute_settings_kwargs(self, 
                                        settings_class: Optional[Type[BaseSettings]] = None
                                        ) -> Dict[str, Any]:

        valid_kwarg_names = self._get_valid_kwarg_names(settings_class=settings_class)
        return {k: v for k, v in self.kwargs.items() if k in valid_kwarg_names} if self.kwargs else {}


    def get_pydantic_settings_kwargs(self) -> Dict[str, Any]:

        return {k: v for k, v in self.kwargs.items() if k in self._reserved_pydantic_kwargs} if self.kwargs else {}


    def get_pydantic_modelconfig_kwargs(self) -> Dict[str, Any]:

        return {k: v for k, v in self.kwargs.items() if k in self._reserved_pydantic_modelconfig_kwargs} if self.kwargs else {}


    def get_all_kwargs(self) -> Dict[str, Any]:

        return {k: v for k, v in self.kwargs.items()} if self.kwargs else {}




    #Export a .env file from the settings parameters and class
    # def export_env_file(self, 
    #                     env_file: UPath,
    #                     encoding: Optional[str] = "utf-8") -> None:
        
    #     valid_kwarg_names = self._get_settings_kwargs(self.settings_class)

    #     with env_file.open(mode="w", encoding=encoding) as f:
    #         for k, v in self.kwargs:
    #             if k in valid_kwarg_names:
    #                 f.write(f"{k}={v}\n")