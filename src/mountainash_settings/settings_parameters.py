
from typing import Optional, Union, Any, Tuple, Type
from dataclasses import dataclass
from mountainash_settings.base_settings import MountainAshBaseSettings

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
    
    
    namespace:      Optional[str]
    config_files:   Optional[Union[Any, str, Tuple[Any|str]]]
    kwargs:         Optional[Tuple[str,Any]]
    settings_class: Optional[Type[MountainAshBaseSettings]]

    #Get a hashcode for the object
    def __hash__(self):
        """
        Calculate the hashcode for the object. This is used for caching purposes.
        """
        return hash((self.namespace, self.config_files, self.kwargs, self.settings_class))
