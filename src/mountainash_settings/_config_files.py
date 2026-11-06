"""Private config-file path machinery shared by parameters, cache and sources.

One home for: input normalization, option-aware path identity, independent
ownership of option containers, safe diagnostic labels, HTTP-aware filename
classification and the structured (YAML/TOML/JSON) UPath source adapters.

Ownership contract: exact ordinary containers (dict/list/tuple/set/frozenset)
and immutable value types are owned recursively and compared by value. Every
other option object (clients, timeouts, credentials, enum members, models,
container subclasses ...) is an opaque access capability: it is retained
strongly and compared by identity, never cloned or closed. Identity encoding
does not call capability equality/hash hooks; ordinary container construction
retains Python's key protocol. No filesystem is opened here.

This module must not import ``settings_parameters.filehandler`` at runtime:
that module consumes it.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import PurePath
from typing import Any, cast
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import SecretBytes, SecretStr
from pydantic._internal._utils import deep_update
from pydantic_settings import (
    JsonConfigSettingsSource,
    TomlConfigSettingsSource,
    YamlConfigSettingsSource,
)
from pydantic_settings.sources import ConfigFileSourceMixin
from upath import UPath

__all__ = [
    "ConfigPathIdentity",
    "ConfigPathOwnershipError",
    "UPathJsonSource",
    "UPathTomlSource",
    "UPathYamlSource",
    "config_filename",
    "config_path_identities",
    "config_path_label",
    "normalize_config_path",
    "own_config_paths",
]

_HTTP_PROTOCOLS = frozenset({"http", "https"})
# Protocols whose first segment is an object/key name, never URL userinfo.
_KEYED_PROTOCOLS = frozenset({"", "file", "local", "memory"})

_EXACT_VALUE_TYPES = frozenset({
    type(None), bool, int, float, complex, str, bytes,
    date, datetime, time, timedelta, Decimal, UUID,
})
_CONTAINER_TYPES = (dict, list, tuple, set, frozenset)


class ConfigPathOwnershipError(TypeError):
    """A declared config path cannot be reconstructed with owned option containers."""


# --- option values -------------------------------------------------------------------

def _is_value(value: object) -> bool:
    """Exact immutable value types compared and copied by value."""
    value_type = type(value)
    if value_type in (datetime, time):
        tzinfo = value.tzinfo  # type: ignore[attr-defined]
        return tzinfo is None or type(tzinfo) is timezone
    if value_type in _EXACT_VALUE_TYPES:
        return True
    # Concrete pathlib classes only; UPath and user subclasses are capabilities.
    return value_type.__module__ == "pathlib" and isinstance(value, PurePath)


def _own_value(value: Any, memo: dict[int, Any], active: set[int]) -> Any:
    value_type = type(value)
    if _is_value(value):
        return value
    if value_type in (SecretStr, SecretBytes):
        return value_type(value.get_secret_value())
    if value_type not in _CONTAINER_TYPES:
        return value  # opaque capability: borrowed by identity
    identity = id(value)
    if identity in active:
        raise ConfigPathOwnershipError("Config path options contain a cycle")
    if identity in memo:
        return memo[identity]
    active.add(identity)
    try:
        if value_type is dict:
            result: Any = {
                _own_value(key, memo, active): _own_value(child, memo, active)
                for key, child in value.items()
            }
        else:
            result = value_type(_own_value(child, memo, active) for child in value)
    finally:
        active.discard(identity)
    memo[identity] = result
    return result


def _option_key(value: Any, active: set[int], borrowed: list[Any]) -> Any:
    """Hashable detached comparison form: values by value, capabilities by id."""
    value_type = type(value)
    if _is_value(value):
        return ("v", value_type, value)
    if value_type in (SecretStr, SecretBytes):
        return ("v", value_type, value.get_secret_value())
    if value_type not in _CONTAINER_TYPES:
        borrowed.append(value)
        return ("o", id(value))
    identity = id(value)
    if identity in active:
        raise ConfigPathOwnershipError("Config path options contain a cycle")
    active.add(identity)
    try:
        if value_type is dict:
            return ("d", frozenset(
                (_option_key(key, active, borrowed), _option_key(child, active, borrowed))
                for key, child in value.items()
            ))
        children = [_option_key(child, active, borrowed) for child in value]
        if value_type in (set, frozenset):
            return ("s", frozenset(children))
        return ("l" if value_type is list else "t", tuple(children))
    finally:
        active.discard(identity)


# --- normalization ------------------------------------------------------------------

def _is_local(path: UPath) -> bool:
    return path.protocol == ""


def _expand(path: UPath) -> UPath:
    """Expand ``~`` for local paths only; remote keys are never expanded."""
    return path.expanduser() if _is_local(path) else path


def normalize_config_path(path: str | UPath) -> str | UPath:
    """Return the canonical config input without any I/O.

    Local strings stay strings (``~`` expanded); local UPaths stay UPaths;
    remote strings become default-option UPaths; remote UPaths keep options.
    """
    if isinstance(path, UPath):
        return _expand(path)
    if isinstance(path, os.PathLike):
        path = os.fspath(path)
    if not isinstance(path, str):
        raise TypeError("Invalid configuration path")
    resolved = _expand(UPath(path))
    return str(resolved) if _is_local(resolved) else resolved


def _as_upath(path: str | UPath) -> UPath:
    return path if isinstance(path, UPath) else UPath(path)


# --- identity / ownership ------------------------------------------------------------

class ConfigPathIdentity:
    """Option-aware comparison key for one config path.

    Hash uses location/protocol/type only (collisions are legal); equality also
    compares detached option data by value and capabilities by identity. The
    identity keeps capabilities strongly referenced so their ids stay valid.
    """

    __slots__ = ("protocol", "location", "path_type", "_options", "_borrowed")

    def __init__(self, protocol: str, location: str, path_type: type | None,
                 options: Any, borrowed: tuple[Any, ...]) -> None:
        self.protocol = protocol
        self.location = location
        self.path_type = path_type
        self._options = options
        self._borrowed = borrowed

    def __hash__(self) -> int:
        return hash((self.protocol, self.location, self.path_type))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ConfigPathIdentity):
            return NotImplemented
        return (
            self.protocol == other.protocol
            and self.location == other.location
            and self.path_type is other.path_type
            and self._options == other._options
        )

    def __repr__(self) -> str:
        return f"ConfigPathIdentity(protocol={self.protocol!r}, type={getattr(self.path_type, '__name__', None)})"


def _identity(path: str | UPath) -> ConfigPathIdentity:
    if not isinstance(path, (str, UPath)):
        raise ConfigPathOwnershipError("Config path must be a string or UPath")
    upath = _as_upath(path)
    borrowed: list[Any] = []
    options = _option_key(dict(upath.storage_options), set(), borrowed)
    local = _is_local(upath)
    return ConfigPathIdentity(
        upath.protocol, str(upath), None if local else type(upath), options, tuple(borrowed),
    )


def config_path_identities(paths: Sequence[str | UPath]) -> tuple[ConfigPathIdentity, ...]:
    """Identity keys for already-normalized paths, in order; no I/O."""
    return tuple(_identity(path) for path in paths)


def _own_path(path: str | UPath, memo: dict[int, Any]) -> str | UPath:
    if isinstance(path, str):
        return path
    if not isinstance(path, UPath):
        raise ConfigPathOwnershipError("Config path must be a string or UPath")
    if _is_local(path) and not path.storage_options:
        return path  # a location, not an open resource
    active: set[int] = set()
    options = {name: _own_value(value, memo, active) for name, value in path.storage_options.items()}
    try:
        rebuilt = type(path)(str(path), protocol=path.protocol, **options)
    except (TypeError, ValueError):
        rebuilt = None
    if (
        rebuilt is None
        or type(rebuilt) is not type(path)
        or rebuilt.protocol != path.protocol
        or str(rebuilt) != str(path)
        or set(rebuilt.storage_options) != set(path.storage_options)
    ):
        raise ConfigPathOwnershipError(
            f"Config path of type {type(path).__name__} cannot be faithfully owned"
        )
    return rebuilt


def own_config_paths(paths: Sequence[str | UPath]) -> tuple[str | UPath, ...]:
    """Independently owned path descriptions; borrowed capabilities are retained.

    Raises ``ConfigPathOwnershipError`` when upstream construction cannot
    reproduce the declared path or its options contain cycles. This does not
    certify state omitted from a subclass's own reconstruction contract.
    """
    memo: dict[int, Any] = {}
    return tuple(_own_path(path, memo) for path in paths)


# --- diagnostics ----------------------------------------------------------------------

def _safe_text(path: UPath) -> str:
    text = str(path)
    protocol = path.protocol
    if protocol in _HTTP_PROTOCOLS:
        parts = urlsplit(text)
        host = parts.netloc.rpartition("@")[2]
        return f"{parts.scheme}://{host}{parts.path}"
    marker = f"{protocol}://"
    if protocol not in _KEYED_PROTOCOLS and text.startswith(marker):
        rest = text[len(marker):]
        netloc, slash, tail = rest.partition("/")
        return f"{marker}{netloc.rpartition('@')[2]}{slash}{tail}"
    return text


def config_path_label(path: str | UPath) -> str | UPath:
    """Safe diagnostic form: no userinfo, HTTP query/fragment or access options.

    Ordinary local paths are returned unchanged. Not a reconstruction API.
    """
    upath = _as_upath(path)
    if _is_local(upath) and not upath.storage_options:
        return path
    return _safe_text(upath)


def config_filename(path: str | UPath) -> str:
    """Filename used for format classification.

    HTTP uses the URL path (queries/fragments never hide the suffix); other
    protocols keep their literal key name, including ``?``/``#``.
    """
    upath = _as_upath(path)
    if upath.protocol in _HTTP_PROTOCOLS:
        return urlsplit(str(upath)).path.rpartition("/")[2]
    return upath.name


# --- structured source adapters ---------------------------------------------------------

def _open_candidate(file: Any) -> UPath | None:
    """UPath for str/PathLike inputs; None leaves resource-like inputs to upstream."""
    if isinstance(file, UPath):
        return _expand(file)
    if isinstance(file, (str, os.PathLike)):
        return _expand(UPath(file))
    return None


class _UPathFilesMixin(ConfigFileSourceMixin):
    """Open selected files through UPath, keeping inherited parsers and merge."""

    def _read_files(self, files: Any, deep_merge: bool = False) -> dict[str, Any]:
        if files is None:
            return {}
        if not isinstance(files, Sequence) or isinstance(files, str):
            files = [files]
        data: dict[str, Any] = {}
        for file in files:
            opened = _open_candidate(file)
            target = file if opened is None else opened
            if not target.is_file():
                continue
            updating = self._read_file(cast(Any, target))
            data = deep_update(data, updating) if deep_merge else {**data, **updating}
        return data


class UPathYamlSource(_UPathFilesMixin, YamlConfigSettingsSource):
    """YAML source whose selected files may be local or remote UPaths."""


class UPathJsonSource(_UPathFilesMixin, JsonConfigSettingsSource):
    """JSON source whose selected files may be local or remote UPaths."""


class UPathTomlSource(_UPathFilesMixin, TomlConfigSettingsSource):
    """TOML source; also replaces upstream's local-only existence check."""

    @staticmethod
    def _any_file_exists(paths: Any) -> bool:
        if paths is None:
            return False
        if isinstance(paths, str) or not isinstance(paths, Sequence):
            paths = [paths]
        for item in paths:
            opened = _open_candidate(item)
            if opened is not None:
                if opened.exists():
                    return True
            elif item.is_file():
                return True
        return False
