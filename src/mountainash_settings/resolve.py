"""General-purpose reference resolution for dicts and pydantic model trees."""
from __future__ import annotations

import typing as t

from pydantic import AliasChoices, AliasPath, BaseModel, SecretStr
from pydantic.fields import FieldInfo

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


def _validation_paths(
    field_name: str,
    field: FieldInfo,
) -> tuple[tuple[str | int, ...], ...]:
    alias = field.validation_alias
    if isinstance(alias, AliasChoices):
        aliases = alias.choices
    elif alias is None:
        aliases = (field_name,)
    else:
        aliases = (alias,)

    paths: list[tuple[str | int, ...]] = []
    for alias_choice in aliases:
        if isinstance(alias_choice, AliasPath):
            paths.append(tuple(alias_choice.path))
        else:
            paths.append((alias_choice,))
    return tuple(paths)


def _paths_conflict(
    path: tuple[str | int, ...],
    other: tuple[str | int, ...],
) -> bool:
    shared_length = min(len(path), len(other))
    return path[:shared_length] == other[:shared_length]


def _selected_paths_are_unambiguous(
    candidates: list[
        tuple[str, tuple[tuple[str | int, ...], ...]]
    ],
    selected: tuple[tuple[str | int, ...], ...],
) -> bool:
    for (_, paths), selected_path in zip(candidates, selected):
        for path in paths:
            if path == selected_path:
                break
            if any(_paths_conflict(path, other) for other in selected):
                return False
        else:
            return False
    return True


def _select_validation_paths(
    fields: list[tuple[str, FieldInfo]],
) -> tuple[tuple[str | int, ...], ...]:
    candidates = [
        (field_name, _validation_paths(field_name, field))
        for field_name, field in fields
    ]

    def choose(
        index: int,
        selected: tuple[tuple[str | int, ...], ...],
    ) -> tuple[tuple[str | int, ...], ...] | None:
        if index == len(candidates):
            if _selected_paths_are_unambiguous(candidates, selected):
                return selected
            return None
        _, paths = candidates[index]
        for path in paths:
            if any(_paths_conflict(path, previous) for previous in selected):
                continue
            result = choose(index + 1, (*selected, path))
            if result is not None:
                return result
        return None

    selected = choose(0, ())
    if selected is None:
        field_names = [field_name for field_name, _ in fields]
        raise ValueError(
            f"Could not construct non-conflicting validation aliases for {field_names!r}"
        )
    return selected


def _set_validation_path(
    payload: dict[str, t.Any],
    path: tuple[str | int, ...],
    value: t.Any,
) -> None:
    current: dict[str, t.Any] | list[t.Any] = payload
    for index, segment in enumerate(path):
        last = index == len(path) - 1
        next_is_index = not last and isinstance(path[index + 1], int)
        if isinstance(segment, int):
            if not isinstance(current, list):
                raise TypeError(f"Alias path requires list at {path[:index]!r}")
            if segment < 0:
                while len(current) < -segment:
                    current.append(None)
            else:
                while len(current) <= segment:
                    current.append(None)
            if last:
                current[segment] = value
                return
            child = current[segment]
            if child is None:
                child = [] if next_is_index else {}
                current[segment] = child
            current = child
            continue

        if not isinstance(current, dict):
            raise TypeError(f"Alias path requires mapping at {path[:index]!r}")
        if last:
            current[segment] = value
            return
        child = current.get(segment)
        if child is None:
            child = [] if next_is_index else {}
            current[segment] = child
        current = child


def _resolve_reference_value(
    value: t.Any,
    backend: SecretsBackend,
    prefix: str,
) -> tuple[t.Any, bool]:
    if isinstance(value, SecretStr):
        raw = value.get_secret_value()
        if raw.startswith(prefix):
            return SecretStr(_resolve_value(raw[len(prefix):], backend)), True
        return value, False

    if isinstance(value, str):
        if value.startswith(prefix):
            return _resolve_value(value[len(prefix):], backend), True
        return value, False

    if isinstance(value, BaseModel):
        resolved_fields: list[tuple[str, t.Any, bool]] = []
        changed = False
        model_fields = list(type(value).model_fields.items())
        for field_name, _ in model_fields:
            resolved, field_changed = _resolve_reference_value(
                getattr(value, field_name), backend, prefix
            )
            resolved_fields.append((field_name, resolved, field_changed))
            changed = changed or field_changed
        if not changed:
            return value, False

        selected_paths = _select_validation_paths(model_fields)
        payload: dict[str, t.Any] = {}
        for (_, resolved, _), path in zip(resolved_fields, selected_paths):
            _set_validation_path(payload, path, resolved)
        return type(value).model_validate(payload), True

    if isinstance(value, dict):
        resolved_dict: dict[t.Any, t.Any] = {}
        changed = False
        for key, item in value.items():
            resolved, item_changed = _resolve_reference_value(item, backend, prefix)
            resolved_dict[key] = resolved
            changed = changed or item_changed
        return resolved_dict, changed

    if isinstance(value, list):
        resolved_list: list[t.Any] = []
        changed = False
        for item in value:
            resolved, item_changed = _resolve_reference_value(item, backend, prefix)
            resolved_list.append(resolved)
            changed = changed or item_changed
        return resolved_list, changed

    if isinstance(value, tuple):
        resolved_items: list[t.Any] = []
        changed = False
        for item in value:
            resolved, item_changed = _resolve_reference_value(item, backend, prefix)
            resolved_items.append(resolved)
            changed = changed or item_changed
        return tuple(resolved_items), changed

    return value, False


def resolve_references_in_dict(
    data: dict[str, t.Any],
    backend: SecretsBackend,
    prefix: str = "secret:",
) -> dict[str, t.Any]:
    resolved, _ = _resolve_reference_value(data, backend, prefix)
    return t.cast(dict[str, t.Any], resolved)


def resolve_references_in_model_tree(
    instance: BaseModel,
    backend: SecretsBackend,
    prefix: str = "secret:",
) -> None:
    for field_name in type(instance).model_fields:
        if field_name.startswith(_SETTINGS_SOURCE_PREFIX) or field_name in _SETTINGS_META_FIELDS:
            continue
        resolved, changed = _resolve_reference_value(
            getattr(instance, field_name), backend, prefix
        )
        if changed:
            setattr(instance, field_name, resolved)
