"""Secrets backend registry and protocols."""
from .backend import ClearableBackend, SecretsBackend
from .filesystem import FilesystemBackend
from .registry import (
    register_secrets_backend,
    get_secrets_backend,
    replace_secrets_backend,
    clear_secrets_registry,
)

__all__ = [
    "ClearableBackend",
    "FilesystemBackend",
    "SecretsBackend",
    "register_secrets_backend",
    "get_secrets_backend",
    "replace_secrets_backend",
    "clear_secrets_registry",
]
