from typing import Optional, Union, List, Any, Dict, Type, Tuple, TypeVar, cast
from upath import UPath
from string import Formatter
from importlib import import_module
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from enum import Enum
from pathlib import PurePosixPath, PureWindowsPath, PosixPath, WindowsPath
from uuid import UUID

from pydantic import AliasPath, BaseModel, Field, PrivateAttr, SecretStr, SecretBytes
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
    YamlConfigSettingsSource,
)

from mountainash_settings.settings_parameters import SettingsFileHandler, SettingsParameters, SettingsKwargsHandler, SettingsFiles

# T = TypeVar('T', bound='BaseSettings')
T = TypeVar('T', BaseSettings, 'MountainAshBaseSettings')


_CACHE_SOURCE_UNSET = object()
_LOCAL_PATH_TYPE = type(UPath("."))


@dataclass(frozen=True)
class _DirectSourceFrame:
    """Invocation-local file-source paths for one direct construction (MAS-SEC-004).

    Carries only the declared settings class and normalized YAML/TOML/JSON
    path tuples -- never resolved credential values. Consulted by
    ``settings_customise_sources`` only when it belongs to the class
    currently under construction; never exposed as a public API.
    """

    settings_class: Type[BaseSettings]
    yaml_files: Any
    toml_files: Any
    json_files: Any


_CURRENT_DIRECT_SOURCE_FRAME: ContextVar[Optional["_DirectSourceFrame"]] = ContextVar(
    "mountainash_settings_direct_source_frame", default=None,
)


@contextmanager
def _direct_source_frame(
    settings_class: Type[BaseSettings], yaml_files: Any, toml_files: Any, json_files: Any,
):
    """Install this invocation's file-source paths for the duration of construction.

    A private ContextVar frame, never a class/model_config mutation: overlapping,
    nested, and failing construction of the same or different declared classes
    cannot leak one invocation's source paths into another's.
    """

    frame = _DirectSourceFrame(settings_class, yaml_files, toml_files, json_files)
    token = _CURRENT_DIRECT_SOURCE_FRAME.set(frame)
    try:
        yield frame
    finally:
        _CURRENT_DIRECT_SOURCE_FRAME.reset(token)


class _UnownedReconstruction(Exception):
    """Internal signal; never retains an input or exception from user code."""



def _reconstruction_key_is_safe(value: Any) -> bool:
    """Hash only exact value types, never user model hash/equality hooks."""
    value_type = type(value)
    if value_type in (tuple, frozenset):
        return all(_reconstruction_key_is_safe(child) for child in value)
    return value_type in (
        type(None), bool, int, float, complex, str, bytes,
        SecretStr, SecretBytes, date, datetime, time, timedelta, Decimal, UUID,
        PurePosixPath, PureWindowsPath, PosixPath, WindowsPath, _LOCAL_PATH_TYPE,
    )


def _enum_value_is_immutable(value: Any) -> bool:
    if type(value) in (tuple, frozenset):
        return all(_enum_value_is_immutable(child) for child in value)
    return type(value) in (type(None), bool, int, float, complex, str, bytes)


def _copy_reconstruction(value: Any, memo: dict[int, Any], active: set[int]) -> Any:
    """Copy source values without trusting arbitrary user copy hooks.

    Exact value types are deliberate: subclasses may carry mutable state.
    Extraction may discard unsupported state; cached materialization rejects it.
    """
    value_type = type(value)
    if value_type in (type(None), bool, int, float, complex, str, bytes):
        return value
    identity = id(value)
    if identity in active:
        raise _UnownedReconstruction
    if identity in memo:
        return memo[identity]
    active.add(identity)
    try:
        if value_type in (SecretStr, SecretBytes):
            result = value_type(value.get_secret_value())
        elif value_type is dict:
            if not all(_reconstruction_key_is_safe(key) for key in value):
                raise _UnownedReconstruction
            result = {
                _copy_reconstruction(key, memo, active): _copy_reconstruction(child, memo, active)
                for key, child in value.items()
            }
        elif value_type in (list, tuple, set, frozenset):
            if value_type in (set, frozenset) and not all(
                _reconstruction_key_is_safe(child) for child in value
            ):
                raise _UnownedReconstruction
            result = value_type(_copy_reconstruction(child, memo, active) for child in value)
        elif isinstance(value, Enum):
            # Standard enum members are schema identities, not per-call objects.
            # Mutable values or custom member state cannot cross this boundary.
            if any(cls.__dict__.get("__slots__") for cls in value_type.__mro__):
                raise _UnownedReconstruction
            state = object.__getattribute__(value, "__dict__")
            if (
                state.keys() - {"_value_", "_name_", "__objclass__", "_sort_order_"}
                or not _enum_value_is_immutable(state.get("_value_"))
            ):
                raise _UnownedReconstruction
            result = value
        elif value_type in (date, datetime, time, timedelta, Decimal, UUID, PurePosixPath, PureWindowsPath, PosixPath, WindowsPath):
            if value_type in (datetime, time) and value.tzinfo is not None and type(value.tzinfo) is not timezone:
                raise _UnownedReconstruction
            result = value
        elif value_type is _LOCAL_PATH_TYPE:
            # Local paths describe locations, not open filesystem resources.
            result = UPath(str(value))
            if value.storage_options:
                raise _UnownedReconstruction
        elif isinstance(value, BaseModel):
            # Bypass constructors, validation and user-defined copy hooks.
            # Custom slots have no generic ownership contract.
            for cls in value_type.__mro__:
                if cls is BaseModel:
                    break
                if cls.__dict__.get("__slots__"):
                    raise _UnownedReconstruction
            result = object.__new__(value_type)
            for attribute in ("__dict__", "__pydantic_extra__", "__pydantic_private__", "__pydantic_fields_set__"):
                object.__setattr__(
                    result, attribute,
                    _copy_reconstruction(object.__getattribute__(value, attribute), memo, active),
                )
        else:
            raise _UnownedReconstruction
        memo[identity] = result
        return result
    finally:
        active.remove(identity)


