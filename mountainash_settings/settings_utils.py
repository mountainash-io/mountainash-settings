
from typing import Optional, Union, List, Any, Tuple, Dict, Type
from upath import UPath
from importlib import import_module
import platform

from .settings_parameters import SettingsParameters
from .base_settings import MountainAshBaseSettings


class SettingsUtils:

    #Hashable format for settings parameters
    default_namespace = "DEFAULT"


    @classmethod
    def prepare_settings_parameters(
            cls,
            settings_namespace: str,
            settings_class:     Type[MountainAshBaseSettings],
            config_files:       Optional[Union[UPath, str, List[UPath|str], Tuple[UPath|str]]]  = None,
            p_kwargs:           Optional[Dict[Any,Any]] = None,
            **kwargs
            ) -> SettingsParameters:
        """
        Initializes the application settings for a given namespace.

        Args:
            namespace (str): The namespace for the configuration.
            config_files (Union[UPath, List[UPath]]): The configuration file or list of configuration files.
            **kwargs: Keyword arguments to set the configuration attributes.

        Raises:
            ValueError: If an invalid attribute is provided in kwargs.
        """
        # Namespace
        if not settings_namespace:
            raise ValueError("A namespace must be provided.")

        if not settings_class:
            raise ValueError("A settings_class must be provided.")


        # Config_files
        config_files_tuple: Optional[Tuple[UPath | str]] = cls.format_config_file_tuple(config_files=config_files)

        #Consolidate and validate the kwargs
        kwargs_resolved: Dict[str, Any] | None = cls.resolve_kwargs(new_kwargs=kwargs, original_kwargs=p_kwargs)
        kwargs_validated = cls.get_valid_setting_kwargs(p_kwargs=kwargs_resolved, settings_class=settings_class)

        kwarg_keys_resolved:    set = set(kwargs_resolved.keys()) if kwargs_resolved else set() 
        kwarg_keys_validated:   set = set(kwargs_validated.keys()) if kwargs_validated else set()
        
        len_kwargs_resolved: int = len(kwargs_resolved) if kwargs_resolved else 0

        if len(kwarg_keys_validated) != len_kwargs_resolved:
            print(f"Invalid kwargs were provided: {set(kwarg_keys_resolved)-set(kwarg_keys_validated)}")

        kwargs_tuple = cls.format_kwargs_tuple(p_kwargs=kwargs_validated)

        #Create the settings parameters
        settings_parameters =  SettingsParameters(namespace=settings_namespace, 
                                                  config_files=config_files_tuple, 
                                                  kwargs=kwargs_tuple, 
                                                  settings_class=settings_class)

        return settings_parameters
    

    @classmethod
    def get_valid_setting_kwargs(cls, 
                                 settings_class:    Type[MountainAshBaseSettings],
                                 p_kwargs:          Dict[Any, Any]
                                 ) -> Optional[Dict[Any, Any]]:
        """
        Returns a dictionary of valid kwargs for AppSettings.

        Args:
            kwargs (dict): The kwargs to validate.

        Returns:
            dict: The valid kwargs.
        """


        settings_class_mod: Type[MountainAshBaseSettings] = getattr(import_module(name=settings_class.__module__), settings_class.__name__)       
        obj_dummy_settings: MountainAshBaseSettings = settings_class_mod(_dummy=True)

        # valid_attribute_names = set(vars(__object=obj_dummy_settings))
        valid_attribute_names = set(obj_dummy_settings.model_fields)

        # Filter the kwargs dictionary to include only valid attributes
        valid_kwargs = {key: value for key, value in p_kwargs.items() if key in valid_attribute_names}

        # If an empty dictionary, return None
        if not valid_kwargs:
            return None

        return valid_kwargs
    

    @classmethod
    def get_settings_parameters(cls, objSettings) -> SettingsParameters:

        existing_namespace = objSettings.SETTINGS_NAMESPACE
        existing_config_files = cls.format_config_file_list(config_files=objSettings.SETTINGS_SOURCE_ENV_FILES)
        existing_kwargs = cls.format_kwargs_dict(p_kwargs=objSettings.SETTINGS_SOURCE_KWARGS)
        existing_settings_class = objSettings.SETTINGS_CLASS

        params: SettingsParameters = cls.prepare_settings_parameters(
            settings_namespace=existing_namespace,
            config_files=existing_config_files,
            p_kwargs=existing_kwargs,
            settings_class=existing_settings_class)
            
        return params        

    @classmethod
    def resolve_config_files(cls, 
                                    new_config_files: Optional[Union[UPath, str, List[UPath|str], Tuple[UPath|str]]]  = None,
                                    original_config_files: Optional[Union[UPath, str, List[UPath|str], Tuple[UPath|str]]]  = None
                                    ) -> Optional[List[UPath|str]]:

        prep_new_config_files: List[UPath | str] | None = cls.format_config_file_list(new_config_files)
        prep_original_config_files: List[UPath | str] | None = cls.format_config_file_list(original_config_files)

        if prep_new_config_files is None and prep_original_config_files is None:
            return None

        if prep_new_config_files is not None and prep_original_config_files is not None:
            combined_config_files = list(sorted(set(prep_original_config_files + prep_new_config_files)))
            final_config_files = SettingsUtils.format_config_file_list(config_files=combined_config_files)

        elif prep_new_config_files is not None:
            final_config_files = prep_new_config_files

        else:
            final_config_files = prep_original_config_files

        return final_config_files






    #Combine mutable and immutable settings parameters

    @classmethod
    def resolve_namespace(cls,
                          new_namespace: Optional[str] = None, 
                          original_namespace: Optional[str] = None)-> str:
        
        #Set the namespace
        if new_namespace is not None: 
            if original_namespace and new_namespace != original_namespace:
                print(f"Namespace '{new_namespace}' based upon '{original_namespace}'")

            namespace: str = new_namespace

        elif original_namespace is not None:
            namespace = original_namespace
        else:
            namespace = cls.default_namespace

        return namespace 



    @classmethod
    def resolve_kwargs(cls,
                       new_kwargs: Optional[Dict[str,Any] | Tuple[Any,Any]] = None, 
                       original_kwargs: Optional[Dict[str,Any] | Tuple[Any,Any]] = None
                       )-> Dict[str,Any]:
        
        new_kwargs = cls.format_kwargs_dict(p_kwargs=new_kwargs)
        original_kwargs = cls.format_kwargs_dict(p_kwargs=original_kwargs)

        kwargs: Optional[Dict[str, Any]]  = {}

        if new_kwargs is not None:
            if original_kwargs is not None:
                kwargs = {**original_kwargs, **new_kwargs}
            else:
                kwargs = new_kwargs
        elif original_kwargs is not None:
            kwargs = original_kwargs

        return kwargs


    #Translation functions between mutable and immutable

    @classmethod
    def format_kwargs_dict(cls, 
                                 p_kwargs: None | Dict[str,Any] | Tuple[Any,Any] = None
                                 ) -> Optional[Dict[str,Any]]:
        if p_kwargs is None:
            return None
        
        if isinstance(p_kwargs, dict):
            return p_kwargs
        
        if isinstance(p_kwargs, tuple):
            return dict(p_kwargs)
        
        raise ValueError(f"Invalid p_kwargs: {p_kwargs}")


    @classmethod
    def format_kwargs_tuple(cls, 
                            p_kwargs: None | Dict[str,Any] | Tuple[Any,Any]  = None
                            ) -> Optional[Tuple[Any,Any]]:
        

        if p_kwargs is None:
            return None
        
        if isinstance(p_kwargs, dict):
            return tuple(sorted(p_kwargs.items()))
        
        if isinstance(p_kwargs, tuple):
            return p_kwargs
        
        raise ValueError(f"Invalid p_kwargs: {p_kwargs}")


    @classmethod
    def format_config_file_list(cls, 
                                 config_files: Optional[Union[UPath, str, List[UPath|str], Tuple[UPath|str]]]  = None
                                 ) -> Optional[List[UPath|str]]:
        
        if config_files is None:
            return None
        
        if isinstance(config_files, (list, tuple)):
            mutable_config_files = list(sorted(set(config_files)))
        else:
            mutable_config_files = [config_files]
        
        return mutable_config_files


    @classmethod
    def format_config_file_tuple(cls, 
                                     config_files: Optional[Union[UPath, str, List[UPath|str], Tuple[UPath|str]]]  = None
                                     ) -> Optional[Tuple[UPath|str]]:

        if config_files is None:
            return None
        
        hashable_config_files: Optional[Tuple[UPath|str]] = None
        if isinstance(config_files, tuple):
            hashable_config_files = config_files
        elif isinstance(config_files, list):
            sorted_config_files: List[UPath | str] = sorted(set(config_files))

            hashable_config_files = tuple(sorted_config_files)
        elif isinstance(config_files, (str, UPath)):
            hashable_config_files = (config_files,)
        else:
            raise ValueError(f"Invalid config_files: {config_files}")
        
        return hashable_config_files


    #Extraction from immutable settings parameters

    @classmethod
    def extract_settings_parameters(cls, settings_parameters: SettingsParameters) -> dict[str, Any]:

        namespace = settings_parameters.namespace or cls.default_namespace
        config_files_mutable:   Optional[List[UPath | str]] =   cls.format_config_file_list(config_files=settings_parameters.config_files) if settings_parameters.config_files else None
        kwargs_mutable:         Optional[dict[str, Any]] =      cls.format_kwargs_dict(p_kwargs=settings_parameters.kwargs) if settings_parameters.kwargs else None

        # Construct and return the original dictionary structure
        return {
            "namespace":    namespace, 
            "config_files": config_files_mutable,
            "kwargs":       kwargs_mutable
        }

    @classmethod
    def extract_namespace_from_settings_parameters(cls, settings_parameters: SettingsParameters) -> Optional[str]:

        mutable_parameters: dict[str, Any] = cls.extract_settings_parameters(settings_parameters=settings_parameters)

        return mutable_parameters["namespace"]

    @classmethod
    def extract_config_files_from_settings_parameters(cls, settings_parameters: SettingsParameters) -> Optional[List[UPath|str]]:

        mutable_parameters: dict[str, Any] = cls.extract_settings_parameters(settings_parameters=settings_parameters)

        return mutable_parameters["config_files"]

    @classmethod
    def extract_kwargs_from_settings_parameters(cls, settings_parameters: SettingsParameters) -> Optional[dict[str, Any]]:

        mutable_parameters: dict[str, Any] = cls.extract_settings_parameters(settings_parameters=settings_parameters)

        return mutable_parameters["kwargs"]

    @classmethod
    def get_platform_slash(cls) -> str:

        if platform.system() == "Windows":
            return "\\"
        else:
            return "/"

