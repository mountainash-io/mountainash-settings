"""General-purpose reference resolution for dicts and pydantic model trees."""
from __future__ import annotations

import typing as t

from pydantic import AliasChoices, AliasPath, BaseModel, SecretStr, ValidationError
from pydantic.fields import FieldInfo

from mountainash_settings.secrets.backend import SecretsBackend


class _ValidationPathConflict(Exception):
    """Internal signal for incompatible overlapping validation paths."""

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


_MISSING = object()
_INVALID = object()


def _paths_overlap(
    path: tuple[str | int, ...],
    other: tuple[str | int, ...],
) -> bool:
    shared_length = min(len(path), len(other))
    return path[:shared_length] == other[:shared_length]


def _values_compatible(left: t.Any, right: t.Any) -> bool:
    if isinstance(left, SecretStr):
        left = left.get_secret_value()
    if isinstance(right, SecretStr):
        right = right.get_secret_value()
    if left is None or right is None:
        return True
    if isinstance(left, dict) and isinstance(right, dict):
        return all(
            key not in right or _values_compatible(value, right[key])
            for key, value in left.items()
        )
    if isinstance(left, list) and isinstance(right, list):
        return all(
            index >= len(right)
            or _values_compatible(value, right[index])
            for index, value in enumerate(left)
        )
    return left == right


def _value_at_suffix(value: t.Any, suffix: tuple[str | int, ...]) -> t.Any:
    current = value
    for segment in suffix:
        if isinstance(current, dict):
            if segment not in current:
                return _MISSING
            current = current[segment]
        elif isinstance(current, list) and isinstance(segment, int):
            try:
                current = current[segment]
            except IndexError:
                return _MISSING
        else:
            return _INVALID
    return current


def _paths_are_compatible(
    path: tuple[str | int, ...],
    value: t.Any,
    other: tuple[str | int, ...],
    other_value: t.Any,
) -> bool:
    if not _paths_overlap(path, other):
        return True
    if path == other:
        return _values_compatible(value, other_value)
    if len(path) < len(other):
        nested = _value_at_suffix(value, other[len(path):])
        if nested is _INVALID:
            return False
        return nested is _MISSING or _values_compatible(nested, other_value)
    nested = _value_at_suffix(other_value, path[len(other):])
    if nested is _INVALID:
        return False
    return nested is _MISSING or _values_compatible(nested, value)


def _selected_paths_are_unambiguous(
    candidates: list[
        tuple[str, tuple[tuple[str | int, ...], ...], t.Any]
    ],
    selected: tuple[tuple[tuple[str | int, ...], t.Any], ...],
) -> bool:
    for (_, paths, value), (selected_path, _) in zip(candidates, selected):
        for path in paths:
            if path == selected_path:
                break
            for other_path, other_value in selected:
                if _paths_overlap(path, other_path) and not _paths_are_compatible(
                    path,
                    value,
                    other_path,
                    other_value,
                ):
                    return False
        else:
            return False
    return True


def _select_validation_paths(
    fields: list[tuple[str, FieldInfo]],
    values: list[t.Any],
) -> tuple[tuple[str | int, ...], ...]:
    candidates = [
        (field_name, _validation_paths(field_name, field), value)
        for (field_name, field), value in zip(fields, values)
    ]

    def choose(
        index: int,
        selected: tuple[tuple[tuple[str | int, ...], t.Any], ...],
    ) -> tuple[tuple[tuple[str | int, ...], t.Any], ...] | None:
        if index == len(candidates):
            if _selected_paths_are_unambiguous(candidates, selected):
                return selected
            return None
        _, paths, value = candidates[index]
        for path in paths:
            if any(
                _paths_overlap(path, previous_path)
                and not _paths_are_compatible(
                    path,
                    value,
                    previous_path,
                    previous_value,
                )
                for previous_path, previous_value in selected
            ):
                continue
            result = choose(index + 1, (*selected, (path, value)))
            if result is not None:
                return result
        return None

    selected = choose(0, ())
    if selected is None:
        field_names = [field_name for field_name, _ in fields]
        raise ValueError(
            f"Could not construct compatible validation aliases for {field_names!r}"
        )
    return tuple(path for path, _ in selected)


