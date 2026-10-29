"""Pre-Pydantic header routing, isolated from native field construction."""

from __future__ import annotations

import typing as t

from pydantic._internal._config import config_keys
from pydantic._internal._model_construction import build_lenient_weakvaluedict
from pydantic._internal._typing_extra import parent_frame_namespace
from pydantic_settings import SettingsConfigDict

from mountainash_settings.settings._metaclass import _SettingsMetaclass

from ._declaration import prepare_declaration

_CONFIG_KEYS = frozenset(config_keys) | frozenset(SettingsConfigDict.__annotations__)


class _ProfileMetaclass(_SettingsMetaclass):
    def __new__(
        mcs, cls_name: str, bases: tuple[type, ...], namespace: dict[str, t.Any],
        __pydantic_generic_metadata__: t.Any = None,
        __pydantic_reset_parent_namespace__: bool = True,
        _create_model_module: str | None = None, **kwargs: t.Any,
    ) -> type:
        if __pydantic_reset_parent_namespace__:
            # Our routing frame must not replace the user's local type namespace.
            namespace["__pydantic_parent_namespace__"] = build_lenient_weakvaluedict(parent_frame_namespace())
        declaration = prepare_declaration(cls_name, bases, namespace, kwargs, config_keys=_CONFIG_KEYS)
        if declaration is not None:
            namespace["_profile_declaration"] = declaration
            namespace["__spec__"] = None
            kwargs = {}
        return super().__new__(
            mcs, cls_name, bases, namespace,
            __pydantic_generic_metadata__=__pydantic_generic_metadata__,
            __pydantic_reset_parent_namespace__=False,
            _create_model_module=_create_model_module, **kwargs,
        )