def _snapshot_reconstruction(values: dict[str, Any]) -> Optional[dict[str, Any]]:
    try:
        return _copy_reconstruction(values, {}, set())
    except (_UnownedReconstruction, RecursionError):
        return None



def _same_reconstruction_value(left: Any, right: Any) -> bool:
    """Compare already-owned source values without user model equality hooks."""
    if left is right:
        return True
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(
            _same_reconstruction_value(value, right[key]) for key, value in left.items()
        )
    if type(left) in (list, tuple):
        return len(left) == len(right) and all(
            _same_reconstruction_value(a, b) for a, b in zip(left, right)
        )
    if isinstance(left, BaseModel):
        return all(
            _same_reconstruction_value(
                object.__getattribute__(left, attribute),
                object.__getattribute__(right, attribute),
            )
            for attribute in ("__dict__", "__pydantic_extra__", "__pydantic_private__", "__pydantic_fields_set__")
        )
    # Remaining snapshot-supported exact types have value equality; opaque
    # objects and model hash keys were rejected at the ownership boundary.
    return bool(left == right)


def _replace_reconstruction_path(tree: Any, path: tuple[str | int, ...], value: Any) -> Any:
    """Copy the changed path, replacing a field rather than deep-merging it."""
    if not path:
        return value
    segment, *rest = path
    if isinstance(segment, str):
        result = dict(tree) if isinstance(tree, dict) else {}
        result[segment] = _replace_reconstruction_path(result.get(segment), tuple(rest), value)
        return result
    items = list(tree) if type(tree) in (list, tuple) else []
    required = segment + 1 if segment >= 0 else -segment
    items.extend([None] * max(0, required - len(items)))
    items[segment] = _replace_reconstruction_path(items[segment], tuple(rest), value)
    return tuple(items) if type(tree) is tuple else items


def _patch_reconstruction(
    recipe: dict[str, Any], patch: dict[str, Any], model_type: Type[BaseSettings],
) -> Optional[dict[str, Any]]:
    """Patch accepted paths only when every logical input remains faithful."""
    from pydantic_core import PydanticUndefined
    from mountainash_settings.resolve import _validation_paths

    def input_paths(name: str) -> tuple[tuple[str | int, ...], ...]:
        field = model_type.model_fields.get(name)
        if field is None or model_type.model_config.get("validate_by_alias") is False:
            return ((name,),)
        paths = _validation_paths(name, field)
        if model_type.model_config.get("validate_by_name") or model_type.model_config.get("populate_by_name"):
            if (name,) not in paths:
                paths += ((name,),)
        return paths

    def at(tree: dict[str, Any], path: tuple[str | int, ...]) -> Any:
        return AliasPath(cast(str, path[0]), *path[1:]).search_dict_for_path(tree)

    def selected_input(tree: dict[str, Any], name: str) -> Any:
        for path in input_paths(name):
            value = at(tree, path)
            if value is not PydanticUndefined:
                return value
        return PydanticUndefined

    result = recipe
    for name, value in patch.items():
        # A lower choice can lose to an earlier file/env alias. The highest
        # choice must also survive the existing canonical-only kwargs filter.
        selected = input_paths(name)[0]
        if selected[0] not in model_type.model_fields:
            return None
        result = _replace_reconstruction_path(result, selected, value)
        if selected[0] != name:
            result.pop(name, None)

    for name in model_type.model_fields:
        actual = selected_input(result, name)
        expected = patch[name] if name in patch else selected_input(recipe, name)
        # Compare only owned source values, never resolved model fields.
        if not _same_reconstruction_value(actual, expected):
            return None
        if name not in patch and expected is PydanticUndefined:
            for path in input_paths(name):
                for index, segment in enumerate(path):
                    if isinstance(segment, int):
                        parent = path[:index]
                        if at(recipe, parent) is PydanticUndefined and at(result, parent) is not PydanticUndefined:
                            # A newly supplied sequence replaces, rather than
                            # merges with, a file/env sequence we cannot read.
                            return None
    return result


def _cache_field_input_paths(
    model_type: Type[BaseSettings], field_name: str,
) -> tuple[tuple[str | int, ...], ...]:
    """Return every input path Pydantic accepts for one logical field."""
    from mountainash_settings.resolve import _validation_paths

    field = model_type.model_fields[field_name]
    paths = _validation_paths(field_name, field)
    if model_type.model_config.get("validate_by_name") or model_type.model_config.get("populate_by_name"):
        if (field_name,) not in paths:
            paths += ((field_name,),)
    return paths


