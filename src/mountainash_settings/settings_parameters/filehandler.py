"""Configuration path normalization and order-preserving grouping.

Local strings keep their string form (``~`` expanded, local only); remote
URL strings become UPaths; UPaths keep their filesystem options. Paths are
de-duplicated first-seen by option-aware identity. Format classification uses
the URL path for HTTP(S) and the literal key name elsewhere. Missing-file
errors use safe labels (no userinfo, HTTP query/fragment or options).
"""

from collections.abc import Sequence
from pathlib import PurePosixPath
from typing import NamedTuple

from upath import UPath

from mountainash_settings._config_files import (
    ConfigPathIdentity,
    config_filename,
    config_path_identities,
    _display_location,
    config_path_exists,
    normalize_config_path,
)
from mountainash_settings._safe_errors import raise_safe

ConfigPath = str | UPath
ConfigFilesInput = ConfigPath | Sequence[ConfigPath] | None


class SettingsFiles(NamedTuple):
    """Immutable paths grouped by supported source type."""

    env_files: tuple[ConfigPath, ...] = ()
    yaml_files: tuple[ConfigPath, ...] = ()
    toml_files: tuple[ConfigPath, ...] = ()
    json_files: tuple[ConfigPath, ...] = ()


class FileType:
    ENV = "env"
    YML = "yml"
    YAML = "yaml"
    TOML = "toml"
    JSON = "json"


class FileTypeRegistry:
    """Registry of supported extensions."""

    _registry = {"env": FileType.ENV, "yaml": FileType.YAML, "yml": FileType.YAML,
                 "toml": FileType.TOML, "json": FileType.JSON}

    @classmethod
    def register_type(cls, extension: str, file_type: str) -> None:
        cls._registry[extension] = file_type

    @classmethod
    def identify(cls, file_path: ConfigPath) -> str | None:
        filename = config_filename(file_path)
        if filename.startswith(".") and "." not in filename[1:]:
            return cls._registry.get(filename[1:].lower())
        return cls._registry.get(PurePosixPath(filename).suffix.lower().lstrip("."))


class SettingsFileHandler:
    """Normalize inputs before validation, merging or grouping."""

    @staticmethod
    def format_config_file_tuple(config_files: ConfigFilesInput = None) -> tuple[ConfigPath, ...]:
        if config_files is None:
            return ()
        raw = (config_files,) if isinstance(config_files, (str, UPath)) else config_files
        if not isinstance(raw, Sequence):
            raise_safe(TypeError("Invalid configuration paths"))
        normalized = tuple(normalize_config_path(item) for item in raw)
        unique: dict[ConfigPathIdentity, ConfigPath] = {}
        for identity, path in zip(config_path_identities(normalized), normalized):
            unique.setdefault(identity, path)
        return tuple(unique.values())

    @classmethod
    def format_config_file_list(cls, config_files: ConfigFilesInput = None) -> list[ConfigPath]:
        return list(cls.format_config_file_tuple(config_files))

    @classmethod
    def deduplicate_files(cls, config_files: ConfigFilesInput = None) -> list[ConfigPath]:
        return cls.format_config_file_list(config_files)

    @classmethod
    def merge_config_files(
        cls, config_files1: ConfigFilesInput = None, config_files2: ConfigFilesInput = None,
    ) -> tuple[ConfigPath, ...]:
        return cls.format_config_file_tuple(
            cls.format_config_file_tuple(config_files1) + cls.format_config_file_tuple(config_files2)
        )

    @staticmethod
    def identify_file_extension(file_path: ConfigPath) -> str:
        if file_path is None:
            raise_safe(TypeError("Invalid configuration path"))
        extension = FileTypeRegistry.identify(file_path)
        if extension is None:
            raise_safe(ValueError("Unsupported configuration file extension"))
        return extension

    @classmethod
    def validate_config_files_exist(cls, config_files: ConfigFilesInput = None) -> None:
        for item in cls.format_config_file_tuple(config_files):
            if not config_path_exists(item):
                raise_safe(FileNotFoundError(f"Config file {_display_location(item)} not found."))

    @classmethod
    def group_files_by_type(cls, config_files: ConfigFilesInput = None) -> dict[str, list[ConfigPath]]:
        groups: dict[str, list[ConfigPath]] = {}
        for item in cls.format_config_file_tuple(config_files):
            extension = cls.identify_file_extension(item)
            groups.setdefault(extension, []).append(item)
        return groups

    @classmethod
    def separate_config_files(cls, config_files: ConfigFilesInput = None) -> SettingsFiles:
        groups = cls.group_files_by_type(config_files)
        return SettingsFiles(
            env_files=tuple(groups.get(FileType.ENV, ())),
            yaml_files=tuple(groups.get(FileType.YAML, ())),
            toml_files=tuple(groups.get(FileType.TOML, ())),
            json_files=tuple(groups.get(FileType.JSON, ())),
        )
