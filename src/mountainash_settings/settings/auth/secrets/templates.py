
from pydantic import Field
from pydantic_settings import BaseSettings
from functools import lru_cache

class SecretsSettingsTemplates(BaseSettings):

    """Templates for secret-related settings"""
    
    # Connection Templates
    AZURE_KEYVAULT_URL_TEMPLATE: str = Field(
        default="https://{VAULT_NAME}.vault.azure.net/"
    )
    
    AWS_SECRETS_ENDPOINT_TEMPLATE: str = Field(
        default="https://secretsmanager.{REGION}.amazonaws.com"
    )
    
    GCP_SECRETS_ENDPOINT_TEMPLATE: str = Field(
        default="https://secretmanager.googleapis.com/v1/projects/{PROJECT_ID}"
    )
    
    VAULT_ADDR_TEMPLATE: str = Field(
        default="https://{VAULT_HOST}:{VAULT_PORT}"
    )
    
    # Composite Setting Templates
    AZURE_CONNECTION_STRING_TEMPLATE: str = Field(
        default="DefaultEndpointsProtocol=https;AccountName={STORAGE_ACCOUNT};AccountKey={ACCOUNT_KEY};EndpointSuffix=core.windows.net"
    )
    
    AWS_CREDENTIALS_TEMPLATE: str = Field(
        default='{"aws_access_key_id": "{ACCESS_KEY}", "aws_secret_access_key": "{SECRET_KEY}", "region": "{REGION}"}'
    )

@lru_cache(maxsize=None)
def get_secrets_templates() -> SecretsSettingsTemplates:

    return SecretsSettingsTemplates()    