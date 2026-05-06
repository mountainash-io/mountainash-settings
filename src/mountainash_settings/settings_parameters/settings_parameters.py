from __future__ import annotations

from typing import Optional, Any, Tuple, Type, List, Dict, TYPE_CHECKING
from dataclasses import dataclass

from pydantic_settings import BaseSettings
from upath import UPath

if TYPE_CHECKING:
    from mountainash_settings.settings.base_settings import MountainAshBaseSettings

from .filehandler import SettingsFileHandler
from .kwargshandler import SettingsKwargsHandler

@dataclass(frozen=True)
class SettingsParameters():

    """
    SettingsParameters is a dataclass that holds the parameters needed to create a settings object.

    This class implements an efficient caching strategy by separating 'structural' parameters
    that define the core configuration identity from 'runtime' parameters that provide
    dynamic overrides. The custom __hash__ and __eq__ methods only consider structural
    parameters, enabling cache reuse when only runtime parameters differ.

    Structural Parameters (affect cache identity):
        config_files:   The configuration files that the settings object will use to load settings.
        settings_class: The class/type that will be used to create the settings object.
        env_prefix:     Environment variable prefix for this settings instance.
        secrets_dir:    Directory for secrets storage (pydantic-settings reads from it).

    Runtime Parameters (don't affect cache identity):
        kwargs:         Additional keyword arguments for runtime overrides.

    Caching Strategy:
        Two SettingsParameters with identical structural parameters but different
        runtime parameters will hash to the same value, allowing efficient reuse
        of cached settings objects with runtime modifications applied as needed.

    Example:
        # These will use the same cached settings object:
        params1 = SettingsParameters(config_files=["config.yaml"],
                                   kwargs={"debug": True})
        params2 = SettingsParameters(config_files=["config.yaml"],
                                   kwargs={"log_level": "INFO"})
    """
    config_files:   Optional[List[str|UPath]|Tuple[str|UPath]] = None
    settings_class: Optional[Type[BaseSettings]] = None
    env_prefix:     Optional[str] = None
    secrets_dir:    Optional[str] = None
    kwargs:         Optional[Dict[str,Any]] = None
    secrets_provider: Optional[str] = None

    # _reserved_mountainash_kwargs = ["_dummy"]


    _reserved_pydantic_modelconfig_kwargs = [
                                 "extra",
                                 "arbitrary_types_allowed",
                                 "validate_default"
    ]


    _reserved_pydantic_kwargs = ["_case_sensitive",
                                 "_nested_model_default_partial_update",
                                 "_env_prefix",
                                 "_env_file",
                                 "_env_file_encoding",
                                 "_env_ignore_empty",
                                 "_env_nested_delimiter",
                                 "_env_parse_none_str",
                                 "_env_parse_enums",
                                 "_cli_prog_name",
                                 "_cli_parse_args",
                                 "_cli_settings_source",
                                 "_cli_parse_none_str",
                                 "_cli_hide_none_type",
                                 "_cli_avoid_json",
                                 "_cli_enforce_required",
                                 "_cli_use_class_docs_for_groups",
                                 "_cli_exit_on_error",
                                 "_cli_prefix",
                                 "_cli_flag_prefix_char",
                                 "_cli_implicit_flags",
                                 "_cli_ignore_unknown_args",
                                 "_secrets_dir",
                                 ]



    def __hash__(self):
        """
        Custom hash implementation for efficient settings caching strategy.

        Only includes 'structural' parameters that define the core configuration identity:
        - config_files: Source configuration files
        - settings_class: Type of settings object
        - env_prefix: Environment variable prefix
        - secrets_dir: Directory for pydantic-settings secrets files

        Deliberately EXCLUDES runtime parameters (kwargs) to enable
        cache reuse when only dynamic overrides differ.

        This allows efficient retrieval of cached settings objects when the core
        configuration is identical but runtime kwargs vary.

        Example:
            These two parameter sets will have the same hash (same cached object):

            params1 = SettingsParameters(config_files=["config.yaml"],
                                       settings_class=AppSettings, kwargs={"debug": True})

            params2 = SettingsParameters(config_files=["config.yaml"],
                                       settings_class=AppSettings, kwargs={"log_level": "INFO"})

        Returns:
            int: Hash value based on structural parameters only
        """
        hashable_config_files = SettingsFileHandler.format_config_file_tuple(self.config_files)

        hashable_attrs = tuple([
            hashable_config_files,
            self.settings_class,
            self.env_prefix,
            self.secrets_dir,
            self.secrets_provider,
            # Deliberately exclude: self.kwargs
        ])

        return hash(hashable_attrs)

    def __eq__(self, other):
        """
        Equality based on the same structural parameters used in __hash__.

        Two SettingsParameters are equal if their core configuration identity
        matches, regardless of runtime parameter differences (kwargs).

        This supports the caching strategy where settings objects with the same
        structural configuration can be reused even when runtime overrides differ.

        Args:
            other: Object to compare with

        Returns:
            bool: True if structural parameters match, False otherwise
        """
        if not isinstance(other, SettingsParameters):
            return False

        self_hashable_config_files = SettingsFileHandler.format_config_file_tuple(self.config_files)
        other_hashable_config_files = SettingsFileHandler.format_config_file_tuple(other.config_files)

        return (
            self_hashable_config_files == other_hashable_config_files and
            self.settings_class == other.settings_class and
            self.env_prefix == other.env_prefix and
            self.secrets_dir == other.secrets_dir and
            self.secrets_provider == other.secrets_provider
            # Deliberately exclude: kwargs comparison
        )


    def get_settings(self, **kwargs) -> MountainAshBaseSettings:
        # Lazy import to avoid circular dependency
        from ..settings_cache import get_settings

        if self.settings_class is None:
            raise ValueError("Settings class is required to get settings.")

        return get_settings(settings_parameters=self, **kwargs)


    # Creation methods
    @classmethod
    def create(cls,
               config_files: Optional[str|UPath|List[str|UPath]|Tuple[str|UPath]] = None,
               settings_class: Optional[Type[BaseSettings]] = None,
               env_prefix: Optional[str] = None,
               secrets_dir: Optional[str] = None,
               secrets_provider: Optional[str] = None,
               **kwargs: Any
               ) -> 'SettingsParameters':


        #Combine the parameters into a single object
        resolved_config_files =  SettingsFileHandler.format_config_file_tuple(config_files)
        resolved_kwargs =        SettingsKwargsHandler.format_kwargs_dict(kwargs) if kwargs else None

        return cls(
            config_files=resolved_config_files,
            settings_class=settings_class,
            env_prefix=env_prefix,
            secrets_dir=secrets_dir,
            secrets_provider=secrets_provider,
            kwargs=resolved_kwargs
        )



    @classmethod
    def merge(cls,
              base: 'SettingsParameters',
              other: Optional['SettingsParameters'] = None,
              prioritise_base: bool = False
              ) -> 'SettingsParameters':
        """
        Merge two SettingsParameters objects.

        Per-field strategies:
        - config_files: combined and deduplicated
        - settings_class: must match if both provided (raises ValueError)
        - scalars (env_prefix, secrets_dir): last wins (or first if prioritise_base)
        - kwargs: merged dict, second takes precedence (or first if prioritise_base)

        Args:
            base: The base parameters.
            other: Parameters to merge in. If None, returns base.
            prioritise_base: If True, base values win over other values.

        Returns:
            A new SettingsParameters with merged values.

        Raises:
            ValueError: If base is None or settings_class values conflict.
        """
        if base is None:
            raise ValueError("Base SettingsParameters cannot be None")
        if other is None:
            return base

        # Config files: combine and deduplicate
        if base.config_files is None and other.config_files is None:
            merged_config_files = None
        elif prioritise_base:
            merged_config_files = base.config_files or other.config_files
        else:
            merged = set(base.config_files or ()) | set(other.config_files or ())
            merged_config_files = tuple(sorted(str(p) for p in merged)) if merged else None

        # Settings class: validate compatibility
        if base.settings_class is not None and other.settings_class is not None:
            if base.settings_class != other.settings_class:
                raise ValueError(
                    f"Settings class must match for merging. "
                    f"base: {base.settings_class} != other: {other.settings_class}"
                )
        if prioritise_base:
            merged_class = base.settings_class or other.settings_class
        else:
            merged_class = other.settings_class or base.settings_class

        # Scalars: simple priority
        if prioritise_base:
            merged_env_prefix = base.env_prefix or other.env_prefix
            merged_secrets_dir = base.secrets_dir or other.secrets_dir
        else:
            merged_env_prefix = other.env_prefix or base.env_prefix
            merged_secrets_dir = other.secrets_dir or base.secrets_dir

        # Secrets provider: simple priority (same as scalars)
        if prioritise_base:
            merged_secrets_provider = base.secrets_provider or other.secrets_provider
        else:
            merged_secrets_provider = other.secrets_provider or base.secrets_provider

        # Kwargs: merge dicts
        if base.kwargs is None and other.kwargs is None:
            merged_kwargs = None
        elif prioritise_base:
            merged_kwargs = base.kwargs or other.kwargs
        else:
            merged_kwargs = dict(base.kwargs or {}) | dict(other.kwargs or {})
            merged_kwargs = merged_kwargs if merged_kwargs else None

        return cls.create(
            settings_class=merged_class,
            config_files=merged_config_files,
            env_prefix=merged_env_prefix,
            secrets_dir=merged_secrets_dir,
            secrets_provider=merged_secrets_provider,
            **(merged_kwargs or {})
        )


    #Export / retrieve values
    def to_dict(self) -> Dict[str, Any]:
        return {
            'config_files': list(self.config_files) if self.config_files else None,
            'kwargs': self.get_all_kwargs() if self.kwargs else None,
            'settings_class': self.settings_class,
            'env_prefix': self.env_prefix,
            'secrets_dir': self.secrets_dir,
            'secrets_provider': self.secrets_provider,
        }


    def _get_settings_kwarg_names(self,
                             settings_class: Optional[Type[BaseSettings]] = None
                             ) -> set[str]:

        if settings_class is None:
            settings_class = self.settings_class
        if settings_class is None:
            return set()

        #This relies on the _dummay parameter on MountainAshBaseSettings. If I actuallly use that type (rather than pydantic_settings.BaseSettings) I will get a circular dependency.
        # settings_class_mod: Type[BaseSettings] = getattr(import_module(name=settings_class.__module__), settings_class.__name__)
        # obj_dummy_settings: BaseSettings = settings_class_mod(_dummy=True)
        # settings_kwarg_names = set(obj_dummy_settings.model_fields)
        settings_kwarg_names = set(settings_class.model_fields.keys())


        return settings_kwarg_names

    def _get_valid_kwarg_names(self,
                          settings_class:    Optional[Type[BaseSettings]] = None
                          ) -> set[str]:

        if settings_class is None:
            settings_class = self.settings_class
        if settings_class is None:
            return set()

        settings_kwarg_names = self._get_settings_kwarg_names(settings_class)
        valid_kwarg_names = settings_kwarg_names.union(self._reserved_pydantic_kwargs)

        return valid_kwarg_names


    def get_attribute_settings_kwargs(self,
                                        settings_class: Optional[Type[BaseSettings]] = None
                                        ) -> Dict[str, Any]:

        valid_kwarg_names = self._get_valid_kwarg_names(settings_class=settings_class)

        return {k: v for k, v in self.kwargs.items() if k in valid_kwarg_names} if self.kwargs else {}


    def get_pydantic_settings_kwargs(self) -> Dict[str, Any]:

        return {k: v for k, v in self.kwargs.items() if k in self._reserved_pydantic_kwargs} if self.kwargs else {}


    def get_pydantic_modelconfig_kwargs(self) -> Dict[str, Any]:

        return {k: v for k, v in self.kwargs.items() if k in self._reserved_pydantic_modelconfig_kwargs} if self.kwargs else {}


    def get_all_kwargs(self) -> Dict[str, Any]:

        return {k: v for k, v in self.kwargs.items()} if self.kwargs else {}

    def apply_runtime_overrides(self, cached_settings: BaseSettings) -> BaseSettings:
        """
        Apply runtime kwargs to a cached settings object without affecting cache identity.

        This method supports the caching strategy by allowing runtime parameter
        modifications to be applied to cached settings objects. The cached object's
        identity remains unchanged, but a modified copy is returned when runtime
        overrides are present.

        Args:
            cached_settings: The cached BaseSettings object to apply overrides to

        Returns:
            BaseSettings: Original object if no runtime kwargs, or modified copy with overrides

        Example:
            cached = get_cached_settings(params.structural_key())
            final_settings = params.apply_runtime_overrides(cached)
        """
        if self.kwargs:
            # Create a copy and apply runtime overrides
            settings_copy = cached_settings.model_copy()
            override_kwargs = self.get_attribute_settings_kwargs()
            if override_kwargs:
                if self.secrets_provider:
                    from ..secrets.registry import get_secrets_resolver
                    from ..resolve import resolve_references_in_dict
                    resolver = get_secrets_resolver(self.secrets_provider)
                    override_kwargs = resolve_references_in_dict(override_kwargs, resolver)
                settings_copy.update_settings_from_dict(settings_dict=override_kwargs)
            return settings_copy
        return cached_settings




    #Export a .env file from the settings parameters and class
    # def export_env_file(self,
    #                     env_file: UPath,
    #                     encoding: Optional[str] = "utf-8") -> None:

    #     valid_kwarg_names = self._get_settings_kwargs(self.settings_class)

    #     with env_file.open(mode="w", encoding=encoding) as f:
    #         for k, v in self.kwargs:
    #             if k in valid_kwarg_names:
    #                 f.write(f"{k}={v}\n")
