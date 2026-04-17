from typing import Optional, Any, Type, Dict
from importlib import import_module


from ..settings_parameters import SettingsParameters, SettingsKwargsHandler
from ..settings import MountainAshBaseSettings

class SettingsManager:
    """
    A manager class for handling multiple instances of application settings.

    Maintains a cache of settings objects keyed by SettingsParameters.
    When runtime override kwargs are present, returns a copy with overrides
    applied -- the cached instance is never mutated.
    """

    def __init__(self) -> None:
        self.settings_object_cache: Dict[Any, MountainAshBaseSettings] = {}


    def get_settings_object(self, settings_parameters: SettingsParameters) -> MountainAshBaseSettings:
        """
        Gets the configuration object for a given set of parameters.

        If the parameters contain runtime override kwargs, returns a copy
        with overrides applied. The cached instance is never mutated.

        Args:
            settings_parameters: The parameters for the configuration.
        Returns:
            MountainAshBaseSettings: The configuration object for the given parameters.
        Raises:
            ValueError: If the configuration object is not a MountainAshBaseSettings object.
        """

        obj_settings: Optional[MountainAshBaseSettings] = self.settings_object_cache.get(settings_parameters, None)

        if not isinstance(obj_settings, MountainAshBaseSettings):
            raise ValueError(
                f"Configuration for '{settings_parameters}' found, but is not a "
                f"MountainAshBaseSettings object. Received a {type(obj_settings)}"
            )

        override_kwargs = settings_parameters.get_attribute_settings_kwargs()
        if override_kwargs:
            obj_settings = obj_settings.model_copy()
            obj_settings.update_settings_from_dict(settings_dict=override_kwargs)

        return obj_settings

    def is_initialised(self, settings_parameters: SettingsParameters) -> bool:
        """
        Checks if the settings parameters are already initialised in the cache.

        Args:
            settings_parameters: The parameters for the configuration.
        Returns:
            bool: True if already initialised, False otherwise.
        """
        return settings_parameters in self.settings_object_cache


    def get_or_create_settings(self,
                    settings_parameters: SettingsParameters) -> MountainAshBaseSettings:
        """
        Gets existing or creates new settings for a given set of parameters.

        Args:
            settings_parameters: The settings parameters for the configuration.
        Returns:
            MountainAshBaseSettings: The settings object.
        Raises:
            ValueError: If settings_class is not provided.
        """

        if self.is_initialised(settings_parameters=settings_parameters):
            return self.get_settings_object(settings_parameters=settings_parameters)

        else:
            if not settings_parameters.settings_class:
                raise ValueError("settings_parameters.settings_class cannot be empty.")

            class_module = settings_parameters.settings_class.__module__
            class_name = settings_parameters.settings_class.__name__
            settings_class_ref: Type[MountainAshBaseSettings] = getattr(import_module(name=class_module), class_name)

            if issubclass(settings_class_ref, MountainAshBaseSettings):
                obj_settings = settings_class_ref(settings_parameters=settings_parameters)
            else:
                settings_kwargs: Dict[str, Any]|None = SettingsKwargsHandler.format_kwargs_dict(p_kwargs=settings_parameters.kwargs)
                if settings_kwargs:
                    obj_settings = settings_class_ref(**settings_kwargs)
                else:
                    obj_settings = settings_class_ref()

        self.settings_object_cache[settings_parameters] = obj_settings
        return obj_settings
