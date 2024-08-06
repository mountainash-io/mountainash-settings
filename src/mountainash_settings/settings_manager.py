from typing import Optional, Union, List, Any, Tuple, Dict, Type
from upath import UPath
import os 

from importlib import import_module

from mountainash_settings.settings_utils import SettingsUtils
from mountainash_settings.settings_parameters import SettingsParameters
from mountainash_settings.base_settings import MountainAshBaseSettings

class SettingsManager:
    """
    A manager class for handling multiple instances of application settings.

    Attributes:
        app_settings_objects (dict): A dictionary to store AppSettings objects with their namespaces.
        default_namespace (str): The default namespace for the application settings.

    """

    app_settings_objects: dict[Any, MountainAshBaseSettings] = {}
    protected_attributes: List[str] = ['BATCH_TIER', 'BATCH_VERSION']
    reserved_kwargs = {"_env_file","_env_file_encoding", "_env_prefix","_dummy"}

    auth_parameters: Optional[SettingsParameters] = None


    def __init__(self,
                 auth_parameters: Optional[SettingsParameters] = None
                 ) -> None:
        
        self.auth_parameters = auth_parameters


    # # @classmethod
    def validate_config_files_exist(self, 
                                    config_files: Optional[Union[UPath, str, List[UPath|str], Tuple[UPath|str]]] = None
                                    ) -> None:
        
        config_files_list = SettingsUtils.format_config_file_list(config_files=config_files)

        if config_files_list:

            for config_file_temp in config_files_list:
                
                #Only works for local files
                if not os.path.exists(path=config_file_temp):
                    raise FileNotFoundError(f"Config file {config_file_temp} not found.")
                    
                print(f"Config file found: {config_file_temp}")



    # @classmethod
    def validate_kwargs_keys(self, 
                             settings_class:    Type[MountainAshBaseSettings],                             
                             kwargs:            Optional[Dict[str, Any]]=None, 
        ) -> None:
        """
        Combines multiple dictionaries or sets and checks if a comparison dictionary or set
        has elements not present in the combined inputs. Returns a set of unique elements.

        :param inputs_to_combine: Variable number of dictionaries or sets to combine.
        :param comparison_input: Dictionary or set to be checked against the combined inputs.
        :return: Set of unique elements in comparison_input or an error message if input is invalid.
        """
        # Build a set of all keys/elements from the inputs to be combined

        if kwargs:
            combined_elements: set = self.reserved_kwargs

            valid_setting_kwargs = SettingsUtils.get_valid_setting_kwargs(p_kwargs=kwargs, settings_class=settings_class)
            if valid_setting_kwargs:
                combined_elements.update(valid_setting_kwargs.keys())

            # Create a set of keys from the kwargs dictionary
            kwargs_elements = set(kwargs.keys())

            # Find the unique elements in the comparison input
            unique_elements = kwargs_elements - combined_elements

            if len(unique_elements) > 0:
                raise ValueError(f"Invalid kwargs provided: {unique_elements}")


        
    # @classmethod
    def validate_init_existing_namespace(self, 
                    settings_namespace: str, 
                    config_files: Optional[Union[UPath, str, List[UPath|str], Tuple[UPath|str]]]  = None,
                    **kwargs) -> None:
        
        #This will raise an error if not found
        obj_settings: MountainAshBaseSettings = self.get_config_object(settings_namespace=settings_namespace)

        existing_config_files = SettingsUtils.format_config_file_list(config_files=obj_settings.SETTINGS_SOURCE_ENV_FILES)
        existing_kwargs = obj_settings.SETTINGS_SOURCE_KWARGS

        new_config_files = SettingsUtils.format_config_file_list(config_files=config_files)
        new_kwargs = SettingsUtils.format_kwargs_dict(p_kwargs=kwargs)

        if (config_files and new_config_files != existing_config_files)  or (new_kwargs and new_kwargs != existing_kwargs):
            config_file_message = f" Config files {new_config_files} were provided. Previously initialised with config files {existing_config_files}."
            kwargs_message = f" Kwargs {new_kwargs} were provided. Previously initialised with kwargs {existing_kwargs}."
            raise ValueError(f"Namespace '{settings_namespace}' is already initialised. {config_file_message} {kwargs_message}")

        print(f"Warning: Namespace '{settings_namespace}' is already initialised. The parameters have not changed.")



    # @classmethod
    def init_config(self, 
                    settings_namespace: str, 
                    settings_class:     Type[MountainAshBaseSettings],                    
                    config_files: Optional[Union[UPath, str, List[UPath|str], Tuple[UPath|str]]]  = None,
                    **kwargs) -> MountainAshBaseSettings:
        """
        Initializes the configuration for a given namespace.

        Args:
            namespace (str): The namespace for the configuration.
            config_files (Union[UPath, List[UPath]]): The configuration file or list of configuration files.
        """


        if not settings_namespace:
            raise ValueError("settings_namespace cannot be empty.")

        if not settings_class:
            raise ValueError("settings_class cannot be empty.")


        #Check if the namespace is already initialised
        if self.is_namespace_initialised(settings_namespace=settings_namespace):

            #If it was already initialised, why are we trying to re-initialse it? Fail if parameters have changed. Pass if the same, but with a warning.
            self.validate_init_existing_namespace(settings_namespace=settings_namespace, config_files=config_files, **kwargs)
            
            #Get the existing settings object
            obj_settings: MountainAshBaseSettings = self.get_config_object(settings_namespace=settings_namespace)

        #Otherwise We have a new config to create
        else:
            ### HANDLE CONFIG FILES ###

            config_files_list: Optional[List[UPath | str]] = SettingsUtils.format_config_file_list(config_files=config_files)
            self.validate_config_files_exist(config_files=config_files_list)            
            
            ### HANDLE KWARGS ###
            self.validate_kwargs_keys(settings_class=settings_class, kwargs=kwargs)

            #Create the Settings object
            settings_class_ref: Type[MountainAshBaseSettings] = getattr(import_module(name=settings_class.__module__), settings_class.__name__)
            obj_settings = settings_class_ref(                
                                              SETTINGS_SOURCE_ENV_FILES =config_files_list,                                               
                                            #   _env_file=config_files_list, 
                                              SETTINGS_NAMESPACE=settings_namespace, 
                                              SETTINGS_CLASS = settings_class_ref, 
                                              SETTINGS_CLASS_NAME = settings_class.__name__, 
                                              **kwargs)

            self.app_settings_objects[settings_namespace] = obj_settings

        return obj_settings

 
    # @classmethod
    def is_namespace_initialised(self, settings_namespace: str) -> bool:

        #check if the namespace is already initialised by looking at the keys in the app_settings_objects dict
        return settings_namespace in self.app_settings_objects.keys()


    # @classmethod
    def get_config_object(self,settings_namespace: str) -> MountainAshBaseSettings:

        obj_settings: Optional[MountainAshBaseSettings] = self.app_settings_objects.get(settings_namespace, None)

        if isinstance(obj_settings, MountainAshBaseSettings):
            return obj_settings
        else:
            raise ValueError(f"Configuration for namespace '{settings_namespace}' found, but is not an MountainAshBaseSettings object.")


    # @classmethod
    def get_existing_config(self,
                settings_namespace: str,
                #config_files: Optional[Union[UPath, str, List[UPath|str], Tuple[UPath|str]]]  = None,
                **kwargs) -> MountainAshBaseSettings:

        print(f"Getting existing config via get_existing_config(): {settings_namespace}")

        # Get the existing settings object
        obj_settings: MountainAshBaseSettings = self.get_config_object(settings_namespace=settings_namespace)       
        settings_class: Type = obj_settings.SETTINGS_CLASS

        # Overwrite the settings with valid runtime kwargs
        new_kwargs: Dict[Any, Any] | None = SettingsUtils.get_valid_setting_kwargs(p_kwargs=kwargs, settings_class=settings_class)
        merged_kwargs: Dict[str, Any] | None = SettingsUtils.resolve_kwargs(new_kwargs=new_kwargs,
                                                    original_kwargs=obj_settings.SETTINGS_SOURCE_KWARGS)

        #Is this correct? 
        if merged_kwargs and merged_kwargs != obj_settings.SETTINGS_SOURCE_KWARGS:
            print(f"Creating a copy of settings for namespace '{settings_namespace}' with kwargs: {merged_kwargs}. Original kwargs {obj_settings.SETTINGS_SOURCE_KWARGS}")
            #This is a localised update with kwargs. Not a change to the original
            obj_settings = obj_settings.model_copy()
            obj_settings.update_settings_from_dict(settings_dict=merged_kwargs)

        return obj_settings

    # @classmethod
    def get_new_config(self,
                settings_namespace: str,
                settings_class:     Type[MountainAshBaseSettings],  
                config_files: Optional[Union[UPath, str, List[UPath|str], Tuple[UPath|str]]]  = None,
                **kwargs) -> MountainAshBaseSettings:    

        print(f"Initialising new config via get_new_config(): {settings_namespace}")

        obj_settings: MountainAshBaseSettings = self.init_config(settings_namespace=settings_namespace, 
                                                                 settings_class=settings_class, 
                                                                 config_files=config_files,  **kwargs)

        if isinstance(obj_settings, MountainAshBaseSettings):
            return obj_settings
        else:
            raise ValueError(f"Configuration for namespace '{settings_namespace}' created, but is not a MountainAshBaseSettings object.")        


 
    def get_config(self,
                settings_namespace: str,
                settings_class:     Optional[Type[MountainAshBaseSettings]] = None,  
                config_files: Optional[Union[UPath, str, List[UPath|str], Tuple[UPath|str]]]  = None,
                **kwargs) -> MountainAshBaseSettings:
                    
        # First step is the namespace only
        if settings_namespace is None:
            raise ValueError("get_config(): settings_namespace cannot be empty.")
            # settings_namespace = SettingsUtils.default_namespace

        # Check if the namespace is already initialised
        if self.is_namespace_initialised(settings_namespace=settings_namespace):

            # Get the existing settings object
            obj_settings: MountainAshBaseSettings = self.get_existing_config(settings_namespace=settings_namespace, **kwargs)

        else:
            if not settings_class:
                raise ValueError(f"Settings class not provided for namespace '{settings_namespace}'.")

            # Create a new one
            obj_settings = self.get_new_config(settings_namespace=settings_namespace, settings_class=settings_class, config_files=config_files, **kwargs)

        if not isinstance(obj_settings, MountainAshBaseSettings):
            raise ValueError(f"Configuration for namespace '{settings_namespace}' not found.")

        return obj_settings


