
from typing import Optional, Union, Any, Tuple, Type
from dataclasses import dataclass
from mountainash_settings.base_settings import MountainAshBaseSettings

@dataclass(frozen=True)
class SettingsParameters():

    namespace:      Optional[str]
    config_files:   Optional[Union[Any, str, Tuple[Any|str]]]
    kwargs:         Optional[Tuple[str,Any]]
    settings_class: Optional[Type[MountainAshBaseSettings]]

    #Get a hashcode for the object
    def __hash__(self):
        return hash((self.namespace, self.config_files, self.kwargs, self.settings_class))
