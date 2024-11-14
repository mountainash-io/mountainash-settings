from typing import Optional, Any
from pydantic import SecretStr

class SecretsError(Exception):
    """Base exception for all secrets-related errors"""
    def __init__(self, message: str, provider: Optional[str] = None):
        self.provider = provider
        super().__init__(f"[{provider or 'unknown'}] {message}")

class SecretConfigurationError(SecretsError):
    """Raised when there is an error in the secret provider configuration"""
    def __init__(self, message: str, provider: Optional[str] = None, setting: Optional[str] = None):
        self.setting = setting
        super().__init__(f"Configuration error - {message}" + (f" (setting: {setting})" if setting else ""), provider)

class SecretAuthenticationError(SecretsError):
    """Raised when authentication to the secret provider fails"""
    def __init__(self, message: str, provider: Optional[str] = None, auth_method: Optional[str] = None):
        self.auth_method = auth_method
        super().__init__(
            f"Authentication failed - {message}" + (f" (method: {auth_method})" if auth_method else ""),
            provider
        )

class SecretNotFoundError(SecretsError):
    """Raised when a requested secret is not found"""
    def __init__(self, secret_name: str, provider: Optional[str] = None, version: Optional[str] = None):
        self.secret_name = secret_name
        self.version = version
        super().__init__(
            f"Secret not found: {secret_name}" + (f" (version: {version})" if version else ""),
            provider
        )

class SecretAccessError(SecretsError):
    """Raised when there is an error accessing a secret"""
    def __init__(self, secret_name: str, provider: Optional[str] = None, operation: Optional[str] = None):
        self.secret_name = secret_name
        self.operation = operation
        super().__init__(
            f"Failed to {operation or 'access'} secret: {secret_name}",
            provider
        )

class SecretValidationError(SecretsError):
    """Raised when secret validation fails"""
    def __init__(self, message: str, provider: Optional[str] = None, validation_type: Optional[str] = None):
        self.validation_type = validation_type
        super().__init__(
            f"Validation failed - {message}" + (f" (type: {validation_type})" if validation_type else ""),
            provider
        )

class SecretOperationError(SecretsError):
    """Raised when a secret operation fails"""
    def __init__(self, operation: str, message: str, provider: Optional[str] = None):
        self.operation = operation
        super().__init__(f"Operation '{operation}' failed - {message}", provider)


class SecretSyncError(SecretsError):
    """Raised when synchronization between secret providers fails"""
    def __init__(self, message: str, source: Optional[str] = None, destination: Optional[str] = None):
        self.source = source
        self.destination = destination
        super().__init__(
            f"Sync failed - {message}" + (
                f" (from: {source or 'unknown'} to: {destination or 'unknown'})" if source or destination else ""
            )
        )