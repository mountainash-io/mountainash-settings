


from typing import Optional, List, Tuple
from upath import UPath
from pydantic import Field, field_validator

from mountainash_settings import SettingsParameters
from ..constants import CONST_LOCAL_SECRETS_STORAGE, CONST_SECRET_PROVIDER_TYPE
from ..base import SecretsAuthBase
from ..exceptions import SecretValidationError

class LocalSecretsSettings(SecretsAuthBase):
    """Settings for local secrets storage"""
    
    PROVIDER_TYPE: str = Field(default=CONST_SECRET_PROVIDER_TYPE.LOCAL)
    
    # Storage Configuration
    STORAGE_TYPE: str = Field(default=CONST_LOCAL_SECRETS_STORAGE.FILE)
    STORAGE_PATH: Optional[str] = Field(default=None)
    STORAGE_FORMAT: str = Field(default="json")
    
    def __init__(self, 
                 config_files: Optional[str|UPath|List[str|UPath]|Tuple[str|UPath]] = None,
                 settings_parameters:   Optional[SettingsParameters] = None,
                 _dummy: Optional[bool] = False,
                 **kwargs) -> None:  
        

        super().__init__(config_files=config_files, 
                         settings_parameters=settings_parameters,
                         _dummy=_dummy, 
                         **kwargs)



    ## Field Validators ##
    @field_validator("STORAGE_TYPE")
    def validate_storage_type(cls, v):
        """Validate storage type"""
        if v not in CONST_LOCAL_SECRETS_STORAGE.__dict__:
            raise SecretValidationError(
                f"Invalid storage type: {v}",
                provider="local",
                validation_type="storage_type"
            )
        return v 

    def _init_dynamic_settings(self, reinitialise: bool = False) -> None:
        """Initialize dynamic settings from templates"""
        pass


    # def _init_provider_specific(self, reinitialise: bool = False):
    #     """Initialize storage based on configuration"""
    #     pass

        # if self.STORAGE_TYPE == CONST_LOCAL_SECRETS_STORAGE.FILE:
        #     if not self.STORAGE_PATH:
        #         raise SecretConfigurationError(
        #             "STORAGE_PATH is required for file storage",
        #             provider="local",
        #             setting="STORAGE_PATH"
        #         )
        #     # Create directory if it doesn't exist
        #     UPath(self.STORAGE_PATH).parent.mkdir(parents=True, exist_ok=True)
            
        #     # Initialize empty secrets file if it doesn't exist
        #     if not os.path.exists(self.STORAGE_PATH):
        #         self._save_file_data({'secrets': {}, 'metadata': {}})
        
        # elif self.STORAGE_TYPE == CONST_LOCAL_SECRETS_STORAGE.KEYRING:
        #     try:
        #         import keyring
        #     except ImportError:
        #         raise SecretConfigurationError(
        #             "keyring package is required for keyring storage",
        #             provider="local"
        #         )

    # def _save_file_data(self, data: Dict[str, Any]) -> None:
    #     """Save data to file storage"""
    #     try:
    #         with open(self.STORAGE_PATH, 'w') as f:
    #             json.dump(data, f, indent=2)
    #     except Exception as e:
    #         raise SecretOperationError(
    #             "save",
    #             f"Failed to save to file: {str(e)}",
    #             provider="local"
    #         )

    # def _load_file_data(self) -> Dict[str, Any]:
    #     """Load data from file storage"""
    #     try:
    #         if not os.path.exists(self.STORAGE_PATH):
    #             return {'secrets': {}, 'metadata': {}}
            
    #         with open(self.STORAGE_PATH, 'r') as f:
    #             return json.load(f)
    #     except Exception as e:
    #         raise SecretOperationError(
    #             "load",
    #             f"Failed to load from file: {str(e)}",
    #             provider="local"
    #         )


    # def get_secret(self, name: str, version: Optional[str] = None) -> SecretStr:
    #     """Get a secret value"""
    #     try:
    #         # Check cache first
    #         cached_value = self._cache_get(name)
    #         if cached_value:
    #             return SecretStr(cached_value)

    #         if self.STORAGE_TYPE == CONST_LOCAL_SECRETS_STORAGE.FILE:
    #             data = self._load_file_data()
    #             if name not in data['secrets']:
    #                 raise SecretNotFoundError(name, provider="local")
    #             encoded_value = data['secrets'][name]
            
    #         elif self.STORAGE_TYPE == CONST_LOCAL_SECRETS_STORAGE.KEYRING:
    #             encoded_value = keyring.get_password(
    #                 self.SECRET_NAMESPACE or "mountainash",
    #                 name
    #             )
    #             if encoded_value is None:
    #                 raise SecretNotFoundError(name, provider="local")
            
    #         elif self.STORAGE_TYPE == CONST_LOCAL_SECRETS_STORAGE.ENVIRONMENT:
    #             if name not in os.environ:
    #                 raise SecretNotFoundError(name, provider="local")
    #             encoded_value = os.environ[name]
            
    #         else:
    #             raise SecretConfigurationError(
    #                 f"Unsupported storage type: {self.STORAGE_TYPE}",
    #                 provider="local"
    #             )

    #         # Decode value and update cache
    #         decoded_value = self._decode_value(encoded_value)
    #         self._cache_set(name, decoded_value)
    #         return SecretStr(decoded_value)

    #     except SecretNotFoundError:
    #         raise
    #     except Exception as e:
    #         raise SecretAccessError(
    #             name,
    #             provider="local",
    #             operation="get"
    #         ) from e



    # def list_secrets(self, prefix: Optional[str] = None) -> List[str]:
    #     """List available secrets"""
    #     try:
    #         if self.STORAGE_TYPE == CONST_LOCAL_SECRETS_STORAGE.FILE:
    #             data = self._load_file_data()
    #             secrets = list(data['secrets'].keys())
            
    #         elif self.STORAGE_TYPE == CONST_LOCAL_SECRETS_STORAGE.KEYRING:
    #             # Note: keyring doesn't provide a native way to list secrets
    #             # This is a limitation of the local secrets implementation
    #             raise NotImplementedError(
    #                 "Listing secrets is not supported with keyring storage"
    #             )
            
    #         elif self.STORAGE_TYPE == CONST_LOCAL_SECRETS_STORAGE.ENVIRONMENT:
    #             secrets = [
    #                 key for key in os.environ.keys()
    #                 if self.SECRET_NAMESPACE is None or key.startswith(self.SECRET_NAMESPACE)
    #             ]
            
    #         if prefix:
    #             secrets = [s for s in secrets if s.startswith(prefix)]
            
    #         return sorted(secrets)

    #     except Exception as e:
    #         raise SecretOperationError(
    #             "list",
    #             f"Failed to list secrets: {str(e)}",
    #             provider="local"
    #         )

    # def get_secret_metadata(self, name: str) -> Dict[str, Any]:
    #     """Get metadata about a secret"""
    #     if not self.METADATA_ENABLED:
    #         raise NotImplementedError("Metadata is not enabled")

    #     try:
    #         if self.STORAGE_TYPE == CONST_LOCAL_SECRETS_STORAGE.FILE:
    #             data = self._load_file_data()
    #             if name not in data['secrets']:
    #                 raise SecretNotFoundError(name, provider="local")
    #             return data['metadata'].get(name, {})
            
    #         elif self.STORAGE_TYPE == CONST_LOCAL_SECRETS_STORAGE.KEYRING:
    #             metadata_key = f"{name}__metadata"
    #             metadata = keyring.get_password(
    #                 self.SECRET_NAMESPACE or "mountainash",
    #                 metadata_key
    #             )
    #             if metadata is None:
    #                 return {}
    #             return json.loads(metadata)
            
    #         elif self.STORAGE_TYPE == CONST_LOCAL_SECRETS_STORAGE.ENVIRONMENT:
    #             return {}  # Environment variables don't support metadata
            
    #         return {}

    #     except SecretNotFoundError:
    #         raise
    #     except Exception as e:
    #         raise SecretOperationError(
    #             "metadata",
    #             f"Failed to get secret metadata: {str(e)}",
    #             provider="local"
    #         )

