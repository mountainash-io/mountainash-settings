# from pydantic import BaseModel, BaseSettings
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

from mountainash_acdrs.utils.file_utils import LocalFileUtils

PLATFORM_SLASH = LocalFileUtils.get_platform_slash()


class AuthSettingsTemplates(BaseSettings):

    model_config = SettingsConfigDict(
        # `.env.prod` takes priority over `.env`
        # env_file=(
        #     "~/.mountainash_acdrs/mountainash_acdrs_file_templates.env",
        #     "mountainash_acdrs_file_templates.env",
        # ),
        extra="ignore",
    )

    # File and Path Templates
    MSSQL_CONNECTION_STRING_TEMPLATE: str = Field(        default=f"{PLATFORM_SLASH}data")
    POSTGRES_CONNECTION_STRING_TEMPLATE: str = Field(        default=f"{PLATFORM_SLASH}data")
    SNOWFLAKE_CONNECTION_STRING_TEMPLATE: str = Field(        default=f"{PLATFORM_SLASH}data")


#This is here to avoid a circular import. Would otherwise be in app_settings_functions
@lru_cache(maxsize=None)
def get_auth_settings_templates() -> AuthSettingsTemplates:
    return AuthSettingsTemplates()