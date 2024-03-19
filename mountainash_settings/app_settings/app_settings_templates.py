# from pydantic import BaseModel, BaseSettings
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

from mountainash_utils.os_utils import get_platform_slash

PLATFORM_SLASH = get_platform_slash()

class AppSettingsTemplates(BaseSettings):

    model_config = SettingsConfigDict(
        # `.env.prod` takes priority over `.env`
        env_file=(
            "~/.mountainash_acdrs/mountainash_acdrs_file_templates.env",
            "mountainash_acdrs_file_templates.env",
        ),
        extra="ignore",
    )

    # File and Path Templates
    REPORT_BASE_PATH_TEMPLATE: str = Field(        default=f"~{PLATFORM_SLASH}data{PLATFORM_SLASH}mountainash{PLATFORM_SLASH}{{ORGANISATION_NAME}}{PLATFORM_SLASH}{{PORTFOLIO_NAME}}{PLATFORM_SLASH}{{RUNDATE}}{PLATFORM_SLASH}report")
    RESPONSE_BASE_PATH_TEMPLATE: str = Field(      default=f"~{PLATFORM_SLASH}data{PLATFORM_SLASH}mountainash{PLATFORM_SLASH}{{ORGANISATION_NAME}}{PLATFORM_SLASH}{{PORTFOLIO_NAME}}{PLATFORM_SLASH}{{RUNDATE}}{PLATFORM_SLASH}response")

    REPORT_DATA_PATH_TEMPLATE: str = Field(        default=f"{{REPORT_BASE_PATH}}{PLATFORM_SLASH}report_data")
    RESPONSE_DATA_PATH_TEMPLATE: str = Field(      default=f"{{RESPONSE_BASE_PATH}}{PLATFORM_SLASH}response_data")

    REPORT_FLATTENED_DATA_PATH_TEMPLATE: str = Field(        default=f"{{REPORT_BASE_PATH}}{PLATFORM_SLASH}flattened_report_data")
    RESPONSE_FLATTENED_DATA_PATH_TEMPLATE: str = Field(      default=f"{{RESPONSE_BASE_PATH}}{PLATFORM_SLASH}flattened_response_data")


    REPORT_VALIDATION_DATA_PATH_TEMPLATE: str = Field(        default=f"{{REPORT_BASE_PATH}}{PLATFORM_SLASH}report_validation_data")
    RESPONSE_VALIDATION_DATA_PATH_TEMPLATE: str = Field(      default=f"{{RESPONSE_BASE_PATH}}{PLATFORM_SLASH}response_validation_data")

    # Filename templates
    REPORT_FILENAME_TEMPLATE: str = Field(        default="{ORGANISATION_NAME}_{PORTFOLIO_NAME}_{RUNDATETIME}_{ORGANISATION_TLA}_{RUNDATE}.xml")
    RESPONSE_FILENAME_TEMPLATE: str = Field(      default="{ORGANISATION_NAME}_{PORTFOLIO_NAME}_{RUNDATETIME}_{ORGANISATION_TLA}_{RUNDATE}{BUREAU_RESPONSE_SUFFIX}.xml")


    # Application Config Module Paths
    APP_METADATA_PATH_TEMPLATE: str = Field(                            default="mountainash_acdrs.config.app_metadata")

    APP_BUILD_REPORT_FIELDMAPPINGS_PATH_TEMPLATE: str = Field(          default="mountainash_acdrs.config.fieldmappings.report.build.{BATCH_VERSION}")
    APP_BUILD_RESPONSE_FIELDMAPPINGS_PATH_TEMPLATE: str = Field(        default="mountainash_acdrs.config.fieldmappings.response.build.{BATCH_VERSION}")

    APP_FLATTEN_REPORT_FIELDMAPPINGS_PATH_TEMPLATE: str = Field(        default="mountainash_acdrs.config.fieldmappings.report.flatten.{BATCH_VERSION}")
    APP_FLATTEN_RESPONSE_FIELDMAPPINGS_PATH_TEMPLATE: str = Field(      default="mountainash_acdrs.config.fieldmappings.response.flatten.{BATCH_VERSION}")


    # Report Validation Filenames
    REPORT_VALIDATION_BATCHVERSION_FILENAME_TEMPLATE: str = Field(      default="REPORT_VALIDATION_DATA_BATCHVERSION_{BATCH_ID}.{DATA_FILE_FORMAT}")
    REPORT_VALIDATION_BATCHHEADER_FILENAME_TEMPLATE: str = Field(       default="REPORT_VALIDATION_DATA_BATCHHEADER_{BATCH_ID}.{DATA_FILE_FORMAT}")
    REPORT_VALIDATION_ACCOUNTS_FILENAME_TEMPLATE: str = Field(          default="REPORT_VALIDATION_DATA_ACCOUNTS_{BATCH_ID}.{DATA_FILE_FORMAT}")
    REPORT_VALIDATION_ACCOUNTHOLDERS_FILENAME_TEMPLATE: str = Field(    default="REPORT_VALIDATION_DATA_ACCOUNTHOLDERS_{BATCH_ID}.{DATA_FILE_FORMAT}")
    REPORT_VALIDATION_REPAYMENTHISTORY_FILENAME_TEMPLATE: str = Field(  default="REPORT_VALIDATION_DATA_REPAYMENTHISTORY_{BATCH_ID}.{DATA_FILE_FORMAT}")

    # Report Filenames
    REPORT_DATA_BATCH_VERSION_FILENAME_TEMPLATE: str = Field(           default="REPORT_DATA_BATCHVERSION_{BATCH_ID}.{DATA_FILE_FORMAT}")
    REPORT_DATA_BATCH_HEADER_FILENAME_TEMPLATE: str = Field(            default="REPORT_DATA_BATCHHEADER_{BATCH_ID}.{DATA_FILE_FORMAT}")
    REPORT_DATA_ACCOUNTS_FILENAME_TEMPLATE: str = Field(                default="REPORT_DATA_ACCOUNTS_{BATCH_ID}.{DATA_FILE_FORMAT}")
    REPORT_DATA_ACCOUNTHOLDERS_FILENAME_TEMPLATE: str = Field(          default="REPORT_DATA_ACCOUNTHOLDERS_{BATCH_ID}.{DATA_FILE_FORMAT}")
    REPORT_DATA_REPAYMENTHISTORY_FILENAME_TEMPLATE: str = Field(        default="REPORT_DATA_REPAYMENTHISTORY_{BATCH_ID}.{DATA_FILE_FORMAT}")

    REPORT_FLATTENED_DATA_BATCH_VERSION_FILENAME_TEMPLATE: str = Field(      default="REPORT_FLATTENED_DATA_BATCHVERSION_{BATCH_ID}.{DATA_FILE_FORMAT}")
    REPORT_FLATTENED_DATA_BATCH_HEADER_FILENAME_TEMPLATE: str = Field(       default="REPORT_FLATTENED_DATA_BATCHHEADER_{BATCH_ID}.{DATA_FILE_FORMAT}")
    REPORT_FLATTENED_DATA_ACCOUNTS_FILENAME_TEMPLATE: str = Field(           default="REPORT_FLATTENED_DATA_ACCOUNTS_{BATCH_ID}.{DATA_FILE_FORMAT}")
    REPORT_FLATTENED_DATA_ACCOUNTHOLDERS_FILENAME_TEMPLATE: str = Field(     default="REPORT_FLATTENED_DATA_ACCOUNTHOLDERS_{BATCH_ID}.{DATA_FILE_FORMAT}")
    REPORT_FLATTENED_DATA_REPAYMENTHISTORY_FILENAME_TEMPLATE: str = Field(   default="REPORT_FLATTENED_DATA_REPAYMENTHISTORY_{BATCH_ID}.{DATA_FILE_FORMAT}")

    # Response Filenames
    RESPONSE_DATA_VERSION_FILENAME_TEMPLATE: str = Field(               default="RESPONSE_DATA_VERSION_{BATCH_ID}.{DATA_FILE_FORMAT}")
    RESPONSE_DATA_FILEHEADER_FILENAME_TEMPLATE: str = Field(            default="RESPONSE_DATA_FILEHEADER_{BATCH_ID}.{DATA_FILE_FORMAT}")
    RESPONSE_DATA_FILESTATISTICS_FILENAME_TEMPLATE: str = Field(        default="RESPONSE_DATA_FILESTATISTICS_{BATCH_ID}.{DATA_FILE_FORMAT}")
    RESPONSE_DATA_FILEMESSAGE_FILENAME_TEMPLATE: str = Field(           default="RESPONSE_DATA_FILEMESSAGE_{BATCH_ID}.{DATA_FILE_FORMAT}")
    RESPONSE_DATA_ACCOUNTHEADER_FILENAME_TEMPLATE: str = Field(         default="RESPONSE_DATA_ACCOUNTHOLDERS_{BATCH_ID}.{DATA_FILE_FORMAT}")
    RESPONSE_DATA_ACCOUNTSTATISTICS_FILENAME_TEMPLATE: str = Field(     default="RESPONSE_DATA_ACCOUNTSTATISTICS_{BATCH_ID}.{DATA_FILE_FORMAT}")
    RESPONSE_DATA_ACCOUNTMESSAGE_FILENAME_TEMPLATE: str = Field(        default="RESPONSE_DATA_ACCOUNTMESSAGE_{BATCH_ID}.{DATA_FILE_FORMAT}")

    RESPONSE_FLATTENED_DATA_VERSION_FILENAME_TEMPLATE: str = Field(          default="RESPONSE_FLATTENED_DATA_VERSION_{BATCH_ID}.{DATA_FILE_FORMAT}")
    RESPONSE_FLATTENED_DATA_FILEHEADER_FILENAME_TEMPLATE: str = Field(       default="RESPONSE_FLATTENED_DATA_FILEHEADER_{BATCH_ID}.{DATA_FILE_FORMAT}")
    RESPONSE_FLATTENED_DATA_FILESTATISTICS_FILENAME_TEMPLATE: str = Field(   default="RESPONSE_FLATTENED_DATA_FILESTATISTICS_{BATCH_ID}.{DATA_FILE_FORMAT}")
    RESPONSE_FLATTENED_DATA_FILEMESSAGE_FILENAME_TEMPLATE: str = Field(      default="RESPONSE_FLATTENED_DATA_FILEMESSAGE_{BATCH_ID}.{DATA_FILE_FORMAT}")
    RESPONSE_FLATTENED_DATA_ACCOUNTHEADER_FILENAME_TEMPLATE: str = Field(    default="RESPONSE_FLATTENED_DATA_ACCOUNTHEADER_{BATCH_ID}.{DATA_FILE_FORMAT}")
    RESPONSE_FLATTENED_DATA_ACCOUNTSTATISTICS_FILENAME_TEMPLATE: str = Field(default="RESPONSE_FLATTENED_DATA_ACCOUNTSTATISTICS_{BATCH_ID}.{DATA_FILE_FORMAT}")
    RESPONSE_FLATTENED_DATA_ACCOUNTMESSAGE_FILENAME_TEMPLATE: str = Field(   default="RESPONSE_FLATTENED_DATA_ACCOUNTMESSAGE_{BATCH_ID}.{DATA_FILE_FORMAT}")

    # Batch Templates
    BATCH_ID_TEMPLATE: str =    Field(default="BATCH_{ORGANISATION_NAME}_{PORTFOLIO_NAME}_{RUNDATE}")
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