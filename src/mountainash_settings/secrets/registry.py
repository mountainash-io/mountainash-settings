"""Secrets backend registry — write-once provider mapping."""
from __future__ import annotations

from .backend import SecretsBackend

__all__ = [
    "register_secrets_backend",
    "get_secrets_backend",
    "replace_secrets_backend",
    "clear_secrets_registry",
]

_REGISTRY: dict[str, SecretsBackend] = {}


def register_secrets_backend(provider: str, backend: SecretsBackend) -> None:
    if provider in _REGISTRY:
        raise ValueError(
            f"Secrets backend '{provider}' is already registered. "
            f"Use replace_secrets_backend() for explicit replacement."
        )
    _REGISTRY[provider] = backend


def get_secrets_backend(provider: str) -> SecretsBackend:
    return _REGISTRY[provider]


def replace_secrets_backend(provider: str, backend: SecretsBackend) -> None:
    _REGISTRY[provider] = backend


def clear_secrets_registry() -> None:
    _REGISTRY.clear()
