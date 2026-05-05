"""Secret reference resolution for dicts and settings instances."""

from __future__ import annotations

import typing as t

from pydantic import SecretStr

if t.TYPE_CHECKING:
    from .registry import SecretsResolver

__all__ = ["resolve_secrets_in_dict", "resolve_secrets_on_instance"]

_SETTINGS_SOURCE_PREFIX = "SETTINGS_SOURCE_"
_SETTINGS_META_FIELDS = {"SETTINGS_CLASS", "SETTINGS_CLASS_NAME"}


def resolve_secrets_in_dict(
    data: dict[str, t.Any],
    resolver: SecretsResolver,
    prefix: str = "secret:",
) -> dict[str, t.Any]:
    resolved: dict[str, t.Any] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            resolved[key] = resolve_secrets_in_dict(value, resolver, prefix)
        elif isinstance(value, str) and value.startswith(prefix):
            secret_path = value[len(prefix):]
            resolved[key] = resolver(secret_path)
        else:
            resolved[key] = value
    return resolved


def resolve_secrets_on_instance(
    instance: t.Any,
    resolver: SecretsResolver,
    prefix: str = "secret:",
) -> None:
    for field_name in instance.model_fields:
        if field_name.startswith(_SETTINGS_SOURCE_PREFIX) or field_name in _SETTINGS_META_FIELDS:
            continue
        value = getattr(instance, field_name)
        if isinstance(value, SecretStr):
            raw = value.get_secret_value()
            if isinstance(raw, str) and raw.startswith(prefix):
                secret_path = raw[len(prefix):]
                setattr(instance, field_name, resolver(secret_path))
        elif isinstance(value, str) and value.startswith(prefix):
            secret_path = value[len(prefix):]
            setattr(instance, field_name, resolver(secret_path))
