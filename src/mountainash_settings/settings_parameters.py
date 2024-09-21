
from typing import Optional, Union, Any, Tuple, Type, List, Dict
from dataclasses import dataclass
from mountainash_settings.base_settings import MountainAshBaseSettings
from upath import UPath

@dataclass(frozen=True)
class SettingsParameters():

    """
    SettingsParameters is a dataclass that holds the parameters needed to create a settings object.
    
    Parameters:
        namespace:      The namespace of the settings object. This is used to group settings together, and make the settings findable.
        config_files:   The configuration files that the settings object will use to load settings.
        kwargs:         Additional keyword arguments that will be passed to the settings object.
        settings_class: The class/type that will be used to create the settings object.

    """
    namespace:      Optional[str] = "DEFAULT"
    config_files:   Optional[Union[Any, str, Tuple[Any|str]]] = None
    kwargs:         Optional[Tuple[str,Any]] = None
    settings_class: Optional[Type[MountainAshBaseSettings]] = MountainAshBaseSettings
    env_prefix:     Optional[str] = None
    secrets_dir:    Optional[str] = None    


    def __hash__(self):
        return hash((self.namespace, self.config_files, self.kwargs, self.settings_class, self.env_prefix, self.secrets_dir))

    @classmethod
    def create(cls, 
               namespace: Optional[str] = None,
               config_files: Optional[Union[UPath, str, List[Union[UPath, str]]]] = None,
               kwargs: Optional[Dict[str, Any]] = None,
               settings_class: Type[MountainAshBaseSettings] = MountainAshBaseSettings,
               env_prefix: Optional[str] = None,
               secrets_dir: Optional[str] = None) -> 'SettingsParameters':
        
        
        resolved_namespace = cls._resolve_namespace(namespace)
        resolved_config_files = cls._format_config_files(config_files)
        resolved_kwargs = cls._format_kwargs(kwargs)

        return cls(
            namespace=resolved_namespace,
            config_files=resolved_config_files,
            kwargs=resolved_kwargs,
            settings_class=settings_class,
            env_prefix=env_prefix,
            secrets_dir=secrets_dir
        )

    @staticmethod
    def _resolve_namespace(namespace: Optional[str]) -> str:
        return namespace or "DEFAULT"

    @staticmethod
    def _format_config_files(config_files: Optional[Union[UPath, str, List[Union[UPath, str]]]]) -> Optional[Tuple[Union[UPath, str], ...]]:
        if config_files is None:
            return None
        if isinstance(config_files, (UPath, str)):
            return (config_files,)
        return tuple(sorted(set(config_files)))

    @staticmethod
    def _format_kwargs(kwargs: Optional[Dict[str, Any]]) -> Optional[Tuple[Tuple[str, Any], ...]]:
        if kwargs is None:
            return None
        return tuple(sorted(kwargs.items()))

    def resolve_with(self, other: 'SettingsParameters') -> 'SettingsParameters':
        new_config_files = self._merge_config_files(self.config_files, other.config_files)
        new_kwargs = self._merge_kwargs(self.kwargs, other.kwargs)

        return SettingsParameters(
            namespace=other.namespace or self.namespace,
            config_files=new_config_files,
            kwargs=new_kwargs,
            settings_class=other.settings_class or self.settings_class,
            env_prefix=other.env_prefix or self.env_prefix,
            secrets_dir=other.secrets_dir or self.secrets_dir
        )

    @staticmethod
    def _merge_config_files(config_files1: Optional[Tuple[Union[UPath, str], ...]],
                            config_files2: Optional[Tuple[Union[UPath, str], ...]]) -> Optional[Tuple[Union[UPath, str], ...]]:
        if config_files1 is None and config_files2 is None:
            return None
        merged = set(config_files1 or ()) | set(config_files2 or ())
        return tuple(sorted(merged))

    @staticmethod
    def _merge_kwargs(kwargs1: Optional[Tuple[Tuple[str, Any], ...]],
                      kwargs2: Optional[Tuple[Tuple[str, Any], ...]]) -> Optional[Tuple[Tuple[str, Any], ...]]:
        if kwargs1 is None and kwargs2 is None:
            return None
        merged = dict(kwargs1 or ()) | dict(kwargs2 or ())
        return tuple(sorted(merged.items()))

    def to_dict(self) -> Dict[str, Any]:
        return {
            'namespace': self.namespace,
            'config_files': list(self.config_files) if self.config_files else None,
            'kwargs': dict(self.kwargs) if self.kwargs else None,
            'settings_class': self.settings_class,
            'env_prefix': self.env_prefix,
            'secrets_dir': self.secrets_dir
        }
