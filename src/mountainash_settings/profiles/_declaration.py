"""Class-header configuration for generated specs; never merges model fields."""

from __future__ import annotations

import typing as t
from copy import deepcopy
from dataclasses import dataclass, fields
from types import MappingProxyType

from pydantic import ConfigDict, PydanticUserError, TypeAdapter

from .spec import ParameterSpec, ProfileSpec

_CONTROLS = frozenset({"name", "provider_type", "spec_type", "driver_keys"})
_GENERATED = frozenset({"name", "provider_type", "parameters"})


@dataclass(frozen=True)
class _Declaration:
    class_name: str
    name: str | None
    provider_type: t.Any
    spec_type: type[ProfileSpec]
    driver_keys: t.Literal["lower"] | None
    metadata: t.Mapping[str, t.Any]


def _copy_metadata(value: t.Any) -> t.Any:
    """Own mutable containers while retaining executable/class identifiers."""
    memo: dict[int, t.Any] = {}
    visited: set[int] = set()

    def preserve_identifiers(item: t.Any) -> None:
        if id(item) in visited:
            return
        visited.add(id(item))
        if callable(item):
            memo[id(item)] = item
        elif isinstance(item, dict):
            for key, child in item.items():
                preserve_identifiers(key)
                preserve_identifiers(child)
        elif isinstance(item, (list, tuple, set, frozenset)):
            for child in item:
                preserve_identifiers(child)

    preserve_identifiers(value)
    return deepcopy(value, memo)


def _validate_metadata(class_name: str, option: str, annotation: t.Any, value: t.Any) -> None:
    # Raise outside the handler: value-bearing validation errors must not remain
    # reachable through __context__ on our declaration error.
    invalid = False
    try:
        try:
            adapter = TypeAdapter(annotation, config=ConfigDict(strict=True, arbitrary_types_allowed=True))
        except PydanticUserError as error:
            if error.code != "type-adapter-config-unused":
                raise
            # Native models, dataclasses and TypedDicts own their schema config.
            adapter = TypeAdapter(annotation)
        adapter.validate_python(value, strict=True)
    except Exception:
        invalid = True
    if invalid:
        raise TypeError(f"{class_name}: invalid metadata type for {option}")


def prepare_declaration(
    class_name: str, bases: tuple[type, ...], namespace: t.Mapping[str, t.Any],
    header: t.Mapping[str, t.Any], *, config_keys: frozenset[str],
) -> _Declaration | None:
    profile_bases = [base for base in bases if hasattr(base, "_profile_declaration")]
    parents = [declaration for base in profile_bases
               if (declaration := getattr(base, "_profile_declaration")) is not None]
    if not parents and not _CONTROLS.intersection(header):
        return None
    if "__spec__" in namespace:
        raise TypeError(f"{class_name}: explicit __spec__ conflicts with generated declaration")
    if any(not (issubclass(left, right) or issubclass(right, left))
           for left in profile_bases for right in profile_bases):
        raise TypeError(f"{class_name}: independent profile bases are unsupported")
    parent = parents[0] if parents else None
    spec_type = header.get("spec_type", parent.spec_type if parent else ProfileSpec)
    if not isinstance(spec_type, type) or not issubclass(spec_type, ProfileSpec):
        raise TypeError(f"{class_name}: spec_type must be a ProfileSpec dataclass subclass")
    reserved = config_keys | _CONTROLS | {"model_config", "parameters"}
    metadata_fields = {f.name for f in fields(spec_type) if f.name not in _GENERATED}
    collisions = metadata_fields & reserved
    if collisions:
        raise TypeError(f"{class_name}: reserved metadata option {sorted(collisions)[0]}")
    accepted = {f.name for f in fields(spec_type) if f.init} - _GENERATED
    unknown = set(header) - _CONTROLS - accepted
    if unknown:
        raise TypeError(f"{class_name}: unsupported header option {sorted(unknown)[0]}")
    if ("name" in header) != ("provider_type" in header) or (
        "name" in header and (header["name"] is None or header["provider_type"] is None)
    ):
        raise TypeError(f"{class_name}: identity requires both name and non-None provider_type")
    name = header.get("name")
    if name is not None and (not isinstance(name, str) or not name or name != name.lower()):
        raise TypeError(f"{class_name}: name must be a nonempty lowercase string")
    driver_keys = header.get("driver_keys", parent.driver_keys if parent else None)
    if driver_keys not in (None, "lower"):
        raise TypeError(f"{class_name}: driver_keys must be lower or None")
    metadata = _copy_metadata(dict(parent.metadata)) if parent else {}
    metadata.update({key: _copy_metadata(value) for key, value in header.items() if key in accepted})
    annotations = t.get_type_hints(spec_type)
    for key, value in metadata.items():
        if key not in accepted:
            raise TypeError(f"{class_name}: unsupported inherited metadata option {key}")
        _validate_metadata(class_name, key, annotations[key], value)
    return _Declaration(
        class_name, name, header.get("provider_type"), spec_type, driver_keys,
        MappingProxyType(metadata),
    )


def build_spec(declaration: _Declaration, parameters: list[ParameterSpec]) -> ProfileSpec:
    assert declaration.name is not None
    spec = declaration.spec_type(
        name=declaration.name, provider_type=declaration.provider_type,
        parameters=parameters, **_copy_metadata(dict(declaration.metadata)),
    )
    annotations = t.get_type_hints(declaration.spec_type)
    for item in fields(spec):
        if item.name not in _GENERATED:
            _validate_metadata(declaration.class_name, item.name, annotations[item.name], getattr(spec, item.name))
    return spec
