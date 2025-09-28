from typing import Optional, Union, List, Any, Dict, Type, Tuple, TypeVar
from upath import UPath
from string import Formatter
from importlib import import_module

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict, PydanticBaseSettingsSource, TomlConfigSettingsSource, YamlConfigSettingsSource, JsonConfigSettingsSource

from mountainash_settings.settings_parameters import SettingsFileHandler, SettingsParameters, SettingsUtils, SettingsFiles
from mountainash_settings.settings_cache import get_settings #as func_get_settings

# T = TypeVar('T', bound='BaseSettings')
T = TypeVar('T', BaseSettings, 'MountainAshBaseSettings')

class MountainAshBaseSettings(BaseSettings):

    model_config = SettingsConfigDict(
            extra="ignore",
            validate_default=False,
            arbitrary_types_allowed=True,
            # validate_assignment=True,
            # validate_assignment=False,

        )

    #Tracablility and repeatability
    SETTINGS_NAMESPACE: str =                                         Field(default=None)
    SETTINGS_CLASS: Type =                                            Field(default=None)
    SETTINGS_CLASS_NAME: str =                                        Field(default=None)

    SETTINGS_SOURCE_ENV_FILES: Optional[Union[Any, str, List[Any|str]]] =       Field(default=None)
    SETTINGS_SOURCE_ENV_PREFIX: Optional[str] =                                 Field(default=None)
    SETTINGS_SOURCE_YAML_FILES: Optional[Union[Any, str, List[Any|str]]] =      Field(default=None)
    SETTINGS_SOURCE_TOML_FILES: Optional[Union[Any, str, List[Any|str]]] =      Field(default=None)
    SETTINGS_SOURCE_JSON_FILES: Optional[Union[Any, str, List[Any|str]]] =      Field(default=None)
    SETTINGS_SOURCE_KWARGS: Optional[Dict[str,Any]] =                           Field(default=None)
    SETTINGS_SOURCE_SECRETS_DIR: Optional[Dict[str,Any]] =                      Field(default=None)


    # protected_attributes: List[str] = ['BATCH_TIER', 'BATCH_VERSION']
    # reserved_kwargs = {"_env_file","_env_file_encoding", "_env_prefix"}


    def __init__(self,
                 config_files:          Optional[str|UPath|List[str|UPath]|Tuple[str|UPath]] = None,
                 settings_parameters:   Optional[SettingsParameters] = None,
                 **kwargs) -> None:


        # Create a baseline settings parameters object
        local_settings_params = SettingsParameters.create(
            settings_class=self.__class__,
            config_files=config_files,
            **kwargs
        )

        if settings_parameters is not None:
            local_settings_params = SettingsUtils.merge_settings_parameter_objects(settings_parameters, local_settings_params)

        obj_config_files: SettingsFiles = SettingsFileHandler.separate_config_files(local_settings_params.config_files)

        # Validate config files exist
        SettingsFileHandler.validate_config_files_exist(obj_config_files.env_files)
        SettingsFileHandler.validate_config_files_exist(obj_config_files.yaml_files)
        SettingsFileHandler.validate_config_files_exist(obj_config_files.toml_files)
        SettingsFileHandler.validate_config_files_exist(obj_config_files.json_files)

        # Handle attribute kwargs
        valid_pydantic_modelconfig_kwargs: Dict[str, Any] = local_settings_params.get_pydantic_modelconfig_kwargs()
        valid_attribute_kwargs: Dict[str, Any] =            local_settings_params.get_attribute_settings_kwargs(settings_class=self.__class__)
        valid_pydantic_kwargs: Dict[str, Any] =             local_settings_params.get_pydantic_settings_kwargs()


        # Handle non env config files via model_config
        self.model_config["yaml_file"] = obj_config_files.yaml_files or None
        self.model_config["toml_file"] = obj_config_files.toml_files or None
        self.model_config["json_file"] = obj_config_files.json_files or None

        # Handle model_config kwargs
        self.model_config.update(**valid_pydantic_modelconfig_kwargs)

        # NOTE: All that has happened before now is prior to calling the init on Base Settings!
        #Now we initialise the values!
        super().__init__(   _case_sensitive=valid_pydantic_kwargs.get('_case_sensitive', True),
                            _nested_model_default_partial_update=valid_pydantic_kwargs.get('_nested_model_default_partial_update', False),
                            _env_prefix=            local_settings_params.env_prefix or valid_pydantic_kwargs.get('_env_prefix', None),
                            _env_file=              obj_config_files.env_files or valid_pydantic_kwargs.get('_env_file', None),
                            _env_file_encoding =    valid_pydantic_kwargs.get('_env_file_encoding', 'utf-8'),
                            _env_ignore_empty =     valid_pydantic_kwargs.get('_env_ignore_empty', True),
                            _env_nested_delimiter = valid_pydantic_kwargs.get('_env_nested_delimiter', None),
                            _env_parse_none_str =   valid_pydantic_kwargs.get('_env_parse_none_str', "None"),
                            _env_parse_enums =      valid_pydantic_kwargs.get('_env_parse_enums', True),
                            _secrets_dir=           local_settings_params.secrets_dir or valid_pydantic_kwargs.get('_secrets_dir', None),
                            **valid_attribute_kwargs
                        )


        #Update all vals from valid kwargs
        self.update_settings_from_dict(settings_dict=valid_attribute_kwargs)

        setattr(self, "SETTINGS_NAMESPACE",             local_settings_params.namespace)
        setattr(self, "SETTINGS_CLASS",                 local_settings_params.settings_class or MountainAshBaseSettings)
        setattr(self, "SETTINGS_CLASS_NAME",            local_settings_params.settings_class.__name__ if local_settings_params.settings_class else "MountainAshBaseSettings")
        setattr(self, "SETTINGS_SOURCE_ENV_PREFIX",     local_settings_params.env_prefix)
        setattr(self, "SETTINGS_SOURCE_ENV_FILES",      obj_config_files.env_files)
        setattr(self, "SETTINGS_SOURCE_YAML_FILES",     obj_config_files.yaml_files)
        setattr(self, "SETTINGS_SOURCE_TOML_FILES",     obj_config_files.toml_files)
        setattr(self, "SETTINGS_SOURCE_JSON_FILES",     obj_config_files.json_files)
        setattr(self, "SETTINGS_SOURCE_SECRETS_DIR",    local_settings_params.secrets_dir)

        # Initialise templated variables
        self.post_init()


    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        return ( init_settings,
                env_settings,
                dotenv_settings,
                YamlConfigSettingsSource(settings_cls),
                TomlConfigSettingsSource(settings_cls),
                JsonConfigSettingsSource(settings_cls),
                file_secret_settings
        )

    @classmethod
    # @abstractmethod
    def get_settings(cls,
                    settings_parameters:   Optional[SettingsParameters] = None,
                    settings_class:        Optional[Type[T]] = None,
                    settings_namespace:    Optional[str] = None,
                    config_files:          Optional[Union[UPath, str, List[UPath|str]]]  = None,
                    env_prefix:            Optional[str] = None,
                    **kwargs

                     ) -> Any:
        pass

        if settings_class is None:
            class_module = cls.__module__
            class_name = cls.__name__
            settings_class = getattr(import_module(name=class_module), class_name)


        settings_instance: Any =  get_settings(
                                    settings_parameters = settings_parameters,
                                    settings_class = settings_class,
                                    settings_namespace = settings_namespace,
                                    config_files = config_files,
                                    env_prefix=env_prefix,
                                    **kwargs
                            )

        if not isinstance(settings_instance, cls):
            raise TypeError(
                f"Created instance of type {type(settings_instance).__name__} "
                f"but expected {cls.__name__} when calling {cls.__name__}.get_settings()"
            )

        return settings_instance


    def __hash__(self) -> int:
        """
        Hash the settings object based on the settings namespace, class name, and source kwargs.

        """

        return hash((self.SETTINGS_NAMESPACE,
                     self.SETTINGS_CLASS_NAME,
                     tuple(self.SETTINGS_SOURCE_ENV_FILES) if self.SETTINGS_SOURCE_ENV_FILES else None,
                     tuple(self.SETTINGS_SOURCE_ENV_PREFIX) if self.SETTINGS_SOURCE_ENV_PREFIX else None,
                     tuple(self.SETTINGS_SOURCE_YAML_FILES) if self.SETTINGS_SOURCE_YAML_FILES else None,
                     tuple(self.SETTINGS_SOURCE_TOML_FILES) if self.SETTINGS_SOURCE_TOML_FILES else None,
                     tuple(self.SETTINGS_SOURCE_JSON_FILES) if self.SETTINGS_SOURCE_JSON_FILES else None,
                    #  self.SETTINGS_SOURCE_KWARGS
                     ))


    def _build_template_mapping(self, template_str: str) -> Dict[str, Any]:
        """Build field mapping for template formatting."""
        mapping = {}
        for _, field_name, _, _ in Formatter().parse(template_str):
            if field_name:
                if hasattr(self, field_name):
                    mapping[field_name] = getattr(self, field_name)
                else:
                    raise AttributeError(f"The object does not have an attribute named '{field_name}'")
        return mapping

    def init_setting_from_template(self, template_str:str, current_value: Optional[str] = None, reinitialise: bool = False):

        """Initializes a setting value from a template string,
        replacing placeholders with  values from the settings object.

        Args:
            template_str: The template string to parse and format.
            current_value: The current value in the settings object if already set.

        Returns:
            (str) The formatted string from the template.

        Examples:

            template = "my_{BATCH_ID}_file.csv"
            settings.init_setting_from_template(template)
            # Returns: "my_20230101_file.csv" if BATCH_ID is 20230101
        """
        if current_value is not None and reinitialise is False:
            return current_value

        mapping = self._build_template_mapping(template_str)

        return template_str.format(**mapping)


    def format_template_from_settings(self, template_str:str) -> str:

        """Formats a template string with values from the settings object.

        Args:
            template_str: The template string to format.

        Returns:
            The formatted string from the template.

        Examples:

            template = "my_{BATCH_ID}_file.csv"
            settings.format_template_from_settings(template)
            # Returns: "my_20230101_file.csv" if BATCH_ID is 20230101
        """
        mapping = self._build_template_mapping(template_str)

        return template_str.format(**mapping)

    def update_settings_from_dict(self, settings_dict: Optional[dict[str, Any]]) -> None:
        """Updates the settings object with values from a dictionary.

        Args:
            settings_dict: The dictionary of settings to update.
        """

        settings_dict = SettingsUtils.format_kwargs_dict(p_kwargs=settings_dict)

        if settings_dict is None:
            return None

        for key, value in settings_dict.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                raise AttributeError(f"The object does not have an attribute named '{key}'")

        setattr(self, 'SETTINGS_SOURCE_KWARGS', settings_dict)

    def post_init(self, reinitialise: bool = False) -> None:
        """
        Hook for post-initialization processing.

        Called after all settings have been loaded and processed.
        Override in subclasses to add custom initialization logic.

        Args:
            reinitialise: Whether this is a re-initialization call
        """
        pass  # Intentionally empty - hook for subclasses to implement


    def extract_settings_parameters(self) -> SettingsParameters:
        """
        Returns a SettingsParameters object reconstructed from a BaseSettings object.

        Args:
            objSettings (BaseSettings): The settings object.

        Returns:
            SettingsParameters: The settings parameters object
        """

        # combine the config files into a single list
        config_files : List = []
        if self.SETTINGS_SOURCE_ENV_FILES:
            config_files += self.SETTINGS_SOURCE_ENV_FILES
        if self.SETTINGS_SOURCE_YAML_FILES:
            config_files += self.SETTINGS_SOURCE_YAML_FILES
        if self.SETTINGS_SOURCE_TOML_FILES:
            config_files += self.SETTINGS_SOURCE_TOML_FILES
        if self.SETTINGS_SOURCE_JSON_FILES:
            config_files += self.SETTINGS_SOURCE_JSON_FILES


        existing_namespace =        self.SETTINGS_NAMESPACE or None
        existing_config_files =     SettingsUtils.format_config_file_list(config_files=config_files)
        existing_kwargs =           SettingsUtils.format_kwargs_dict(p_kwargs=self.SETTINGS_SOURCE_KWARGS)
        existing_settings_class =   self.SETTINGS_CLASS or None
        existing_env_prefix =       self.SETTINGS_SOURCE_ENV_PREFIX or None

        params: SettingsParameters = SettingsParameters.create(
            namespace= existing_namespace,
            settings_class=     existing_settings_class,
            config_files=       existing_config_files,
            kwargs=             existing_kwargs,
            env_prefix=         existing_env_prefix)

        return params

    # def __getattribute__(self, name):
    #     """
    #     Custom attribute access that handles SecretStr types by automatically extracting their values.

    #     This allows transparent access to secret values through normal property access.
    #     """
    #     # Get the attribute normally first
    #     value = super().__getattribute__(name)

    #     # If it's a SecretStr, return its value instead
    #     if hasattr(value, 'get_secret_value') and callable(getattr(value, 'get_secret_value')):
    #         return value.get_secret_value()

    #     # Otherwise return the original value
    #     return value
