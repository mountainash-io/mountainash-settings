"""Local storage capabilities."""
from .backend import (
    ClearableSecretStore,
    SecretReader,
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
from .namespaced import NamespacedSecretStore

__all__ = [
    "ClearableSecretStore", "SecretReader",
    "SecretWriter", "SecretCapabilityError", "SecretStoreError",
    "SecretStoreUnavailableError", "FilesystemBackend", "to_key_segment", "JSONValue", "SecretRecord",
    "MemorySecretStore", "NamespacedSecretStore",
]
