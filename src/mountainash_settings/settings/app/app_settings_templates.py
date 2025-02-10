from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class AppSettingsTemplates(BaseSettings):

    model_config = SettingsConfigDict(
        extra="ignore",
    )

    RUNDATETIME_TEMPLATE: str = Field(default="{RUNDATE}T{RUNTIME}")

#This is here to avoid a circular import. Would otherwise be in app_settings_functions
@lru_cache(maxsize=None)
def get_app_settings_templates() -> AppSettingsTemplates:
    """
    Retrieves the AppSettings object for a given namespace.

    Args:
        namespace (str): The namespace for the configuration.

    Returns:
        AppSettings: The AppSettings object for the given namespace.
    """
    return AppSettingsTemplates()