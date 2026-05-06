"""Secrets resolver registry — write-once provider mapping.

Resolution logic lives in ``mountainash_settings.resolve`` (domain-agnostic).
This package owns the secrets-specific provider registry only.
"""

from .registry import (
    SecretsResolver,
    register_secrets_resolver,
    get_secrets_resolver,
    replace_secrets_resolver,
    clear_secrets_registry,
)

__all__ = [
    "SecretsResolver",
    "register_secrets_resolver",
    "get_secrets_resolver",
    "replace_secrets_resolver",
    "clear_secrets_registry",
]
