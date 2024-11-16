from typing import Optional, Union, List, Any, Dict, Type, Tuple
from upath import UPath

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict, PydanticBaseSettingsSource, TomlConfigSettingsSource, YamlConfigSettingsSource
from string import Formatter
from .settings_filehandler import SettingsFileHandler


class MountainAshBaseSettings(BaseSettings):

    model_config = SettingsConfigDict(
            extra="ignore",
            validate_default=False,
            #validate_assignment=True,
            arbitrary_types_allowed=True
        )

    def __init__(self, 
                 config_files: Optional[str|UPath|List[str|UPath]|Tuple[str|UPath]] = None,
                 _dummy: Optional[bool] = False,
                 **kwargs) -> None:  

        if config_files is not None:

            config_files_sorted = SettingsFileHandler.separate_config_files(config_files)
            
            # # Validate config files exist
            SettingsFileHandler.validate_config_files_exist(config_files_sorted.env_files)
            SettingsFileHandler.validate_config_files_exist(config_files_sorted.yaml_files)
            SettingsFileHandler.validate_config_files_exist(config_files_sorted.toml_files)

            # Check for conflicting kwargs
            if config_files_sorted.env_files is not None and "SETTINGS_SOURCE_ENV_FILES" in kwargs:
                raise ValueError("Cannot specify both env files in config_files and SETTINGS_SOURCE_ENV_FILES in kwargs")

            if config_files_sorted.yaml_files is not None and "SETTINGS_SOURCE_YAML_FILES" in kwargs:
                raise ValueError("Cannot specify both yaml files in config_files and SETTINGS_SOURCE_YAML_FILES in kwargs")

            if config_files_sorted.toml_files is not None and "SETTINGS_SOURCE_TOML_FILES" in kwargs:
                raise ValueError("Cannot specify both toml files in config_files and SETTINGS_SOURCE_TOML_FILES in kwargs")

            #Add to the kwargs
            if config_files_sorted.env_files is not None:
                kwargs["SETTINGS_SOURCE_ENV_FILES"] = config_files_sorted.env_files
            if config_files_sorted.yaml_files is not None:
                kwargs["SETTINGS_SOURCE_YAML_FILES"] = config_files_sorted.yaml_files
            if config_files_sorted.toml_files is not None:
                kwargs["SETTINGS_SOURCE_TOML_FILES"] = config_files_sorted.toml_files

        if not _dummy:

            if kwargs.get("SETTINGS_SOURCE_YAML_FILES", None) is not None:
                self.model_config["yaml_file"] = kwargs.get("SETTINGS_SOURCE_YAML_FILES", None)
            if kwargs.get("SETTINGS_SOURCE_TOML_FILES", None) is not None:
                self.model_config["toml_file"] = kwargs.get("SETTINGS_SOURCE_TOML_FILES", None)

        super().__init__(_case_sensitive=True, 
                            _env_prefix=            kwargs.get("SETTINGS_SOURCE_ENV_PREFIX", None),
                            _env_file=              kwargs.get("SETTINGS_SOURCE_ENV_FILES", None), 
                            _env_file_encoding =    'utf-8',
                            _env_ignore_empty =     True,
                            _env_parse_none_str =   "None",
                            _secrets_dir=           kwargs.get("SETTINGS_SOURCE_SECRETS_DIR", None),
                            # _yaml_file=             kwargs.get("SETTINGS_SOURCE_YAML_FILES", None),
                            # _toml_file=             kwargs.get("SETTINGS_SOURCE_TOML_FILES", None),
                            #**config_kwargs
                        )

        if not _dummy:

            # Handle kwargs via Initialisation
            if kwargs:
                #Remove special flags from the stored kwargs
                kwargs_to_remove = set(["SETTINGS_CLASS", 
                                        "SETTINGS_CLASS_NAME", 
                                        "SETTINGS_NAMESPACE", 
                                        "SETTINGS_SOURCE_ENV_FILES", 
                                        "SETTINGS_SOURCE_ENV_PREFIX",
                                        "SETTINGS_SOURCE_YAML_FILES", 
                                        "SETTINGS_SOURCE_TOML_FILES", 
                                        "SETTINGS_SOURCE_KWARGS", 
                                        "SETTINGS_SOURCE_SECRETS_DIR"])
                
                config_kwargs = {k: v for k, v in kwargs.items() if k not in kwargs_to_remove}

                #Update all vals from valid kwargs                
                self.update_settings_from_dict(config_kwargs)

            setattr(self, "SETTINGS_NAMESPACE", kwargs.get("SETTINGS_NAMESPACE", "DEFAULT"))
            setattr(self, "SETTINGS_CLASS", kwargs.get("SETTINGS_CLASS", MountainAshBaseSettings))
            setattr(self, "SETTINGS_CLASS_NAME", kwargs.get("SETTINGS_CLASS_NAME", "MountainAshBaseSettings"))
            setattr(self, "SETTINGS_SOURCE_ENV_PREFIX", kwargs.get("SETTINGS_SOURCE_ENV_PREFIX", None))
            setattr(self, "SETTINGS_SOURCE_ENV_FILES", kwargs.get("SETTINGS_SOURCE_ENV_FILES", None))
            setattr(self, "SETTINGS_SOURCE_YAML_FILES", kwargs.get("SETTINGS_SOURCE_YAML_FILES", None))
            setattr(self, "SETTINGS_SOURCE_TOML_FILES", kwargs.get("SETTINGS_SOURCE_TOML_FILES", None))
            setattr(self, "SETTINGS_SOURCE_SECRETS_DIR", kwargs.get("SETTINGS_SOURCE_SECRETS_DIR", None))



            # Initialise templated variables
            self.post_init()

        else:
            setattr(self, "SETTINGS_NAMESPACE", "DUMMY")
            setattr(self, "SETTINGS_CLASS", MountainAshBaseSettings)
            setattr(self, "SETTINGS_CLASS_NAME", "MountainAshBaseSettings")

    #Tracablility and repeatability
    SETTINGS_NAMESPACE: str =                                         Field(default=None)
    SETTINGS_CLASS: Type =                                            Field(default=None)
    SETTINGS_CLASS_NAME: str =                                        Field(default=None)

    SETTINGS_SOURCE_ENV_FILES: Optional[Union[Any, str, List[Any|str]]] =       Field(default=None)
    SETTINGS_SOURCE_ENV_PREFIX: Optional[str] =                                 Field(default=None)
    SETTINGS_SOURCE_YAML_FILES: Optional[Union[Any, str, List[Any|str]]] =      Field(default=None)
    SETTINGS_SOURCE_TOML_FILES: Optional[Union[Any, str, List[Any|str]]] =      Field(default=None)
    SETTINGS_SOURCE_KWARGS: Optional[Dict[str,Any]] =                           Field(default=None)
    SETTINGS_SOURCE_SECRETS_DIR: Optional[Dict[str,Any]] =                      Field(default=None)


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
                TomlConfigSettingsSource(settings_cls), 
                YamlConfigSettingsSource(settings_cls),
                # JsonConfigSettingsSource(settings_cls),
                file_secret_settings
        )

    
    def __hash__(self) -> int:
        """
        Hash the settings object based on the settings namespace, class name, and source kwargs.
        
        """

        return hash((self.SETTINGS_NAMESPACE, self.SETTINGS_CLASS_NAME, self.SETTINGS_SOURCE_ENV_FILES, self.SETTINGS_SOURCE_ENV_PREFIX, self.SETTINGS_SOURCE_YAML_FILES, self.SETTINGS_SOURCE_TOML_FILES,self.SETTINGS_SOURCE_KWARGS))

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

        mapping = {}
        for _, field_name, _, _ in Formatter().parse(template_str):

            if field_name:
                if hasattr(self, field_name):
                    mapping[field_name] = getattr(self, field_name)
                else:
                    raise AttributeError(f"The object does not have an attribute named '{field_name}'")
                
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
        mapping = {}

        for _, field_name, _, _ in Formatter().parse(format_string=template_str):

            if field_name:
                if hasattr(self, field_name):
                    mapping[field_name] = getattr(self, field_name)
                else:
                    raise AttributeError(f"The object does not have an attribute named '{field_name}'")
                
        return template_str.format(**mapping)

    def update_settings_from_dict(self, settings_dict: dict[str, Any]) -> None:
        """Updates the settings object with values from a dictionary.

        Args:
            settings_dict: The dictionary of settings to update.
        """
        
        for key, value in settings_dict.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                raise AttributeError(f"The object does not have an attribute named '{key}'")

        setattr(self, 'SETTINGS_SOURCE_KWARGS', settings_dict)

    def post_init(self, reinitialise: bool = False):
        """Post-initialization function to run after the settings object has been initialized."""
        # Set the settings namespace to the class name if not
        pass