def _list_sizes_for_paths(
    paths: tuple[tuple[str | int, ...], ...],
) -> dict[tuple[str | int, ...], int]:
    indexes_by_parent: dict[tuple[str | int, ...], list[int]] = {}
    for path in paths:
        for index, segment in enumerate(path):
            if isinstance(segment, int):
                indexes_by_parent.setdefault(path[:index], []).append(segment)

    sizes: dict[tuple[str | int, ...], int] = {}
    for parent, indexes in indexes_by_parent.items():
        positive = [index for index in indexes if index >= 0]
        negative = [-index for index in indexes if index < 0]
        if positive and negative:
            sizes[parent] = max(max(positive) + max(negative) + 1, max(negative))
        elif positive:
            sizes[parent] = max(positive) + 1
        else:
            sizes[parent] = max(negative)
    return sizes


def _merge_validation_values(existing: t.Any, value: t.Any) -> t.Any:
    if existing is None:
        return value
    if value is None:
        return existing
    if isinstance(existing, dict) and isinstance(value, dict):
        for key, child in value.items():
            if key in existing:
                existing[key] = _merge_validation_values(existing[key], child)
            else:
                existing[key] = child
        return existing
    if isinstance(existing, list) and isinstance(value, list):
        for index, child in enumerate(value):
            if index < len(existing):
                existing[index] = _merge_validation_values(existing[index], child)
            else:
                existing.append(child)
        return existing
    if _values_compatible(existing, value):
        return existing
    raise _ValidationPathConflict


def _set_validation_path(
    payload: dict[str, t.Any],
    path: tuple[str | int, ...],
    value: t.Any,
    list_sizes: dict[tuple[str | int, ...], int] | None = None,
) -> None:
    current: dict[str, t.Any] | list[t.Any] = payload
    for index, segment in enumerate(path):
        last = index == len(path) - 1
        next_is_index = not last and isinstance(path[index + 1], int)
        if isinstance(segment, int):
            if not isinstance(current, list):
                raise TypeError(f"Alias path requires list at {path[:index]!r}")
            required_length = (list_sizes or {}).get(path[:index])
            if required_length is not None:
                while len(current) < required_length:
                    current.append(None)
            elif segment < 0:
                while len(current) < -segment:
                    current.append(None)
            else:
                while len(current) <= segment:
                    current.append(None)
            if last:
                current[segment] = _merge_validation_values(current[segment], value)
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
            if segment in current:
                current[segment] = _merge_validation_values(current[segment], value)
            else:
                current[segment] = value
            return
        child = current.get(segment)
        if child is None:
            child = [] if next_is_index else {}
            current[segment] = child
        current = child


def _raise_sanitized_resolution_error(
    model_type: type[BaseModel],
    field_names: list[str],
) -> t.NoReturn:
    error = ValueError(
        f"Secret resolution validation failed for {model_type.__name__} "
        f"field(s): {', '.join(field_names)}"
    )
    error.__cause__ = None
    error.__context__ = None
    error.__suppress_context__ = True
    raise error


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

        changed_field_names = [
            field_name for field_name, _, field_changed in resolved_fields if field_changed
        ]
        resolved_values = [resolved for _, resolved, _ in resolved_fields]
        selection_failed = False
        try:
            selected_paths = _select_validation_paths(model_fields, resolved_values)
        except ValueError:
            selection_failed = True
        if selection_failed:
            _raise_sanitized_resolution_error(type(value), changed_field_names)

        list_sizes = _list_sizes_for_paths(selected_paths)
        payload: dict[str, t.Any] = {}
        path_failed = False
        try:
            for (_, resolved, _), path in zip(resolved_fields, selected_paths):
                _set_validation_path(payload, path, resolved, list_sizes)
        except (TypeError, _ValidationPathConflict):
            path_failed = True
        if path_failed:
            _raise_sanitized_resolution_error(type(value), changed_field_names)
        validation_failed = False
        try:
            rebuilt = type(value).model_validate(payload)
        except ValidationError:
            validation_failed = True
        if validation_failed:
            _raise_sanitized_resolution_error(type(value), changed_field_names)
        return rebuilt, True

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
            assignment_failed = False
            try:
                setattr(instance, field_name, resolved)
            except ValidationError:
                assignment_failed = True
            if assignment_failed:
                _raise_sanitized_resolution_error(type(instance), [field_name])
