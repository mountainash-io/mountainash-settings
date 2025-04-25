#providers/azure_keyvault.py


from typing import Optional, List, Tuple
from upath import UPath
from pydantic import Field, SecretStr, field_validator

# from azure.identity import (
#     DefaultAzureCredential,
#     ManagedIdentityCredential,
#     ClientSecretCredential,
#     CertificateCredential
# )
# from azure.keyvault.secrets import SecretClient
# from azure.core.exceptions import HttpResponseError
# from azure.core.credentials import TokenCredential

from mountainash_settings import SettingsParameters
from ..base import SecretsAuthBase
from ..constants import (
    CONST_SECRET_PROVIDER_TYPE,
    CONST_SECRET_AUTH_METHOD,
)
from ..exceptions import (
    SecretValidationError
)
from ..templates import get_secrets_templates

class AzureKeyVaultSettings(SecretsAuthBase):
    """Azure Key Vault specific settings for read-only secret access"""
    
    PROVIDER_TYPE: str = Field(default=CONST_SECRET_PROVIDER_TYPE.AZURE_KEYVAULT)
    
    # Azure-specific Settings
    VAULT_NAME: str = Field(default=None)
    SUBSCRIPTION_ID: Optional[str] = Field(default=None)
    RESOURCE_GROUP: Optional[str] = Field(default=None)
    
    # Authentication Settings
    AUTH_METHOD: str = Field(default=CONST_SECRET_AUTH_METHOD.MANAGED_IDENTITY)
    MANAGED_IDENTITY_CLIENT_ID: Optional[str] = Field(default=None)
    CERTIFICATE_PATH: Optional[str] = Field(default=None)
    CERTIFICATE_PASSWORD: Optional[SecretStr] = Field(default=None)
    
    # Dynamic Settings
    VAULT_URL: Optional[str] = Field(default=None)
    
    # Internal state
    # _client: Optional[SecretClient] = None
    # _credential: Optional[TokenCredential] = None

    def __init__(self, 
                 config_files: Optional[str|UPath|List[str|UPath]|Tuple[str|UPath]] = None,
                 settings_parameters:   Optional[SettingsParameters] = None,
                #  _dummy: Optional[bool] = False,
                 **kwargs) -> None:  
        

        super().__init__(config_files=config_files, 
                         settings_parameters=settings_parameters,
                        #  _dummy=_dummy, 
                         **kwargs)



    ## Field Validators ##
    @field_validator("VAULT_NAME")
    def validate_vault_name(cls, v: Optional[str]) -> str:
        """Validate vault name format"""
        if not v:
            raise SecretValidationError(
                "VAULT_NAME is required for Azure Key Vault",
                provider="azure",
                validation_type="vault_name"
            )
        if not v.isalnum():
            raise SecretValidationError(
                "VAULT_NAME must be alphanumeric",
                provider="azure",
                validation_type="vault_name"
            )
        return v

    def _init_dynamic_settings(self, reinitialise: bool = False) -> None:
        """Initialize dynamic settings from templates"""
        
        # Initialize VAULT_URL if not set
        self.VAULT_URL = self.init_setting_from_template(
            template_str=get_secrets_templates().AZURE_KEYVAULT_URL_TEMPLATE,
            current_value=self.VAULT_URL,
            reinitialise=reinitialise
        )

    # def _init_provider_specific(self, reinitialise: bool = False) -> None:
    #     """Initialize Azure Key Vault client and authentication"""
    #     if reinitialise or self._client is None:
    #         self._init_azure_client()

    # def _init_azure_client(self) -> None:
    #     """Initialize Azure Key Vault client with appropriate authentication"""
    #     try:
    #         # Initialize credential based on authentication method
    #         self._credential = self._get_credential()
            
    #         # Initialize the Key Vault client
    #         self._client = SecretClient(
    #             vault_url=self.VAULT_URL,
    #             credential=self._credential
    #         )
            
    #     except Exception as e:
    #         raise SecretConfigurationError(
    #             f"Failed to initialize Azure Key Vault client: {str(e)}",
    #             provider="azure"
    #         )

    # def _get_credential(self) -> TokenCredential:
    #     """
    #     Get the appropriate credential based on authentication method.
        
    #     Returns:
    #         TokenCredential: The appropriate Azure credential object
        
    #     Raises:
    #         SecretConfigurationError: If authentication configuration is invalid
    #     """
    #     try:
    #         if self.AUTH_METHOD == CONST_SECRET_AUTH_METHOD.MANAGED_IDENTITY:
    #             if self.MANAGED_IDENTITY_CLIENT_ID:
    #                 return ManagedIdentityCredential(
    #                     client_id=self.MANAGED_IDENTITY_CLIENT_ID
    #                 )
    #             return ManagedIdentityCredential()
            
    #         elif self.AUTH_METHOD == CONST_SECRET_AUTH_METHOD.SERVICE_PRINCIPAL:
    #             if not all([self.TENANT_ID, self.CLIENT_ID, self.CLIENT_SECRET]):
    #                 raise SecretConfigurationError(
    #                     "TENANT_ID, CLIENT_ID, and CLIENT_SECRET are required for service principal authentication",
    #                     provider="azure"
    #                 )
    #             return ClientSecretCredential(
    #                 tenant_id=self.TENANT_ID,
    #                 client_id=self.CLIENT_ID,
    #                 client_secret=self.CLIENT_SECRET
    #             )
            
    #         elif self.AUTH_METHOD == CONST_SECRET_AUTH_METHOD.CERTIFICATE:
    #             if not all([self.TENANT_ID, self.CLIENT_ID, self.CERTIFICATE_PATH]):
    #                 raise SecretConfigurationError(
    #                     "TENANT_ID, CLIENT_ID, and CERTIFICATE_PATH are required for certificate authentication",
    #                     provider="azure"
    #                 )
    #             return CertificateCredential(
    #                 tenant_id=self.TENANT_ID,
    #                 client_id=self.CLIENT_ID,
    #                 certificate_path=self.CERTIFICATE_PATH,
    #                 password=self.CERTIFICATE_PASSWORD if self.CERTIFICATE_PASSWORD else None
    #             )
            
    #         # Default to DefaultAzureCredential as fallback
    #         return DefaultAzureCredential()
            
    #     except Exception as e:
    #         raise SecretAuthenticationError(
    #             f"Failed to initialize Azure credentials: {str(e)}",
    #             provider="azure",
    #             auth_method=self.AUTH_METHOD
    #         )

    def _format_secret_name(self, name: str) -> str:
        """Format secret name with namespace if specified"""
        if self.SECRET_NAMESPACE:
            return f"{self.SECRET_NAMESPACE}-{name}"
        return name

    # def get_secret(self, name: str, version: Optional[str] = None) -> SecretStr:
    #     """
    #     Get a secret value from Azure Key Vault.
        
    #     Args:
    #         name: Name of the secret
    #         version: Optional version ID of the secret
            
    #     Returns:
    #         SecretStr containing the secret value
            
    #     Raises:
    #         SecretNotFoundError: If the secret doesn't exist
    #         SecretAccessError: If there's an error accessing the secret
    #     """
    #     try:
    #         # Check cache first
    #         cached_value = self._cache_get(name)
    #         if cached_value:
    #             return SecretStr(cached_value)

    #         secret_name = self._format_secret_name(name)
            
    #         # Get the secret
    #         if version:
    #             secret = self._client.get_secret(name=secret_name, version=version)
    #         else:
    #             secret = self._client.get_secret(name=secret_name)
            
    #         # Update cache and return
    #         self._cache_set(name, secret.value)
    #         return SecretStr(secret.value)
            
    #     except HttpResponseError as e:
    #         if e.status_code == 404:
    #             raise SecretNotFoundError(name, provider="azure", version=version)
    #         if e.status_code == 403:
    #             raise SecretAccessError(
    #                 name,
    #                 provider="azure",
    #                 operation="get: access denied"
    #             )
    #         raise SecretAccessError(
    #             name,
    #             provider="azure",
    #             operation=f"get: {str(e)}"
    #         )
    #     except Exception as e:
    #         raise SecretOperationError(
    #             "get",
    #             f"Failed to get secret: {str(e)}",
    #             provider="azure"
    #         )

    # def list_secrets(self, prefix: Optional[str] = None) -> List[str]:
    #     """
    #     List secrets from Azure Key Vault.
        
    #     Args:
    #         prefix: Optional prefix to filter secrets
            
    #     Returns:
    #         List of secret names
            
    #     Raises:
    #         SecretOperationError: If there's an error listing secrets
    #     """
    #     try:
    #         secrets = []
            
    #         # List all secrets
    #         secret_properties = self._client.list_properties_of_secrets()
            
    #         # Process each secret
    #         for secret_property in secret_properties:
    #             name = secret_property.name
                
    #             # Remove namespace prefix if present
    #             if self.SECRET_NAMESPACE:
    #                 if name.startswith(f"{self.SECRET_NAMESPACE}-"):
    #                     name = name[len(f"{self.SECRET_NAMESPACE}-"):]
    #                 else:
    #                     continue  # Skip secrets not in our namespace
                
    #             # Apply prefix filter if specified
    #             if prefix is None or name.startswith(prefix):
    #                 secrets.append(name)
            
    #         return sorted(secrets)
            
    #     except HttpResponseError as e:
    #         if e.status_code == 403:
    #             raise SecretAccessError(
    #                 "list_secrets",
    #                 provider="azure",
    #                 operation="list: access denied"
    #             )
    #         raise SecretOperationError(
    #             "list",
    #             f"Failed to list secrets: {str(e)}",
    #             provider="azure"
    #         )
    #     except Exception as e:
    #         raise SecretOperationError(
    #             "list",
    #             f"Failed to list secrets: {str(e)}",
    #             provider="azure"
    #         )

    # def get_secret_metadata(self, name: str) -> Dict[str, Any]:
    #     """
    #     Get metadata about a secret from Azure Key Vault.
        
    #     Args:
    #         name: Name of the secret
            
    #     Returns:
    #         Dictionary containing secret metadata
            
    #     Raises:
    #         SecretNotFoundError: If the secret doesn't exist
    #         SecretOperationError: If there's an error getting metadata
    #     """
    #     try:
    #         secret_name = self._format_secret_name(name)
    #         secret_properties = self._client.get_secret_properties(secret_name)
            
    #         metadata = {
    #             'id': secret_properties.id,
    #             'name': name,  # Return the original name without namespace
    #             'created': secret_properties.created_on,
    #             'updated': secret_properties.updated_on,
    #             'enabled': secret_properties.enabled,
    #             'recovery_level': secret_properties.recovery_level,
    #             'content_type': secret_properties.content_type,
    #             'tags': secret_properties.tags or {},
    #             'version': secret_properties.version
    #         }
            
    #         return metadata
            
    #     except HttpResponseError as e:
    #         if e.status_code == 404:
    #             raise SecretNotFoundError(name, provider="azure")
    #         raise SecretOperationError(
    #             "metadata",
    #             f"Failed to get secret metadata: {str(e)}",
    #             provider="azure"
    #         )
    #     except Exception as e:
    #         raise SecretOperationError(
    #             "metadata",
    #             f"Failed to get secret metadata: {str(e)}",
    #             provider="azure"
    #         )

    # def get_secret_versions(self, name: str) -> List[Dict[str, Any]]:
    #     """
    #     Get all versions of a secret from Azure Key Vault.
        
    #     Args:
    #         name: Name of the secret
            
    #     Returns:
    #         List of dictionaries containing version information
            
    #     Raises:
    #         SecretNotFoundError: If the secret doesn't exist
    #         SecretOperationError: If there's an error getting versions
    #     """
    #     try:
    #         secret_name = self._format_secret_name(name)
    #         versions = []
            
    #         # List all versions of the secret
    #         version_properties = self._client.list_properties_of_secret_versions(secret_name)
            
    #         # Process each version
    #         for version_property in version_properties:
    #             version_info = {
    #                 'version': version_property.version,
    #                 'created': version_property.created_on,
    #                 'updated': version_property.updated_on,
    #                 'enabled': version_property.enabled,
    #                 'tags': version_property.tags or {}
    #             }
    #             versions.append(version_info)
            
    #         return versions
            
    #     except HttpResponseError as e:
    #         if e.status_code == 404:
    #             raise SecretNotFoundError(name, provider="azure")
    #         raise SecretOperationError(
    #             "versions",
    #             f"Failed to get secret versions: {str(e)}",
    #             provider="azure"
    #         )
    #     except Exception as e:
    #         raise SecretOperationError(
    #             "versions",
    #             f"Failed to get secret versions: {str(e)}",
    #             provider="azure"
    #         )