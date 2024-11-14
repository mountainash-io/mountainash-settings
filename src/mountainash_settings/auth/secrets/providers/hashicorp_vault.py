#providers/hashicorp_vault.py

from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import Field, SecretStr, field_validator
import hvac
from hvac.exceptions import InvalidRequest, Forbidden, InvalidPath
from urllib.parse import urljoin

from ..base import SecretsAuthBase
from ..constants import (
    CONST_SECRET_PROVIDER_TYPE,
    CONST_SECRET_AUTH_METHOD
)
from ..exceptions import (
    SecretConfigurationError,
    SecretAuthenticationError,
    SecretNotFoundError,
    SecretAccessError,
    SecretOperationError,
    SecretValidationError
)
from ..templates import get_secrets_settings_templates

class HashiCorpVaultSettings(SecretsAuthBase):
    """HashiCorp Vault settings for read-only secret access"""
    
    PROVIDER_TYPE: str = Field(default=CONST_SECRET_PROVIDER_TYPE.HASHICORP)
    
    # Vault Connection Settings
    VAULT_HOST: str = Field(default=None)
    VAULT_PORT: int = Field(default=8200)
    VAULT_SCHEME: str = Field(default="https")
    
    # Authentication Settings
    AUTH_METHOD: str = Field(default=CONST_SECRET_AUTH_METHOD.TOKEN)
    VAULT_TOKEN: Optional[SecretStr] = Field(default=None)
    
    # Certificate Settings
    CERT_PATH: Optional[str] = Field(default=None)
    KEY_PATH: Optional[str] = Field(default=None)
    CERT_VERIFY: bool = Field(default=True)
    CA_PATH: Optional[str] = Field(default=None)
    
    # Vault Specific Settings
    MOUNT_POINT: str = Field(default="secret")  # KV secrets engine mount point
    KV_VERSION: int = Field(default=2)  # KV secrets engine version
    
    # Dynamic Settings
    VAULT_URL: Optional[str] = Field(default=None)
    
    # Internal state
    _client: Optional[hvac.Client] = None

    ## Field Validators ##
    @field_validator("VAULT_HOST")
    def validate_vault_host(cls, v: Optional[str]) -> str:
        """Validate Vault host"""
        if not v:
            raise SecretValidationError(
                "VAULT_HOST is required for HashiCorp Vault",
                provider="vault",
                validation_type="host"
            )
        return v

    @field_validator("KV_VERSION")
    def validate_kv_version(cls, v: int) -> int:
        """Validate KV version"""
        if v not in [1, 2]:
            raise SecretValidationError(
                "KV_VERSION must be either 1 or 2",
                provider="vault",
                validation_type="kv_version"
            )
        return v

    def _init_dynamic_settings(self, reinitialise: bool = False) -> None:
        """Initialize dynamic settings from templates"""
        templates = get_secrets_settings_templates()
        
        # Initialize VAULT_URL if not set
        vault_addr_template = templates.VAULT_ADDR_TEMPLATE
        self.VAULT_URL = self.init_setting_from_template(
            template_str=vault_addr_template,
            current_value=self.VAULT_URL,
            reinitialise=reinitialise
        )

    def _init_provider_specific(self, reinitialise: bool = False) -> None:
        """Initialize HashiCorp Vault client and authentication"""
        if reinitialise or self._client is None:
            self._init_vault_client()

    def _init_vault_client(self) -> None:
        """Initialize HashiCorp Vault client with appropriate authentication"""
        try:
            # Prepare SSL verification settings
            if self.CERT_VERIFY and self.CA_PATH:
                verify = self.CA_PATH
            else:
                verify = self.CERT_VERIFY

            # Prepare client certificate if configured
            cert = None
            if self.CERT_PATH and self.KEY_PATH:
                cert = (self.CERT_PATH, self.KEY_PATH)
            
            # Build Vault URL
            url = f"{self.VAULT_SCHEME}://{self.VAULT_HOST}:{self.VAULT_PORT}"
            
            # Initialize the Vault client
            self._client = hvac.Client(
                url=url,
                token=self.VAULT_TOKEN.get_secret_value() if self.VAULT_TOKEN else None,
                cert=cert,
                verify=verify
            )
            
            # Verify authentication
            if not self._client.is_authenticated():
                raise SecretAuthenticationError(
                    "Failed to authenticate with Vault",
                    provider="vault",
                    auth_method=self.AUTH_METHOD
                )
            
        except Exception as e:
            raise SecretConfigurationError(
                f"Failed to initialize HashiCorp Vault client: {str(e)}",
                provider="vault"
            )

    def _format_path(self, name: str) -> str:
        """Format the secret path according to namespace and KV version"""
        # Add namespace prefix if specified
        if self.SECRET_NAMESPACE:
            name = f"{self.SECRET_NAMESPACE}/{name}"
            
        # For KV v2, data needs to be included in the path
        if self.KV_VERSION == 2:
            # Split path into parts to handle potential subpaths
            path_parts = name.split('/')
            # Insert 'data' after the first component (which is typically the mount point)
            if len(path_parts) > 1:
                path_parts.insert(1, 'data')
            name = '/'.join(path_parts)
            
        return name

    def _extract_secret_value(self, response: Dict[str, Any]) -> str:
        """Extract secret value from Vault response based on KV version"""
        try:
            if self.KV_VERSION == 2:
                return response['data']['data']['value']
            return response['data']['value']
        except KeyError:
            raise SecretOperationError(
                "extract",
                "Unexpected secret format in response",
                provider="vault"
            )

    def get_secret(self, name: str, version: Optional[str] = None) -> SecretStr:
        """
        Get a secret value from HashiCorp Vault.
        
        Args:
            name: Name of the secret
            version: Optional version number (only for KV v2)
            
        Returns:
            SecretStr containing the secret value
            
        Raises:
            SecretNotFoundError: If the secret doesn't exist
            SecretAccessError: If there's an error accessing the secret
        """
        try:
            # Check cache first
            cached_value = self._cache_get(name)
            if cached_value:
                return SecretStr(cached_value)

            # Format the secret path
            path = self._format_path(name)
            
            # Read the secret
            try:
                if self.KV_VERSION == 2:
                    kwargs = {'path': path}
                    if version:
                        kwargs['version'] = version
                    response = self._client.secrets.kv.v2.read_secret_version(
                        mount_point=self.MOUNT_POINT,
                        **kwargs
                    )
                else:
                    response = self._client.secrets.kv.v1.read_secret(
                        path=path,
                        mount_point=self.MOUNT_POINT
                    )
                
                # Extract and cache the secret value
                secret_value = self._extract_secret_value(response)
                self._cache_set(name, secret_value)
                return SecretStr(secret_value)
                
            except InvalidPath:
                raise SecretNotFoundError(name, provider="vault", version=version)
            except Forbidden:
                raise SecretAccessError(
                    name,
                    provider="vault",
                    operation="get: access denied"
                )
                
        except Exception as e:
            if isinstance(e, (SecretNotFoundError, SecretAccessError)):
                raise
            raise SecretOperationError(
                "get",
                f"Failed to get secret: {str(e)}",
                provider="vault"
            )

    def list_secrets(self, prefix: Optional[str] = None) -> List[str]:
        """
        List secrets from HashiCorp Vault.
        
        Args:
            prefix: Optional prefix to filter secrets
            
        Returns:
            List of secret names
            
        Raises:
            SecretOperationError: If there's an error listing secrets
        """
        try:
            # Determine the list path based on KV version
            base_path = self.SECRET_NAMESPACE if self.SECRET_NAMESPACE else ""
            if self.KV_VERSION == 2:
                list_path = f"metadata/{base_path}" if base_path else "metadata"
            else:
                list_path = base_path
            
            try:
                # List secrets
                if self.KV_VERSION == 2:
                    response = self._client.secrets.kv.v2.list_secrets(
                        path=list_path,
                        mount_point=self.MOUNT_POINT
                    )
                else:
                    response = self._client.secrets.kv.v1.list_secrets(
                        path=list_path,
                        mount_point=self.MOUNT_POINT
                    )
                
                # Extract secret names
                secrets = response.get('data', {}).get('keys', [])
                
                # Filter by prefix if specified
                if prefix:
                    secrets = [s for s in secrets if s.startswith(prefix)]
                
                # Remove namespace prefix if present
                if self.SECRET_NAMESPACE:
                    secrets = [
                        s[len(f"{self.SECRET_NAMESPACE}/"):]
                        for s in secrets
                        if s.startswith(f"{self.SECRET_NAMESPACE}/")
                    ]
                
                return sorted(secrets)
                
            except InvalidPath:
                return []  # Return empty list if path doesn't exist
            except Forbidden:
                raise SecretAccessError(
                    "list_secrets",
                    provider="vault",
                    operation="list: access denied"
                )
                
        except Exception as e:
            if isinstance(e, SecretAccessError):
                raise
            raise SecretOperationError(
                "list",
                f"Failed to list secrets: {str(e)}",
                provider="vault"
            )

    def get_secret_metadata(self, name: str) -> Dict[str, Any]:
        """
        Get metadata about a secret from HashiCorp Vault.
        Only available for KV v2.
        
        Args:
            name: Name of the secret
            
        Returns:
            Dictionary containing secret metadata
            
        Raises:
            SecretNotFoundError: If the secret doesn't exist
            SecretOperationError: If there's an error getting metadata
        """
        if self.KV_VERSION == 1:
            raise NotImplementedError("Metadata is only available for KV v2")
            
        try:
            path = self._format_path(name)
            
            try:
                # Get metadata
                response = self._client.secrets.kv.v2.read_secret_metadata(
                    path=path,
                    mount_point=self.MOUNT_POINT
                )
                
                metadata = {
                    'name': name,
                    'created_time': response['data'].get('created_time'),
                    'updated_time': response['data'].get('updated_time'),
                    'deletion_time': response['data'].get('deletion_time'),
                    'current_version': response['data'].get('current_version'),
                    'oldest_version': response['data'].get('oldest_version'),
                    'max_versions': response['data'].get('max_versions'),
                    'versions': response['data'].get('versions', {}),
                    'custom_metadata': response['data'].get('custom_metadata', {})
                }
                
                return metadata
                
            except InvalidPath:
                raise SecretNotFoundError(name, provider="vault")
            except Forbidden:
                raise SecretAccessError(
                    name,
                    provider="vault",
                    operation="metadata: access denied"
                )
                
        except Exception as e:
            if isinstance(e, (SecretNotFoundError, SecretAccessError)):
                raise
            raise SecretOperationError(
                "metadata",
                f"Failed to get secret metadata: {str(e)}",
                provider="vault"
            )

    def get_secret_versions(self, name: str) -> List[Dict[str, Any]]:
        """
        Get all versions of a secret from HashiCorp Vault.
        Only available for KV v2.
        
        Args:
            name: Name of the secret
            
        Returns:
            List of dictionaries containing version information
            
        Raises:
            SecretNotFoundError: If the secret doesn't exist
            SecretOperationError: If there's an error getting versions
        """
        if self.KV_VERSION == 1:
            raise NotImplementedError("Version history is only available for KV v2")
            
        try:
            metadata = self.get_secret_metadata(name)
            versions = []
            
            for version_num, version_data in metadata['versions'].items():
                version_info = {
                    'version': version_num,
                    'created_time': version_data.get('created_time'),
                    'deletion_time': version_data.get('deletion_time'),
                    'destroyed': version_data.get('destroyed', False)
                }
                versions.append(version_info)
            
            return sorted(versions, key=lambda x: x['version'])
            
        except Exception as e:
            if isinstance(e, (SecretNotFoundError, SecretAccessError)):
                raise
            raise SecretOperationError(
                "versions",
                f"Failed to get secret versions: {str(e)}",
                provider="vault"
            )