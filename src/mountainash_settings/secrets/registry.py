"""Secrets resolver registry — write-once provider mapping."""

from __future__ import annotations

import typing as t

__all__ = [
    "SecretsResolver",
    "register_secrets_resolver",
    "get_secrets_resolver",
    "replace_secrets_resolver",
    "clear_secrets_registry",
]

SecretsResolver = t.Callable[[str], str]

_REGISTRY: dict[str, SecretsResolver] = {}


def register_secrets_resolver(provider: str, resolver: SecretsResolver) -> None:
    if provider in _REGISTRY:
        raise ValueError(
            f"Secrets resolver '{provider}' is already registered. "
            f"Use replace_secrets_resolver() for explicit replacement."
        )
    _REGISTRY[provider] = resolver


def get_secrets_resolver(provider: str) -> SecretsResolver:
    return _REGISTRY[provider]


def replace_secrets_resolver(provider: str, resolver: SecretsResolver) -> None:
    _REGISTRY[provider] = resolver


def clear_secrets_registry() -> None:
    _REGISTRY.clear()
