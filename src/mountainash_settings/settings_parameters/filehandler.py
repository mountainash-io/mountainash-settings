"""Configuration path normalization and order-preserving grouping."""

from collections.abc import Sequence
from typing import NamedTuple

from upath import UPath

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
        path = UPath(file_path)
        if path.name.startswith(".") and "." not in path.name[1:]:
            return cls._registry.get(path.name[1:].lower())
        return cls._registry.get(path.suffix.lower().lstrip("."))


class SettingsFileHandler:
    """Normalize inputs before validation, merging or grouping."""

    @staticmethod
    def format_config_file_tuple(config_files: ConfigFilesInput = None) -> tuple[ConfigPath, ...]:
        if config_files is None:
            return ()
        raw = (config_files,) if isinstance(config_files, (str, UPath)) else config_files
        if not isinstance(raw, Sequence):
            raise TypeError("Invalid configuration paths")
        unique: dict[str, ConfigPath] = {}
        for item in raw:
            path = UPath(item).expanduser()
            # Retain UPath filesystem options; never reconstruct it from a URL.
            unique.setdefault(str(path), path if isinstance(item, UPath) else str(path))
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
            raise TypeError("Invalid configuration path")
        extension = FileTypeRegistry.identify(file_path)
        if extension is None:
            raise ValueError("Unsupported configuration file extension")
        return extension

    @classmethod
    def validate_config_files_exist(cls, config_files: ConfigFilesInput = None) -> None:
        for item in cls.format_config_file_tuple(config_files):
            if not UPath(item).exists():
                raise FileNotFoundError(f"Config file {item} not found.")

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
