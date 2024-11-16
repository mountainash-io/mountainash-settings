from typing import Optional, Tuple
from pydantic import Field, SecretStr
from upath import UPath

from typing import List

from .constants import CONST_SECRET_VERSION_HANDLING, CONST_SECRET_ROTATION_POLICY
from mountainash_settings import MountainAshBaseSettings



class SecretsAuthBase(MountainAshBaseSettings):
    """Base class for secret storage authentication settings"""
    
    # Provider Configuration
    PROVIDER_TYPE: str = Field(default=None)
    AUTH_METHOD: str = Field(default=None)
    
    # Connection Settings
    ENDPOINT_URL: Optional[str] = Field(default=None)
    API_VERSION: Optional[str] = Field(default=None)
    TIMEOUT: int = Field(default=30)
    
    # Authentication
    TENANT_ID: Optional[str] = Field(default=None)
    CLIENT_ID: Optional[str] = Field(default=None)
    CLIENT_SECRET: Optional[SecretStr] = Field(default=None)
    
    # Secret Management
    SECRET_NAMESPACE: Optional[str] = Field(default=None)
    VERSION_HANDLING: str = Field(default=CONST_SECRET_VERSION_HANDLING.LATEST.value)
    ROTATION_POLICY: str = Field(default=CONST_SECRET_ROTATION_POLICY.MANUAL.value)
    
    # Caching and Performance
    CACHE_TTL: Optional[int] = Field(default=300)  # 5 minutes
    MAX_RETRIES: int = Field(default=3)
    RETRY_DELAY: int = Field(default=1)
    
    # Security
    ENCRYPTION_KEY_PATH: Optional[str] = Field(default=None)
    ENCRYPTION_TYPE: Optional[str] = Field(default=None)
    

    # Caching and Performance
    ENABLE_CACHE: bool = Field(default=True)
    CACHE_TTL: Optional[int] = Field(default=300)  # 5 minutes
    MAX_RETRIES: int = Field(default=3)
    RETRY_DELAY: int = Field(default=1)
    
    # Internal state
    # _fernet: Optional[Fernet] = None
    # _cache: Dict[str, Dict[str, Any]] = {}

    def __init__(self, 
                 config_files: Optional[str|UPath|List[str|UPath]|Tuple[str|UPath]] = None,
                 _dummy: Optional[bool] = False,
                 **kwargs) -> None:  
        super().__init__(config_files=config_files, _dummy=_dummy, **kwargs)


    def post_init(self, reinitialise: bool = False):
        """Initialize dynamic settings from templates"""
        super().post_init()
        self._init_dynamic_settings(reinitialise)
        # self._init_encryption(reinitialise)
        # self._init_provider_specific(reinitialise)
   


    # @field_validator("ENCODING_TYPE")
    # def validate_encoding_type(cls, v):
    #     """Validate encoding type"""
    #     if v not in CONST_SECRET_ENCODING.__dict__:
    #         raise SecretValidationError(
    #             f"Invalid encoding type: {v}",
    #             validation_type="encoding_type"
    #         )
    #     return v


    # def _init_encryption(self, reinitialise: bool = False):
    #     """Initialize encryption based on configuration"""
    #     if self.ENCODING_TYPE == CONST_SECRET_ENCODING.FERNET:
    #         if self.ENCRYPTION_KEY:
    #             key = self.ENCRYPTION_KEY.get_secret_value().encode()
    #         elif self.ENCRYPTION_KEY_FILE:
    #             try:
    #                 with open(self.ENCRYPTION_KEY_FILE, 'rb') as f:
    #                     key = f.read()
    #             except Exception as e:
    #                 raise SecretEncryptionError(
    #                     f"Failed to read encryption key file: {str(e)}",
    #                     operation="init"
    #                 )
    #         else:
    #             raise SecretConfigurationError(
    #                 "Either ENCRYPTION_KEY or ENCRYPTION_KEY_FILE must be provided for Fernet encryption"
    #             )
            
    #         try:
    #             self._fernet = Fernet(base64.urlsafe_b64encode(key))
    #         except Exception as e:
    #             raise SecretEncryptionError(
    #                 f"Failed to initialize Fernet: {str(e)}",
    #                 operation="init"
    #             )
 
    # @abstractmethod
    # def _init_provider_specific(self, reinitialise: bool = False):
    #     """Initialize provider-specific settings and connections"""
    #     pass

    # def _encode_value(self, value: str) -> str:
    #     """Encode a value based on encoding type"""
    #     if self.ENCODING_TYPE == CONST_SECRET_ENCODING.NONE:
    #         return value
    #     elif self.ENCODING_TYPE == CONST_SECRET_ENCODING.BASE64:
    #         return base64.b64encode(value.encode()).decode()
    #     elif self.ENCODING_TYPE == CONST_SECRET_ENCODING.FERNET:
    #         if not self._fernet:
    #             raise SecretEncryptionError(
    #                 "Fernet encryption not initialized",
    #                 operation="encode"
    #             )
    #         return self._fernet.encrypt(value.encode()).decode()
        
    #     raise SecretEncryptionError(
    #         f"Unsupported encoding type: {self.ENCODING_TYPE}",
    #         operation="encode"
    #     )

    # def _decode_value(self, value: str) -> str:
    #     """Decode a value based on encoding type"""
    #     try:
    #         if self.ENCODING_TYPE == CONST_SECRET_ENCODING.NONE:
    #             return value
    #         elif self.ENCODING_TYPE == CONST_SECRET_ENCODING.BASE64:
    #             return base64.b64decode(value.encode()).decode()
    #         elif self.ENCODING_TYPE == CONST_SECRET_ENCODING.FERNET:
    #             if not self._fernet:
    #                 raise SecretEncryptionError(
    #                     "Fernet encryption not initialized",
    #                     operation="decode"
    #                 )
    #             return self._fernet.decrypt(value.encode()).decode()
    #     except Exception as e:
    #         raise SecretEncryptionError(
    #             f"Failed to decode value: {str(e)}",
    #             operation="decode"
    #         )
        
    #     raise SecretEncryptionError(
    #         f"Unsupported encoding type: {self.ENCODING_TYPE}",
    #         operation="decode"
    #     )

    # def _cache_get(self, key: str) -> Optional[Dict[str, Any]]:
    #     """Get a value from the cache"""
    #     if not self.ENABLE_CACHE:
    #         return None
        
    #     cached = self._cache.get(key)
    #     if cached is None:
    #         return None
        
    #     # Check if cached value is expired
    #     if (datetime.now() - cached['timestamp']).total_seconds() > self.CACHE_TTL:
    #         del self._cache[key]
    #         return None
        
    #     return cached['value']

    # def _cache_set(self, key: str, value: Any):
    #     """Set a value in the cache"""
    #     if self.ENABLE_CACHE:
    #         self._cache[key] = {
    #             'value': value,
    #             'timestamp': datetime.now()
    #         }

    # def _cache_delete(self, key: str):
    #     """Delete a value from the cache"""
    #     if key in self._cache:
    #         del self._cache[key]


    # #Abstract Methods
    # @abstractmethod
    # def get_secret(self, name: str, version: Optional[str] = None) -> SecretStr:
    #     """
    #     Get a secret value
        
    #     Args:
    #         name: Name of the secret
    #         version: Optional version of the secret
            
    #     Returns:
    #         SecretStr containing the secret value
            
    #     Raises:
    #         SecretNotFoundError: If the secret doesn't exist
    #         SecretAccessError: If there's an error accessing the secret
    #     """
    #     pass


    # @abstractmethod
    # def list_secrets(self, prefix: Optional[str] = None) -> List[str]:
    #     """
    #     List available secrets
        
    #     Args:
    #         prefix: Optional prefix to filter secrets
            
    #     Returns:
    #         List of secret names
            
    #     Raises:
    #         SecretAccessError: If there's an error listing secrets
    #     """
    #     pass


    # def get_secret_metadata(self, name: str) -> Dict[str, Any]:
    #     """
    #     Get metadata about a secret
        
    #     Args:
    #         name: Name of the secret
            
    #     Returns:
    #         Dictionary containing secret metadata
            
    #     Raises:
    #         SecretNotFoundError: If the secret doesn't exist
    #         SecretAccessError: If there's an error accessing the secret
    #     """
    #     raise NotImplementedError("Secret metadata not supported by this provider")

    # def get_secret_versions(self, name: str) -> List[str]:
    #     """
    #     Get available versions of a secret
        
    #     Args:
    #         name: Name of the secret
            
    #     Returns:
    #         List of version identifiers
            
    #     Raises:
    #         SecretNotFoundError: If the secret doesn't exist
    #         SecretAccessError: If there's an error accessing the secret
    #     """
    #     raise NotImplementedError("Secret versioning not supported by this provider")


    # def validate_secret(self, name: str, validation_func: callable) -> bool:
    #     """
    #     Validate a secret using a custom validation function
        
    #     Args:
    #         name: Name of the secret to validate
    #         validation_func: Function that takes a SecretStr and returns bool
            
    #     Returns:
    #         True if validation passes, False otherwise
            
    #     Raises:
    #         SecretNotFoundError: If the secret doesn't exist
    #         SecretValidationError: If there's an error during validation
    #     """
    #     try:
    #         secret = self.get_secret(name)
    #         return validation_func(secret)
    #     except Exception as e:
    #         raise SecretValidationError(
    #             f"Validation failed: {str(e)}",
    #             validation_type="custom"
    #         )    