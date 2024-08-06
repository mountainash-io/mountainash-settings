from datetime import datetime

from pydantic import Field

from mountainash_utils_os import get_platform_slash
from mountainash_settings import MountainAshBaseSettings

from .app_settings_templates import  get_app_settings_templates

"""AppSettings class.

Subclass of MountainAshBaseSettings for defining application settings.

Parameters:
- _dummy: Whether to use dummy config.
- **kwargs: Additional keyword arguments.

"""


class AppSettings(MountainAshBaseSettings):

    def __init__(self, 
                 _dummy:bool    =   False,
                 **kwargs) -> None:

        super().__init__(_dummy=_dummy,
                         **kwargs)

    # General App Settings
    PLATFORM_SLASH: str =                    Field(default=get_platform_slash())
    LOCALE_TIMEZONE: str =                   Field(default="Australia/Melbourne")

    DEBUG: bool =                            Field(default=False)
    RUNDATE: str =                           Field(default=datetime.now().strftime("%Y%m%d"))
    RUNTIME: str =                           Field(default=datetime.now().strftime("%H%M%S"))
    RUNDATETIME: str =                       Field(default=None)


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
        super().post_init()

        self.RUNDATETIME = self.init_setting_from_template(get_app_settings_templates().RUNDATETIME_TEMPLATE, self.RUNDATETIME)



