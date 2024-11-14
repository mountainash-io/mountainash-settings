#path: mountainash_settings/auth/database/integration/secrets.py

from typing import Optional, Dict, Any
from functools import lru_cache
from pydantic import SecretStr

from mountainash_settings.auth.database.base import BaseDBAuthSettings
from mountainash_settings.auth.database.exceptions import DBAuthConfigError, DBAuthSecurityError

from mountainash_settings.auth.secrets import create_secrets_settings
from mountainash_settings.auth.database.constants import CONST_DB_PROVIDER_TYPE

class DBSecretsIntegration:
    """Integration with Mountain Ash secrets system"""
    
    def __init__(self, auth_settings: BaseDBAuthSettings):
        self.auth_settings = auth_settings
        self._secrets_client = None
        self._secret_cache: Dict[str, Any] = {}
    
    @property
    def secrets_client(self):
        """Lazy initialization of secrets client"""
        if not self._secrets_client and self.auth_settings.SECRETS_NAMESPACE:
            self._init_secrets_client()
        return self._secrets_client
    
    def _init_secrets_client(self) -> None:
        """Initialize the secrets client"""
        try:
            self._secrets_client = create_secrets_settings(
                provider_type=self._get_secret_provider_type(),
                settings_namespace=self.auth_settings.SECRETS_NAMESPACE
            )
        except Exception as e:
            raise DBAuthConfigError(
                f"Failed to initialize secrets client: {str(e)}",
                provider=self.auth_settings.PROVIDER_TYPE
            )
    
    def _get_secret_provider_type(self) -> str:
        """Map database provider to appropriate secrets provider"""
        provider_map = {
            CONST_DB_PROVIDER_TYPE.MYSQL: "local",
            CONST_DB_PROVIDER_TYPE.POSTGRESQL: "local",
            CONST_DB_PROVIDER_TYPE.MSSQL: "local",
            CONST_DB_PROVIDER_TYPE.SNOWFLAKE: "local",
            CONST_DB_PROVIDER_TYPE.BIGQUERY: "gcp_secrets",
            CONST_DB_PROVIDER_TYPE.REDSHIFT: "aws_secrets",
            CONST_DB_PROVIDER_TYPE.SQLITE: "local",
            CONST_DB_PROVIDER_TYPE.DUCKDB: "local"
        }
        return provider_map.get(self.auth_settings.PROVIDER_TYPE, "local")
    
    def get_credentials(self) -> Dict[str, SecretStr]:
        """
        Retrieve credentials from secret store
        
        Returns:
            Dictionary containing username and password
            
        Raises:
            DBAuthSecurityError: If secret retrieval fails
        """
        if not self.auth_settings.SECRETS_NAMESPACE:
            raise DBAuthConfigError(
                "Secrets namespace not configured",
                provider=self.auth_settings.PROVIDER_TYPE
            )
            
        try:
            namespace = self.auth_settings.SECRETS_NAMESPACE
            credentials = {}
            
            # Get username
            username_key = f"{namespace}/username"
            if username_key not in self._secret_cache:
                self._secret_cache[username_key] = self.secrets_client.get_secret(
                    username_key
                )
            credentials["username"] = self._secret_cache[username_key]
            
            # Get password
            password_key = f"{namespace}/password"
            if password_key not in self._secret_cache:
                self._secret_cache[password_key] = self.secrets_client.get_secret(
                    password_key
                )
            credentials["password"] = self._secret_cache[password_key]
            
            return credentials
            
        except Exception as e:
            raise DBAuthSecurityError(
                f"Failed to retrieve credentials: {str(e)}",
                provider=self.auth_settings.PROVIDER_TYPE,
                security_check="credential_retrieval"
            )
    
    def get_secret(self, secret_name: str) -> SecretStr:
        """
        Retrieve a specific secret
        
        Args:
            secret_name: Name of the secret to retrieve
            
        Returns:
            SecretStr containing the secret value
            
        Raises:
            DBAuthSecurityError: If secret retrieval fails
        """
        try:
            secret_key = f"{self.auth_settings.SECRETS_NAMESPACE}/{secret_name}"
            if secret_key not in self._secret_cache:
                self._secret_cache[secret_key] = self.secrets_client.get_secret(
                    secret_key
                )
            return self._secret_cache[secret_key]
        except Exception as e:
            raise DBAuthSecurityError(
                f"Failed to retrieve secret {secret_name}: {str(e)}",
                provider=self.auth_settings.PROVIDER_TYPE,
                security_check="secret_retrieval"
            )
    
    def rotate_credentials(self) -> None:
        """
        Rotate database credentials
        
        Raises:
            DBAuthSecurityError: If credential rotation fails
        """
        raise NotImplementedError("Credential rotation not yet implemented")
    
    def clear_cache(self) -> None:
        """Clear the secret cache"""
        self._secret_cache.clear()