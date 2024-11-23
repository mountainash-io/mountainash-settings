from typing import Optional, Union, List, Any, Dict, Type, Tuple
from mountainash_settings.settings_utils import SettingsUtils
from upath import UPath

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict, PydanticBaseSettingsSource, TomlConfigSettingsSource, YamlConfigSettingsSource, JsonConfigSettingsSource
from string import Formatter
from .settings_filehandler import SettingsFileHandler, ConfigFiles
from .settings_parameters import SettingsParameters

class MountainAshBaseSettings(BaseSettings):

    model_config = SettingsConfigDict(
            extra="ignore",
            validate_default=False,
            #validate_assignment=True,
            arbitrary_types_allowed=True
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
    # reserved_kwargs = {"_env_file","_env_file_encoding", "_env_prefix","_dummy"}


    def __init__(self, 
                 config_files:          Optional[str|UPath|List[str|UPath]|Tuple[str|UPath]] = None,
                 settings_parameters:   Optional[SettingsParameters] = None,
                 _dummy: Optional[bool] = False,
                 **kwargs) -> None:  

        # Create a settings parameters object
        local_settings_params = SettingsParameters.create(config_files=config_files, 
                                                          kwargs = kwargs,
                                                          settings_class=self.__class__,
                                                          )
        #Merge with the settings parameters
        if settings_parameters is not None:
            local_settings_params = SettingsUtils.merge_settings_parameter_objects(settings_parameters, local_settings_params)


        obj_config_files: ConfigFiles = SettingsFileHandler.separate_config_files(local_settings_params.config_files)
        
        # # Validate config files exist
        SettingsFileHandler.validate_config_files_exist(obj_config_files.env_files )
        SettingsFileHandler.validate_config_files_exist(obj_config_files.yaml_files)
        SettingsFileHandler.validate_config_files_exist(obj_config_files.toml_files)
        SettingsFileHandler.validate_config_files_exist(obj_config_files.json_files)

        if not _dummy:
            # Handle non env config files via model_config
            self.model_config["yaml_file"] = obj_config_files.yaml_files or None
            self.model_config["toml_file"] = obj_config_files.toml_files or None
            self.model_config["json_file"] = obj_config_files.json_files or None

        super().__init__(_case_sensitive=True, 
                            _env_prefix=            local_settings_params.env_prefix or None,
                            _env_file=              obj_config_files.env_files or None, 
                            _env_file_encoding =    'utf-8',
                            _env_ignore_empty =     True,
                            _env_parse_none_str =   "None",
                            _secrets_dir=           local_settings_params.secrets_dir or None,
                        )

        if not _dummy:

            #Update all vals from valid kwargs                
            self.update_settings_from_dict(local_settings_params.kwargs)

            setattr(self, "SETTINGS_NAMESPACE",             local_settings_params.namespace)
            setattr(self, "SETTINGS_CLASS",                 local_settings_params.settings_class or MountainAshBaseSettings)
            setattr(self, "SETTINGS_CLASS_NAME",            local_settings_params.settings_class.__name__ or "MountainAshBaseSettings")
            setattr(self, "SETTINGS_SOURCE_ENV_PREFIX",     local_settings_params.env_prefix)
            setattr(self, "SETTINGS_SOURCE_ENV_FILES",      obj_config_files.env_files)
            setattr(self, "SETTINGS_SOURCE_YAML_FILES",     obj_config_files.yaml_files)
            setattr(self, "SETTINGS_SOURCE_TOML_FILES",     obj_config_files.toml_files)
            setattr(self, "SETTINGS_SOURCE_JSON_FILES",     obj_config_files.json_files)
            setattr(self, "SETTINGS_SOURCE_SECRETS_DIR",    local_settings_params.secrets_dir)

            # Initialise templated variables
            self.post_init()

        else:
            setattr(self, "SETTINGS_NAMESPACE", "DUMMY")
            setattr(self, "SETTINGS_CLASS", MountainAshBaseSettings)
            setattr(self, "SETTINGS_CLASS_NAME", "MountainAshBaseSettings")




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

    
    def __hash__(self) -> int:
        """
        Hash the settings object based on the settings namespace, class name, and source kwargs.
        
        """

        return hash((self.SETTINGS_NAMESPACE, 
                     self.SETTINGS_CLASS_NAME, 
                     self.SETTINGS_SOURCE_ENV_FILES, 
                     self.SETTINGS_SOURCE_ENV_PREFIX, 
                     self.SETTINGS_SOURCE_YAML_FILES, 
                     self.SETTINGS_SOURCE_TOML_FILES,
                     self.SETTINGS_SOURCE_JSON_FILES,
                     self.SETTINGS_SOURCE_KWARGS))

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
        
        settings_dict = SettingsUtils.format_kwargs_dict(p_kwargs=settings_dict)


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
        existing_config_files =     self.format_config_file_list(config_files=config_files)
        existing_kwargs =           self.format_kwargs_dict(p_kwargs=self.SETTINGS_SOURCE_KWARGS)
        existing_settings_class =   self.SETTINGS_CLASS or None
        existing_env_prefix =       self.SETTINGS_SOURCE_ENV_PREFIX or None

        params: SettingsParameters = SettingsParameters.create(
            settings_namespace= existing_namespace,
            config_files=       existing_config_files,
            kwargs=             existing_kwargs,
            settings_class=     existing_settings_class,
            env_prefix=         existing_env_prefix)
            
        return params        

