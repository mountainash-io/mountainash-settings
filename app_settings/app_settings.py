from typing import Any

from pydantic import Field
# from goodconf import GoodConf, Field, Value
from datetime import datetime
from pydantic_settings import SettingsConfigDict

from mountainash_acdrs.constants.app_constants import (
    CONST_FILESYSTEM,
    CONST_DATAFILEFORMAT,
    CONST_DATAFRAME_FRAMEWORK,
    CONST_REPORT_VALIDATION_DATAFRAME_NAMES,
    CONST_DB_BACKEND,
    CONST_DB_ABSTRACTION_LAYER)
 
from mountainash_acdrs.utils.dataclass_utils import DataclassUtils
from mountainash_acdrs.utils.os_utils import get_platform_slash

from .app_settings_templates import  get_app_settings_templates
from mountainash_settings.settings.base_settings import MountainAshBaseSettings


class AppSettings(MountainAshBaseSettings):

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
                         _dummy=_dummy,
                         **kwargs
                         )

    # App Settings
    PLATFORM_SLASH: str =                    Field(default=get_platform_slash())
    LOCALE_TIMEZONE: str =                   Field(default="Australia/Melbourne")

    # Runtime Settings
    MOUNTAINASH_ACRDS_PACKAGE_VERSION: str = Field(default="2023.11.01")
    DEBUG: bool =                            Field(default=False)
    RUNDATE: str =                           Field(default=datetime.now().strftime("%Y%m%d"))
    RUNTIME: str =                           Field(default=datetime.now().strftime("%H%M%S"))
    RUNDATETIME: str =                       Field(default=None)

    # Organisation + Portfolio Settings
    ORGANISATION_NAME: str =                Field(default="ORGANISATION")
    ORGANISATION_TLA: str =                 Field(default="ORG")
    PORTFOLIO_NAME: str =                   Field(default="PORTFOLIO")
    BATCH_PROVIDER_NAME: str =              Field(default="PROVIDER")
    BATCH_PROVIDER_SIGNATORY_ID: str =      Field(default="PROVIDER_SIGNATORY_ID")
    BATCH_PROVIDER_SIGNATORY_SUB_ID: str =  Field(default="PROVIDER_SIGNATORY_SUB_ID")
    BATCH_CONTACT_NAME: str =               Field(default="CONTACT NAME")
    BATCH_CONTACT_EMAIL: str =              Field(default="contact@example.com")
    BATCH_CONTACT_PHONE: str =              Field(default="0123456789")

    #Runtime Batch Settings
    BATCH_ID: str =                         Field(default=None)
    BATCH_MODE: str =                       Field(default="T")
    BATCH_VERSION: str =                    Field(default=None)
    BATCH_BATCH_TYPE: str =                 Field(default="P")
    BATCH_TIER: str =                       Field(default="C")
    BATCH_RESPONSE_DETAIL: str =            Field(default="C")

    # Bureau Settings
    BUREAU_RESPONSE_SUFFIX: str =           Field(default="")

    # File and Path Settings
    REPORT_BASE_PATH: str =                 Field(default=None)
    RESPONSE_BASE_PATH: str =               Field(default=None)

    REPORT_FILENAME: str =                  Field(default=None)
    RESPONSE_FILENAME: str =                Field(default=None)

    REPORT_DATA_PATH: str =                 Field(default=None)
    RESPONSE_DATA_PATH: str =               Field(default=None)

    REPORT_FLATTENED_DATA_PATH: str =                 Field(default=None)
    RESPONSE_FLATTENED_DATA_PATH: str =               Field(default=None)

    REPORT_VALIDATION_DATA_PATH: str =      Field(default=None)
    RESPONSE_VALIDATION_DATA_PATH: str =    Field(default=None)

    PGP_HOME: str =                         Field(default="~/.gnupgp")

    # Filename templates and constants
    REPORT_DATA_BATCH_VERSION_FILENAME: str =       Field(default=None)
    REPORT_DATA_BATCH_HEADER_FILENAME: str =        Field(default=None)
    REPORT_DATA_ACCOUNTS_FILENAME: str =            Field(default=None)
    REPORT_DATA_ACCOUNTHOLDERS_FILENAME: str =      Field(default=None)
    REPORT_DATA_REPAYMENTHISTORY_FILENAME: str =    Field(default=None)

    RESPONSE_DATA_VERSION_FILENAME: str =           Field(default=None)
    RESPONSE_DATA_FILEHEADER_FILENAME: str =        Field(default=None)
    RESPONSE_DATA_FILESTATISTICS_FILENAME: str =    Field(default=None)
    RESPONSE_DATA_FILEMESSAGE_FILENAME: str =       Field(default=None)
    RESPONSE_DATA_ACCOUNTHEADER_FILENAME: str =     Field(default=None)
    RESPONSE_DATA_ACCOUNTSTATISTICS_FILENAME: str = Field(default=None)
    RESPONSE_DATA_ACCOUNTMESSAGE_FILENAME: str =    Field(default=None)

    # Flattened Data Filename templates and constants
    REPORT_FLATTENED_DATA_BATCH_VERSION_FILENAME: str =       Field(default=None)
    REPORT_FLATTENED_DATA_BATCH_HEADER_FILENAME: str =        Field(default=None)
    REPORT_FLATTENED_DATA_ACCOUNTS_FILENAME: str =            Field(default=None)
    REPORT_FLATTENED_DATA_ACCOUNTHOLDERS_FILENAME: str =      Field(default=None)
    REPORT_FLATTENED_DATA_REPAYMENTHISTORY_FILENAME: str =    Field(default=None)

    RESPONSE_FLATTENED_DATA_VERSION_FILENAME: str =           Field(default=None)
    RESPONSE_FLATTENED_DATA_FILEHEADER_FILENAME: str =        Field(default=None)
    RESPONSE_FLATTENED_DATA_FILESTATISTICS_FILENAME: str =    Field(default=None)
    RESPONSE_FLATTENED_DATA_FILEMESSAGE_FILENAME: str =       Field(default=None)
    RESPONSE_FLATTENED_DATA_ACCOUNTHEADER_FILENAME: str =     Field(default=None)
    RESPONSE_FLATTENED_DATA_ACCOUNTSTATISTICS_FILENAME: str = Field(default=None)
    RESPONSE_FLATTENED_DATA_ACCOUNTMESSAGE_FILENAME: str =    Field(default=None)


    # The templated values for these settings are determined at runtime, rather than at initialisation. Hence the template is hard-coded here. 
    # In particular, VALIDATORNAME is not known until runtime, and these settings are used for multiple validators.
    REPORT_VALIDATION_BRONZE_SCHEMA_PK: str =           Field(default="REPORT_VALIDATION_BRONZE_SCHEMA_PK_{VALIDATORNAME}_{BATCH_ID}.{DATA_FILE_FORMAT}")
    REPORT_VALIDATION_BRONZE_SCHEMA_ELEMENTS: str =     Field(default="REPORT_VALIDATION_BRONZE_SCHEMA_ELEMENTS_{VALIDATORNAME}_{BATCH_ID}.{DATA_FILE_FORMAT}")
    REPORT_VALIDATION_BRONZE_SCHEMA_FIELDS: str =       Field(default="REPORT_VALIDATION_BRONZE_SCHEMA_FIELDS_{VALIDATORNAME}_{BATCH_ID}.{DATA_FILE_FORMAT}")
    REPORT_VALIDATION_SILVER_SCHEMA_MALFORMED: str =    Field(default="REPORT_VALIDATION_SILVER_SCHEMA_MALFORMED_{VALIDATORNAME}_{BATCH_ID}.{DATA_FILE_FORMAT}")
    REPORT_VALIDATION_SILVER_SCHEMA_FIELD_VALUES: str = Field(default="REPORT_VALIDATION_SILVER_SCHEMA_FIELD_VALUES_{VALIDATORNAME}_{BATCH_ID}.{DATA_FILE_FORMAT}")
    REPORT_VALIDATION_SILVER_SCHEMA_ERRORS: str =       Field(default="REPORT_VALIDATION_SILVER_SCHEMA_ERRORS_{VALIDATORNAME}_{BATCH_ID}.{DATA_FILE_FORMAT}")


    #Internal Configuration Paths - Common
    APP_ACRDS_SCHEMA_VERSION_PATH:str =             Field(default="mountainash_acdrs.config.app_schema_versions")
    APP_VALIDATION_SCHEMA_PATH: str =               Field(default="mountainash_acdrs.config.validation_schema")

    #Internal Configuration Paths - Version Dependent
    APP_METADATA_PATH: str =                        Field(default=None)
    APP_BUILD_REPORT_FIELDMAPPINGS_PATH: str =      Field(default=None)
    APP_BUILD_RESPONSE_FIELDMAPPINGS_PATH: str =    Field(default=None)
    APP_FLATTEN_REPORT_FIELDMAPPINGS_PATH: str =    Field(default=None)
    APP_FLATTEN_RESPONSE_FIELDMAPPINGS_PATH: str =  Field(default=None)

    # Data Interfaces Default settings if not specified at runtime, or in module-speciifc config values
    FILESYSTEM: str =                               Field(default=CONST_FILESYSTEM.LOCAL_DISK.value)
    DATA_FILE_FORMAT: str =                         Field(default=CONST_DATAFILEFORMAT.PARQUET.value)
    DATAFRAME_FRAMEWORK: str =                      Field(default=CONST_DATAFRAME_FRAMEWORK.POLARS.value)
    DB_BACKEND: str =                               Field(default=CONST_DB_BACKEND.SQLITE.value)
    DB_ABSTRACTION_LAYER: str =                     Field(default=CONST_DB_ABSTRACTION_LAYER.IBIS.value)

    DATA_PROCESSING_NUM_WORKERS: int =              Field(default=2)
    DATA_PROCESSING_BATCH_SIZE: int =               Field(default=2000)

    SYNTHETIC_DATA_NUM_RECORDS: int =               Field(default=100)

    DEFAULT_SQLITE_DB_PATH: str =                   Field(default="~/.mountainash_acdrs")
    DEFAULT_SQLITE_DB_FILE: str =                   Field(default="mountainash_acdrs.db")

    def post_init(self):
        """Initializes dynamic settings from template strings.

        This method sets attribute values that need to be dynamically 
        generated or formatted, such as file paths with batch IDs.
        It parses template strings containing placeholders like {BATCH_ID}
        and formats them using values from existing attributes.

        The order of the 

        The updated attributes include:
        - File paths for reports, responses, metadata
        - Field mapping files 
        - Data and validation data paths
        - Batch ID value
        - Report and response data filenames

        No arguments are taken.

        Returns: None

        Example usage:
            
            settings = AppSettings()
            settings.load_from_config()
            settings.post_init() # Dynamically initialize settings
        """
        print("Post-init")
        print(self.BATCH_ID)
        print(self.BATCH_VERSION)
        print(self.RUNDATE)
        print(self.RUNTIME)


        # self.init_batch_id(objAppSettingsTemplates.BATCH_ID_TEMPLATE)
        self.BATCH_ID = self.init_setting_from_template(get_app_settings_templates().BATCH_ID_TEMPLATE, self.BATCH_ID)
        self.RUNDATETIME = self.init_setting_from_template(get_app_settings_templates().RUNDATETIME_TEMPLATE, self.RUNDATETIME)


        # self.init_report_data_filesystem()
        # self.init_default_data_file_format()

        self.REPORT_BASE_PATH =         self.init_setting_from_template(get_app_settings_templates().REPORT_BASE_PATH_TEMPLATE, current_value=self.REPORT_BASE_PATH)
        self.REPORT_FILENAME =          self.init_setting_from_template(get_app_settings_templates().REPORT_FILENAME_TEMPLATE, current_value=self.REPORT_FILENAME)

        self.RESPONSE_BASE_PATH =       self.init_setting_from_template(get_app_settings_templates().RESPONSE_BASE_PATH_TEMPLATE, current_value=self.RESPONSE_BASE_PATH)
        self.RESPONSE_FILENAME =        self.init_setting_from_template(get_app_settings_templates().RESPONSE_FILENAME_TEMPLATE, current_value=self.RESPONSE_FILENAME)

        self.APP_METADATA_PATH =        self.init_setting_from_template(get_app_settings_templates().APP_METADATA_PATH_TEMPLATE)

        #builder field mappings
        self.APP_BUILD_REPORT_FIELDMAPPINGS_PATH =      self.init_setting_from_template(get_app_settings_templates().APP_BUILD_REPORT_FIELDMAPPINGS_PATH_TEMPLATE)
        self.APP_BUILD_RESPONSE_FIELDMAPPINGS_PATH =    self.init_setting_from_template(get_app_settings_templates().APP_BUILD_RESPONSE_FIELDMAPPINGS_PATH_TEMPLATE)

        self.APP_FLATTEN_REPORT_FIELDMAPPINGS_PATH =    self.init_setting_from_template(get_app_settings_templates().APP_FLATTEN_REPORT_FIELDMAPPINGS_PATH_TEMPLATE)
        self.APP_FLATTEN_RESPONSE_FIELDMAPPINGS_PATH =  self.init_setting_from_template(get_app_settings_templates().APP_FLATTEN_RESPONSE_FIELDMAPPINGS_PATH_TEMPLATE)

        #Data Paths
        self.REPORT_DATA_PATH =                         self.init_setting_from_template(get_app_settings_templates().REPORT_DATA_PATH_TEMPLATE)
        self.RESPONSE_DATA_PATH =                       self.init_setting_from_template(get_app_settings_templates().RESPONSE_DATA_PATH_TEMPLATE)

        self.REPORT_FLATTENED_DATA_PATH =          self.init_setting_from_template(get_app_settings_templates().REPORT_FLATTENED_DATA_PATH_TEMPLATE)
        self.RESPONSE_FLATTENED_DATA_PATH =        self.init_setting_from_template(get_app_settings_templates().RESPONSE_FLATTENED_DATA_PATH_TEMPLATE)

        self.REPORT_VALIDATION_DATA_PATH =              self.init_setting_from_template(get_app_settings_templates().REPORT_VALIDATION_DATA_PATH_TEMPLATE)
        self.RESPONSE_VALIDATION_DATA_PATH =            self.init_setting_from_template(get_app_settings_templates().RESPONSE_VALIDATION_DATA_PATH_TEMPLATE)

        #Report Filenames
        self.REPORT_DATA_BATCH_VERSION_FILENAME =       self.init_setting_from_template(get_app_settings_templates().REPORT_DATA_BATCH_VERSION_FILENAME_TEMPLATE)
        self.REPORT_DATA_BATCH_HEADER_FILENAME =        self.init_setting_from_template(get_app_settings_templates().REPORT_DATA_BATCH_HEADER_FILENAME_TEMPLATE)
        self.REPORT_DATA_ACCOUNTS_FILENAME =            self.init_setting_from_template(get_app_settings_templates().REPORT_DATA_ACCOUNTS_FILENAME_TEMPLATE)
        self.REPORT_DATA_ACCOUNTHOLDERS_FILENAME =      self.init_setting_from_template(get_app_settings_templates().REPORT_DATA_ACCOUNTHOLDERS_FILENAME_TEMPLATE)
        self.REPORT_DATA_REPAYMENTHISTORY_FILENAME =    self.init_setting_from_template(get_app_settings_templates().REPORT_DATA_REPAYMENTHISTORY_FILENAME_TEMPLATE)

        #Response Filenames
        self.RESPONSE_DATA_VERSION_FILENAME =           self.init_setting_from_template(get_app_settings_templates().RESPONSE_DATA_VERSION_FILENAME_TEMPLATE)
        self.RESPONSE_DATA_FILEHEADER_FILENAME =        self.init_setting_from_template(get_app_settings_templates().RESPONSE_DATA_FILEHEADER_FILENAME_TEMPLATE)
        self.RESPONSE_DATA_FILESTATISTICS_FILENAME =    self.init_setting_from_template(get_app_settings_templates().RESPONSE_DATA_FILESTATISTICS_FILENAME_TEMPLATE)
        self.RESPONSE_DATA_FILEMESSAGE_FILENAME =       self.init_setting_from_template(get_app_settings_templates().RESPONSE_DATA_FILEMESSAGE_FILENAME_TEMPLATE)
        self.RESPONSE_DATA_ACCOUNTHEADER_FILENAME =     self.init_setting_from_template(get_app_settings_templates().RESPONSE_DATA_ACCOUNTHEADER_FILENAME_TEMPLATE)
        self.RESPONSE_DATA_ACCOUNTSTATISTICS_FILENAME = self.init_setting_from_template(get_app_settings_templates().RESPONSE_DATA_ACCOUNTSTATISTICS_FILENAME_TEMPLATE)
        self.RESPONSE_DATA_ACCOUNTMESSAGE_FILENAME =    self.init_setting_from_template(get_app_settings_templates().RESPONSE_DATA_ACCOUNTMESSAGE_FILENAME_TEMPLATE)


        #Flattened Report Filenames
        self.REPORT_FLATTENED_DATA_BATCH_VERSION_FILENAME =       self.init_setting_from_template(get_app_settings_templates().REPORT_FLATTENED_DATA_BATCH_VERSION_FILENAME_TEMPLATE)
        self.REPORT_FLATTENED_DATA_BATCH_HEADER_FILENAME =        self.init_setting_from_template(get_app_settings_templates().REPORT_FLATTENED_DATA_BATCH_HEADER_FILENAME_TEMPLATE)
        self.REPORT_FLATTENED_DATA_ACCOUNTS_FILENAME =            self.init_setting_from_template(get_app_settings_templates().REPORT_FLATTENED_DATA_ACCOUNTS_FILENAME_TEMPLATE)
        self.REPORT_FLATTENED_DATA_ACCOUNTHOLDERS_FILENAME =      self.init_setting_from_template(get_app_settings_templates().REPORT_FLATTENED_DATA_ACCOUNTHOLDERS_FILENAME_TEMPLATE)
        self.REPORT_FLATTENED_DATA_REPAYMENTHISTORY_FILENAME =    self.init_setting_from_template(get_app_settings_templates().REPORT_FLATTENED_DATA_REPAYMENTHISTORY_FILENAME_TEMPLATE)

        #Flattened Response Filenames
        self.RESPONSE_FLATTENED_DATA_VERSION_FILENAME =           self.init_setting_from_template(get_app_settings_templates().RESPONSE_FLATTENED_DATA_VERSION_FILENAME_TEMPLATE)
        self.RESPONSE_FLATTENED_DATA_FILEHEADER_FILENAME =        self.init_setting_from_template(get_app_settings_templates().RESPONSE_FLATTENED_DATA_FILEHEADER_FILENAME_TEMPLATE)
        self.RESPONSE_FLATTENED_DATA_FILESTATISTICS_FILENAME =    self.init_setting_from_template(get_app_settings_templates().RESPONSE_FLATTENED_DATA_FILESTATISTICS_FILENAME_TEMPLATE)
        self.RESPONSE_FLATTENED_DATA_FILEMESSAGE_FILENAME =       self.init_setting_from_template(get_app_settings_templates().RESPONSE_FLATTENED_DATA_FILEMESSAGE_FILENAME_TEMPLATE)
        self.RESPONSE_FLATTENED_DATA_ACCOUNTHEADER_FILENAME =     self.init_setting_from_template(get_app_settings_templates().RESPONSE_FLATTENED_DATA_ACCOUNTHEADER_FILENAME_TEMPLATE)
        self.RESPONSE_FLATTENED_DATA_ACCOUNTSTATISTICS_FILENAME = self.init_setting_from_template(get_app_settings_templates().RESPONSE_FLATTENED_DATA_ACCOUNTSTATISTICS_FILENAME_TEMPLATE)
        self.RESPONSE_FLATTENED_DATA_ACCOUNTMESSAGE_FILENAME =    self.init_setting_from_template(get_app_settings_templates().RESPONSE_FLATTENED_DATA_ACCOUNTMESSAGE_FILENAME_TEMPLATE)


    def get_report_validation_filenames(self, VALIDATORNAME: str) -> dict[Any, str]:

        """Gets the file paths for report validation dataframes.
        These paths are initialized from templates and include placeholders for the batch id and validator name.
        These are not known until runtime, and so must be initialised 'just-in-time' for use.

        Args:
            validatorname: The name of the validator.

        Returns: 
            A dict with keys as the dataframe names and values as the file paths.

        Example:
            
            settings = AppSettings()
            filenames = settings.get_report_validation_filenames(
                validatorname="report_data_validator")
        """

        keys = DataclassUtils.get_enum_values(enumclass=CONST_REPORT_VALIDATION_DATAFRAME_NAMES)

        filenames = {

            key: self.init_setting_from_template(template_str=self.__getattribute__(key))

            # key: self.__getattribute__(key).format(
            #     BATCH_ID=self.BATCH_ID,
            #     VALIDATORNAME=VALIDATORNAME,
            #     DATA_FILE_FORMAT=self.DATA_FILE_FORMAT,
            
            for key in keys
        }

        return filenames








