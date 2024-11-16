from typing import Optional, Union, List, Any, Tuple, Dict, Type
from upath import UPath

from importlib import import_module

from mountainash_settings.settings_utils import SettingsUtils
from mountainash_settings.settings_parameters import SettingsParameters
from mountainash_settings.base import MountainAshBaseSettings
from .settings_filehandler import SettingsFileHandler

class SettingsManager:
    """
    A manager class for handling multiple instances of application settings.

    Attributes:
        app_settings_objects (dict): A dictionary to store AppSettings objects with their namespaces.
        protected_attributes (list): A list of attributes that are protected from being overwritten.
        reserved_kwargs (set): A set of reserved keyword arguments that are not allowed to be passed to the settings object.
        auth_parameters (SettingsParameters): The parameters needed to create an authentication settings object.

    """

    app_settings_objects: dict[Any, MountainAshBaseSettings] = {}
    protected_attributes: List[str] = ['BATCH_TIER', 'BATCH_VERSION']
    reserved_kwargs = {"_env_file","_env_file_encoding", "_env_prefix","_dummy"}

    auth_parameters: Optional[SettingsParameters] = None


    def __init__(self,
                 auth_parameters: Optional[SettingsParameters] = None
                 ) -> None:
        
        self.auth_parameters = auth_parameters


    # @classmethod
    def validate_kwargs_keys(self, 
                             settings_class:    Type[MountainAshBaseSettings],                             
                             kwargs:            Optional[Dict[str, Any]]=None, 
        ) -> None:
        """
        Combines multiple dictionaries or sets and checks if a comparison dictionary or set
        has elements not present in the combined inputs. Returns a set of unique elements.

        Args:
            settings_class (Type[MountainAshBaseSettings]): The settings class to be used.
            kwargs (Dict[str, Any]): The keyword arguments to be combined.

        Raises:
            ValueError: If the comparison dictionary has elements not present in the combined inputs.
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
        """
        
        Validates that the namespace is already initialised and that the parameters have not changed.

        Args:
            settings_namespace (str): The namespace for the configuration.
            config_files (Union[UPath, List[UPath]]): The configuration file or list of configuration files.
            kwargs (Dict[str, Any]): The keyword arguments to be combined.
        Raises:
            ValueError: If the namespace is already initialised and the parameters have changed.
        """

        
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
            settings_namespace (str): The namespace for the configuration.
            settings_class (Type[MountainAshBaseSettings]): The settings class to be used.
            config_files (Union[UPath, List[UPath]]): The configuration file or list of configuration files.
            kwargs (Dict[str, Any]): The keyword arguments to be combined.
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

            # Process config files
            config_files_sorted = SettingsFileHandler.separate_config_files(config_files)
            
            # Validate config files exist
            SettingsFileHandler.validate_config_files_exist(config_files_sorted.env_files)
            SettingsFileHandler.validate_config_files_exist(config_files_sorted.yaml_files)
            SettingsFileHandler.validate_config_files_exist(config_files_sorted.toml_files)
           
            ### HANDLE KWARGS ###
            self.validate_kwargs_keys(settings_class=settings_class, kwargs=kwargs)

            #Create the Settings object
            settings_class_ref: Type[MountainAshBaseSettings] = getattr(import_module(name=settings_class.__module__), settings_class.__name__)
            obj_settings = settings_class_ref(                
                                              SETTINGS_SOURCE_ENV_FILES=config_files_sorted.env_files,
                                              SETTINGS_SOURCE_YAML_FILES=config_files_sorted.yaml_files,
                                              SETTINGS_SOURCE_TOML_FILES=config_files_sorted.toml_files,
                                              SETTINGS_NAMESPACE=settings_namespace, 
                                              SETTINGS_CLASS = settings_class_ref, 
                                              SETTINGS_CLASS_NAME = settings_class.__name__, 
                                              **kwargs)

            self.app_settings_objects[settings_namespace] = obj_settings

        return obj_settings

 
    # @classmethod
    def is_namespace_initialised(self, settings_namespace: str) -> bool:
        """
        Checks if the namespace is already initialised.
        Args:
            settings_namespace (str): The namespace for the configuration.
        Returns:
            bool: True if the namespace is already initialised, False otherwise.
        Raises:
            ValueError: If the namespace is not found in the app_settings_objects dictionary.
        """

        #check if the namespace is already initialised by looking at the keys in the app_settings_objects dict
        return settings_namespace in self.app_settings_objects.keys()


    # @classmethod
    def get_config_object(self,settings_namespace: str) -> MountainAshBaseSettings:
        """
        Gets the configuration object for a given namespace.
        Args:
            settings_namespace (str): The namespace for the configuration.
        Returns:
            MountainAshBaseSettings: The configuration object for the given namespace.
        Raises:
            ValueError: If the configuration object is is not an MountainAshBaseSettings object.
        """

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
        """
        Gets the existing configuration object for a given namespace.
        Args:
            settings_namespace (str): The namespace for the configuration.
            kwargs (Dict[str, Any]): The keyword arguments to be combined.
        Returns:
            MountainAshBaseSettings: The configuration object for the given namespace.
        """

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

        """
        Creates a new configuration object for a given namespace.

        Args:
            settings_namespace (str): The namespace for the configuration.
            settings_class (Type[MountainAshBaseSettings]): The settings class to be used.
            config_files (Union[UPath, List[UPath]]): The configuration file or list of configuration files.
            kwargs (Dict[str, Any]): The keyword arguments to be combined.

        Returns:
            MountainAshBaseSettings: The configuration object for the given namespace.
        
        """


        print(f"Initialising new config via get_new_config(): {settings_namespace}")

        obj_settings: MountainAshBaseSettings = self.init_config(settings_namespace=settings_namespace, 
                                                                 settings_class=settings_class, 
                                                                 config_files=config_files,  **kwargs)

        if isinstance(obj_settings, MountainAshBaseSettings):
            return obj_settings


 
    def get_config(self,
                settings_namespace: str,
                settings_class:     Optional[Type[MountainAshBaseSettings]] = MountainAshBaseSettings,  
                config_files: Optional[Union[UPath, str, List[UPath|str], Tuple[UPath|str]]]  = None,
                **kwargs) -> MountainAshBaseSettings:
                    
        """
        
        Gets the configuration object for a given namespace. If the namespace is not initialised, it will create a new configuration object.
        
        Args:
            settings_namespace (str): The namespace for the configuration.
            settings_class (Type[MountainAshBaseSettings]): The settings class to be used.
            config_files (Union[UPath, List[UPath]]): The configuration file or list of configuration files.
            kwargs (Dict[str, Any]): The keyword arguments to be combined.

        Returns:
            MountainAshBaseSettings: The configuration object for the given namespace.

        Raises:
            ValueError: If the settings_class is empty.
            
        """

        # First step is the namespace only
        if settings_namespace is None:
            raise ValueError("get_config(): settings_namespace cannot be empty.")

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


