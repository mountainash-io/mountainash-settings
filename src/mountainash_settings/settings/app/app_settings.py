from typing import Optional, List, Tuple
from datetime import datetime

from pydantic import Field
from upath import UPath
from functools import lru_cache

# from mountainash_utils_os import get_platform_slash
from mountainash_settings import MountainAshBaseSettings, SettingsParameters

from .app_settings_templates import  AppSettingsTemplates

"""AppSettings class.

Subclass of MountainAshBaseSettings for defining application settings.

Parameters:
# - _dummy: Whether to use dummy config.
- **kwargs: Additional keyword arguments.

"""


class AppSettings(MountainAshBaseSettings):

    def __init__(self,
                 config_files: Optional[str|UPath|List[str|UPath]|Tuple[str|UPath]] = None,
                 settings_parameters:   Optional[SettingsParameters] = None,
                 template_settings_parameters:   Optional[SettingsParameters] = None,

                 **kwargs) -> None:


        super().__init__(config_files=config_files,
                         settings_parameters=settings_parameters,
                         template_settings_parameters=template_settings_parameters,
                         **kwargs)

    # General App Settings
    # PLATFORM_SLASH: str =                    Field(default=get_platform_slash())
    LOCALE_TIMEZONE: str =                   Field(default="UTC")

    DEBUG: bool =                            Field(default=False)
    RUNDATE: str =                           Field(default=datetime.now().strftime("%Y%m%d"))
    RUNTIME: str =                           Field(default=datetime.now().strftime("%H%M%S"))
    RUNDATETIME: str =                       Field(default=None)



    def post_init(self,
        template_settings_parameters: Optional[SettingsParameters] = None,
        reinitialise: Optional[bool] = False
    ):
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
        super().post_init(reinitialise=reinitialise)
        app_settings_templates = self._init_template_object(template_settings_parameters)

        self.RUNDATETIME = self.init_setting_from_template(template_str=app_settings_templates.RUNDATETIME_TEMPLATE, current_value=self.RUNDATETIME, reinitialise=reinitialise)

    def _init_template_object(self, template_settings_parameters) -> AppSettingsTemplates:

        template_class =  template_settings_parameters.settings_class if template_settings_parameters is not None else None

        if template_class is not None and issubclass(template_class, AppSettingsTemplates):
            app_settings_templates = template_class.get_settings(template_settings_parameters)
        else:
            app_settings_templates =  AppSettingsTemplates.get_settings()

        return app_settings_templates
