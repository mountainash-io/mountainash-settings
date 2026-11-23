"""Private config-file path machinery shared by parameters, cache and sources.

One home for: input normalization, option-aware path identity, independent
ownership of option containers, safe diagnostic labels, HTTP-aware filename
classification and the YAML/TOML/JSON/dotenv UPath source adapters.

Ownership contract: exact ordinary containers (dict/list/tuple/set/frozenset)
and immutable value types are owned recursively and compared by value. Every
other option object (clients, timeouts, credentials, enum members, models,
container subclasses ...) is an opaque access capability: it is retained
strongly and compared by identity, never cloned or closed. Identity encoding
does not call capability equality/hash hooks; ordinary container construction
retains Python's key protocol. Path normalization and ownership perform no I/O.

This module must not import ``settings_parameters.filehandler`` at runtime:
that module consumes it.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import PurePath
from typing import Any, NoReturn, cast
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import SecretBytes, SecretStr
from pydantic._internal._utils import deep_update
from dotenv import dotenv_values
from pydantic_settings import (
    DotEnvSettingsSource,
    JsonConfigSettingsSource,
    TomlConfigSettingsSource,
    YamlConfigSettingsSource,
)
from pydantic_settings.sources.utils import parse_env_vars
from pydantic_settings.sources import ConfigFileSourceMixin
from upath import UPath

from mountainash_settings._safe_errors import (
    install_config_log_filters, raise_safe, safe_detail, safe_location,
)

install_config_log_filters()

__all__ = [
    "ConfigPathIdentity",
    "ConfigPathOwnershipError",
    "UPathJsonSource",
    "UPathTomlSource",
    "UPathYamlSource",
    "config_filename",
    "config_path_identities",
    "config_path_label",
    "config_path_exists",
    "normalize_config_path",
    "own_config_paths",
    "UPathDotenvSource",
    "dotenv_view",
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
        try:
            return _expand(path)
        except Exception as native:
            _raise_invalid_location(path, native)
    if isinstance(path, os.PathLike):
        try:
            path = os.fspath(path)
        except Exception as native:
            _raise_invalid_location(path, native)
    if not isinstance(path, str):
        raise_safe(TypeError("Invalid configuration path"))
    try:
        resolved = _expand(UPath(path))
        return str(resolved) if _is_local(resolved) else resolved
    except Exception as native:
        _raise_invalid_location(path, native)


def is_remote_config_path(path: str | UPath) -> bool:
    """Classify a selector without exposing native path-construction failures."""
    try:
        return _as_upath(path).protocol != ""
    except Exception as native:
        _raise_invalid_location(path, native)


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
        raise_safe(ConfigPathOwnershipError("Config path must be a string or UPath"))
    try:
        upath = _as_upath(path)
        borrowed: list[Any] = []
        options = _option_key(dict(upath.storage_options), set(), borrowed)
        local = _is_local(upath)
        return ConfigPathIdentity(
            upath.protocol, str(upath), None if local else type(upath), options, tuple(borrowed),
        )
    except ConfigPathOwnershipError:
        # Rebuild a controlled refusal; never trust the caught message or attributes.
        raise_safe(ConfigPathOwnershipError("Config path options cannot be identified"))
    except Exception as native:
        _raise_invalid_location(path, native)


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
    owned: list[str | UPath] = []
    for path in paths:
        try:
            owned.append(_own_path(path, memo))
        except ConfigPathOwnershipError:
            raise_safe(ConfigPathOwnershipError(
                f"Config path of type {type(path).__name__} cannot be faithfully owned"
            ))
        except Exception as native:
            _raise_invalid_location(path, native)
    return tuple(owned)


# --- diagnostics ----------------------------------------------------------------------

def _display_location(path: Any) -> str:
    # Remote UPaths are not necessarily PathLike (notably HTTPPath in UPath 0.3).
    try:
        location = str(path)
    except Exception:
        return "***"
    return safe_location(location)


def _raise_invalid_location(path: Any, native: Exception) -> NoReturn:
    raise_safe(
        ValueError(f"Config file {_display_location(path)}: invalid location ({safe_detail(native)})"),
        native,
    )


def _raise_config_access_error(location: str, operation: str, native: Exception) -> NoReturn:
    display = safe_location(location)
    detail = safe_detail(native)
    if isinstance(native, OSError) and native.errno is not None:
        error = OSError(native.errno, f"Config file {operation} failed ({detail})", display)
    elif isinstance(native, FileNotFoundError):
        error = FileNotFoundError(f"Config file {display}: {operation} failed ({detail})")
    else:
        error = OSError(f"Config file {display}: {operation} failed ({detail})")
    raise_safe(error, native)


def config_path_exists(path: str | UPath) -> bool:
    """Inspect a config selector without exposing backend exception payloads."""
    try:
        target = _as_upath(path)
        return target.exists()
    except Exception as native:
        _raise_config_access_error(_display_location(path), "inspect", native)


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
    try:
        upath = _as_upath(path)
        if upath.protocol in _HTTP_PROTOCOLS:
            return urlsplit(str(upath)).path.rpartition("/")[2]
        return upath.name
    except Exception as native:
        _raise_invalid_location(path, native)


# --- structured source adapters ---------------------------------------------------------

def _open_candidate(file: Any) -> UPath | None:
    """UPath for str/PathLike inputs; None leaves resource-like inputs to upstream."""
    try:
        if isinstance(file, UPath):
            return _expand(file)
        if isinstance(file, (str, os.PathLike)):
            return _expand(UPath(file))
        return None
    except Exception as native:
        _raise_invalid_location(file, native)


def _config_is_file(path: Any, *, allow_fifo: bool = False) -> bool:
    try:
        return bool(path.is_file() or (allow_fifo and _is_local(path) and path.is_fifo()))
    except Exception as native:
        _raise_config_access_error(_display_location(path), "inspect", native)


class _ConfigReader:
    """Only the read interface consumed by the inherited content parsers."""

    def __init__(self, stream: Any, display: str) -> None:
        self._stream = stream
        self.name = display

    def read(self, *args: Any, **kwargs: Any) -> Any:
        try:
            return self._stream.read(*args, **kwargs)
        except UnicodeDecodeError:
            raise
        except Exception as native:
            _raise_config_access_error(self.name, "read", native)


class _ConfigOpen:
    def __init__(self, manager: Any, display: str) -> None:
        self._manager = manager
        self._display = display

    def __enter__(self) -> _ConfigReader:
        try:
            stream = self._manager.__enter__()
        except Exception as native:
            _raise_config_access_error(self._display, "open", native)
        return _ConfigReader(stream, self._display)

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> Any:
        try:
            return self._manager.__exit__(exc_type, exc, traceback)
        except Exception as native:
            if native is exc:
                raise
            _raise_config_access_error(self._display, "close", native)


class _ConfigPathView:
    def __init__(self, path: Any) -> None:
        self._path = path

    def open(self, *args: Any, **kwargs: Any) -> _ConfigOpen:
        display = _display_location(self._path)
        try:
            manager = self._path.open(*args, **kwargs)
        except Exception as native:
            _raise_config_access_error(display, "open", native)
        return _ConfigOpen(manager, display)


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
            if not _config_is_file(target):
                continue
            updating = self._read_file(cast(Any, _ConfigPathView(target)))
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
                if config_path_exists(opened):
                    return True
            elif _config_is_file(item):
                return True
        return False


# --- dotenv adapter ---------------------------------------------------------------------

class UPathDotenvSource(DotEnvSettingsSource):
    """Dotenv source that streams selected UPaths and keeps upstream interpretation.

    Only file opening differs from the inherited source: parsing, empty/None handling,
    case folding, filtering, prefix/alias targeting and nested handling are inherited.
    ``captured_env`` supplies an already parsed mapping so a second view of the same
    files never rereads the source.
    """

    def __init__(self, *args: Any, captured_env: Mapping[str, str | None] | None = None,
                 **kwargs: Any) -> None:
        self._captured_env = captured_env
        super().__init__(*args, **kwargs)

    def _load_env_vars(self) -> Mapping[str, str | None]:
        if self._captured_env is not None:
            return dict(self._captured_env)
        return self._read_env_files()

    def _read_env_file(self, file_path: Any) -> Mapping[str, str | None]:
        with _ConfigPathView(file_path).open("r", encoding=self.env_file_encoding or "utf8") as stream:
            file_vars = dotenv_values(stream=cast(Any, stream))
        return parse_env_vars(
            file_vars, self.case_sensitive, self.env_ignore_empty, self.env_parse_none_str,
        )

    def _read_env_files(self) -> Mapping[str, str | None]:
        env_files = self.env_file
        if env_files is None:
            return {}
        if isinstance(env_files, (str, os.PathLike, UPath)):
            env_files = [env_files]
        dotenv_vars: dict[str, str | None] = {}
        for env_file in env_files:
            path = _open_candidate(env_file)
            if path is None:
                try:
                    path = UPath(str(env_file))
                except Exception as native:
                    _raise_invalid_location(env_file, native)
            # FIFOs exist only on local filesystems; remote paths need not implement them.
            if _config_is_file(path, allow_fifo=True):
                dotenv_vars.update(self._read_env_file(path))
        return dotenv_vars


def dotenv_view(
    source: DotEnvSettingsSource,
    files: Any,
    prefix: str,
    *,
    captured_env: Mapping[str, str | None] | None = None,
) -> UPathDotenvSource:
    """Another view of ``source``: same flags and shared init state, other files/prefix."""
    return UPathDotenvSource(
        source.settings_cls,
        env_file=files,
        env_file_encoding=source.env_file_encoding,
        dotenv_filtering=source.dotenv_filtering,
        case_sensitive=source.case_sensitive,
        env_prefix=prefix,
        env_prefix_target=source.env_prefix_target,
        env_nested_delimiter=source.env_nested_delimiter,
        env_nested_max_split=source.env_nested_max_split,
        env_ignore_empty=source.env_ignore_empty,
        env_parse_none_str=source.env_parse_none_str,
        env_parse_enums=source.env_parse_enums,
        _init_state=source._init_state,
        captured_env=captured_env,
    )
