#path: mountainash_settings/auth/database/providers/cloud/snowflake.py

from typing import Optional, Dict, Any
from pydantic import Field, SecretStr, field_validator
import re

from mountainash_settings.auth.database.base import BaseDBAuthSettings
from mountainash_settings.auth.database.constants import (
    CONST_DB_PROVIDER_TYPE,
    CONST_DB_AUTH_METHOD
)
from mountainash_settings.auth.database.exceptions import (
    DBAuthValidationError,
    DBAuthConnectionError
)

class SnowflakeAuthSettings(BaseDBAuthSettings):
    """Snowflake authentication settings"""
    
    PROVIDER_TYPE: str = Field(default=CONST_DB_PROVIDER_TYPE.SNOWFLAKE)
    
    # Snowflake-specific Settings
    ACCOUNT: str = Field(...)
    WAREHOUSE: str = Field(...)
    ROLE: Optional[str] = Field(default=None)
    PRIVATE_KEY: Optional[SecretStr] = Field(default=None)
    PRIVATE_KEY_PATH: Optional[str] = Field(default=None)
    PRIVATE_KEY_PASSPHRASE: Optional[SecretStr] = Field(default=None)
    
    # OAuth Settings
    OAUTH_TOKEN: Optional[SecretStr] = Field(default=None)
    OAUTH_CLIENT_ID: Optional[str] = Field(default=None)
    OAUTH_CLIENT_SECRET: Optional[SecretStr] = Field(default=None)
    OAUTH_REFRESH_TOKEN: Optional[SecretStr] = Field(default=None)
    
    # Connection Settings
    DATABASE: Optional[str] = Field(default=None)
    SCHEMA: Optional[str] = Field(default=None)
    REGION: Optional[str] = Field(default=None)
    
    # Session Settings
    QUERY_TAG: Optional[str] = Field(default=None)
    APPLICATION: Optional[str] = Field(default="MountainAsh")
    CLIENT_SESSION_KEEP_ALIVE: bool = Field(default=True)
    
    ## Field Validators ##
    @field_validator("ACCOUNT")
    def validate_account(cls, v: str) -> str:
        """Validate Snowflake account identifier"""
        if not v:
            raise DBAuthValidationError(
                "Account identifier is required",
                provider=CONST_DB_PROVIDER_TYPE.SNOWFLAKE,
                validation_type="account"
            )
        
        # Account pattern: orgname-accountname
        if not re.match(r'^[a-zA-Z0-9-_]+$', v):
            raise DBAuthValidationError(
                "Invalid account identifier format",
                provider=CONST_DB_PROVIDER_TYPE.SNOWFLAKE,
                validation_type="account"
            )
        return v

    def _init_provider_specific(self, reinitialise: bool) -> None:
        """Initialize provider-specific settings"""
        # Validate authentication method
        if self.AUTH_METHOD == CONST_DB_AUTH_METHOD.CERTIFICATE:
            if not (self.PRIVATE_KEY or self.PRIVATE_KEY_PATH):
                raise DBAuthValidationError(
                    "Private key or key path required for certificate authentication",
                    provider=self.PROVIDER_TYPE,
                    validation_type="auth_method"
                )
        elif self.AUTH_METHOD == "oauth":
            if not (self.OAUTH_TOKEN or (self.OAUTH_CLIENT_ID and self.OAUTH_CLIENT_SECRET)):
                raise DBAuthValidationError(
                    "OAuth token or client credentials required for OAuth authentication",
                    provider=self.PROVIDER_TYPE,
                    validation_type="auth_method"
                )

    def get_connection_string(self) -> str:
        """Generate Snowflake connection string"""
        account = self.ACCOUNT
        if self.REGION:
            account = f"{account}.{self.REGION}"
            
        template = "snowflake://{username}@{account}"
        if self.DATABASE:
            template += "/{database}"
        if self.SCHEMA:
            template += "/{schema}"
        
        params = []
        if self.WAREHOUSE:
            params.append(f"warehouse={self.WAREHOUSE}")
        if self.ROLE:
            params.append(f"role={self.ROLE}")
        if self.CLIENT_SESSION_KEEP_ALIVE:
            params.append("client_session_keep_alive=true")
        if self.APPLICATION:
            params.append(f"application={self.APPLICATION}")
            
        if params:
            template += "?" + "&".join(params)
            
        return self.format_connection_string(template)

    def get_connection_args(self) -> Dict[str, Any]:
        """Get connection arguments for Snowflake"""
        args = super().get_connection_args()
        
        # Add Snowflake-specific arguments
        if self.AUTH_METHOD == CONST_DB_AUTH_METHOD.CERTIFICATE:
            args.update({
                "private_key": self.PRIVATE_KEY.get_secret_value() if self.PRIVATE_KEY else None,
                "private_key_path": self.PRIVATE_KEY_PATH,
                "private_key_passphrase": (
                    self.PRIVATE_KEY_PASSPHRASE.get_secret_value() 
                    if self.PRIVATE_KEY_PASSPHRASE else None
                )
            })
        elif self.AUTH_METHOD == "oauth":
            args.update({
                "token": self.OAUTH_TOKEN.get_secret_value() if self.OAUTH_TOKEN else None,
                "oauth_client_id": self.OAUTH_CLIENT_ID,
                "oauth_client_secret": (
                    self.OAUTH_CLIENT_SECRET.get_secret_value() 
                    if self.OAUTH_CLIENT_SECRET else None
                ),
                "oauth_refresh_token": (
                    self.OAUTH_REFRESH_TOKEN.get_secret_value() 
                    if self.OAUTH_REFRESH_TOKEN else None
                )
            })
            
        return {k: v for k, v in args.items() if v is not None}

    # def _test_connection(self) -> bool:
    #     """Test Snowflake connection"""
    #     try:
    #         import snowflake.connector
            
    #         conn = snowflake.connector.connect(**self.get_connection_args())
    #         with conn.cursor() as cursor:
    #             cursor.execute("SELECT CURRENT_VERSION()")
    #             version = cursor.fetchone()[0]
                
    #         conn.close()
    #         return True
            
    #     except Exception as e:
    #         raise DBAuthConnectionError(
    #             f"Failed to connect to Snowflake: {str(e)}",
    #             provider=self.PROVIDER_TYPE
    #         )