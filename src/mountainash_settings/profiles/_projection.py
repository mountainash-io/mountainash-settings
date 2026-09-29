"""Describe effective Pydantic application fields for profile consumers."""

from __future__ import annotations

import types
import typing as t

from pydantic import SecretStr

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
                raise TypeError(f"{cls.__name__}.{name}: profile option {sorted(options.supplied)[0]} on framework field")
            continue
        if name != name.upper():
            raise TypeError(f"{cls.__name__}.{name}: application fields must be uppercase")
        driver_key: str | dict[t.Hashable, str] | None
        if options.driver_key is _OMITTED:
            driver_key = name.lower() if declaration.driver_keys == "lower" else None
        elif isinstance(options.driver_key, tuple):
            driver_key = dict(options.driver_key)
        else:
            driver_key = options.driver_key
        default = FACTORY_DEFAULT if info.default_factory is not None else MISSING if info.is_required() else info.default
        parameters.append(ParameterSpec(
            name=name, type=info.rebuild_annotation(), tier=options.tier,
            default=default, description=info.description or "", driver_key=driver_key,
            secret=_is_secret(info.annotation), transform=options.transform, template=options.template,
        ))
    _validate_output_keys(cls.__name__, parameters)
    return parameters


def _validate_output_keys(class_name: str, parameters: list[ParameterSpec]) -> None:
    bare: dict[str, str] = {}
    targeted: dict[t.Hashable, dict[str, str]] = {}
    for param in parameters:
        mapping = param.driver_key
        if isinstance(mapping, str):
            if mapping in bare:
                raise TypeError(f"{class_name}.{param.name}: duplicate output key")
            bare[mapping] = param.name
        elif isinstance(mapping, dict):
            for target, key in mapping.items():
                keys = targeted.setdefault(target, {})
                if key in keys:
                    raise TypeError(f"{class_name}.{param.name}: duplicate target output key")
                keys[key] = param.name
    for keys in targeted.values():
        for key, name in keys.items():
            if key in bare:
                raise TypeError(f"{class_name}.{name}: target output key conflicts with bare mapping")
