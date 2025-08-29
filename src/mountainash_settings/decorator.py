from typing import Optional, Union, List, Type, Callable
from upath import UPath

from pydantic_settings import BaseSettings

from .settings_parameters import SettingsParameters
from .settings_cache.settings_functions import get_settings as get_settings_func


def mountainash_settings(
    cls_or_cache: Optional[Union[Type[BaseSettings], bool]] = None,
    *,
    cache: bool = True,
    templates: bool = True, 
    multi_format: bool = True,
    namespace: Optional[str] = None
) -> Union[Type[BaseSettings], Callable[[Type[BaseSettings]], Type[BaseSettings]]]:
    """
    Decorator that enhances Pydantic BaseSettings classes with mountainash-settings functionality.
    
    This decorator makes Pydantic classes work seamlessly with the existing SettingsParameters
    infrastructure while preserving the familiar Pydantic BaseSettings interface.
    
    Can be used with or without parentheses:
        @mountainash_settings
        class Settings(BaseSettings): ...
        
        @mountainash_settings()
        class Settings(BaseSettings): ...
        
        @mountainash_settings(cache=False)
        class Settings(BaseSettings): ...
    
    Args:
        cls_or_cache: Either the class being decorated (when used without parentheses) or
                     the cache parameter value (when used with parentheses)
        cache: Enable smart caching via SettingsManager (default: True)
        templates: Enable template resolution for string fields (default: True)
        multi_format: Enable multi-format configuration file support (default: True)
        namespace: Default namespace for settings (default: None)
        
    Returns:
        Either the enhanced class (when used without parentheses) or decorator function
        
    Example:
        @mountainash_settings(cache=True, templates=True, multi_format=True)
        class AppSettings(BaseSettings):
            debug: bool = Field(default=False)
            log_path: str = Field(default="logs/{RUNDATE}/app.log")
    """
    
    # Handle usage without parentheses: @mountainash_settings
    if cls_or_cache is not None and not isinstance(cls_or_cache, bool):
        # cls_or_cache is actually the class, called directly without parentheses
        return _apply_decorator(cls_or_cache, cache=True, templates=True, multi_format=True, namespace=None)
    
    # Handle cache parameter when passed positionally (legacy support)
    if isinstance(cls_or_cache, bool):
        cache = cls_or_cache
    
    # Return decorator function for @mountainash_settings() or @mountainash_settings(params...)
    def decorator(cls: Type[BaseSettings]) -> Type[BaseSettings]:
        return _apply_decorator(cls, cache=cache, templates=templates, multi_format=multi_format, namespace=namespace)
    
    return decorator


