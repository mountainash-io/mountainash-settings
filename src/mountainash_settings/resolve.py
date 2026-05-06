"""General-purpose reference resolution for dicts and pydantic model trees.

This module provides the mechanism for resolving prefixed string references
(e.g., ``secret:path/to/value``) in data structures. It is domain-agnostic —
the caller supplies a resolver callable and a prefix string. The ``secrets``
package is one consumer; future reference patterns can reuse the same mechanism.
"""

from __future__ import annotations

import typing as t

from pydantic import BaseModel, SecretStr

__all__ = ["resolve_references_in_dict", "resolve_references_in_model_tree"]

_SETTINGS_SOURCE_PREFIX = "SETTINGS_SOURCE_"
_SETTINGS_META_FIELDS = {"SETTINGS_CLASS", "SETTINGS_CLASS_NAME"}


def resolve_references_in_dict(
    data: dict[str, t.Any],
    resolver: t.Callable[[str], str],
    prefix: str = "secret:",
) -> dict[str, t.Any]:
    resolved: dict[str, t.Any] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            resolved[key] = resolve_references_in_dict(value, resolver, prefix)
        elif isinstance(value, str) and value.startswith(prefix):
            resolved[key] = resolver(value[len(prefix):])
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
    resolver: t.Callable[[str], str],
    prefix: str = "secret:",
) -> None:
    for field_name in instance.model_fields:
        if field_name.startswith(_SETTINGS_SOURCE_PREFIX) or field_name in _SETTINGS_META_FIELDS:
            continue
        value = getattr(instance, field_name)
        if isinstance(value, BaseModel):
            raw_dict, has_refs = _extract_model_values(value, prefix)
            if has_refs:
                resolved_dict = resolve_references_in_dict(raw_dict, resolver, prefix)
                rebuilt = type(value)(**resolved_dict)
                setattr(instance, field_name, rebuilt)
        elif isinstance(value, SecretStr):
            raw = value.get_secret_value()
            if isinstance(raw, str) and raw.startswith(prefix):
                setattr(instance, field_name, resolver(raw[len(prefix):]))
        elif isinstance(value, str) and value.startswith(prefix):
            setattr(instance, field_name, resolver(value[len(prefix):]))
