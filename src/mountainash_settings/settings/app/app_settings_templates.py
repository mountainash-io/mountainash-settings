from typing import Optional,List, Tuple
from upath import UPath
from pydantic import Field
from functools import lru_cache
from mountainash_settings import MountainAshBaseSettings, SettingsParameters

class AppSettingsTemplates(MountainAshBaseSettings):

    def __init__(self,
                 config_files: Optional[str|UPath|List[str|UPath]|Tuple[str|UPath]] = None,
                 settings_parameters:   Optional[SettingsParameters] = None,
                 **kwargs) -> None:


        super().__init__(config_files=config_files,
                         settings_parameters=settings_parameters,
                         **kwargs)

    RUNDATETIME_TEMPLATE: str = Field(default="{RUNDATE}T{RUNTIME}")

#This is here to avoid a circular import. Would otherwise be in app_settings_functions
@lru_cache(maxsize=None)
def get_default_app_settings_templates() -> AppSettingsTemplates:
    """
    Retrieves the AppSettings object for a given namespace.

    Args:
        namespace (str): The namespace for the configuration.

    Returns:
        AppSettings: The AppSettings object for the given namespace.
    """
    return AppSettingsTemplates()
