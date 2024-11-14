from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from pydantic import Field, SecretStr, field_validator
from urllib.parse import quote_plus

from mountainash_settings import MountainAshBaseSettings
from mountainash_settings.auth.database.constants import CONST_DB_AUTH_METHOD, CONST_DB_PROVIDER_TYPE
from mountainash_settings.auth.database.exceptions import (
    DBAuthConfigError,
    DBAuthConnectionError,
    DBAuthValidationError,
    DBAuthSecurityError
)

class BaseDBAuthSettings(MountainAshBaseSettings, ABC):
    """Base class for database authentication settings"""
    
    # Provider Configuration
    PROVIDER_TYPE: str = Field(...)
    AUTH_METHOD: str = Field(default=CONST_DB_AUTH_METHOD.PASSWORD)
    
    # Connection Settings
    HOST: Optional[str] = Field(default=None)
    PORT: Optional[int] = Field(default=None)
    DATABASE: Optional[str] = Field(default=None)
    SCHEMA: Optional[str] = Field(default=None)
    
    # Authentication
    USERNAME: Optional[str] = Field(default=None)
    PASSWORD: Optional[SecretStr] = Field(default=None)
    
    # Security
    SSL_ENABLED: bool = Field(default=True)
    SSL_VERIFY: bool = Field(default=True)
    SSL_CA: Optional[str] = Field(default=None)
    SSL_CERT: Optional[str] = Field(default=None)
    SSL_KEY: Optional[str] = Field(default=None)
    
    # Connection Pool
    POOL_SIZE: Optional[int] = Field(default=5)
    POOL_TIMEOUT: Optional[int] = Field(default=30)
    MAX_OVERFLOW: Optional[int] = Field(default=10)
    
    # Integration
    SECRETS_NAMESPACE: Optional[str] = Field(default=None)
    CONNECTION_TIMEOUT: int = Field(default=30)
    COMMAND_TIMEOUT: int = Field(default=30)
    
    # State tracking
    _connection_tested: bool = False
    _connection_valid: bool = False

    @field_validator("PROVIDER_TYPE")
    def validate_provider_type(cls, v: str) -> str:
        """Validate provider type"""
        if v not in CONST_DB_PROVIDER_TYPE.__dict__:
            raise DBAuthValidationError(
                f"Invalid provider type: {v}",
                validation_type="provider_type"
            )
        return v

    @field_validator("AUTH_METHOD")
    def validate_auth_method(cls, v: str) -> str:
        """Validate authentication method"""
        if v not in CONST_DB_AUTH_METHOD.__dict__:
            raise DBAuthValidationError(
                f"Invalid authentication method: {v}",
                validation_type="auth_method"
            )
        return v

    @field_validator("PORT")
    def validate_port(cls, v: Optional[int]) -> Optional[int]:
        """Validate port number"""
        if v is not None and not (1 <= v <= 65535):
            raise DBAuthValidationError(
                f"Invalid port number: {v}",
                validation_type="port"
            )
        return v

    def post_init(self, reinitialise: bool = False) -> None:
        """Post-initialization validation and setup"""
        super().post_init(reinitialise)
        self._validate_security_config()
        self._init_provider_specific(reinitialise)

    def _validate_security_config(self) -> None:
        """Validate security configuration"""
        if self.SSL_ENABLED:
            if self.SSL_VERIFY and not self.SSL_CA:
                raise DBAuthSecurityError(
                    "SSL verification enabled but no CA certificate provided",
                    security_check="ssl_config"
                )
            if self.SSL_CERT and not self.SSL_KEY:
                raise DBAuthSecurityError(
                    "SSL certificate provided without private key",
                    security_check="ssl_config"
                )

    @abstractmethod
    def _init_provider_specific(self, reinitialise: bool) -> None:
        """Initialize provider-specific settings"""
        pass

    @abstractmethod
    def get_connection_string(self) -> str:
        """Generate connection string from settings"""
        pass

    def get_connection_args(self) -> Dict[str, Any]:
        """Get connection arguments as dictionary"""
        args = {
            "host": self.HOST,
            "port": self.PORT,
            "database": self.DATABASE,
            "username": self.USERNAME,
            "password": self.PASSWORD.get_secret_value() if self.PASSWORD else None,
            "connect_timeout": self.CONNECTION_TIMEOUT
        }
        
        # Add SSL configuration if enabled
        if self.SSL_ENABLED:
            args.update({
                "ssl_ca": self.SSL_CA,
                "ssl_cert": self.SSL_CERT,
                "ssl_key": self.SSL_KEY,
                "ssl_verify": self.SSL_VERIFY
            })
        
        return {k: v for k, v in args.items() if v is not None}

    def get_pool_config(self) -> Dict[str, Any]:
        """Get connection pool configuration"""
        return {
            "pool_size": self.POOL_SIZE,
            "pool_timeout": self.POOL_TIMEOUT,
            "max_overflow": self.MAX_OVERFLOW
        }

    def validate_connection(self) -> bool:
        """Validate connection parameters"""
        try:
            if not self._connection_tested:
                self._connection_valid = self._test_connection()
                self._connection_tested = True
            return self._connection_valid
        except Exception as e:
            raise DBAuthConnectionError(
                f"Connection validation failed: {str(e)}",
                provider=self.PROVIDER_TYPE
            )

    @abstractmethod
    def _test_connection(self) -> bool:
        """Test database connection"""
        pass

    def format_connection_string(self, template: str) -> str:
        """Format connection string using template"""
        try:
            # Get connection parameters
            params = self.get_connection_args()
            
            # Quote special characters in values
            quoted_params = {
                k: quote_plus(str(v)) if isinstance(v, str) else v
                for k, v in params.items()
            }
            
            # Format the template
            return template.format(**quoted_params)
        except KeyError as e:
            raise DBAuthConfigError(
                f"Missing required parameter in connection string template: {str(e)}",
                provider=self.PROVIDER_TYPE
            )
        except Exception as e:
            raise DBAuthConfigError(
                f"Failed to format connection string: {str(e)}",
                provider=self.PROVIDER_TYPE
            )