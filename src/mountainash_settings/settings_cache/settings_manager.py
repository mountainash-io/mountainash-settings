from typing import Optional, Any, Type, Dict
from importlib import import_module

from pydantic_settings import BaseSettings

from ..settings_parameters import SettingsParameters, SettingsUtils
from ..settings import MountainAshBaseSettings

class SettingsManager:
    """
    A manager class for handling multiple instances of application settings.

    Attributes:
        settings_object_cache (dict): A dictionary to store AppSettings objects with their namespaces.
        protected_attributes (list): A list of attributes that are protected from being overwritten.
        reserved_kwargs (set): A set of reserved keyword arguments that are not allowed to be passed to the settings object.
        # auth_parameters (SettingsParameters): The parameters needed to create an authentication settings object.

    """

    # protected_attributes: List[str] = ['BATCH_TIER', 'BATCH_VERSION']
    # reserved_kwargs = {"_env_file","_env_file_encoding", "_env_prefix"}

    # auth_parameters: Optional[SettingsParameters] = None
    # settings_object_cache: dict[Any, BaseSettings] = {}

    def __init__(self
                 ) -> None:

        self.settings_object_cache: Dict[Any, MountainAshBaseSettings] = {}


    def get_settings_object(self, settings_parameters: SettingsParameters) -> MountainAshBaseSettings:
        """
        Gets the configuration object for a given set of parameters.

        If the parameters contain runtime override kwargs, returns a copy
        with overrides applied. The cached instance is never mutated.

        Args:
            settings_parameters (SettingsParameters): The parameters for the configuration.
        Returns:
            MountainAshBaseSettings: The configuration object for the given parameters.
        Raises:
            ValueError: If the configuration object is not a MountainAshBaseSettings object.
        """

        obj_settings: Optional[MountainAshBaseSettings] = self.settings_object_cache.get(settings_parameters, None)

        if not isinstance(obj_settings, MountainAshBaseSettings):
            raise ValueError(
                f"Configuration for '{settings_parameters}' found, but is not a "
                f"MountainAshBaseSettings object. Received a {type(obj_settings)}"
            )

        override_kwargs = settings_parameters.get_attribute_settings_kwargs()
        if override_kwargs:
            obj_settings = obj_settings.model_copy()
            obj_settings.update_settings_from_dict(settings_dict=override_kwargs)

        return obj_settings

    # @classmethod
    def is_initialised(self, settings_parameters: SettingsParameters) -> bool:
        """
        Checks if the settings parameters are already initialised in the cache.
        Args:
            settings_parameters (SettingsParameters): The parameters for the configuration.
        Returns:
            bool: True if the settings are already initialised, False otherwise.
        """

        #check if the settings are already initialised by looking at the keys in the settings_object_cache dict
        return settings_parameters in self.settings_object_cache


    # @classmethod
    def get_or_create_settings(self,
                    settings_parameters: SettingsParameters) -> MountainAshBaseSettings:
        """
        Initializes the settings for a given set of parameters.

        Args:
            settings_parameters (SettingsParameters): The settings for the configuration.
        """


        #Check if the namespace is already initialised
        if self.is_initialised(settings_parameters=settings_parameters):
            #Get the existing settings object
            return self.get_settings_object(settings_parameters=settings_parameters)

        #Otherwise We have a new config to create
        else:

            if not settings_parameters.settings_class:
                raise ValueError("settings_parameters.settings_class cannot be empty.")

            # #Create the Settings object
            class_module = settings_parameters.settings_class.__module__
            class_name = settings_parameters.settings_class.__name__
            settings_class_ref: Type[MountainAshBaseSettings] = getattr(import_module(name=class_module), class_name)

            if issubclass(settings_class_ref, MountainAshBaseSettings):
                obj_settings = settings_class_ref(settings_parameters = settings_parameters)

            else:

                settings_kwargs: Dict[str, Any]|None = SettingsUtils.format_kwargs_dict(p_kwargs=settings_parameters.kwargs)
                #Create the settings object with no settings_parameters, but kwargs if they are provided
                if settings_kwargs:
                    obj_settings = settings_class_ref(**settings_kwargs)
                else:
                    obj_settings = settings_class_ref()

            # if not isinstance(obj_settings, BaseSettings):
            #     raise ValueError(f"Configuration for namespace '{settings_parameters.namespace}' found, but obj_settings is not an BaseSettings object. It is of type {type(obj_settings)}")

        self.settings_object_cache[settings_parameters] = obj_settings
        return obj_settings


    # def get_settings(self,
    #             settings_parameters: SettingsParameters,

    #             # settings_namespace: str,
    #             # settings_class:     Optional[Type[BaseSettings]] = BaseSettings,
    #             # config_files: Optional[Union[UPath, str, List[UPath|str], Tuple[UPath|str]]]  = None,
    #             # **kwargs

    #             ) -> BaseSettings:

    #     """

    #     Gets the configuration object for a given namespace. If the namespace is not initialised, it will create a new configuration object.

    #     Args:
    #         settings_namespace (str): The namespace for the configuration.
    #         settings_class (Type[BaseSettings]): The settings class to be used.
    #         config_files (Union[UPath, List[UPath]]): The configuration file or list of configuration files.
    #         kwargs (Dict[str, Any]): The keyword arguments to be combined.

    #     Returns:
    #         BaseSettings: The configuration object for the given namespace.

    #     Raises:
    #         ValueError: If the settings_class is empty.

    #     """

    #     # First step is the namespace only

    #     # Check if the namespace is already initialised
    #     if self.is_initialised(settings_parameters=settings_parameters):

    #         # Get the existing settings object
    #         obj_settings: BaseSettings = self.get_settings_object(settings_parameters=settings_parameters)

    #     else:
    #         # Create a new one
    #         obj_settings = self.init_settings(settings_parameters=settings_parameters)

    #     if not isinstance(obj_settings, BaseSettings):
    #         raise ValueError(f"Configuration for namespace '{settings_parameters.namespace}' not found.")

    #     return obj_settings


    # # @classmethod
    # def get_existing_settings(self,
    #             settings_parameters: SettingsParameters,
    #             # settings_namespace: str,
    #             # #config_files: Optional[Union[UPath, str, List[UPath|str], Tuple[UPath|str]]]  = None,
    #             # **kwargs
    #             ) -> BaseSettings:
    #     """
    #     Gets the existing configuration object for a given namespace.
    #     Args:
    #         settings_namespace (str): The namespace for the configuration.
    #         kwargs (Dict[str, Any]): The keyword arguments to be combined.
    #     Returns:
    #         BaseSettings: The configuration object for the given namespace.
    #     """

    #     print(f"Getting existing config via get_existing_config(): {settings_namespace}")

    #     # Get the existing settings object
    #     obj_settings: BaseSettings = self.get_config_object(settings_namespace=settings_namespace)
    #     settings_class: Type = obj_settings.SETTINGS_CLASS

    #     # Overwrite the settings with valid runtime kwargs
    #     new_kwargs: Dict[Any, Any] | None = SettingsUtils.get_valid_setting_kwargs(p_kwargs=kwargs, settings_class=settings_class)
    #     merged_kwargs: Dict[str, Any] | None = SettingsUtils.resolve_kwargs(new_kwargs=new_kwargs,
    #                                                 original_kwargs=obj_settings.SETTINGS_SOURCE_KWARGS)

    #     #Is this correct?
    #     if merged_kwargs and merged_kwargs != obj_settings.SETTINGS_SOURCE_KWARGS:
    #         print(f"Creating a copy of settings for namespace '{settings_namespace}' with kwargs: {merged_kwargs}. Original kwargs {obj_settings.SETTINGS_SOURCE_KWARGS}")
    #         #This is a localised update with kwargs. Not a change to the original
    #         obj_settings = obj_settings.model_copy()
    #         obj_settings.update_settings_from_dict(settings_dict=merged_kwargs)

    #     return obj_settings

    # # @classmethod
    # def get_new_config(self,
    #             settings_namespace: str,
    #             settings_class:     Type[BaseSettings],
    #             config_files: Optional[Union[UPath, str, List[UPath|str], Tuple[UPath|str]]]  = None,
    #             **kwargs) -> BaseSettings:

    #     """
    #     Creates a new configuration object for a given namespace.

    #     Args:
    #         settings_namespace (str): The namespace for the configuration.
    #         settings_class (Type[BaseSettings]): The settings class to be used.
    #         config_files (Union[UPath, List[UPath]]): The configuration file or list of configuration files.
    #         kwargs (Dict[str, Any]): The keyword arguments to be combined.

    #     Returns:
    #         BaseSettings: The configuration object for the given namespace.

    #     """


    #     print(f"Initialising new config via get_new_config(): {settings_namespace}")

    #     obj_settings: BaseSettings = self.init_config(settings_namespace=settings_namespace,
    #                                                              settings_class=settings_class,
    #                                                              config_files=config_files,  **kwargs)

    #     if isinstance(obj_settings, BaseSettings):
    #         return obj_settings






    # # @classmethod
    # def validate_kwargs_keys(self,
    #                          settings_class:    Type[BaseSettings],
    #                          kwargs:            Optional[Dict[str, Any]]=None,
    #     ) -> None:
    #     """
    #     Combines multiple dictionaries or sets and checks if a comparison dictionary or set
    #     has elements not present in the combined inputs. Returns a set of unique elements.

    #     Args:
    #         settings_class (Type[BaseSettings]): The settings class to be used.
    #         kwargs (Dict[str, Any]): The keyword arguments to be combined.

    #     Raises:
    #         ValueError: If the comparison dictionary has elements not present in the combined inputs.
    #     """
    #     # Build a set of all keys/elements from the inputs to be combined

    #     if kwargs:
    #         combined_elements: set = self.reserved_kwargs

    #         valid_setting_kwargs = SettingsUtils.get_valid_setting_kwargs(p_kwargs=kwargs, settings_class=settings_class)
    #         if valid_setting_kwargs:
    #             combined_elements.update(valid_setting_kwargs.keys())

    #         # Create a set of keys from the kwargs dictionary
    #         kwargs_elements = set(kwargs.keys())

    #         # Find the unique elements in the comparison input
    #         unique_elements = kwargs_elements - combined_elements

    #         if len(unique_elements) > 0:
    #             raise ValueError(f"Invalid kwargs provided: {unique_elements}")



    # # @classmethod
    # def validate_init_existing_namespace(self,
    #                 settings_namespace: str,
    #                 config_files: Optional[Union[UPath, str, List[UPath|str], Tuple[UPath|str]]]  = None,
    #                 env_prefix: Optional[str] = None,
    #                 **kwargs) -> None:
    #     """

    #     Validates that the namespace is already initialised and that the parameters have not changed.

    #     Args:
    #         settings_namespace (str): The namespace for the configuration.
    #         config_files (Union[UPath, List[UPath]]): The configuration file or list of configuration files.
    #         kwargs (Dict[str, Any]): The keyword arguments to be combined.
    #     Raises:
    #         ValueError: If the namespace is already initialised and the parameters have changed.
    #     """


    #     #This will raise an error if not found
    #     obj_settings: BaseSettings = self.get_config_object(settings_namespace=settings_namespace)

    #     existing_config_files = SettingsUtils.format_config_file_list(config_files=obj_settings.SETTINGS_SOURCE_ENV_FILES)
    #     existing_kwargs = obj_settings.SETTINGS_SOURCE_KWARGS
    #     existing_env_prefix = obj_settings.SETTINGS_SOURCE_ENV_PREFIX

    #     new_config_files = SettingsUtils.format_config_file_list(config_files=config_files)
    #     new_kwargs = SettingsUtils.format_kwargs_dict(p_kwargs=kwargs)

    #     if (config_files and new_config_files != existing_config_files)  or (new_kwargs and new_kwargs != existing_kwargs) or (env_prefix and env_prefix != existing_env_prefix):
    #         config_file_message = f" Config files {new_config_files} were provided. Previously initialised with config files {existing_config_files}."
    #         kwargs_message = f" Kwargs {new_kwargs} were provided. Previously initialised with kwargs {existing_kwargs}."
    #         env_prefix_message = f" Env prefix {env_prefix} was provided. Previously initialised with env prefix {existing_env_prefix}."
    #         raise ValueError(f"Namespace '{settings_namespace}' is already initialised. {config_file_message} {kwargs_message} {env_prefix_message}")

    #     print(f"Warning: Namespace '{settings_namespace}' is already initialised. The parameters have not changed.")




    # # @classmethod
    # def init_settings(self,
    #                 settings_parameters: SettingsParameters) -> BaseSettings:
    #                 # settings_namespace: str,
    #                 # settings_class:     Type[BaseSettings],
    #                 # config_files: Optional[Union[UPath, str, List[UPath|str], Tuple[UPath|str]]]  = None,
    #                 # env_prefix: Optional[str] = None,
    #                 # **kwargs) -> BaseSettings:
    #     """
    #     Initializes the configuration for a given namespace.

    #     Args:
    #         settings_namespace (str): The namespace for the configuration.
    #         settings_class (Type[BaseSettings]): The settings class to be used.
    #         config_files (Union[UPath, List[UPath]]): The configuration file or list of configuration files.
    #         kwargs (Dict[str, Any]): The keyword arguments to be combined.
    #     """

    #     # if not settings_namespace:
    #     #     raise ValueError("settings_namespace cannot be empty.")

    #     # if not settings_class:
    #     #     raise ValueError("settings_class cannot be empty.")


    #     #Check if the namespace is already initialised
    #     if self.is_initialised(settings_parameters=settings_parameters):

    #         #If it was already initialised, why are we trying to re-initialse it? Fail if parameters have changed. Pass if the same, but with a warning.
    #         # self.validate_init_existing_namespace(settings_namespace=settings_namespace, config_files=config_files, **kwargs)

    #         #Get the existing settings object
    #         obj_settings: BaseSettings = self.get_config_object(settings_parameters=settings_parameters)

    #     #Otherwise We have a new config to create
    #     else:
    #         ### HANDLE CONFIG FILES ###
    #         #Lets not do it this way!

    #         # Process config files
    #         # config_files_sorted = SettingsFileHandler.separate_config_files(config_files)

    #         # # Validate config files exist
    #         # SettingsFileHandler.validate_config_files_exist(config_files_sorted.env_files)
    #         # SettingsFileHandler.validate_config_files_exist(config_files_sorted.yaml_files)
    #         # SettingsFileHandler.validate_config_files_exist(config_files_sorted.toml_files)

    #         # ### HANDLE KWARGS ###
    #         # self.validate_kwargs_keys(settings_class=settings_class, kwargs=kwargs)

    #         # #Create the Settings object
    #         class_module = settings_parameters.settings_class.__module__
    #         class_name = settings_parameters.settings_class.__name__
    #         settings_class_ref: Type[BaseSettings] = getattr(import_module(name=class_module), class_name)

    #         # #Create the parameters object
    #         # obj_settings_parameters = SettingsParameters.create(
    #         #     namespace = settings_namespace,
    #         #     config_files=config_files,
    #         #     kwargs=kwargs,
    #         #     settings_class=settings_class,
    #         #     env_prefix=env_prefix
    #         # )

    #         #Create the settings object
    #         obj_settings = settings_class_ref(
    #             settings_parameters = settings_parameters
    #         )

    #         # obj_settings = settings_class_ref(
    #         #                                   SETTINGS_SOURCE_ENV_FILES=config_files_sorted.env_files,
    #         #                                   SETTINGS_SOURCE_YAML_FILES=config_files_sorted.yaml_files,
    #         #                                   SETTINGS_SOURCE_TOML_FILES=config_files_sorted.toml_files,
    #         #                                   SETTINGS_NAMESPACE=settings_namespace,
    #         #                                   SETTINGS_CLASS = settings_class_ref,
    #         #                                   SETTINGS_CLASS_NAME = settings_class.__name__,
    #         #                                   **kwargs)

    #         self.settings_object_cache[settings_parameters.__hash__()] = obj_settings

    #     return obj_settings