def _cache_path_value(
    inputs: dict[str, Any], path: tuple[str | int, ...],
) -> Any:

    return AliasPath(cast(str, path[0]), *path[1:]).search_dict_for_path(inputs)


def _cache_input_field_names(
    model_type: Type[BaseSettings], inputs: dict[str, Any],
) -> frozenset[str]:
    """Return logical fields represented by complete supplied input paths."""
    from pydantic_core import PydanticUndefined

    return frozenset(
        field_name
        for field_name in model_type.model_fields
        if any(
            _cache_path_value(inputs, path) is not PydanticUndefined
            for path in _cache_field_input_paths(model_type, field_name)
        )
    )




def _cache_remove_path(
    tree: dict[str, Any], path: tuple[str | int, ...],
) -> bool:
    """Remove one dictionary path without disturbing a shared alias sibling."""
    from pydantic_core import PydanticUndefined

    if path and _cache_path_value(tree, path) is PydanticUndefined:
        return True
    if not path or any(isinstance(segment, int) for segment in path):
        return False
    current: Any = tree
    parents: list[tuple[dict[str, Any], str]] = []
    for segment in path[:-1]:
        if not isinstance(current, dict) or segment not in current:
            return True
        parents.append((current, cast(str, segment)))
        current = current[segment]
    leaf = cast(str, path[-1])
    if not isinstance(current, dict) or leaf not in current:
        return True
    del current[leaf]
    while parents and not current:
        parent, segment = parents.pop()
        del parent[segment]
        current = parent
    return True


def _cache_overlay_fields(
    candidate: dict[str, Any], patch: dict[str, Any], model_type: Type[BaseSettings],
    *, logical_fields: bool = False,
) -> dict[str, Any]:
    """Replace represented logical fields while retaining shared alias siblings."""
    from pydantic_core import PydanticUndefined

    result = _snapshot_reconstruction(candidate)
    patch_copy = _snapshot_reconstruction(patch)
    if result is None or patch_copy is None:
        raise ValueError("Cached settings candidate cannot be safely owned")

    selected: dict[str, tuple[tuple[str | int, ...], Any]] = {}
    for field_name in model_type.model_fields:
        if logical_fields:
            if field_name in patch_copy:
                selected[field_name] = (_cache_field_input_paths(model_type, field_name)[0], patch_copy[field_name])
            continue
        for path in _cache_field_input_paths(model_type, field_name):
            value = _cache_path_value(patch_copy, path)
            if value is not PydanticUndefined:
                selected[field_name] = (path, value)
                break

    if not logical_fields:
        represented_roots = {cast(str, path[0]) for path, _ in selected.values()}
        for name, value in patch_copy.items():
            if name not in represented_roots:
                result[name] = value

    for field_name, (selected_path, value) in selected.items():
        field_paths = _cache_field_input_paths(model_type, field_name)
        for path in field_paths:
            if path == selected_path:
                break
            if not _cache_remove_path(result, path):
                raise ValueError("Cached settings aliases cannot be represented safely")
        result = cast(dict[str, Any], _replace_reconstruction_path(result, selected_path, value))
    for field_name in model_type.model_fields:
        paths = _cache_field_input_paths(model_type, field_name)
        actual = next((value for path in paths if (value := _cache_path_value(result, path)) is not PydanticUndefined), PydanticUndefined)
        expected = selected[field_name][1] if field_name in selected else next(
            (value for path in paths if (value := _cache_path_value(candidate, path)) is not PydanticUndefined), PydanticUndefined,
        )
        if not _same_reconstruction_value(actual, expected):
            raise ValueError("Cached settings aliases cannot preserve logical field values")
    return result


def _detach_cached_result(instance: BaseSettings) -> None:
    """Install one independently-owned graph across every Pydantic compartment."""
    original_dict = object.__getattribute__(instance, "__dict__")
    source_dict = dict(original_dict)
    framework_identity = (
        isinstance(instance, MountainAshBaseSettings)
        and source_dict.get("SETTINGS_CLASS") is type(instance)
    )
    retained_metadata = (
        {"SETTINGS_CLASS": source_dict.pop("SETTINGS_CLASS")}
        if framework_identity
        else {}
    )
    source_private = dict(object.__getattribute__(instance, "__pydantic_private__") or {})
    # The bound secret store travels by identity, never copied or reconstructed.
    retained_secret_store = source_private.pop("_settings_secret_store", None)
    memo: dict[int, Any] = {}
    active: set[int] = set()
    try:
        detached_dict = _copy_reconstruction(source_dict, memo, active)
        detached_extra = _copy_reconstruction(
            object.__getattribute__(instance, "__pydantic_extra__"), memo, active,
        )
        detached_private = _copy_reconstruction(source_private, memo, active)
        detached_fields_set = _copy_reconstruction(
            object.__getattribute__(instance, "__pydantic_fields_set__"), memo, active,
        )
    except (_UnownedReconstruction, RecursionError):
        raise ValueError("Cached settings result cannot be safely owned") from None
    detached_dict.update(retained_metadata)
    detached_private["_settings_secret_store"] = retained_secret_store
    object.__setattr__(instance, "__dict__", detached_dict)
    object.__setattr__(instance, "__pydantic_extra__", detached_extra)
    object.__setattr__(instance, "__pydantic_private__", detached_private)
    object.__setattr__(instance, "__pydantic_fields_set__", detached_fields_set)



