#providers/aws_secrets.py


from typing import Optional, List, Tuple
from upath import UPath
from pydantic import Field, SecretStr, field_validator

# import boto3
# from botocore.exceptions import ClientError
# from botocore.config import Config

from mountainash_settings import SettingsParameters
from ..base import SecretsAuthBase
from ..constants import (
    CONST_SECRET_PROVIDER_TYPE,
    CONST_SECRET_AUTH_METHOD
)
from ..exceptions import (
    SecretValidationError
)
from ..templates import get_secrets_templates

class AWSSecretsSettings(SecretsAuthBase):
    """AWS Secrets Manager settings for read-only secret access"""
    
    PROVIDER_TYPE: str = Field(default=CONST_SECRET_PROVIDER_TYPE.AWS_SECRETS)
    
    # AWS-specific Settings
    REGION: str = Field(default=None)
    ENDPOINT_URL: Optional[str] = Field(default=None)
    
    # Authentication Settings
    AUTH_METHOD: str = Field(default=CONST_SECRET_AUTH_METHOD.IAM_ROLE)
    ACCESS_KEY_ID: Optional[str] = Field(default=None)
    SECRET_ACCESS_KEY: Optional[SecretStr] = Field(default=None)
    SESSION_TOKEN: Optional[SecretStr] = Field(default=None)
    ROLE_ARN: Optional[str] = Field(default=None)
    
    # AWS Specific Settings
    MAX_CONNECTIONS: int = Field(default=100)
    CONNECT_TIMEOUT: int = Field(default=30)
    READ_TIMEOUT: int = Field(default=30)
    
    # Internal state
    # _client: Any = None
    # _sts_client: Any = None
    # _assumed_role_credentials: Optional[Dict[str, Any]] = None

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
    @field_validator("REGION")
    def validate_region(cls, v: Optional[str]) -> str:
        """Validate AWS region format"""
        if not v:
            raise SecretValidationError(
                "REGION is required for AWS Secrets Manager",
                provider="aws",
                validation_type="region"
            )
        if not v.startswith(('us-', 'eu-', 'ap-', 'sa-', 'ca-', 'me-', 'af-')):
            raise SecretValidationError(
                f"Invalid AWS region format: {v}",
                provider="aws",
                validation_type="region"
            )
        return v

    def _init_dynamic_settings(self, reinitialise: bool = False) -> None:
        """Initialize dynamic settings from templates"""
        
        # Initialize ENDPOINT_URL if not set
        self.ENDPOINT_URL = self.init_setting_from_template(
            template_str=get_secrets_templates().AWS_SECRETS_ENDPOINT_TEMPLATE,
            current_value=self.ENDPOINT_URL,
            reinitialise=reinitialise
        )

    # def _init_provider_specific(self, reinitialise: bool = False) -> None:
    #     """Initialize AWS Secrets Manager client and authentication"""
    #     if reinitialise or self._client is None:
    #         self._init_aws_client()

    # def _init_aws_client(self) -> None:
    #     """Initialize AWS Secrets Manager client with appropriate authentication"""
    #     try:
    #         # Configure AWS client settings
    #         config = Config(
    #             max_pool_connections=self.MAX_CONNECTIONS,
    #             connect_timeout=self.CONNECT_TIMEOUT,
    #             read_timeout=self.READ_TIMEOUT,
    #             retries={'max_attempts': self.MAX_RETRIES}
    #         )
            
    #         # Handle role assumption if specified
    #         if self.AUTH_METHOD == CONST_SECRET_AUTH_METHOD.IAM_ROLE and self.ROLE_ARN:
    #             self._assume_role()
    #             credentials = self._assumed_role_credentials
    #         else:
    #             # Use direct credentials if provided
    #             credentials = {}
    #             if self.ACCESS_KEY_ID:
    #                 credentials['aws_access_key_id'] = self.ACCESS_KEY_ID
    #             if self.SECRET_ACCESS_KEY:
    #                 credentials['aws_secret_access_key'] = self.SECRET_ACCESS_KEY.get_secret_value()
    #             if self.SESSION_TOKEN:
    #                 credentials['aws_session_token'] = self.SESSION_TOKEN.get_secret_value()

    #         # Initialize the Secrets Manager client
    #         self._client = boto3.client(
    #             'secretsmanager',
    #             region_name=self.REGION,
    #             endpoint_url=self.ENDPOINT_URL,
    #             config=config,
    #             **credentials
    #         )
            
    #     except Exception as e:
    #         raise SecretConfigurationError(
    #             f"Failed to initialize AWS Secrets Manager client: {str(e)}",
    #             provider="aws"
    #         )

    # def _assume_role(self) -> None:
    #     """Assume IAM role if specified"""
    #     try:
    #         if not self._sts_client:
    #             sts_credentials = {}
    #             if self.ACCESS_KEY_ID:
    #                 sts_credentials['aws_access_key_id'] = self.ACCESS_KEY_ID
    #             if self.SECRET_ACCESS_KEY:
    #                 sts_credentials['aws_secret_access_key'] = self.SECRET_ACCESS_KEY.get_secret_value()
    #             if self.SESSION_TOKEN:
    #                 sts_credentials['aws_session_token'] = self.SESSION_TOKEN.get_secret_value()

    #             self._sts_client = boto3.client(
    #                 'sts',
    #                 region_name=self.REGION,
    #                 **sts_credentials
    #             )

    #         response = self._sts_client.assume_role(
    #             RoleArn=self.ROLE_ARN,
    #             RoleSessionName=f"SecretsAccess-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    #         )

    #         self._assumed_role_credentials = {
    #             'aws_access_key_id': response['Credentials']['AccessKeyId'],
    #             'aws_secret_access_key': response['Credentials']['SecretAccessKey'],
    #             'aws_session_token': response['Credentials']['SessionToken']
    #         }

    #     except Exception as e:
    #         raise SecretAuthenticationError(
    #             f"Failed to assume role: {str(e)}",
    #             provider="aws",
    #             auth_method=CONST_SECRET_AUTH_METHOD.IAM_ROLE
    #         )

    def _format_secret_name(self, name: str) -> str:
        """Format secret name with namespace if specified"""
        if self.SECRET_NAMESPACE:
            return f"{self.SECRET_NAMESPACE}/{name}"
        return name

    # def get_secret(self, name: str, version: Optional[str] = None) -> SecretStr:
    #     """
    #     Get a secret value from AWS Secrets Manager.
        
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

    #         secret_id = self._format_secret_name(name)
    #         kwargs = {'SecretId': secret_id}

    #         if version:
    #             kwargs['VersionId'] = version
    #         elif self.VERSION_HANDLING != CONST_AWS_SECRET_STAGES.CURRENT:
    #             kwargs['VersionStage'] = self.VERSION_HANDLING

    #         response = self._client.get_secret_value(**kwargs)
    #         secret_value = response['SecretString']

    #         # Update cache
    #         self._cache_set(name, secret_value)
            
    #         return SecretStr(secret_value)

    #     except ClientError as e:
    #         error_code = e.response['Error']['Code']
    #         if error_code == 'ResourceNotFoundException':
    #             raise SecretNotFoundError(name, provider="aws", version=version)
    #         elif error_code == 'AccessDeniedException':
    #             raise SecretAccessError(
    #                 name,
    #                 provider="aws",
    #                 operation="get: access denied"
    #             )
    #         raise SecretAccessError(
    #             name,
    #             provider="aws",
    #             operation=f"get: {error_code}"
    #         )
    #     except Exception as e:
    #         raise SecretOperationError(
    #             "get",
    #             f"Failed to get secret: {str(e)}",
    #             provider="aws"
    #         )

    # def list_secrets(self, prefix: Optional[str] = None) -> List[str]:
    #     """
    #     List secrets from AWS Secrets Manager.
        
    #     Args:
    #         prefix: Optional prefix to filter secrets
            
    #     Returns:
    #         List of secret names
            
    #     Raises:
    #         SecretOperationError: If there's an error listing secrets
    #     """
    #     try:
    #         secrets = []
    #         paginator = self._client.get_paginator('list_secrets')
            
    #         filters = []
    #         if prefix:
    #             search_prefix = f"{self.SECRET_NAMESPACE}/{prefix}" if self.SECRET_NAMESPACE else prefix
    #             filters.append({
    #                 'Key': 'name',
    #                 'Values': [search_prefix]
    #             })

    #         for page in paginator.paginate(Filters=filters):
    #             for secret in page['SecretList']:
    #                 name = secret['Name']
    #                 if self.SECRET_NAMESPACE:
    #                     if name.startswith(f"{self.SECRET_NAMESPACE}/"):
    #                         name = name[len(f"{self.SECRET_NAMESPACE}/"):]
    #                         secrets.append(name)
    #                 else:
    #                     secrets.append(name)

    #         return sorted(secrets)

    #     except ClientError as e:
    #         error_code = e.response['Error']['Code']
    #         if error_code == 'AccessDeniedException':
    #             raise SecretAccessError(
    #                 "list_secrets",
    #                 provider="aws",
    #                 operation="list: access denied"
    #             )
    #         raise SecretOperationError(
    #             "list",
    #             f"Failed to list secrets: {error_code}",
    #             provider="aws"
    #         )
    #     except Exception as e:
    #         raise SecretOperationError(
    #             "list",
    #             f"Failed to list secrets: {str(e)}",
    #             provider="aws"
    #         )

    # def get_secret_metadata(self, name: str) -> Dict[str, Any]:
    #     """
    #     Get metadata about a secret from AWS Secrets Manager.
        
    #     Args:
    #         name: Name of the secret
            
    #     Returns:
    #         Dictionary containing secret metadata
            
    #     Raises:
    #         SecretNotFoundError: If the secret doesn't exist
    #         SecretOperationError: If there's an error getting metadata
    #     """
    #     try:
    #         secret_id = self._format_secret_name(name)
    #         response = self._client.describe_secret(SecretId=secret_id)
            
    #         metadata = {
    #             'name': name,
    #             'arn': response.get('ARN'),
    #             'description': response.get('Description'),
    #             'kms_key_id': response.get('KmsKeyId'),
    #             'last_changed_date': response.get('LastChangedDate').isoformat() if response.get('LastChangedDate') else None,
    #             'last_accessed_date': response.get('LastAccessedDate').isoformat() if response.get('LastAccessedDate') else None,
    #             'deletion_date': response.get('DeletedDate').isoformat() if response.get('DeletedDate') else None,
    #             'tags': {tag['Key']: tag['Value'] for tag in response.get('Tags', [])},
    #             'versions': list(response.get('VersionIdsToStages', {}).keys())
    #         }
            
    #         return metadata

    #     except ClientError as e:
    #         error_code = e.response['Error']['Code']
    #         if error_code == 'ResourceNotFoundException':
    #             raise SecretNotFoundError(name, provider="aws")
    #         elif error_code == 'AccessDeniedException':
    #             raise SecretAccessError(
    #                 name,
    #                 provider="aws",
    #                 operation="metadata: access denied"
    #             )
    #         raise SecretOperationError(
    #             "metadata",
    #             f"Failed to get secret metadata: {error_code}",
    #             provider="aws"
    #         )
    #     except Exception as e:
    #         raise SecretOperationError(
    #             "metadata",
    #             f"Failed to get secret metadata: {str(e)}",
    #             provider="aws"
    #         )

    # def get_secret_versions(self, name: str) -> List[Dict[str, Any]]:
    #     """
    #     Get all versions of a secret from AWS Secrets Manager.
        
    #     Args:
    #         name: Name of the secret
            
    #     Returns:
    #         List of dictionaries containing version information
            
    #     Raises:
    #         SecretNotFoundError: If the secret doesn't exist
    #         SecretOperationError: If there's an error getting versions
    #     """
    #     try:
    #         secret_id = self._format_secret_name(name)
    #         metadata = self.get_secret_metadata(name)
    #         versions = []
            
    #         for version_id in metadata['versions']:
    #             try:
    #                 version_response = self._client.get_secret_value(
    #                     SecretId=secret_id,
    #                     VersionId=version_id
    #                 )
                    
    #                 version_info = {
    #                     'version_id': version_id,
    #                     'created_date': version_response['CreatedDate'].isoformat(),
    #                     'stages': version_response.get('VersionStages', [])
    #                 }
    #                 versions.append(version_info)
                    
    #             except ClientError as e:
    #                 # Skip versions we can't access (might be deleted or lacking permissions)
    #                 if e.response['Error']['Code'] != 'ResourceNotFoundException':
    #                     versions.append({
    #                         'version_id': version_id,
    #                         'error': e.response['Error']['Code']
    #                     })

    #         return sorted(versions, key=lambda x: x.get('version_id', ''))

    #     except Exception as e:
    #         if isinstance(e, (SecretNotFoundError, SecretAccessError)):
    #             raise
    #         raise SecretOperationError(
    #             "versions",
    #             f"Failed to get secret versions: {str(e)}",
    #             provider="aws"
    #         )