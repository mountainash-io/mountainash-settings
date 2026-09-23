"""Local storage capabilities and current M3-stage legacy imports."""
from .backend import (
    ClearableBackend,
    ClearableSecretStore,
    SecretReader,
    SecretsBackend,
    SecretWriter,
)
from .errors import (
    SecretCapabilityError,
    SecretStoreError,
    SecretStoreUnavailableError,
)
from .filesystem import FilesystemBackend
from .keys import to_key_segment
from .records import JSONValue, SecretRecord
from .memory import MemorySecretStore
from .registry import (
    clear_secrets_registry,
    get_secrets_backend,
    register_secrets_backend,
    replace_secrets_backend,
)

__all__ = [
    "ClearableBackend", "ClearableSecretStore", "SecretReader", "SecretsBackend",
    "SecretWriter", "SecretCapabilityError", "SecretStoreError",
    "SecretStoreUnavailableError", "FilesystemBackend", "to_key_segment", "JSONValue", "SecretRecord",
    "MemorySecretStore",
    "clear_secrets_registry", "get_secrets_backend", "register_secrets_backend",
    "replace_secrets_backend",
]