def _apply_cached_static_defaults(
    instance: BaseSettings,
    candidate: dict[str, Any],
    resolved_defaults: dict[str, Any],
) -> None:
    """Assign capture-resolved declared defaults absent from all input paths."""
    from pydantic_core import PydanticUndefined
    from mountainash_settings.resolve import _raise_sanitized_resolution_error

    for name, resolved in resolved_defaults.items():
        if name not in type(instance).model_fields:
            continue
        if any(
            _cache_path_value(candidate, path) is not PydanticUndefined
            for path in _cache_field_input_paths(type(instance), name)
        ):
            continue
        try:
            setattr(instance, name, resolved)
        except Exception:
            _raise_sanitized_resolution_error(type(instance), [name])


class MountainAshBaseSettings(BaseSettings):
    """Base settings class with template support, multi-format config files,
    and smart caching.

    Assignments to declared fields after construction are revalidated via
    pydantic's field-validator pipeline — ``SecretStr`` wrapping, enum
    coercion, and ``AfterValidator`` transforms all run on every ``setattr``.
    This is canonical pydantic v2 behaviour; see
    ``docs/superpowers/specs/2026-04-18-setattr-bypass-fix-design.md``.
    """

    model_config = SettingsConfigDict(
            extra="ignore",
            validate_default=False,
            arbitrary_types_allowed=True,
            validate_assignment=True,

        )

    #Tracablility and repeatability
    SETTINGS_CLASS: Type =                                            Field(default=None)
    SETTINGS_CLASS_NAME: str =                                        Field(default=None)

    SETTINGS_SOURCE_ENV_FILES: Optional[Union[Any, str, List[Any|str]]] =       Field(default=None)
    SETTINGS_SOURCE_ENV_PREFIX: Optional[str] =                                 Field(default=None)
    SETTINGS_SOURCE_YAML_FILES: Optional[Union[Any, str, List[Any|str]]] =      Field(default=None)
    SETTINGS_SOURCE_TOML_FILES: Optional[Union[Any, str, List[Any|str]]] =      Field(default=None)
    SETTINGS_SOURCE_JSON_FILES: Optional[Union[Any, str, List[Any|str]]] =      Field(default=None)
    SETTINGS_SOURCE_KWARG_NAMES: tuple[str, ...] = Field(default=())
    _settings_reconstruction_kwargs: Optional[dict[str, Any]] = PrivateAttr(default=None)
    _settings_secret_store: Optional[Any] = PrivateAttr(default=None)
    SETTINGS_SOURCE_SECRETS_DIR: Optional[str] = Field(default=None)

    # MAS-SEC-005 (M6): value-free origin handoff -- field names only, never
    # values. Populated only inside _initialise_from_cache_frame; both stay
    # frozenset() on direct (non-cached) construction, since no cache frame
    # runs there. See the M6 plan's decision checkpoint (2026-09-25).
    _settings_carried_field_names: frozenset[str] = PrivateAttr(default=frozenset())
    _settings_runtime_field_names: frozenset[str] = PrivateAttr(default=frozenset())

    def __new__(cls, *args: Any, **kwargs: Any) -> "MountainAshBaseSettings":
        """Bind the frame to this outer allocation before custom init can nest."""
        instance = super().__new__(cls)
        from mountainash_settings.settings_cache._context import bind_cache_frame_instance

        bind_cache_frame_instance(instance)
        return instance

    def __setattr__(self, name: str, value: Any) -> None:
        """Record cached post-init field assignments before normal validation."""
        from mountainash_settings.settings_cache._context import current_cache_assignment_recorder

        recorder = current_cache_assignment_recorder(self)
        if recorder is None or name not in type(self).model_fields:
            super().__setattr__(name, value)
            return
        if name in recorder.suppressed_fields:
            return
        raw_value = recorder.prepare_assignment(name, value)
        super().__setattr__(name, value)
        recorder.record_validated_assignment(name, raw_value, object.__getattribute__(self, "__dict__").get(name))


    # protected_attributes: List[str] = ['BATCH_TIER', 'BATCH_VERSION']
    # reserved_kwargs = {"_env_file","_env_file_encoding", "_env_prefix"}
    def _initialise_from_cache_frame(self, frame: Any, effective_runtime: Dict[str, Any]) -> None:
        """Validate a complete pinned candidate without rebuilding settings sources."""
        parameters = frame.context.key.parameters()
        config_files = SettingsFileHandler.separate_config_files(parameters.config_files)
        candidate = frame.candidate(effective_runtime)
        caught_error: Optional[Exception] = None
        try:
            BaseModel.__init__(self, **candidate)
        except Exception as exc:
            caught_error = exc
        if caught_error is not None:
            # MAS-SEC-006 (M7): record the failure and leave the handler
            # before raising -- Python reattaches whatever exception is
            # currently being handled into a newly raised error's
            # __context__ regardless of `from None`, so the sanitizer must
            # run outside this except block, never inside it.
            sensitive_fields = frame.context.source_sensitive_field_names() | frame.runtime_sensitive_fields
            if sensitive_fields:
                from mountainash_settings.resolve import _raise_sanitized_resolution_error

                _raise_sanitized_resolution_error(type(self), sorted(sensitive_fields))
            raise caught_error
        _apply_cached_static_defaults(
            self, candidate, frame.static_defaults_for_call(),
        )
        recipe = frame.context.recipe(frame.original_runtime)
        self._settings_reconstruction_kwargs = recipe
        object.__setattr__(self, "SETTINGS_SOURCE_KWARG_NAMES", tuple(recipe))
        object.__setattr__(self, "SETTINGS_CLASS", type(self))
        object.__setattr__(self, "SETTINGS_CLASS_NAME", type(self).__name__)
        object.__setattr__(self, "SETTINGS_SOURCE_ENV_PREFIX", parameters.env_prefix)
        object.__setattr__(self, "SETTINGS_SOURCE_ENV_FILES", config_files.env_files)
        object.__setattr__(self, "SETTINGS_SOURCE_YAML_FILES", config_files.yaml_files)
        object.__setattr__(self, "SETTINGS_SOURCE_TOML_FILES", config_files.toml_files)
        object.__setattr__(self, "SETTINGS_SOURCE_JSON_FILES", config_files.json_files)
        object.__setattr__(self, "SETTINGS_SOURCE_SECRETS_DIR", parameters.secrets_dir)
        self._settings_secret_store = parameters.secret_store
        fields = type(self).model_fields
        expected = _snapshot_reconstruction({
            name: value for name, value in object.__getattribute__(self, "__dict__").items()
            if name in fields and name != "SETTINGS_CLASS"
        })
        if expected is None:
            raise ValueError("Cached post-init state cannot be safely owned")
        frame.expected_fields = expected
        frame.recording_instance = self
        # MAS-SEC-005 (M6): value-free origin handoff for Profile.post_init
        # (and any other consumer) -- field names only, populated
        # immediately before the call that consumes them.
        object.__setattr__(
            self, "_settings_carried_field_names", frozenset(frame.context._source_carry or {}),
        )
        object.__setattr__(
            self, "_settings_runtime_field_names", _cache_input_field_names(type(self), effective_runtime),
        )
        try:
            self.post_init(reinitialise=frame.reinitialise)
        finally:
            frame.recording_instance = None
        from pydantic_core import PydanticUndefined

        actual = object.__getattribute__(self, "__dict__")
        if any(
            not _same_reconstruction_value(
                expected.get(name, PydanticUndefined), actual.get(name, PydanticUndefined),
            )
            for name in fields if name != "SETTINGS_CLASS"
        ):
            raise ValueError("Cached post-init mutation has no validated assignment origin")



    def __init__(self,
                 config_files:          Optional[str|UPath|List[str|UPath]|Tuple[str|UPath]] = None,
                 settings_parameters:   Optional[SettingsParameters] = None,
                 template_settings_parameters:   Optional[SettingsParameters] = None,
                 **kwargs) -> None:

        from mountainash_settings.settings_cache._context import consume_cache_frame

        frame = consume_cache_frame(self)
        if frame is not None:
            self._initialise_from_cache_frame(frame, kwargs)
            return


        # Create a baseline settings parameters object
        local_settings_params = SettingsParameters.create(
            settings_class=self.__class__,
            config_files=config_files,
            **kwargs
        )

        if settings_parameters is not None:
            local_settings_params = SettingsParameters.merge(settings_parameters, local_settings_params)

        obj_config_files: SettingsFiles = SettingsFileHandler.separate_config_files(local_settings_params.config_files)

        # Validate config files exist
        SettingsFileHandler.validate_config_files_exist(obj_config_files.env_files)
        SettingsFileHandler.validate_config_files_exist(obj_config_files.yaml_files)
        SettingsFileHandler.validate_config_files_exist(obj_config_files.toml_files)
        SettingsFileHandler.validate_config_files_exist(obj_config_files.json_files)

        # Handle attribute kwargs. M5 (MAS-SEC-004): source/schema controls are
        # rejected value-free here, before sources open -- see
        # SettingsParameters.get_attribute_settings_kwargs().
        valid_attribute_kwargs: Dict[str, Any] = local_settings_params.get_attribute_settings_kwargs(settings_class=self.__class__)
        reconstruction_kwargs = _snapshot_reconstruction(valid_attribute_kwargs)
        reconstruction_names = tuple(valid_attribute_kwargs)
        if reconstruction_kwargs is not None:
            valid_attribute_kwargs = _copy_reconstruction(reconstruction_kwargs, {}, set())


        # Resolve prefixed references (e.g. secret:) in kwargs before pydantic validation
        from mountainash_settings.resolve import _resolve_dict_with_changed_fields
        valid_attribute_kwargs, _resolved_field_names = _resolve_dict_with_changed_fields(
            valid_attribute_kwargs, local_settings_params.secret_store,
        )

        # NOTE: All that has happened before now is prior to calling the init on Base Settings!
        # Now we initialise the values! File-source paths for this invocation
        # travel through the invocation-local _direct_source_frame (MAS-SEC-004),
        # never through self.model_config, which stays a shared class dict and
        # is never mutated by construction. The six explicit literals below are
        # MountainAsh-owned fixed defaults, not accepted per-call kwargs; keep
        # them in lockstep with settings_cache/_context.py's mirrored defaults.
        construction_error: Optional[Exception] = None
        with _direct_source_frame(
            self.__class__,
            obj_config_files.yaml_files or None,
            obj_config_files.toml_files or None,
            obj_config_files.json_files or None,
        ):
            try:
                super().__init__(   _case_sensitive=True,
                                    _nested_model_default_partial_update=False,
                                    _env_prefix=            local_settings_params.env_prefix,
                                    _env_file=              obj_config_files.env_files or None,
                                    _env_file_encoding =    'utf-8',
                                    _env_ignore_empty =     True,
                                    _env_nested_delimiter = None,
                                    _env_parse_none_str =   "None",
                                    _env_parse_enums =      True,
                                    _secrets_dir=           local_settings_params.secrets_dir,
                                    **valid_attribute_kwargs
                                )
            except Exception as exc:
                construction_error = exc
        if construction_error is not None:
            # MAS-SEC-006 (M7): record the failure and leave the handler
            # (and the _direct_source_frame block) before raising -- Python
            # reattaches whatever exception is currently being handled into
            # a newly raised error's __context__ regardless of `from None`,
            # so the sanitizer must run outside this except block, never
            # inside it. Only guard when a resolved reference could
            # actually be implicated -- an ordinary caller-literal failure
            # keeps its normal diagnostic.
            if _resolved_field_names:
                from mountainash_settings.resolve import _raise_sanitized_resolution_error

                _raise_sanitized_resolution_error(self.__class__, sorted(_resolved_field_names))
            raise construction_error


        # Meta-field bookkeeping only. super().__init__ above already applied
        # valid_attribute_kwargs under full validation — re-applying them via
        # update_settings_from_dict would overwrite validated values with raw
        # input (see 2026-04-18-setattr-bypass-fix-design.md).
        #
        # object.__setattr__ is intentional: these fields are harness
        # bookkeeping, not user config, and with validate_assignment=True on
        # model_config we want to skip revalidation on them explicitly.
        # Note: this also bypasses __pydantic_fields_set__ tracking, so these
        # meta-fields do not appear in model_fields_set and are dropped by
        # model_dump(exclude_unset=True). That matches the pre-Task-2
        # behaviour and is intentional — bookkeeping is not model state.
        self._settings_reconstruction_kwargs = reconstruction_kwargs
        object.__setattr__(self, "SETTINGS_SOURCE_KWARG_NAMES", reconstruction_names)
        object.__setattr__(self, "SETTINGS_CLASS",            local_settings_params.settings_class or MountainAshBaseSettings)
        object.__setattr__(self, "SETTINGS_CLASS_NAME",       local_settings_params.settings_class.__name__ if local_settings_params.settings_class else "MountainAshBaseSettings")
        object.__setattr__(self, "SETTINGS_SOURCE_ENV_PREFIX", local_settings_params.env_prefix)
        object.__setattr__(self, "SETTINGS_SOURCE_ENV_FILES",  obj_config_files.env_files)
        object.__setattr__(self, "SETTINGS_SOURCE_YAML_FILES", obj_config_files.yaml_files)
        object.__setattr__(self, "SETTINGS_SOURCE_TOML_FILES", obj_config_files.toml_files)
        object.__setattr__(self, "SETTINGS_SOURCE_JSON_FILES", obj_config_files.json_files)
        object.__setattr__(self, "SETTINGS_SOURCE_SECRETS_DIR", local_settings_params.secrets_dir)
        self._settings_secret_store = local_settings_params.secret_store

        # Resolve prefixed references (e.g. secret:) in fields loaded from config files
        from mountainash_settings.resolve import resolve_references_in_model_tree
        resolve_references_in_model_tree(self, local_settings_params.secret_store)

        # Initialise templated variables
        self.post_init()


    @staticmethod
    def _cache_default_sources(
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
        *,
        yaml_files: Any = _CACHE_SOURCE_UNSET,
        toml_files: Any = _CACHE_SOURCE_UNSET,
        json_files: Any = _CACHE_SOURCE_UNSET,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        """Build the shared MountainAsh source ordering for direct and cached use."""
        unprefixed_dotenv_settings = DotEnvSettingsSource(
            settings_cls,
            env_file=dotenv_settings.env_file,
            env_file_encoding=dotenv_settings.env_file_encoding,
            dotenv_filtering=dotenv_settings.dotenv_filtering,
            case_sensitive=dotenv_settings.case_sensitive,
            env_prefix="",
            env_prefix_target=dotenv_settings.env_prefix_target,
            env_nested_delimiter=dotenv_settings.env_nested_delimiter,
            env_nested_max_split=dotenv_settings.env_nested_max_split,
            env_ignore_empty=dotenv_settings.env_ignore_empty,
            env_parse_none_str=dotenv_settings.env_parse_none_str,
            env_parse_enums=dotenv_settings.env_parse_enums,
            _init_state=dotenv_settings._init_state,
        )
        yaml_kwargs = {} if yaml_files is _CACHE_SOURCE_UNSET else {"yaml_file": yaml_files}
        toml_kwargs = {} if toml_files is _CACHE_SOURCE_UNSET else {"toml_file": toml_files}
        json_kwargs = {} if json_files is _CACHE_SOURCE_UNSET else {"json_file": json_files}
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            unprefixed_dotenv_settings,
            YamlConfigSettingsSource(settings_cls, deep_merge=True, **yaml_kwargs),
            TomlConfigSettingsSource(settings_cls, deep_merge=True, **toml_kwargs),
            JsonConfigSettingsSource(settings_cls, deep_merge=True, **json_kwargs),
            file_secret_settings,
        )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        # MAS-SEC-004: use this invocation's own file-source paths when an
        # active direct-construction frame belongs to settings_cls. A cache
        # materialization sentinel (see settings_cache/_context.py) never
        # reaches this hook -- it builds sources itself, bypassing it
        # entirely -- so there is no precedence conflict to resolve here.
        # Without a matching frame (a manual/standalone hook call, or a
        # frame for a different class), fall back to static class
        # configuration, preserving direct-hook-call compatibility.
        frame = _CURRENT_DIRECT_SOURCE_FRAME.get()
        if frame is not None and frame.settings_class is settings_cls:
            return cls._cache_default_sources(
                settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
                yaml_files=frame.yaml_files, toml_files=frame.toml_files, json_files=frame.json_files,
            )
        return cls._cache_default_sources(
            settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
        )

    @classmethod
    def settings_capture_sources(
        cls, sources: Tuple[PydanticBaseSettingsSource, ...],
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        """Declare the cache-safe source order; subclasses opt in here."""
        return sources

    @classmethod
    def get_settings(
        cls,
        settings_parameters: Optional[SettingsParameters] = None,
        settings_class: Optional[Type[T]] = None,
        config_files: Optional[Union[UPath, str, List[UPath | str]]] = None,
        env_prefix: Optional[str] = None,
        *,
        reinitialise: bool = False,
        **kwargs: Any,
    ) -> Any:
        # Lazy import to avoid circular dependency
        from mountainash_settings.settings_cache import get_settings

        if settings_class is None:
            class_module = cls.__module__
            class_name = cls.__name__
            settings_class = getattr(import_module(name=class_module), class_name)


        settings_instance: Any =  get_settings(
                                    settings_parameters = settings_parameters,
                                    settings_class = settings_class,
                                    config_files = config_files,
                                    env_prefix=env_prefix,
                                    reinitialise=reinitialise,
                                    **kwargs
                            )

        if not isinstance(settings_instance, cls):
            raise TypeError(
                f"Created instance of type {type(settings_instance).__name__} "
                f"but expected {cls.__name__} when calling {cls.__name__}.get_settings()"
            )

        return settings_instance


    def __hash__(self) -> int:
        """
        Hash the settings object based on the settings namespace, class name, and source kwargs.

        """

        return hash((self.SETTINGS_CLASS_NAME,
                     tuple(self.SETTINGS_SOURCE_ENV_FILES) if self.SETTINGS_SOURCE_ENV_FILES else None,
                     tuple(self.SETTINGS_SOURCE_ENV_PREFIX) if self.SETTINGS_SOURCE_ENV_PREFIX else None,
                     tuple(self.SETTINGS_SOURCE_YAML_FILES) if self.SETTINGS_SOURCE_YAML_FILES else None,
                     tuple(self.SETTINGS_SOURCE_TOML_FILES) if self.SETTINGS_SOURCE_TOML_FILES else None,
                     tuple(self.SETTINGS_SOURCE_JSON_FILES) if self.SETTINGS_SOURCE_JSON_FILES else None,
                     ))


    def _build_template_mapping(self, template_str: str) -> Dict[str, Any]:
        """Build field mapping for template formatting."""
        mapping = {}
        for _, field_name, _, _ in Formatter().parse(template_str):
            if field_name:
                if hasattr(self, field_name):
                    mapping[field_name] = getattr(self, field_name)
                else:
                    raise AttributeError(f"The object does not have an attribute named '{field_name}'")
        return mapping

    def init_setting_from_template(self, template_str:str, current_value: Optional[str] = None, reinitialise: Optional[bool] = False):

        """Initializes a setting value from a template string,
        replacing placeholders with  values from the settings object.

        Args:
            template_str: The template string to parse and format.
            current_value: The current value in the settings object if already set.

        Returns:
            (str) The formatted string from the template.

        Examples:

            template = "my_{BATCH_ID}_file.csv"
            settings.init_setting_from_template(template)
            # Returns: "my_20230101_file.csv" if BATCH_ID is 20230101
        """
        if current_value is not None and reinitialise is False:
            return current_value

        mapping = self._build_template_mapping(template_str)

        return template_str.format(**mapping)


    def format_template_from_settings(self, template_str:str) -> str:

        """Formats a template string with values from the settings object.

        Args:
            template_str: The template string to format.

        Returns:
            The formatted string from the template.

        Examples:

            template = "my_{BATCH_ID}_file.csv"
            settings.format_template_from_settings(template)
            # Returns: "my_20230101_file.csv" if BATCH_ID is 20230101
        """
        mapping = self._build_template_mapping(template_str)

        return template_str.format(**mapping)

    def update_settings_from_dict(self, settings_dict: Optional[dict[str, Any]]) -> None:
        """Updates the settings object with values from a dictionary.

        Args:
            settings_dict: The dictionary of settings to update.
        """

        settings_dict = SettingsKwargsHandler.format_kwargs_dict(p_kwargs=settings_dict)

        if settings_dict is None:
            return None
        self._apply_settings_inputs(settings_dict)

    def _apply_settings_inputs(self, settings_dict: dict[str, Any], backend: Any = None) -> None:
        """Stage source form before optional runtime resolution and assignment."""

        patch = _snapshot_reconstruction(settings_dict)
        recipe = self._settings_reconstruction_kwargs
        merged = _snapshot_reconstruction(recipe) if recipe is not None else None
        if merged is not None and patch is not None:
            merged = _patch_reconstruction(merged, patch, type(self))
        else:
            merged = None
        if backend is not None:
            from mountainash_settings.resolve import resolve_references_in_dict
            settings_dict = resolve_references_in_dict(settings_dict, backend)
        for key, value in settings_dict.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                raise AttributeError(f"The object does not have an attribute named '{key}'")

        self._settings_reconstruction_kwargs = merged
        names = tuple(merged) if merged is not None else tuple(dict.fromkeys(
            (*self.SETTINGS_SOURCE_KWARG_NAMES, *settings_dict)
        ))
        object.__setattr__(self, "SETTINGS_SOURCE_KWARG_NAMES", names)

    def post_init(self,
                template_settings_parameters: Optional[SettingsParameters] = None,
                reinitialise: Optional[bool] = False
    ) -> None:
        """
        Hook for post-initialization processing.

        Called after all settings have been loaded and processed.
        Override in subclasses to add custom initialization logic.

        Args:
            reinitialise: Whether this is a re-initialization call
        """
        pass  # Intentionally empty - hook for subclasses to implement


    def extract_settings_parameters(self) -> SettingsParameters:
        """
        Returns a SettingsParameters object reconstructed from a BaseSettings object.

        Args:
            objSettings (BaseSettings): The settings object.

        Returns:
            SettingsParameters: The settings parameters object
        """

        # combine the config files into a single list
        config_files : List = []
        if self.SETTINGS_SOURCE_ENV_FILES:
            config_files += self.SETTINGS_SOURCE_ENV_FILES
        if self.SETTINGS_SOURCE_YAML_FILES:
            config_files += self.SETTINGS_SOURCE_YAML_FILES
        if self.SETTINGS_SOURCE_TOML_FILES:
            config_files += self.SETTINGS_SOURCE_TOML_FILES
        if self.SETTINGS_SOURCE_JSON_FILES:
            config_files += self.SETTINGS_SOURCE_JSON_FILES


        existing_config_files =     SettingsFileHandler.format_config_file_list(config_files=config_files)
        recipe = self._settings_reconstruction_kwargs
        existing_kwargs = _snapshot_reconstruction(recipe) if recipe is not None else None
        if existing_kwargs is None:
            raise TypeError(
                f"Cannot extract settings parameters for {type(self).__name__}: "
                "source inputs have no faithful independently owned reconstruction"
            )
        existing_settings_class =   self.SETTINGS_CLASS or None
        existing_env_prefix =       self.SETTINGS_SOURCE_ENV_PREFIX or None

        params: SettingsParameters = SettingsParameters.create(
            settings_class=     existing_settings_class,
            config_files=       existing_config_files,
            kwargs=             existing_kwargs,
            env_prefix=         existing_env_prefix,
            secrets_dir=        self.SETTINGS_SOURCE_SECRETS_DIR,
            secret_store=       self._settings_secret_store)

        return params

    def persist_key(self) -> str:
        """Derive a backend key from this instance's stored meta-fields.

        Format: env_prefix (stripped of trailing underscore, lowercased) + "." +
        settings class name (lowercased). If no env_prefix, just the class name.
        """
        class_name = (self.SETTINGS_CLASS_NAME or type(self).__name__).lower()
        prefix = self.SETTINGS_SOURCE_ENV_PREFIX
        if prefix:
            prefix = prefix.rstrip("_").lower()
            return f"{prefix}.{class_name}"
        return class_name

    def persist(self, data: Dict[str, Any], *, key: Optional[str] = None) -> None:
        """Replace one local record through the selected writer, then update fields.

        Args:
            data: Dict of field names to values to persist.
            key: Backend key. If None, derived via persist_key().

        Raises:
            SecretCapabilityError: No store is selected, or it is not a SecretWriter.
            ValueError: ``data`` is not a strict JSON-native record.
        """
        from mountainash_settings.secrets.backend import SecretWriter
        from mountainash_settings.secrets.errors import SecretCapabilityError, _raise_clean
        from mountainash_settings.secrets.records import _own_record

        store = self._settings_secret_store
        if store is None or not isinstance(store, SecretWriter):
            _raise_clean(SecretCapabilityError("Selected secret store cannot persist"))
        if key is None:
            key = self.persist_key()
        record = _own_record(data)
        update = _own_record(data)
        store.set(key, record)
        self.update_settings_from_dict(update)

    # def __getattribute__(self, name):
    #     """
    #     Custom attribute access that handles SecretStr types by automatically extracting their values.

    #     This allows transparent access to secret values through normal property access.
    #     """
    #     # Get the attribute normally first
    #     value = super().__getattribute__(name)

    #     # If it's a SecretStr, return its value instead
    #     if hasattr(value, 'get_secret_value') and callable(getattr(value, 'get_secret_value')):
    #         return value.get_secret_value()

    #     # Otherwise return the original value
    #     return value
