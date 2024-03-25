from typing import Optional, Union, List, Any, Tuple, Dict

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from ..settings import MountainAshBaseSettings


class AuthSettings(MountainAshBaseSettings):

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
    STORAGE_SYSTEM: str =                                   Field(default=None)
    USERNAME: str =                                         Field(default=None)
    PASSWORD: str =                                         Field(default=None)
    HOST: str =                                             Field(default=None)
    PORT: int =                                             Field(default=None)
    REGION: str =                                           Field(default=None)
    FORMATTED_CONNECTION_STRING: str =                      Field(default=None)

    TOKEN:  str =                                           Field(default=None)
    ENCRYPTION_TYPE:  str =                                 Field(default=None)
    COMPRESSION_TYPE:  str =                                Field(default=None)
    ENCRYPTION_KEY_PATH:  str =                             Field(default=None)

    SSH_KEY_PATH:  str =                                    Field(default=None)
    SSH_FWD_REMOTEPORT: int =                               Field(default=None)
    SSH_FWD_LOCALPORT: int =                                Field(default=None)

    #Eg: Bucketname
    STORAGE_NAMESPACE: str =                                Field(default=None)
    ENV_PREFIX: str =                                       Field(default=None)



    def post_init(self):

        # self.init_batch_id(objAppSettingsTemplates.BATCH_ID_TEMPLATE)
        # self.BATCH_ID = self.init_setting_from_template(get_app_settings_templates().BATCH_ID_TEMPLATE, self.BATCH_ID)
        pass








