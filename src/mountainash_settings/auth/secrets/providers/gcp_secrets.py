#providers/gcp_secrets.py


from typing import Optional, List, Any, Dict, Tuple
from upath import UPath
from pydantic import Field, field_validator

# from google.cloud.secretmanager_v1 import SecretManagerServiceClient
# from google.api_core import exceptions as google_exceptions
# from google.oauth2 import service_account
# from google.auth import exceptions as auth_exceptions
# from google.auth.credentials import Credentials

from ..base import SecretsAuthBase
from ..constants import (
    CONST_SECRET_PROVIDER_TYPE,
    CONST_SECRET_AUTH_METHOD
)
from ..exceptions import (
    SecretValidationError
)
from ..templates import get_secrets_templates

class GCPSecretsSettings(SecretsAuthBase):
    """Google Cloud Secret Manager settings for read-only secret access"""
    
    PROVIDER_TYPE: str = Field(default=CONST_SECRET_PROVIDER_TYPE.GCP_SECRETS)
    
    # GCP-specific Settings
    PROJECT_ID: str = Field(default=None)
    SERVICE_ACCOUNT_INFO: Optional[Dict[str, Any]] = Field(default=None)
    SERVICE_ACCOUNT_FILE: Optional[str] = Field(default=None)
    
    # Authentication Settings
    AUTH_METHOD: str = Field(default=CONST_SECRET_AUTH_METHOD.SERVICE_ACCOUNT)
    
    # Dynamic Settings
    ENDPOINT_URL: Optional[str] = Field(default=None)
    
    # Internal state
    # _client: Optional[SecretManagerServiceClient] = None
    # _credentials: Optional[Credentials] = None

    def __init__(self, 
                 config_files: Optional[str|UPath|List[str|UPath]|Tuple[str|UPath]] = None,
                 _dummy: Optional[bool] = False,
                 **kwargs) -> None:  
        super().__init__(config_files=config_files, _dummy=_dummy, **kwargs)

    ## Field Validators ##
    @field_validator("PROJECT_ID")
    def validate_project_id(cls, v: Optional[str]) -> str:
        """Validate project ID format"""
        if not v:
            raise SecretValidationError(
                "PROJECT_ID is required for GCP Secret Manager",
                provider="gcp",
                validation_type="project_id"
            )
        return v

    def _init_dynamic_settings(self, reinitialise: bool = False) -> None:
        """Initialize dynamic settings from templates"""

        # Initialize ENDPOINT_URL if not set
        self.ENDPOINT_URL = self.init_setting_from_template(
            template_str=get_secrets_templates().GCP_SECRETS_ENDPOINT_TEMPLATE,
            current_value=self.ENDPOINT_URL,
            reinitialise=reinitialise
        )

    # def _init_provider_specific(self, reinitialise: bool = False) -> None:
    #     """Initialize GCP Secret Manager client and authentication"""
    #     if reinitialise or self._client is None:
    #         self._init_gcp_client()

    # def _init_gcp_client(self) -> None:
    #     """Initialize GCP Secret Manager client with appropriate authentication"""
    #     try:
    #         # Initialize credentials
    #         self._credentials = self._get_credentials()
            
    #         # Initialize the Secret Manager client
    #         client_options = {}
    #         if self.ENDPOINT_URL:
    #             client_options['api_endpoint'] = self.ENDPOINT_URL
                
    #         self._client = SecretManagerServiceClient(
    #             credentials=self._credentials,
    #             client_options=client_options
    #         )
            
    #     except Exception as e:
    #         raise SecretConfigurationError(
    #             f"Failed to initialize GCP Secret Manager client: {str(e)}",
    #             provider="gcp"
    #         )

    # def _get_credentials(self) -> Credentials:
    #     """
    #     Get the appropriate GCP credentials based on configuration.
        
    #     Returns:
    #         Credentials: The appropriate GCP credential object
        
    #     Raises:
    #         SecretConfigurationError: If authentication configuration is invalid
    #     """
    #     try:
    #         if self.SERVICE_ACCOUNT_INFO:
    #             # Use service account info dictionary
    #             return service_account.Credentials.from_service_account_info(
    #                 self.SERVICE_ACCOUNT_INFO
    #             )
            
    #         elif self.SERVICE_ACCOUNT_FILE:
    #             # Use service account file
    #             return service_account.Credentials.from_service_account_file(
    #                 self.SERVICE_ACCOUNT_FILE
    #             )
            
    #         # Default to application default credentials
    #         return None  # Let the client use application default credentials
            
    #     except auth_exceptions.DefaultCredentialsError:
    #         raise SecretAuthenticationError(
    #             "No valid credentials found. Please provide service account credentials or ensure application default credentials are set.",
    #             provider="gcp",
    #             auth_method=self.AUTH_METHOD
    #         )
    #     except Exception as e:
    #         raise SecretAuthenticationError(
    #             f"Failed to initialize GCP credentials: {str(e)}",
    #             provider="gcp",
    #             auth_method=self.AUTH_METHOD
    #         )

    def _format_secret_name(self, name: str) -> str:
        """
        Format the full secret name according to GCP naming convention.
        Format: projects/{project}/secrets/{secret}
        """
        secret_name = name
        if self.SECRET_NAMESPACE:
            secret_name = f"{self.SECRET_NAMESPACE}-{name}"
        return f"projects/{self.PROJECT_ID}/secrets/{secret_name}"

    def _format_secret_version(self, secret_name: str, version: str = "latest") -> str:
        """
        Format the full secret version name.
        Format: projects/{project}/secrets/{secret}/versions/{version}
        """
        return f"{secret_name}/versions/{version}"

    # def get_secret(self, name: str, version: Optional[str] = None) -> SecretStr:
    #     """
    #     Get a secret value from GCP Secret Manager.
        
    #     Args:
    #         name: Name of the secret
    #         version: Optional version ID of the secret (default: "latest")
            
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

    #         # Format the full secret name
    #         secret_name = self._format_secret_name(name)
    #         version_name = self._format_secret_version(
    #             secret_name, 
    #             version or "latest"
    #         )
            
    #         # Access the secret version
    #         response = self._client.access_secret_version(
    #             request={"name": version_name}
    #         )
            
    #         # Get the secret value
    #         secret_value = response.payload.data.decode("UTF-8")
            
    #         # Update cache and return
    #         self._cache_set(name, secret_value)
    #         return SecretStr(secret_value)
            
    #     except google_exceptions.NotFound:
    #         raise SecretNotFoundError(name, provider="gcp", version=version)
    #     except google_exceptions.PermissionDenied:
    #         raise SecretAccessError(
    #             name,
    #             provider="gcp",
    #             operation="get: access denied"
    #         )
    #     except Exception as e:
    #         raise SecretOperationError(
    #             "get",
    #             f"Failed to get secret: {str(e)}",
    #             provider="gcp"
    #         )

    # def list_secrets(self, prefix: Optional[str] = None) -> List[str]:
    #     """
    #     List secrets from GCP Secret Manager.
        
    #     Args:
    #         prefix: Optional prefix to filter secrets
            
    #     Returns:
    #         List of secret names
            
    #     Raises:
    #         SecretOperationError: If there's an error listing secrets
    #     """
    #     try:
    #         secrets = []
    #         parent = f"projects/{self.PROJECT_ID}"
            
    #         # List all secrets
    #         try:
    #             # Use pagination to handle large lists
    #             list_response = self._client.list_secrets(request={"parent": parent})
                
    #             for secret in list_response:
    #                 # Extract the secret name from the full path
    #                 name = secret.name.split('/')[-1]
                    
    #                 # Handle namespace
    #                 if self.SECRET_NAMESPACE:
    #                     if name.startswith(f"{self.SECRET_NAMESPACE}-"):
    #                         name = name[len(f"{self.SECRET_NAMESPACE}-"):]
    #                     else:
    #                         continue  # Skip secrets not in our namespace
                    
    #                 # Apply prefix filter if specified
    #                 if prefix is None or name.startswith(prefix):
    #                     secrets.append(name)
            
    #         except google_exceptions.PermissionDenied:
    #             raise SecretAccessError(
    #                 "list_secrets",
    #                 provider="gcp",
    #                 operation="list: access denied"
    #             )
            
    #         return sorted(secrets)
            
    #     except Exception as e:
    #         raise SecretOperationError(
    #             "list",
    #             f"Failed to list secrets: {str(e)}",
    #             provider="gcp"
    #         )

    # def get_secret_metadata(self, name: str) -> Dict[str, Any]:
    #     """
    #     Get metadata about a secret from GCP Secret Manager.
        
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
            
    #         # Get the secret metadata
    #         secret = self._client.get_secret(request={"name": secret_name})
            
    #         # Convert the Timestamp objects to ISO format strings
    #         metadata = {
    #             'name': name,  # Return the original name without namespace
    #             'create_time': secret.create_time.isoformat() if secret.create_time else None,
    #             'labels': dict(secret.labels) if secret.labels else {},
    #             'topics': list(secret.topics) if secret.topics else [],
    #             'rotation': {
    #                 'next_rotation_time': secret.rotation.next_rotation_time.isoformat() if secret.rotation and secret.rotation.next_rotation_time else None,
    #                 'rotation_period': str(secret.rotation.rotation_period) if secret.rotation and secret.rotation.rotation_period else None
    #             } if secret.rotation else None,
    #             'version_aliases': dict(secret.version_aliases) if secret.version_aliases else {}
    #         }
            
    #         return metadata
            
    #     except google_exceptions.NotFound:
    #         raise SecretNotFoundError(name, provider="gcp")
    #     except google_exceptions.PermissionDenied:
    #         raise SecretAccessError(
    #             name,
    #             provider="gcp",
    #             operation="metadata: access denied"
    #         )
    #     except Exception as e:
    #         raise SecretOperationError(
    #             "metadata",
    #             f"Failed to get secret metadata: {str(e)}",
    #             provider="gcp"
    #         )

    # def get_secret_versions(self, name: str) -> List[Dict[str, Any]]:
    #     """
    #     Get all versions of a secret from GCP Secret Manager.
        
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
    #         try:
    #             list_response = self._client.list_secret_versions(
    #                 request={"parent": secret_name}
    #             )
                
    #             for version in list_response:
    #                 version_info = {
    #                     'name': version.name.split('/')[-1],  # Extract version number
    #                     'state': version.state.name if version.state else None,
    #                     'create_time': version.create_time.isoformat() if version.create_time else None,
    #                     'destroy_time': version.destroy_time.isoformat() if version.destroy_time else None,
    #                 }
    #                 versions.append(version_info)
            
    #         except google_exceptions.NotFound:
    #             raise SecretNotFoundError(name, provider="gcp")
    #         except google_exceptions.PermissionDenied:
    #             raise SecretAccessError(
    #                 name,
    #                 provider="gcp",
    #                 operation="versions: access denied"
    #             )
            
    #         return versions
            
    #     except Exception as e:
    #         raise SecretOperationError(
    #             "versions",
    #             f"Failed to get secret versions: {str(e)}",
    #             provider="gcp"
    #         )