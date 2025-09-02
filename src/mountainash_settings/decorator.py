from typing import Optional, Union, List, Type, Callable, Any, Tuple
from string import Formatter
from upath import UPath

from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, TomlConfigSettingsSource, YamlConfigSettingsSource, JsonConfigSettingsSource

from .settings_parameters import SettingsParameters, SettingsUtils, SettingsFileHandler
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
        # Determine effective namespace - match MountainAshBaseSettings behavior
        effective_namespace = namespace or cls._mountainash_namespace or None
        
        # Store original namespace for metadata tracking - None means not provided by caller
        initial_settings_parameters = settings_parameters
        
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
            settings_parameters = SettingsUtils.merge_settings_parameter_objects(
                settings_parameters, local_params
            )
        
        # Handle multi-format configuration if enabled
        if cls._mountainash_multi_format_enabled and settings_parameters.config_files:
            # Separate config files by type
            obj_config_files = SettingsFileHandler.separate_config_files(settings_parameters.config_files)
            
            # Validate config files exist
            SettingsFileHandler.validate_config_files_exist(obj_config_files.env_files)
            SettingsFileHandler.validate_config_files_exist(obj_config_files.yaml_files)
            SettingsFileHandler.validate_config_files_exist(obj_config_files.toml_files)
            SettingsFileHandler.validate_config_files_exist(obj_config_files.json_files)
            
            # Update model_config for non-env files
            if hasattr(cls, 'model_config'):
                cls.model_config["yaml_file"] = obj_config_files.yaml_files or None
                cls.model_config["toml_file"] = obj_config_files.toml_files or None
                cls.model_config["json_file"] = obj_config_files.json_files or None

        # If caching is disabled, create instance directly
        if not cls._mountainash_cache_enabled:
            # Extract attribute kwargs for direct initialization
            attribute_kwargs = settings_parameters.get_attribute_settings_kwargs(cls)
            
            # Handle multi-format env files in direct initialization
            if cls._mountainash_multi_format_enabled and settings_parameters.config_files:
                obj_config_files = SettingsFileHandler.separate_config_files(settings_parameters.config_files)
                # Add env files to kwargs for Pydantic BaseSettings
                if obj_config_files.env_files:
                    attribute_kwargs['_env_file'] = obj_config_files.env_files
                    
            original_init(self, **attribute_kwargs)
            # Set metadata tracking if templates are enabled
            if cls._mountainash_templates_enabled:
                self._set_metadata_tracking(settings_parameters, config_files, effective_namespace, initial_settings_parameters)
            # Call post_init if templates are enabled - just like MountainAshBaseSettings
            if cls._mountainash_templates_enabled:
                self.post_init()
            return
        
        try:
            # Check if this is a decorated class to avoid recursion
            if hasattr(cls, '_mountainash_decorated'):
                raise AttributeError("Avoiding recursion with decorated class")
            
            # Use the caching infrastructure to get or create settings
            # This leverages SettingsParameters smart caching:
            # - Structural parameters (namespace, config_files, settings_class, env_prefix) affect cache
            # - Runtime parameters (kwargs) don't affect cache but are applied as overrides
            cached_instance = get_settings_func(settings_parameters=settings_parameters)
            
            # Copy cached instance attributes to self (preserving cache efficiency)
            for field_name in cls.model_fields:
                if hasattr(cached_instance, field_name):
                    setattr(self, field_name, getattr(cached_instance, field_name))
            
            # Apply runtime overrides without affecting cached instance
            # This maintains the JIT security pattern and smart caching benefits
            final_instance = settings_parameters.apply_runtime_overrides(cached_instance)
            if final_instance is not cached_instance:
                # Copy override values to self
                for field_name in cls.model_fields:
                    if hasattr(final_instance, field_name):
                        setattr(self, field_name, getattr(final_instance, field_name))
                        
        except (AttributeError, ImportError, RecursionError):
            # Fallback to direct initialization if caching infrastructure fails
            # This handles cases like:
            # - Test classes not available at module level
            # - Decorated classes causing recursion
            # - Import failures in distributed environments
            attribute_kwargs = settings_parameters.get_attribute_settings_kwargs(cls)
            original_init(self, **attribute_kwargs)
        
        # Set metadata tracking if templates are enabled
        if cls._mountainash_templates_enabled:
            self._set_metadata_tracking(settings_parameters, config_files, effective_namespace, initial_settings_parameters)
        
        # Call post_init if templates are enabled - just like MountainAshBaseSettings
        if cls._mountainash_templates_enabled:
            self.post_init()
    
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
        # Use provided namespace, otherwise fall back to decorator's default
        effective_namespace = settings_namespace if settings_namespace is not None else cls_inner._mountainash_namespace
        
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
            else:
                # Pass runtime kwargs directly to the constructor so the __init__ method can handle the merge
                # Don't pre-merge here - let the enhanced __init__ method handle it properly
                pass
            
            # Create instance with settings_parameters and runtime kwargs
            # The enhanced __init__ will handle merging them correctly
            # Only pass non-None values to avoid interfering with merge logic
            init_kwargs = {"settings_parameters": settings_parameters}
            if config_files is not None:
                init_kwargs["config_files"] = config_files
            if effective_namespace is not None:
                init_kwargs["namespace"] = effective_namespace
            init_kwargs.update(kwargs)  # Add runtime overrides
            
            return cls_inner(**init_kwargs)
    
    # Inject the classmethod
    cls.get_settings = get_settings
    
    # Add metadata tracking support for traceability and repeatability
    if templates:  # Add metadata when templates are enabled
        # Configure model to allow extra fields for metadata tracking
        if hasattr(cls, 'model_config'):
            # Update existing model_config to allow extra fields
            if hasattr(cls.model_config, 'update'):
                cls.model_config.update({'extra': 'allow'})
            else:
                # If model_config is a dict, update it
                if isinstance(cls.model_config, dict):
                    cls.model_config['extra'] = 'allow'
                else:
                    # Create new model_config allowing extra fields
                    from pydantic_settings import SettingsConfigDict
                    cls.model_config = SettingsConfigDict(extra='allow')
        else:
            # Create model_config if it doesn't exist
            from pydantic_settings import SettingsConfigDict
            cls.model_config = SettingsConfigDict(extra='allow')
            

    # Add template resolution methods if templates are enabled
    if templates:
        def init_setting_from_template(self, template_str: str, current_value: Optional[str] = None, reinitialise: bool = False) -> str:
            """
            Initializes a setting value from a template string,
            replacing placeholders with values from the settings object.

            Args:
                template_str: The template string to parse and format.
                current_value: The current value in the settings object if already set.
                reinitialise: Whether to reinitialize even if current_value exists.

            Returns:
                The formatted string from the template.

            Examples:
                template = "my_{BATCH_ID}_file.csv"
                settings.init_setting_from_template(template)
                # Returns: "my_20230101_file.csv" if BATCH_ID is 20230101
            """
            if current_value is not None and reinitialise is False:
                return current_value

            mapping = {}
            for _, field_name, _, _ in Formatter().parse(template_str):
                if field_name:
                    if hasattr(self, field_name):
                        mapping[field_name] = getattr(self, field_name)
                    else:
                        raise AttributeError(f"The object does not have an attribute named '{field_name}'")

            return template_str.format(**mapping)

        def format_template_from_settings(self, template_str: str) -> str:
            """
            Formats a template string with values from the settings object.

            Args:
                template_str: The template string to format.

            Returns:
                The formatted string from the template.

            Examples:
                template = "my_{BATCH_ID}_file.csv"
                settings.format_template_from_settings(template)
                # Returns: "my_20230101_file.csv" if BATCH_ID is 20230101
            """
            mapping = {}
            for _, field_name, _, _ in Formatter().parse(template_str):
                if field_name:
                    if hasattr(self, field_name):
                        mapping[field_name] = getattr(self, field_name)
                    else:
                        raise AttributeError(f"The object does not have an attribute named '{field_name}'")

            return template_str.format(**mapping)

        def update_settings_from_dict(self, settings_dict: Optional[dict[str, Any]]) -> None:
            """
            Updates the settings object with values from a dictionary.

            Args:
                settings_dict: The dictionary of settings to update.
            """
            settings_dict = SettingsUtils.format_kwargs_dict(p_kwargs=settings_dict)

            if settings_dict is None:
                return None

            for key, value in settings_dict.items():
                if hasattr(self, key):
                    setattr(self, key, value)
                else:
                    raise AttributeError(f"The object does not have an attribute named '{key}'")
                    
            # Store the kwargs like MountainAshBaseSettings does
            try:
                setattr(self, 'SETTINGS_SOURCE_KWARGS', settings_dict)
            except (AttributeError, ValueError):
                # If model is frozen, store in __pydantic_extra__
                if hasattr(self, '__pydantic_extra__'):
                    self.__pydantic_extra__['SETTINGS_SOURCE_KWARGS'] = settings_dict

        # Check if class already has a post_init method
        original_post_init = getattr(cls, 'post_init', None) if hasattr(cls, 'post_init') else None
        
        def post_init(self, reinitialise: bool = False):
            """Post-initialization function to run after the settings object has been initialized."""
            # Call original post_init if it exists
            if original_post_init and callable(original_post_init):
                original_post_init(self, reinitialise)
            # Template processing can be added here in future versions

        def _set_metadata_tracking(self, settings_parameters: SettingsParameters, config_files=None, effective_namespace=None, initial_settings_parameters=None):
            """Set metadata tracking attributes for traceability and repeatability."""
            try:
                # Initialize __pydantic_extra__ if it doesn't exist
                if not hasattr(self, '__pydantic_extra__') or self.__pydantic_extra__ is None:
                    self.__pydantic_extra__ = {}
                
                # Separate config files if multi-format is enabled and we have config files
                if cls._mountainash_multi_format_enabled and settings_parameters.config_files:
                    obj_config_files = SettingsFileHandler.separate_config_files(settings_parameters.config_files)
                    env_files = obj_config_files.env_files
                    yaml_files = obj_config_files.yaml_files  
                    toml_files = obj_config_files.toml_files
                    json_files = obj_config_files.json_files
                else:
                    # Handle basic config_files (assuming they are env files)
                    config_files_list = config_files or settings_parameters.config_files
                    env_files = config_files_list if config_files_list else None
                    yaml_files = None
                    toml_files = None
                    json_files = None

                # Set all metadata attributes - handle frozen models by using __pydantic_extra__
                # Determine which namespace to store:
                # - If SettingsParameters was provided by caller, use its namespace (can be non-None)  
                # - If no SettingsParameters provided, match MountainAshBaseSettings behavior (store None)
                # Use the original settings_parameters.namespace if provided by caller, otherwise effective_namespace 
                namespace_to_store = initial_settings_parameters.namespace if initial_settings_parameters else effective_namespace
                
                metadata_attrs = {
                    "SETTINGS_NAMESPACE": namespace_to_store,
                    "SETTINGS_CLASS": settings_parameters.settings_class or cls,
                    "SETTINGS_CLASS_NAME": (settings_parameters.settings_class.__name__ if settings_parameters.settings_class else cls.__name__),
                    "SETTINGS_SOURCE_ENV_PREFIX": settings_parameters.env_prefix,
                    "SETTINGS_SOURCE_ENV_FILES": env_files,
                    "SETTINGS_SOURCE_YAML_FILES": yaml_files,
                    "SETTINGS_SOURCE_TOML_FILES": toml_files,
                    "SETTINGS_SOURCE_JSON_FILES": json_files,
                    "SETTINGS_SOURCE_KWARGS": settings_parameters.get_attribute_settings_kwargs(cls),
                    "SETTINGS_SOURCE_SECRETS_DIR": settings_parameters.secrets_dir
                }
                
                for key, value in metadata_attrs.items():
                    try:
                        setattr(self, key, value)
                    except (AttributeError, ValueError):
                        # If model is frozen or has restrictions, store in __pydantic_extra__
                        if hasattr(self, '__pydantic_extra__'):
                            self.__pydantic_extra__[key] = value
                        
            except Exception:
                # Silently fail metadata tracking if there are issues
                pass

        def extract_settings_parameters(self) -> SettingsParameters:
            """
            Returns a SettingsParameters object reconstructed from the settings object.
            
            Returns:
                SettingsParameters: The settings parameters object reconstructed from metadata
            """
            def get_metadata_value(attr_name, default=None):
                """Helper to get metadata from either direct attributes or __pydantic_extra__."""
                if hasattr(self, attr_name):
                    return getattr(self, attr_name, default)
                elif hasattr(self, '__pydantic_extra__') and self.__pydantic_extra__:
                    return self.__pydantic_extra__.get(attr_name, default)
                return default
                
            # Combine the config files into a single list
            config_files = []
            env_files = get_metadata_value('SETTINGS_SOURCE_ENV_FILES')
            yaml_files = get_metadata_value('SETTINGS_SOURCE_YAML_FILES')
            toml_files = get_metadata_value('SETTINGS_SOURCE_TOML_FILES')  
            json_files = get_metadata_value('SETTINGS_SOURCE_JSON_FILES')
            
            if env_files:
                config_files += env_files
            if yaml_files:
                config_files += yaml_files
            if toml_files:
                config_files += toml_files
            if json_files:
                config_files += json_files

            existing_namespace = get_metadata_value('SETTINGS_NAMESPACE')
            existing_config_files = SettingsUtils.format_config_file_list(config_files=config_files)
            existing_kwargs = SettingsUtils.format_kwargs_dict(p_kwargs=get_metadata_value('SETTINGS_SOURCE_KWARGS'))
            existing_settings_class = get_metadata_value('SETTINGS_CLASS')
            existing_env_prefix = get_metadata_value('SETTINGS_SOURCE_ENV_PREFIX')
            existing_secrets_dir = get_metadata_value('SETTINGS_SOURCE_SECRETS_DIR')

            return SettingsParameters.create(
                namespace=existing_namespace,
                settings_class=existing_settings_class,
                config_files=existing_config_files,
                env_prefix=existing_env_prefix,
                secrets_dir=existing_secrets_dir,
                **existing_kwargs if existing_kwargs else {}
            )

        # Inject template methods into the class
        cls.init_setting_from_template = init_setting_from_template
        cls.format_template_from_settings = format_template_from_settings
        cls.update_settings_from_dict = update_settings_from_dict
        cls.post_init = post_init
        cls._set_metadata_tracking = _set_metadata_tracking
        cls.extract_settings_parameters = extract_settings_parameters
    
    # Add multi-format configuration support if enabled
    if multi_format:
        @classmethod
        def settings_customise_sources(
            cls_inner,
            settings_cls: Type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
        ) -> Tuple[PydanticBaseSettingsSource, ...]:
            """
            Customize Pydantic settings sources to include multi-format configuration support.
            
            This method adds YAML, TOML, and JSON configuration file sources in addition
            to the standard Pydantic sources.
            
            Args:
                settings_cls: The settings class being configured
                init_settings: Initialization-time settings source
                env_settings: Environment variable settings source  
                dotenv_settings: .env file settings source
                file_secret_settings: Secrets file settings source
                
            Returns:
                Tuple of settings sources in priority order
            """
            return (
                init_settings,
                env_settings, 
                dotenv_settings,
                YamlConfigSettingsSource(settings_cls),
                TomlConfigSettingsSource(settings_cls),
                JsonConfigSettingsSource(settings_cls),
                file_secret_settings
            )
        
        # Inject the settings customization method
        cls.settings_customise_sources = settings_customise_sources
    
    return cls