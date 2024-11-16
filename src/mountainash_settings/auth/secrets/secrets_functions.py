from typing import List, Optional, Union
from mountainash_settings import prepare_settings_parameters, get_settings
from upath import UPath

from .base import SecretsAuthBase
from .constants import CONST_SECRET_PROVIDER_TYPE

from .providers.azure_keyvault import AzureKeyVaultSettings
from .providers.aws_secrets import AWSSecretsSettings
from .providers.gcp_secrets import GCPSecretsSettings
# from .providers.hashicorp import HashiCorpVaultSettings
from .providers.local_secrets import LocalSecretsSettings



def create_secrets_settings(
    provider_type: str,
    settings_namespace: str,
    config_files: Optional[Union[UPath, str, List[UPath|str]]] = None,
    **kwargs
) -> SecretsAuthBase:
    """Factory function to create appropriate secrets settings instance"""
    
    provider_map = {
        CONST_SECRET_PROVIDER_TYPE.AZURE_KEYVAULT: AzureKeyVaultSettings,
        CONST_SECRET_PROVIDER_TYPE.AWS_SECRETS: AWSSecretsSettings,
        CONST_SECRET_PROVIDER_TYPE.GCP_SECRETS: GCPSecretsSettings,
        # CONST_SECRET_PROVIDER_TYPE.HASHICORP: HashiCorpVaultSettings,
        CONST_SECRET_PROVIDER_TYPE.LOCAL: LocalSecretsSettings,
    }
    
    settings_class = provider_map.get(provider_type)
    if not settings_class:
        raise ValueError(f"Unknown provider type: {provider_type}")
    
    settings_parameters = prepare_settings_parameters(
        settings_namespace=settings_namespace,
        settings_class=settings_class,
        config_files=config_files,
        **kwargs
    )
    
    return get_settings(settings_parameters=settings_parameters)