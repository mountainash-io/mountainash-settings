"""Private owned structural contexts for cached settings retrieval."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Iterator, Type, cast

from pydantic import BaseModel, SecretStr
from pydantic._internal._utils import deep_update
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    EnvSettingsSource,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
    SecretsSettingsSource,
    TomlConfigSettingsSource,
    YamlConfigSettingsSource,
)
from pydantic_settings.sources import (
    DefaultSettingsSource,
    DotenvType,
    EnvPrefixTarget,
    InitSettingsSource,
    PathType,
)

from pydantic_settings.sources.utils import InitState

from ..resolve import resolve_references_in_dict
from ..secrets.backend import SecretReader
from ..settings_parameters import SettingsFileHandler, SettingsParameters
from .sources import CacheableSettingsSource

_SourceSnapshot = tuple[type[PydanticBaseSettingsSource], str, dict[str, Any], bool]


@dataclass(frozen=True, eq=False)
class _StructuralKey:
    config_files: tuple[str, ...] | None
    settings_class: Type[BaseSettings]
    env_prefix: str | None
    secrets_dir: str | None
    secret_store: "SecretReader | None" = field(repr=False)

    @classmethod
    def from_parameters(cls, parameters: SettingsParameters) -> "_StructuralKey":
        if parameters.settings_class is None:
            raise ValueError("settings_parameters.settings_class cannot be empty.")
        files = SettingsFileHandler.format_config_file_tuple(parameters.config_files)
        return cls(
            tuple(str(path) for path in files) if files else None,
            parameters.settings_class,
            parameters.env_prefix,
            parameters.secrets_dir,
            parameters.secret_store,
        )

    def __hash__(self) -> int:
        store = None if self.secret_store is None else id(self.secret_store)
        return hash((self.config_files, id(self.settings_class), self.env_prefix, self.secrets_dir, store))

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, _StructuralKey)
            and self.config_files == other.config_files
            and self.settings_class is other.settings_class
            and self.env_prefix == other.env_prefix
            and self.secrets_dir == other.secrets_dir
            and self.secret_store is other.secret_store
        )

    def parameters(self) -> SettingsParameters:
        return SettingsParameters.create(
            config_files=self.config_files,
            settings_class=self.settings_class,
            env_prefix=self.env_prefix,
            secrets_dir=self.secrets_dir,
            secret_store=self.secret_store,
        )

@dataclass
class _CacheFrame:
    context: "_SettingsContext"
    reinitialise: bool
    original_runtime: dict[str, Any] = field(default_factory=dict)
    bound_instance: BaseSettings | None = None
    consumed: bool = False
    raw_assignments: dict[str, Any] | None = None
    expected_fields: dict[str, Any] | None = None
    recording_instance: BaseSettings | None = None
    suppressed_fields: frozenset[str] = frozenset()
    has_runtime_inputs: bool = False

    def bind(self, instance: BaseSettings) -> None:
        if (
            self.bound_instance is None
            and type(instance) is self.context.key.settings_class
        ):
            self.bound_instance = instance

    def consume(self, instance: BaseSettings) -> bool:
        if self.consumed or instance is not self.bound_instance:
            return False
        self.consumed = True
        return True

    def candidate(self, effective_runtime: dict[str, Any]) -> dict[str, Any]:
        self.has_runtime_inputs = bool(effective_runtime)
        candidate, self.suppressed_fields = self.context._candidate(
            effective_runtime, reinitialise=self.reinitialise,
        )
        return candidate

    def static_defaults_for_call(self) -> dict[str, Any]:
        return _copy_for_call(self.context._resolved_static_defaults)

    def prepare_assignment(self, name: str, value: Any) -> Any:
        from ..settings.base_settings import _snapshot_reconstruction

        copied = _snapshot_reconstruction({name: value})
        if copied is None:
            raise ValueError("Cached post-init assignment cannot be safely owned")
        return copied[name]

    def record_validated_assignment(self, name: str, raw_value: Any, value: Any) -> None:
        if self.expected_fields is None:
            raise RuntimeError("Cached post-init recording has not started")
        self.expected_fields[name] = _owned({name: value})[name]
        if self.raw_assignments is None:
            self.raw_assignments = {}
        self.raw_assignments[name] = raw_value


_CURRENT_FRAME: ContextVar[_CacheFrame | None] = ContextVar("mountainash_cached_settings_frame", default=None)


@contextmanager
def cache_materialization_frame(
    context: "_SettingsContext", reinitialise: bool, original_runtime: dict[str, Any],
) -> Iterator[_CacheFrame]:
    frame = _CacheFrame(
        context=context,
        reinitialise=reinitialise,
        original_runtime=_copy_for_call(original_runtime),
    )
    token = _CURRENT_FRAME.set(frame)
    try:
        yield frame
    finally:
        _CURRENT_FRAME.reset(token)


def bind_cache_frame_instance(instance: BaseSettings) -> None:
    frame = _CURRENT_FRAME.get()
    if frame is not None:
        frame.bind(instance)


def consume_cache_frame(instance: BaseSettings) -> _CacheFrame | None:
    frame = _CURRENT_FRAME.get()
    if frame is not None and frame.consume(instance):
        return frame
    return None


def current_cache_assignment_recorder(instance: Any) -> _CacheFrame | None:
    frame = _CURRENT_FRAME.get()
    if frame is not None and frame.recording_instance is instance:
        return frame
    return None


def _owned(values: dict[str, Any]) -> dict[str, Any]:
    from ..settings.base_settings import _snapshot_reconstruction

    copied = _snapshot_reconstruction(values)
    if copied is None:
        raise ValueError("Cached settings state cannot be safely owned")
    return copied


def _copy_for_call(values: dict[str, Any]) -> dict[str, Any]:
    return _owned(values)


def _builtin_source(source: PydanticBaseSettingsSource) -> bool:
    return type(source) in {
        DefaultSettingsSource,
        InitSettingsSource,
        EnvSettingsSource,
        DotEnvSettingsSource,
        YamlConfigSettingsSource,
        TomlConfigSettingsSource,
        JsonConfigSettingsSource,
        SecretsSettingsSource,
    }


def _source_name(source: PydanticBaseSettingsSource) -> str:
    return source.__name__ if hasattr(source, "__name__") else type(source).__name__


def _settings_sources(key: _StructuralKey) -> tuple[PydanticBaseSettingsSource, ...]:
    cls = key.settings_class
    from ..settings.base_settings import MountainAshBaseSettings

    if issubclass(cls, MountainAshBaseSettings):
        inherited_hook = MountainAshBaseSettings.settings_capture_sources
        inherited_legacy = MountainAshBaseSettings.settings_customise_sources
    else:
        inherited_hook = None
        inherited_legacy = BaseSettings.settings_customise_sources
    capture_hook = getattr(cls, "settings_capture_sources", None)
    legacy = getattr(cls, "settings_customise_sources")
    hook_is_inherited = capture_hook is None or (
        inherited_hook is not None
        and getattr(capture_hook, "__func__", capture_hook)
        is getattr(inherited_hook, "__func__", inherited_hook)
    )
    legacy_is_inherited = (
        getattr(legacy, "__func__", legacy)
        is getattr(inherited_legacy, "__func__", inherited_legacy)
    )
    if not legacy_is_inherited and hook_is_inherited:
        raise ValueError("Cached retrieval requires settings_capture_sources for a legacy settings_customise_sources hook")
    # Cache admission permits only the five structural selectors.  Construct the
    # configured sources ourselves so legacy hooks are never invoked implicitly.
    config = cls.model_config
    is_mountainash = issubclass(cls, MountainAshBaseSettings)
    nested_update: bool | None
    case_sensitive: bool | None
    env_ignore_empty: bool | None
    env_parse_none_str: str | None
    env_parse_enums: bool | None
    env_file_encoding: str | None
    if is_mountainash:
        # These are MountainAshBaseSettings.__init__'s effective source
        # options, rather than pydantic-settings' native defaults.
        nested_update = False
        case_sensitive = True
        env_ignore_empty = True
        env_parse_none_str = "None"
        env_parse_enums = True
        env_file_encoding = "utf-8"
    else:
        nested_update = config.get("nested_model_default_partial_update")
        case_sensitive = config.get("case_sensitive")
        env_ignore_empty = config.get("env_ignore_empty")
        env_parse_none_str = config.get("env_parse_none_str")
        env_parse_enums = config.get("env_parse_enums")
        env_file_encoding = config.get("env_file_encoding")
    env_prefix_target: EnvPrefixTarget | None = config.get("env_prefix_target")
    env_nested_delimiter: str | None = config.get("env_nested_delimiter")
    env_nested_max_split: int | None = config.get("env_nested_max_split")
    secrets_dir: PathType | None = (
        key.secrets_dir if key.secrets_dir is not None else config.get("secrets_dir")
    )
    init_state: InitState = {"field_info_ids": set()}
    default = DefaultSettingsSource(
        cls, nested_model_default_partial_update=False, _init_state=init_state,
    )
    init = InitSettingsSource(
        cls, init_kwargs={}, nested_model_default_partial_update=nested_update, _init_state=init_state,
    )
    effective_prefix: str | None = (
        key.env_prefix if key.env_prefix is not None else config.get("env_prefix")
    )
    env = EnvSettingsSource(
        cls, case_sensitive=case_sensitive, env_prefix=effective_prefix,
        env_prefix_target=env_prefix_target, env_nested_delimiter=env_nested_delimiter,
        env_nested_max_split=env_nested_max_split, env_ignore_empty=env_ignore_empty,
        env_parse_none_str=env_parse_none_str, env_parse_enums=env_parse_enums, _init_state=init_state,
    )
    files = SettingsFileHandler.separate_config_files(key.config_files)
    SettingsFileHandler.validate_config_files_exist(files.env_files)
    SettingsFileHandler.validate_config_files_exist(files.yaml_files)
    SettingsFileHandler.validate_config_files_exist(files.toml_files)
    SettingsFileHandler.validate_config_files_exist(files.json_files)
    env_file: DotenvType | None = (
        cast(DotenvType, files.env_files) if files.env_files else config.get("env_file")
    )
    dotenv = DotEnvSettingsSource(
        cls, env_file=env_file, env_file_encoding=env_file_encoding,
        case_sensitive=case_sensitive, env_prefix=effective_prefix,
        env_prefix_target=env_prefix_target, env_nested_delimiter=env_nested_delimiter,
        env_nested_max_split=env_nested_max_split, env_ignore_empty=env_ignore_empty,
        env_parse_none_str=env_parse_none_str, env_parse_enums=env_parse_enums, _init_state=init_state,
    )
    secrets = SecretsSettingsSource(
        cls, secrets_dir=secrets_dir, case_sensitive=case_sensitive, env_prefix=effective_prefix,
        env_prefix_target=env_prefix_target, _init_state=init_state,
    )
    builtins: tuple[PydanticBaseSettingsSource, ...]
    if is_mountainash:
        # Pass None explicitly rather than letting source constructors inherit
        # file selectors mutated by an earlier direct MountainAsh construction.
        builtins = MountainAshBaseSettings._cache_default_sources(
            cls, init, env, dotenv, secrets,
            yaml_files=files.yaml_files, toml_files=files.toml_files, json_files=files.json_files,
        )
    else:
        builtins = (init, env, dotenv, secrets)
    if capture_hook is not None:
        builtins = tuple(capture_hook(tuple(builtins)))
    return (*builtins, default)


def _capture_sources(key: _StructuralKey) -> tuple[tuple[_SourceSnapshot, ...], dict[str, Any]]:
    state: dict[str, Any] = {}
    states: dict[str, dict[str, Any]] = {}
    captured: list[_SourceSnapshot] = []
    for source in _settings_sources(key):
        source._set_current_state(_copy_for_call(state))
        source._set_settings_sources_data(_copy_for_call(states))
        if isinstance(source, CacheableSettingsSource):
            source_state = source.capture()
            custom = True
        elif _builtin_source(source):
            source_state = source()
            custom = False
        else:
            raise ValueError("Cached retrieval requires CacheableSettingsSource for custom sources")
        source_state = _owned(source_state)
        name = _source_name(source)
        states[name] = _copy_for_call(source_state)
        captured.append((type(source), name, source_state, custom))
        state = deep_update(source_state, state)
    return tuple(captured), state


def _resolve_capture(
    key: _StructuralKey, snapshots: tuple[_SourceSnapshot, ...],
) -> tuple[_SourceSnapshot, ...]:
    return tuple(
        (
            source_type,
            name,
            _owned(snapshot) if source_type is DefaultSettingsSource else _owned(
                resolve_references_in_dict(_copy_for_call(snapshot), key.secret_store)
            ),
            custom,
        )
        for source_type, name, snapshot, custom in snapshots
    )


def _capture_static_defaults(key: _StructuralKey) -> dict[str, Any]:
    """Resolve declared non-factory references once for this context."""
    from pydantic_core import PydanticUndefined

    from ..resolve import _resolve_reference_value

    defaults: dict[str, Any] = {}
    for name, field_info in key.settings_class.model_fields.items():
        if field_info.default is PydanticUndefined:
            continue
        resolved, changed = _resolve_reference_value(field_info.default, key.secret_store, "secret:")
        if changed:
            defaults[name] = resolved
    return _owned(defaults)


class _SettingsContext:
    """One structural source snapshot and no retained materialized result."""

    def __init__(self, key: _StructuralKey):
        self.key = key
        self._raw_sources: tuple[_SourceSnapshot, ...] | None = None
        self._resolved_sources: tuple[_SourceSnapshot, ...] | None = None
        self._resolved_static_defaults: dict[str, Any] = {}
        self._source_carry: dict[str, Any] | None = None
        self._publication_lock = Lock()

    def capture(self) -> None:
        raw_sources, _ = _capture_sources(self.key)
        resolved_sources = _resolve_capture(self.key, raw_sources)
        static_defaults = _capture_static_defaults(self.key)
        self._raw_sources = tuple(
            (source_type, name, _owned(values), custom)
            for source_type, name, values, custom in raw_sources
        )
        self._resolved_sources = tuple(
            (source_type, name, _owned(values), custom)
            for source_type, name, values, custom in resolved_sources
        )
        self._resolved_static_defaults = _owned(static_defaults)

    def _project_sources(self, runtime: dict[str, Any]) -> dict[str, Any]:
        if self._resolved_sources is None:
            raise ValueError("Cached source capture is unavailable")
        state: dict[str, Any] = {}
        states: dict[str, dict[str, Any]] = {}
        for source_type, name, snapshot, custom in self._resolved_sources:
            if source_type is DefaultSettingsSource:
                # Partial defaults apply after logical runtime/carry replacement.
                # Absent fields remain absent for ordinary Pydantic defaults.
                continue
            if custom:
                source_type = cast(type[CacheableSettingsSource], source_type)
                source_state = source_type.project(
                    _copy_for_call(snapshot), _copy_for_call(state), _copy_for_call(states),
                )
                if not isinstance(source_state, dict):
                    raise ValueError("Cache source projection must return a dictionary")
                source_state = _owned(source_state)
            elif source_type is InitSettingsSource:
                from ..settings.base_settings import MountainAshBaseSettings

                source_state = InitSettingsSource(
                    self.key.settings_class,
                    init_kwargs=_copy_for_call(runtime),
                    nested_model_default_partial_update=(
                        False
                        if issubclass(self.key.settings_class, MountainAshBaseSettings)
                        else self.key.settings_class.model_config.get(
                            "nested_model_default_partial_update"
                        )
                    ),
                )()
                source_state = _owned(source_state)
            else:
                source_state = _copy_for_call(snapshot)
            states[name] = _copy_for_call(source_state)
            # As with pydantic-settings' source merge, earlier sources retain
            # precedence while each custom projector sees the same ordered
            # source-data names captured above.
            state = deep_update(source_state, state)
        return state

    def recipe(self, original_runtime: dict[str, Any]) -> dict[str, Any]:
        """Return only the caller's source-form runtime input."""
        return _copy_for_call(original_runtime)

    def has_secret_reference(self, runtime: dict[str, Any]) -> bool:
        def contains_reference(value: Any) -> bool:
            if isinstance(value, SecretStr):
                return value.get_secret_value().startswith("secret:")
            if isinstance(value, str):
                return value.startswith("secret:")
            if isinstance(value, dict):
                return any(contains_reference(child) for child in value.values())
            if isinstance(value, (list, tuple)):
                return any(contains_reference(child) for child in value)
            return False

        if contains_reference(runtime):
            return True
        return self._raw_sources is not None and any(
            contains_reference(snapshot)
            for _, _, snapshot, _ in self._raw_sources
        )

    def _candidate(
        self, effective_runtime: dict[str, Any], *, reinitialise: bool = False,
    ) -> tuple[dict[str, Any], frozenset[str]]:
        from ..settings.base_settings import (
            MountainAshBaseSettings,
            _cache_input_field_names,
            _cache_overlay_fields,
        )

        runtime = _owned(effective_runtime) if effective_runtime else {}
        if runtime:
            runtime = resolve_references_in_dict(runtime, self.key.secret_store)
        candidate = self._project_sources(runtime)
        with self._publication_lock:
            retained_carry = self._source_carry
        carry = _copy_for_call(retained_carry) if retained_carry is not None and not reinitialise else {}
        cls = self.key.settings_class
        candidate = _cache_overlay_fields(candidate, carry, cls, logical_fields=True)
        candidate = _cache_overlay_fields(candidate, runtime, cls)
        if not issubclass(cls, MountainAshBaseSettings) and cls.model_config.get("nested_model_default_partial_update"):
            defaults = DefaultSettingsSource(cls, nested_model_default_partial_update=True)()
            # Only enrich supplied nested objects: adding absent defaults would
            # lose input origin and suppress ordinary default evaluation.
            defaults = {name: value for name, value in defaults.items() if name in candidate}
            default_fields = _cache_input_field_names(cls, defaults)
            resolved_defaults = {
                name: value.model_dump()
                for name, value in _copy_for_call(self._resolved_static_defaults).items()
                if name in default_fields and isinstance(value, BaseModel)
            }
            defaults = _cache_overlay_fields(defaults, resolved_defaults, cls, logical_fields=True)
            candidate = deep_update(defaults, candidate)
        return (
            candidate,
            frozenset(carry)
            | _cache_input_field_names(cls, effective_runtime),
        )

    def materialize(self, runtime: dict[str, Any], *, reinitialise: bool = False) -> BaseSettings:
        from ..settings.base_settings import (
            MountainAshBaseSettings,
            _apply_cached_static_defaults,
            _detach_cached_result,
        )

        cls = self.key.settings_class
        frame: _CacheFrame | None = None
        result: BaseSettings
        if issubclass(cls, MountainAshBaseSettings):
            with cache_materialization_frame(self, reinitialise, runtime) as frame:
                result = cls(**_copy_for_call(runtime))
            if not frame.consumed:
                raise ValueError("Cached MountainAsh constructor did not consume its materialization frame")
        else:
            if cls.__init__ is not BaseSettings.__init__:
                raise ValueError("Cached retrieval requires BaseSettings.__init__ for plain settings classes")
            candidate, _ = self._candidate(runtime, reinitialise=reinitialise)
            result = cls.__new__(cls)
            try:
                BaseModel.__init__(result, **candidate)
            except Exception:
                if self.has_secret_reference(runtime):
                    raise ValueError(f"Cached validation failed for {cls.__name__}") from None
                raise
            _apply_cached_static_defaults(
                result, candidate, _copy_for_call(self._resolved_static_defaults),
            )
        _detach_cached_result(result)
        if (
            isinstance(result, MountainAshBaseSettings)
            and frame is not None
            and not reinitialise
            and not runtime
            and not frame.original_runtime
            and not frame.has_runtime_inputs
        ):
            owned_assignments = _owned(frame.raw_assignments or {})
            with self._publication_lock:
                if self._source_carry is None:
                    self._source_carry = owned_assignments
        return result
