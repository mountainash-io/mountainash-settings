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
        namespace:      The namespace of the settings object. Used to group settings together.
        config_files:   The configuration files that the settings object will use to load settings.
        settings_class: The class/type that will be used to create the settings object.
        env_prefix:     Environment variable prefix for this settings instance.

    Runtime Parameters (don't affect cache identity):
        kwargs:         Additional keyword arguments for runtime overrides.
        secrets_dir:    Directory for secrets storage (runtime configuration).

    Caching Strategy:
        Two SettingsParameters with identical structural parameters but different
        runtime parameters will hash to the same value, allowing efficient reuse
        of cached settings objects with runtime modifications applied as needed.

    Example:
        # These will use the same cached settings object:
        params1 = SettingsParameters(namespace="app", config_files=["config.yaml"],
                                   kwargs={"debug": True})
        params2 = SettingsParameters(namespace="app", config_files=["config.yaml"],
                                   kwargs={"log_level": "INFO"})
    """
    namespace:      Optional[str] = None
    config_files:   Optional[List[str|UPath]|Tuple[str|UPath]] = None
    settings_class: Optional[Type[BaseSettings]] = None
    env_prefix:     Optional[str] = None
    secrets_dir:    Optional[str] = None
    kwargs:         Optional[Dict[str,Any]] = None

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
        - namespace: Settings grouping identifier
        - config_files: Source configuration files
        - settings_class: Type of settings object
        - env_prefix: Environment variable prefix

        Deliberately EXCLUDES runtime parameters (kwargs, secrets_dir) to enable
        cache reuse when only dynamic overrides differ.

        This allows efficient retrieval of cached settings objects when the core
        configuration is identical but runtime kwargs vary.

        Example:
            These two parameter sets will have the same hash (same cached object):

            params1 = SettingsParameters(namespace="app", config_files=["config.yaml"],
                                       settings_class=AppSettings, kwargs={"debug": True})

            params2 = SettingsParameters(namespace="app", config_files=["config.yaml"],
                                       settings_class=AppSettings, kwargs={"log_level": "INFO"})

        Returns:
            int: Hash value based on structural parameters only
        """
        hashable_config_files = SettingsFileHandler.format_config_file_tuple(self.config_files)

        hashable_attrs = tuple([
            self.namespace,
            hashable_config_files,
            self.settings_class,
            self.env_prefix,
            # Deliberately exclude: self.kwargs, self.secrets_dir
        ])

        return hash(hashable_attrs)

    def __eq__(self, other):
        """
        Equality based on the same structural parameters used in __hash__.

        Two SettingsParameters are equal if their core configuration identity
        matches, regardless of runtime parameter differences.

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
            self.namespace == other.namespace and
            self_hashable_config_files == other_hashable_config_files and
            self.settings_class == other.settings_class and
            self.env_prefix == other.env_prefix
            # Deliberately exclude: kwargs, secrets_dir comparison
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
               namespace: Optional[str] = None,
               config_files: Optional[str|UPath|List[str|UPath]|Tuple[str|UPath]] = None,
               settings_class: Optional[Type[BaseSettings]] = None,
               env_prefix: Optional[str] = None,
               secrets_dir: Optional[str] = None,
               **kwargs: Any
               ) -> 'SettingsParameters':


        #Combine the parameters into a single object
        # resolved_namespace =     cls._init_namespace(namespace)
        resolved_config_files =  SettingsFileHandler.format_config_file_tuple(config_files)
        # merged_kwargs =         SettingsKwargsHandler.merge_kwargs(kw_params, kwargs) if kwargs else kw_params
        resolved_kwargs =        SettingsKwargsHandler.format_kwargs_dict(kwargs) if kwargs else None

        return cls(
            namespace=namespace,
            config_files=resolved_config_files,
            settings_class=settings_class,
            env_prefix=env_prefix,
            secrets_dir=secrets_dir,
            kwargs=resolved_kwargs
        )



    @staticmethod
    def _init_namespace(namespace: Optional[str]) -> str:
        return namespace or "DEFAULT"


    #Export / retrieve values
    def to_dict(self) -> Dict[str, Any]:
        return {
            'namespace': self.namespace,
            'config_files': list(self.config_files) if self.config_files else None,
            'kwargs': self.get_all_kwargs() if self.kwargs else None,
            'settings_class': self.settings_class,
            'env_prefix': self.env_prefix,
            'secrets_dir': self.secrets_dir
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
