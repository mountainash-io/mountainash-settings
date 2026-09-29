"""Describe effective Pydantic application fields for profile consumers."""

from __future__ import annotations

import types
import typing as t

from pydantic import SecretStr
from pydantic.fields import FieldInfo

from mountainash_settings.settings.base_settings import MountainAshBaseSettings

from ._declaration import _Declaration
from .fields import _OMITTED, _ProfileOptions, _profile_options
from .spec import FACTORY_DEFAULT, MISSING, ParameterSpec


def _is_secret(annotation: t.Any) -> bool:
    if t.get_origin(annotation) is t.Annotated:
        return _is_secret(t.get_args(annotation)[0])
    if t.get_origin(annotation) in (t.Union, types.UnionType):
        return any(_is_secret(member) for member in t.get_args(annotation))
    return isinstance(annotation, type) and issubclass(annotation, SecretStr)


def _project_field(
    name: str, info: FieldInfo, options: _ProfileOptions,
    driver_keys: t.Literal["lower"] | None,
) -> ParameterSpec:
    driver_key: str | dict[t.Hashable, str] | None
    if options.driver_key is _OMITTED:
        driver_key = name.lower() if driver_keys == "lower" else None
    elif isinstance(options.driver_key, tuple):
        driver_key = dict(options.driver_key)
    else:
        driver_key = options.driver_key
    default: t.Any
    if info.default_factory is not None:
        default = FACTORY_DEFAULT
    elif info.is_required():
        default = MISSING
    else:
        default = info.default
    return ParameterSpec(
        name=name, type=info.rebuild_annotation(), tier=options.tier,
        default=default, description=info.description or "", driver_key=driver_key,
        secret=_is_secret(info.annotation), transform=options.transform, template=options.template,
    )


def project_parameters(
    cls: type[MountainAshBaseSettings], declaration: _Declaration,
    framework_names: frozenset[str],
) -> list[ParameterSpec]:
    parameters = []
    for name, info in cls.model_fields.items():
        markers = [item for item in info.metadata if isinstance(item, _ProfileOptions)]
        if len(markers) > 1:
            raise TypeError(f"{cls.__name__}.{name}: multiple ProfileField declarations")
        options = markers[0] if markers else _profile_options()
        if name in framework_names:
            if options.supplied:
                raise TypeError(f"{cls.__name__}.{name}: profile option {min(options.supplied)} on framework field")
            continue
        if name != name.upper():
            raise TypeError(f"{cls.__name__}.{name}: application fields must be uppercase")
        parameters.append(_project_field(name, info, options, declaration.driver_keys))
    _validate_output_keys(cls.__name__, parameters)
    return parameters


def _record_output_key(keys: dict[str, str], key: str, field_name: str, error: str) -> None:
    if key in keys:
        raise TypeError(error)
    keys[key] = field_name


def _validate_output_keys(class_name: str, parameters: list[ParameterSpec]) -> None:
    bare: dict[str, str] = {}
    targeted: dict[t.Hashable, dict[str, str]] = {}
    for param in parameters:
        mapping = param.driver_key
        if isinstance(mapping, str):
            _record_output_key(bare, mapping, param.name, f"{class_name}.{param.name}: duplicate output key")
        elif isinstance(mapping, dict):
            for target, key in mapping.items():
                keys = targeted.setdefault(target, {})
                _record_output_key(keys, key, param.name, f"{class_name}.{param.name}: duplicate target output key")
    for keys in targeted.values():
        for key, name in keys.items():
            if key in bare:
                raise TypeError(f"{class_name}.{name}: target output key conflicts with bare mapping")
