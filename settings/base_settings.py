from typing import Optional, Union, List, Any, Tuple, Dict, Type

# from pydantic import BaseModel, BaseSettings
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from string import Formatter
from pydantic.dataclasses import dataclass


class MountainAshBaseSettings(BaseSettings):

    model_config = SettingsConfigDict(
            extra="ignore",
            validate_default=False,
            # validate_assignment=True
            arbitrary_types_allowed=True

        )

    def __init__(self, 
                 _env_file=None, 
                 _env_file_encoding='utf-8', 
                 _env_prefix='',
                 _dummy=False,

                 **kwargs) -> None:  

        super().__init__(_case_sensitive=   True,
                         _env_file=         _env_file, 
                         _env_file_encoding=_env_file_encoding,
                         _env_prefix=       _env_prefix,
                         )
        
        
        if not _dummy:

            # Set attributes from kwargs - including SETTINGS_NAMESPACE
            self.__dict__.update(kwargs)                    

            if kwargs:
                # remove 'SETTINGS_NAMESPACE' from the kwargs
                kwargs_to_remove = set(["SETTINGS_CLASS", "SETTINGS_CLASS_NAME", "SETTINGS_NAMESPACE"])

                kwargs = {k: v for k, v in kwargs.items() if k not in kwargs_to_remove}
                setattr(self, "SETTINGS_SOURCE_KWARGS", kwargs)

            if _env_file:
                setattr(self, "SETTINGS_SOURCE_ENV_FILES", _env_file)

            if _env_prefix:
                setattr(self, "SETTINGS_SOURCE_ENV_PREFIX", _env_prefix)

            # Initialise templated variables
            self.post_init()

            print(f"Settings Initialised: SETTINGS_NAMESPACE: {self.SETTINGS_NAMESPACE}, SETTINGS_CLASS_NAME: {self.SETTINGS_CLASS_NAME},  SETTINGS_SOURCE_ENV_FILES: {self.SETTINGS_SOURCE_ENV_FILES}, SETTINGS_SOURCE_KWARGS: {self.SETTINGS_SOURCE_KWARGS}, SETTINGS_SOURCE_ENV_PREFIX: {self.SETTINGS_SOURCE_ENV_PREFIX}")
        else:
            setattr(self, "SETTINGS_NAMESPACE", "DUMMY")
            setattr(self, "SETTINGS_CLASS", MountainAshBaseSettings)
            setattr(self, "SETTINGS_CLASS_NAME", "MountainAshBaseSettings")

    #Tracablility and repeatability
    SETTINGS_NAMESPACE: str =                                         Field(default=None)
    SETTINGS_CLASS: Type =                                            Field(default=None)
    SETTINGS_CLASS_NAME: str =                                        Field(default=None)

    # SETTINGS_SOURCE_ENV_FILES: Optional[Union[UPath, str, List[UPath|str]]] =   Field(default=None)
    SETTINGS_SOURCE_ENV_FILES: Optional[Union[Any, str, List[Any|str]]] =       Field(default=None)
    SETTINGS_SOURCE_ENV_PREFIX: Optional[str] =                                 Field(default=None)
    SETTINGS_SOURCE_KWARGS: Optional[Dict[str,Any]] =                           Field(default=None)

    #TODO: Create dictionary that indicates the source of each variable
    # default, env_file, kwarg, env_var, etc
    
    def __hash__(self) -> int:
        return hash((self.SETTINGS_NAMESPACE, self.SETTINGS_CLASS_NAME, self.SETTINGS_SOURCE_ENV_FILES, self.SETTINGS_SOURCE_ENV_PREFIX, self.SETTINGS_SOURCE_KWARGS))

    def init_setting_from_template(self, template_str:str, current_value: Optional[str] = None ):

        """Initializes a setting value from a template string, 
        replacing placeholders with  values from the settings object.

        Args:
            template_str: The template string to parse and format.
            current_value: The current value in the settings object if already set.

        Returns:
            The formatted string from the template.

        Examples:

            template = "my_{BATCH_ID}_file.csv"
            settings.init_setting_from_template(template)
            # Returns: "my_20230101_file.csv" if BATCH_ID is 20230101
        """
        if current_value is not None:
            return current_value

        mapping = {}
        for _, field_name, _, _ in Formatter().parse(template_str):

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


    def post_init(self):
        """Post-initialization function to run after the settings object has been initialized."""
        # Set the settings namespace to the class name if not

        pass