def _apply_decorator(
    cls: Type[BaseSettings], 
    cache: bool, 
    templates: bool, 
    multi_format: bool, 
    namespace: Optional[str]
) -> Type[BaseSettings]:
    """Apply the decorator functionality to the class."""
    # Store feature flags on the class for introspection
    cls._mountainash_cache_enabled = cache
    cls._mountainash_templates_enabled = templates
    cls._mountainash_multi_format_enabled = multi_format
    cls._mountainash_namespace = namespace
    cls._mountainash_decorated = True  # Mark as decorated to avoid recursion
    
    # Store original __init__ for reference
    original_init = cls.__init__
    
    # Create enhanced __init__ method
    def enhanced_init(
        self,
        settings_parameters: Optional[SettingsParameters] = None,
        config_files: Optional[Union[str, UPath, List[Union[str, UPath]]]] = None,
        namespace: Optional[str] = None,
        **kwargs
    ) -> None:
        """
        Enhanced __init__ method that integrates with SettingsParameters infrastructure.
        
        This method provides the same interface as MountainAshBaseSettings while working
        with standard Pydantic BaseSettings classes.
        
        Args:
            settings_parameters: Pre-configured SettingsParameters object
            config_files: Configuration files to load
            namespace: Settings namespace (overrides decorator default)
            **kwargs: Runtime parameter overrides
        """
        # Determine effective namespace
        effective_namespace = namespace or cls._mountainash_namespace
        
        # Create SettingsParameters if not provided
        if settings_parameters is None:
            settings_parameters = SettingsParameters.create(
                namespace=effective_namespace,
                config_files=config_files,
                settings_class=cls,
                **kwargs
            )
        else:
            # Merge with provided parameters
            local_params = SettingsParameters.create(
                namespace=effective_namespace,
                config_files=config_files,
                settings_class=cls,
                **kwargs
            )
            from .settings_parameters.utils import SettingsUtils
            settings_parameters = SettingsUtils.merge_settings_parameter_objects(
                settings_parameters, local_params
            )
        
        # If caching is disabled, create instance directly
        if not cls._mountainash_cache_enabled:
            # Extract attribute kwargs for direct initialization
            attribute_kwargs = settings_parameters.get_attribute_settings_kwargs(cls)
            original_init(self, **attribute_kwargs)
            return
        
        try:
            # Check if this is a decorated class to avoid recursion
            if hasattr(cls, '_mountainash_decorated'):
                raise AttributeError("Avoiding recursion with decorated class")
            
            # Use the caching infrastructure to get or create settings
            cached_instance = get_settings_func(settings_parameters=settings_parameters)
            
            # Copy cached instance attributes to self
            for field_name in cls.model_fields:
                if hasattr(cached_instance, field_name):
                    setattr(self, field_name, getattr(cached_instance, field_name))
            
            # Apply runtime overrides if present
            final_instance = settings_parameters.apply_runtime_overrides(cached_instance)
            if final_instance is not cached_instance:
                # Copy override values to self
                for field_name in cls.model_fields:
                    if hasattr(final_instance, field_name):
                        setattr(self, field_name, getattr(final_instance, field_name))
        except (AttributeError, ImportError, RecursionError):
            # Fallback to direct initialization if caching infrastructure fails
            # (e.g., for test classes, decorated classes, or classes not available at module level)
            attribute_kwargs = settings_parameters.get_attribute_settings_kwargs(cls)
            original_init(self, **attribute_kwargs)
    
    # Replace __init__ method
    cls.__init__ = enhanced_init
    
    # Inject get_settings classmethod
    @classmethod
    def get_settings(
        cls_inner,
        settings_parameters: Optional[SettingsParameters] = None,
        settings_namespace: Optional[str] = None,
        config_files: Optional[Union[UPath, str, List[Union[UPath, str]]]] = None,
        env_prefix: Optional[str] = None,
        **kwargs
    ) -> BaseSettings:
        """
        Class method for retrieving settings using the mountainash-settings infrastructure.
        
        This method delegates to the existing get_settings function while ensuring
        type compatibility with the decorated class.
        
        Args:
            settings_parameters: Pre-configured SettingsParameters object
            settings_namespace: Namespace for settings grouping
            config_files: Configuration files to load
            env_prefix: Environment variable prefix
            **kwargs: Additional runtime parameters
            
        Returns:
            Instance of the decorated settings class
            
        Raises:
            TypeError: If returned instance is not of the expected type
        """
        # Use decorator's default namespace if not specified
        effective_namespace = settings_namespace or cls_inner._mountainash_namespace
        
        try:
            # Avoid recursion for decorated classes
            if hasattr(cls_inner, '_mountainash_decorated'):
                raise AttributeError("Avoiding recursion with decorated class")
                
            settings_instance = get_settings_func(
                settings_parameters=settings_parameters,
                settings_class=cls_inner,
                settings_namespace=effective_namespace,
                config_files=config_files,
                env_prefix=env_prefix,
                **kwargs
            )
            
            if not isinstance(settings_instance, cls_inner):
                raise TypeError(
                    f"Created instance of type {type(settings_instance).__name__} "
                    f"but expected {cls_inner.__name__} when calling {cls_inner.__name__}.get_settings()"
                )
            
            return settings_instance
        except (AttributeError, ImportError, RecursionError):
            # Fallback to direct instantiation if caching infrastructure fails
            # Create SettingsParameters if not provided
            if settings_parameters is None:
                settings_parameters = SettingsParameters.create(
                    namespace=effective_namespace,
                    config_files=config_files,
                    settings_class=cls_inner,
                    env_prefix=env_prefix,
                    **kwargs
                )
            
            # Extract kwargs and create instance directly
            attribute_kwargs = settings_parameters.get_attribute_settings_kwargs(cls_inner)
            return cls_inner(**attribute_kwargs)
    
    # Inject the classmethod
    cls.get_settings = get_settings
    
    return cls