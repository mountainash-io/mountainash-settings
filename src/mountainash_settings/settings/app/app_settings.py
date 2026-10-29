from typing import Any, ClassVar, Literal, Optional

from pydantic import Field

# from mountainash_utils_os import get_platform_slash
from mountainash_settings import MountainAshBaseSettings, SettingsParameters
from mountainash_settings.settings_parameters.filehandler import ConfigFilesInput

from .app_settings_templates import  AppSettingsTemplates
from . import _timestamps

"""AppSettings class.

Subclass of MountainAshBaseSettings for defining application settings.

Parameters:
# - _dummy: Whether to use dummy config.
- **kwargs: Additional keyword arguments.

"""


class AppSettings(MountainAshBaseSettings):

    RUN_TIMESTAMP_SCOPE: ClassVar[Literal["context", "process"]] = "context"

    @classmethod
    def _capture_initialization_defaults(cls) -> dict[str, Any]:
        return _timestamps.capture(cls.RUN_TIMESTAMP_SCOPE)

    def __init__(self,
                 config_files: ConfigFilesInput = None,
                 settings_parameters:   Optional[SettingsParameters] = None,
                 template_settings_parameters:   Optional[SettingsParameters] = None,

                 **kwargs) -> None:


        from mountainash_settings.settings_cache._context import initialization_defaults_for_instance

        defaults = initialization_defaults_for_instance(self)
        # Process scope must consult the PID-aware slot even when a forked child
        # inherits an already-captured manager. This does not resample in one PID.
        if defaults is None or type(self).RUN_TIMESTAMP_SCOPE == "process":
            defaults = type(self)._capture_initialization_defaults()
        with _timestamps.default_scope(defaults):
            super().__init__(config_files=config_files,
                             settings_parameters=settings_parameters,
                             template_settings_parameters=template_settings_parameters,
                             **kwargs)

    # General App Settings
    # PLATFORM_SLASH: str =                    Field(default=get_platform_slash())
    LOCALE_TIMEZONE: str =                   Field(default="UTC")

    DEBUG: bool =                            Field(default=False)
    RUNDATE: str =                           Field(default_factory=_timestamps.run_date)
    RUNTIME: str =                           Field(default_factory=_timestamps.run_time)
    RUNDATETIME: str | None =                Field(default=None)



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
