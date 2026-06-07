"""General-purpose reference resolution for dicts and pydantic model trees."""
from __future__ import annotations

import typing as t

from pydantic import BaseModel, SecretStr

from mountainash_settings.secrets.backend import SecretsBackend

__all__ = ["resolve_references_in_dict", "resolve_references_in_model_tree"]

_SETTINGS_SOURCE_PREFIX = "SETTINGS_SOURCE_"
_SETTINGS_META_FIELDS = {"SETTINGS_CLASS", "SETTINGS_CLASS_NAME"}


def _resolve_value(ref: str, backend: SecretsBackend) -> str:
    """Resolve a secret reference like 'container.field' or 'simple_key'.

    For dotted refs: splits on the last dot, calls backend.get(key), plucks field.
    For simple refs: calls backend.get(ref), returns the single value.
    """
    if "." not in ref:
        result = backend.get(ref)
        if result is None:
            raise KeyError(f"Secret not found: {ref!r}")
        if len(result) == 1:
            return str(next(iter(result.values())))
        raise KeyError(
            f"Ambiguous secret reference {ref!r}: backend returned {len(result)} fields. "
            f"Use a dotted reference like '{ref}.field_name'."
        )
    key, _, field = ref.rpartition(".")
    result = backend.get(key)
    if result is None:
        raise KeyError(f"Secret not found for key: {key!r}")
    if field not in result:
        raise KeyError(f"Field {field!r} not found in secret {key!r}. Available: {list(result.keys())}")
    return str(result[field])


def resolve_references_in_dict(
    data: dict[str, t.Any],
    backend: SecretsBackend,
    prefix: str = "secret:",
) -> dict[str, t.Any]:
    resolved: dict[str, t.Any] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            resolved[key] = resolve_references_in_dict(value, backend, prefix)
        elif isinstance(value, str) and value.startswith(prefix):
            resolved[key] = _resolve_value(value[len(prefix):], backend)
        else:
            resolved[key] = value
    return resolved


def _extract_model_values(
    instance: BaseModel,
    prefix: str,
) -> tuple[dict[str, t.Any], bool]:
    """Extract field values from a BaseModel, unwrapping SecretStr.

    Returns (field_dict, has_references) where has_references is True
    if any string value starts with the given prefix.
    """
    values: dict[str, t.Any] = {}
    has_refs = False
    for field_name in instance.model_fields:
        value = getattr(instance, field_name)
        if isinstance(value, SecretStr):
            raw = value.get_secret_value()
            values[field_name] = raw
            if isinstance(raw, str) and raw.startswith(prefix):
                has_refs = True
        elif isinstance(value, BaseModel):
            inner_values, inner_has_refs = _extract_model_values(value, prefix)
            values[field_name] = inner_values
            if inner_has_refs:
                has_refs = True
        else:
            values[field_name] = value
            if isinstance(value, str) and value.startswith(prefix):
                has_refs = True
    return values, has_refs


def resolve_references_in_model_tree(
    instance: t.Any,
    backend: SecretsBackend,
    prefix: str = "secret:",
) -> None:
    for field_name in instance.model_fields:
        if field_name.startswith(_SETTINGS_SOURCE_PREFIX) or field_name in _SETTINGS_META_FIELDS:
            continue
        value = getattr(instance, field_name)
        if isinstance(value, BaseModel):
            raw_dict, has_refs = _extract_model_values(value, prefix)
            if has_refs:
                resolved_dict = resolve_references_in_dict(raw_dict, backend, prefix)
                rebuilt = type(value)(**resolved_dict)
                setattr(instance, field_name, rebuilt)
        elif isinstance(value, SecretStr):
            raw = value.get_secret_value()
            if isinstance(raw, str) and raw.startswith(prefix):
                setattr(instance, field_name, _resolve_value(raw[len(prefix):], backend))
        elif isinstance(value, str) and value.startswith(prefix):
            setattr(instance, field_name, _resolve_value(value[len(prefix):], backend))
