#path: mountainash_settings/auth/database/integration/security.py

from typing import Dict, Any

from mountainash_settings.auth.database.base import BaseDBAuthSettings
from mountainash_settings.auth.database.exceptions import DBAuthSecurityError

class DBSecurityValidator:
    """Validator for database security settings"""
    
    def __init__(self, auth_settings: BaseDBAuthSettings):
        self.auth_settings = auth_settings

    def validate_ssl_config(self) -> bool:
        """
        Validate SSL configuration parameters
        
        Returns:
            True if configuration is valid
            
        Raises:
            DBAuthSecurityError: If SSL configuration is invalid
        """
        try:
            if not self.auth_settings.SSL_ENABLED:
                return True

            # Only validate file paths if they are provided
            # Actual file access should be done by the connection layer
            if self.auth_settings.SSL_VERIFY and not self.auth_settings.SSL_CA:
                raise DBAuthSecurityError(
                    "SSL verification enabled but no CA certificate specified",
                    provider=self.auth_settings.PROVIDER_TYPE,
                    security_check="ssl_config"
                )
            
            if self.auth_settings.SSL_CERT and not self.auth_settings.SSL_KEY:
                raise DBAuthSecurityError(
                    "SSL certificate specified without private key",
                    provider=self.auth_settings.PROVIDER_TYPE,
                    security_check="ssl_config"
                )

            return True
            
        except DBAuthSecurityError:
            raise
        except Exception as e:
            raise DBAuthSecurityError(
                f"SSL configuration validation failed: {str(e)}",
                provider=self.auth_settings.PROVIDER_TYPE,
                security_check="ssl_config"
            )

    def validate_auth_method(self) -> bool:
        """
        Validate authentication method configuration
        
        Returns:
            True if configuration is valid
            
        Raises:
            DBAuthSecurityError: If authentication configuration is invalid
        """
        try:
            if self.auth_settings.AUTH_METHOD == "password":
                if not (self.auth_settings.USERNAME and self.auth_settings.PASSWORD):
                    raise DBAuthSecurityError(
                        "Username and password required for password authentication",
                        provider=self.auth_settings.PROVIDER_TYPE,
                        security_check="auth_method"
                    )
            
            elif self.auth_settings.AUTH_METHOD == "certificate":
                if not (self.auth_settings.SSL_CERT and self.auth_settings.SSL_KEY):
                    raise DBAuthSecurityError(
                        "Certificate and key required for certificate authentication",
                        provider=self.auth_settings.PROVIDER_TYPE,
                        security_check="auth_method"
                    )
            
            # Add other auth method validations as needed
            
            return True
            
        except DBAuthSecurityError:
            raise
        except Exception as e:
            raise DBAuthSecurityError(
                f"Authentication method validation failed: {str(e)}",
                provider=self.auth_settings.PROVIDER_TYPE,
                security_check="auth_method"
            )

    def get_sanitized_args(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Return a copy of connection arguments with sensitive data masked
        
        Args:
            args: Connection arguments to sanitize
            
        Returns:
            Sanitized connection arguments
        """
        sensitive_keys = {'password', 'pwd', 'secret', 'key', 'token'}
        return {
            k: '***' if any(s in k.lower() for s in sensitive_keys) else v
            for k, v in args.items()
        }
