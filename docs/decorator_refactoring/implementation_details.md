# Implementation Details: @mountainash_settings Decorator

## Core Implementation Architecture

### Decorator Function Design

```python
from typing import Type, Optional, Callable, Any, Dict
from functools import wraps
from pydantic_settings import BaseSettings

def mountainash_settings(
    cache: bool = True,
    templates: bool = True, 
    multi_format: bool = True,
    namespace: Optional[str] = None,
    env_prefix: Optional[str] = None
) -> Callable[[Type[BaseSettings]], Type[BaseSettings]]:
    """
    Decorator that enhances Pydantic BaseSettings with mountainash-settings features.
    
    The decorator preserves all original Pydantic behavior while adding optional
    advanced configuration management features.
    
    Args:
        cache: Enable SettingsParameters-based smart caching
        templates: Enable template string resolution with {VAR} placeholders
        multi_format: Enable YAML/TOML/JSON configuration file support
        namespace: Default settings namespace for caching and organization
        env_prefix: Default environment variable prefix
    
    Returns:
        Enhanced class with mountainash-settings features
    
    Example:
        @mountainash_settings(cache=True, templates=True)
        class AppSettings(BaseSettings):
            debug: bool = Field(default=False)
            log_path: str = Field(default="logs/{RUNDATE}/app.log")
    """
    def decorator(cls: Type[BaseSettings]) -> Type[BaseSettings]:
        return _enhance_settings_class(
            cls, cache, templates, multi_format, namespace, env_prefix
        )
    return decorator
```

### Class Enhancement Process

```python
def _enhance_settings_class(
    original_class: Type[BaseSettings],
    cache_enabled: bool,
    templates_enabled: bool,
    multi_format_enabled: bool,
    default_namespace: Optional[str],
    default_env_prefix: Optional[str]
) -> Type[BaseSettings]:
    """
    Enhance a Pydantic BaseSettings class to work with SettingsParameters infrastructure.
    
    This function preserves the original class structure while integrating with the existing
    mountainash-settings SettingsParameters, SettingsManager, and caching systems.
    The enhanced class works seamlessly with all existing mountainash-settings infrastructure.
    """
    
    # Store original methods to preserve Pydantic behavior
    original_init = original_class.__init__
    original_model_config = getattr(original_class, 'model_config', {})
    
    # Enhanced initialization method that integrates with SettingsParameters
    def enhanced_init(
        self, 
        config_files: Optional[List[Union[str, UPath]]] = None,
        settings_parameters: Optional[SettingsParameters] = None,
        namespace: Optional[str] = None,
        env_prefix: Optional[str] = None,
        **kwargs
    ):
        """
        Enhanced __init__ that integrates with SettingsParameters infrastructure.
        
        This method works with the existing mountainash-settings caching and configuration
        system, ensuring that decorated classes behave identically to MountainAshBaseSettings
        while looking like standard Pydantic classes.
        """
        
        # 1. Handle SettingsParameters integration (core infrastructure)
        if settings_parameters is not None or cache_enabled:
            # Create or use provided SettingsParameters
            if settings_parameters is not None:
                effective_params = settings_parameters
                
                # Merge with additional parameters if provided
                if any([namespace, config_files, env_prefix, kwargs]):
                    local_params = SettingsParameters.create(
                        settings_class=original_class,
                        namespace=namespace,
                        config_files=config_files,
                        env_prefix=env_prefix,
                        **kwargs
                    )
                    from mountainash_settings.settings_parameters import SettingsUtils
                    effective_params = SettingsUtils.merge_settings_parameter_objects(
                        settings_parameters, local_params
                    )
            else:
                # Create SettingsParameters from individual arguments
                effective_params = SettingsParameters.create(
                    settings_class=original_class,
                    namespace=namespace or default_namespace,
                    config_files=config_files,
                    env_prefix=env_prefix or default_env_prefix,
                    **kwargs
                )
            
            # 2. Integrate with existing SettingsManager caching system
            if cache_enabled:
                from mountainash_settings import get_settings_manager
                settings_manager = get_settings_manager()
                
                if settings_manager.is_namespace_initialised(effective_params):
                    # Get cached instance and apply runtime overrides
                    cached_instance = settings_manager.get_settings_object(effective_params)
                    final_instance = effective_params.apply_runtime_overrides(cached_instance)
                    # Copy state to self and return
                    self.__dict__.update(final_instance.__dict__)
                    return
            
            # 3. Process configuration through SettingsParameters pipeline
            config_kwargs = _process_settings_parameters(effective_params)
            self._mountainash_settings_parameters = effective_params
            
        else:
            # Direct Pydantic initialization (when all features disabled)
            config_kwargs = kwargs
        
        # 4. Call original Pydantic initialization
        original_init(self, **config_kwargs)
        
        # 5. Apply post-initialization processing
        if templates_enabled:
            self._apply_template_resolution()
        
        # 6. Cache the instance using existing SettingsManager
        if cache_enabled and hasattr(self, '_mountainash_settings_parameters'):
            settings_manager = get_settings_manager()
            settings_manager.settings_object_cache[self._mountainash_settings_parameters] = self
    
    # Inject get_settings class method that delegates to existing infrastructure
    @classmethod
    def get_settings(
        cls,
        settings_parameters: Optional[SettingsParameters] = None,
        settings_class: Optional[Type[BaseSettings]] = None,
        settings_namespace: Optional[str] = None,
        config_files: Optional[List[Union[str, UPath]]] = None,
        env_prefix: Optional[str] = None,
        **kwargs
    ) -> BaseSettings:
        """
        Get settings instance using existing mountainash-settings infrastructure.
        
        This method provides identical API to MountainAshBaseSettings.get_settings()
        while delegating to the existing get_settings() function and SettingsParameters
        system for complete compatibility and consistency.
        
        Args:
            settings_parameters: Pre-configured SettingsParameters object
            settings_class: Settings class (defaults to decorated class)
            settings_namespace: Settings namespace for caching
            config_files: Configuration files to load
            env_prefix: Environment variable prefix
            **kwargs: Additional settings values or configuration
            
        Returns:
            Settings instance from existing mountainash-settings infrastructure
            
        Example:
            settings = AppSettings.get_settings(
                settings_namespace="production",
                config_files=["config.yaml", "secrets.env"],
                debug=False
            )
        """
        # Delegate to existing mountainash-settings infrastructure
        from mountainash_settings import get_settings
        
        return get_settings(
            settings_parameters=settings_parameters,
            settings_class=settings_class or cls,
            settings_namespace=settings_namespace or default_namespace,
            config_files=config_files,
            env_prefix=env_prefix or default_env_prefix,
            **kwargs
        )
    
    # Inject template resolution methods if enabled
    if templates_enabled:
        def _apply_template_resolution(self):
            """Apply template string resolution to all string fields."""
            for field_name, field_info in self.model_fields.items():
                field_value = getattr(self, field_name)
                if isinstance(field_value, str) and '{' in field_value:
                    resolved_value = self._resolve_template_string(field_value)
                    setattr(self, field_name, resolved_value)
        
        def _resolve_template_string(self, template_str: str) -> str:
            """
            Resolve template string using current field values.
            
            This method replicates the template resolution functionality
            from MountainAshBaseSettings.init_setting_from_template().
            """
            from string import Formatter
            
            mapping = {}
            for _, field_name, _, _ in Formatter().parse(template_str):
                if field_name and hasattr(self, field_name):
                    mapping[field_name] = getattr(self, field_name)
            
            return template_str.format(**mapping)
        
        def post_init(self, reinitialise: bool = False):
            """
            Post-initialization hook for template resolution.
            
            This method maintains compatibility with existing MountainAshBaseSettings
            code that relies on post_init() for template processing.
            """
            self._apply_template_resolution()
        
        # Inject template methods
        setattr(original_class, '_apply_template_resolution', _apply_template_resolution)
        setattr(original_class, '_resolve_template_string', _resolve_template_string)
        setattr(original_class, 'post_init', post_init)
    
    # Replace __init__ and add get_settings
    setattr(original_class, '__init__', enhanced_init)
    setattr(original_class, 'get_settings', get_settings)
    
    # Add feature flags as class attributes for introspection
    setattr(original_class, '_mountainash_cache_enabled', cache_enabled)
    setattr(original_class, '_mountainash_templates_enabled', templates_enabled)
    setattr(original_class, '_mountainash_multi_format_enabled', multi_format_enabled)
    setattr(original_class, '_mountainash_default_namespace', default_namespace)
    
    return original_class
```

## Helper Functions

### Multi-Format Configuration Processing

```python
def _process_settings_parameters(settings_params: SettingsParameters) -> Dict[str, Any]:
    """
    Convert SettingsParameters into kwargs for Pydantic __init__.
    
    This function processes SettingsParameters through the existing mountainash-settings
    pipeline, replicating the configuration processing logic from MountainAshBaseSettings
    while working with standard Pydantic initialization.
    
    Args:
        settings_params: SettingsParameters object containing configuration
        
    Returns:
        Dictionary of configuration values for Pydantic __init__
    """
    from mountainash_settings.settings_parameters import SettingsFileHandler
    
    config_kwargs = {}
    
    # 1. Process configuration files using existing pipeline
    if settings_params.config_files:
        separated_files = SettingsFileHandler.separate_config_files(settings_params.config_files)
        
        # Validate files exist using existing validation
        SettingsFileHandler.validate_config_files_exist(separated_files.env_files)
        SettingsFileHandler.validate_config_files_exist(separated_files.yaml_files)
        SettingsFileHandler.validate_config_files_exist(separated_files.toml_files)
        SettingsFileHandler.validate_config_files_exist(separated_files.json_files)
        
        # Set up Pydantic file sources
        if separated_files.env_files:
            config_kwargs['_env_file'] = separated_files.env_files
            
        # Multi-format files are handled through enhanced model_config
        if separated_files.yaml_files:
            config_kwargs['_yaml_files'] = separated_files.yaml_files
        if separated_files.toml_files:
            config_kwargs['_toml_files'] = separated_files.toml_files
        if separated_files.json_files:
            config_kwargs['_json_files'] = separated_files.json_files
    
    # 2. Process environment prefix
    if settings_params.env_prefix:
        config_kwargs['_env_prefix'] = settings_params.env_prefix
    
    # 3. Process secrets directory
    if settings_params.secrets_dir:
        config_kwargs['_secrets_dir'] = settings_params.secrets_dir
    
    # 4. Process kwargs using existing SettingsParameters methods
    if settings_params.kwargs:
        # Get Pydantic-specific kwargs
        pydantic_kwargs = settings_params.get_pydantic_settings_kwargs()
        config_kwargs.update(pydantic_kwargs)
        
        # Get attribute kwargs (field values)
        attribute_kwargs = settings_params.get_attribute_settings_kwargs(settings_params.settings_class)
        config_kwargs.update(attribute_kwargs)
    
    return config_kwargs

def _create_enhanced_model_config(
    original_config: Dict[str, Any], 
    config_files: Optional[List[Union[str, UPath]]],
    env_prefix: Optional[str]
) -> Dict[str, Any]:
    """
    Create enhanced model_config that supports multi-format configuration.
    
    This function extends the original model_config with file sources
    while preserving all existing configuration.
    """
    enhanced_config = original_config.copy()
    
    if config_files:
        separated_files = SettingsFileHandler.separate_config_files(config_files)
        
        # Add file sources to model_config
        if separated_files.yaml_files:
            enhanced_config['yaml_file'] = separated_files.yaml_files
        if separated_files.toml_files:
            enhanced_config['toml_file'] = separated_files.toml_files
        if separated_files.json_files:
            enhanced_config['json_file'] = separated_files.json_files
    
    if env_prefix:
        enhanced_config['env_prefix'] = env_prefix
    
    return enhanced_config
```

### Caching Integration

```python
def _get_cached_settings(settings_params: SettingsParameters) -> Optional[BaseSettings]:
    """
    Retrieve cached settings instance using existing SettingsParameters caching.
    
    This function integrates with the existing SettingsManager caching system
    while working with decorated classes.
    """
    from mountainash_settings import get_settings_manager
    
    settings_manager = get_settings_manager()
    return settings_manager.get_cached_instance(settings_params)

def _cache_settings_instance(settings_params: SettingsParameters, instance: BaseSettings):
    """
    Cache settings instance using existing SettingsParameters caching system.
    """
    from mountainash_settings import get_settings_manager
    
    settings_manager = get_settings_manager()
    settings_manager.cache_instance(settings_params, instance)
```

## Usage Pattern Compatibility

### Direct Instantiation
```python
@mountainash_settings()
class AppSettings(BaseSettings):
    debug: bool = Field(default=False)

# Works exactly like BaseSettings
settings = AppSettings()
settings = AppSettings(debug=True)
```

### Configuration Files
```python
# Multi-format configuration support
settings = AppSettings(
    config_files=["config.yaml", "secrets.env"],
    namespace="production"
)

# Or using get_settings (maintains compatibility)
settings = AppSettings.get_settings(
    config_files=["config.yaml", "secrets.env"],
    namespace="production"
)
```

### Template Resolution
```python
@mountainash_settings(templates=True)
class BatchSettings(BaseSettings):
    run_date: str = Field(default="20241201")
    batch_id: str = Field(default="B001")
    output_path: str = Field(default="output/{run_date}/batch_{batch_id}/")

settings = BatchSettings()
# output_path automatically resolves to "output/20241201/batch_B001/"
```

### Caching Behavior
```python
@mountainash_settings(cache=True, namespace="myapp")
class CachedSettings(BaseSettings):
    database_url: str = Field(default="sqlite:///app.db")

# First call creates and caches instance
settings1 = CachedSettings.get_settings(namespace="production")

# Second call with same structural parameters returns cached instance
settings2 = CachedSettings.get_settings(namespace="production")

# Different runtime parameters create new instance with cached base
settings3 = CachedSettings.get_settings(
    namespace="production",
    database_url="postgresql://prod-db/app"  # Runtime override
)
```

## Feature Flag Introspection

```python
@mountainash_settings(cache=True, templates=False)
class IntrospectableSettings(BaseSettings):
    value: str = Field(default="test")

# Check which features are enabled
assert IntrospectableSettings._mountainash_cache_enabled == True
assert IntrospectableSettings._mountainash_templates_enabled == False
assert IntrospectableSettings._mountainash_multi_format_enabled == True

# Conditional logic based on features
if IntrospectableSettings._mountainash_cache_enabled:
    # Use cached retrieval
    settings = IntrospectableSettings.get_settings(namespace="cache_test")
else:
    # Direct instantiation
    settings = IntrospectableSettings()
```

## Error Handling and Validation

### Configuration File Validation
```python
def _validate_config_files(config_files: List[Union[str, UPath]]):
    """
    Validate configuration files exist and are readable.
    
    Uses existing SettingsFileHandler validation logic.
    """
    from mountainash_settings.settings_parameters import SettingsFileHandler
    
    separated_files = SettingsFileHandler.separate_config_files(config_files)
    
    # Validate each file type
    SettingsFileHandler.validate_config_files_exist(separated_files.env_files)
    SettingsFileHandler.validate_config_files_exist(separated_files.yaml_files)
    SettingsFileHandler.validate_config_files_exist(separated_files.toml_files)
    SettingsFileHandler.validate_config_files_exist(separated_files.json_files)
```

### Template Resolution Error Handling
```python
def _safe_resolve_template_string(self, template_str: str) -> str:
    """
    Safely resolve template string with error handling for missing variables.
    """
    try:
        return self._resolve_template_string(template_str)
    except (KeyError, AttributeError) as e:
        # Log warning but don't fail initialization
        import warnings
        warnings.warn(
            f"Template resolution failed for '{template_str}': {e}. "
            f"Using original template string.",
            UserWarning
        )
        return template_str
```

## Testing Strategy

### Unit Tests for Decorator
```python
def test_decorator_preserves_pydantic_behavior():
    """Test that decorated class behaves like normal BaseSettings."""
    
    @mountainash_settings(cache=False, templates=False, multi_format=False)
    class TestSettings(BaseSettings):
        test_field: str = Field(default="test")
    
    settings = TestSettings()
    assert settings.test_field == "test"
    
    settings = TestSettings(test_field="override")
    assert settings.test_field == "override"

def test_decorator_enables_features_selectively():
    """Test that features can be enabled/disabled independently."""
    
    @mountainash_settings(cache=True, templates=False)
    class CacheOnlySettings(BaseSettings):
        test_field: str = Field(default="test")
    
    assert CacheOnlySettings._mountainash_cache_enabled == True
    assert CacheOnlySettings._mountainash_templates_enabled == False
    
    # Should have get_settings method
    assert hasattr(CacheOnlySettings, 'get_settings')
    
    # Should not have template methods
    assert not hasattr(CacheOnlySettings, 'post_init')

def test_template_resolution():
    """Test template string resolution functionality."""
    
    @mountainash_settings(templates=True)
    class TemplateSettings(BaseSettings):
        base_path: str = Field(default="/data")
        run_id: str = Field(default="RUN001")
        full_path: str = Field(default="{base_path}/runs/{run_id}/output")
    
    settings = TemplateSettings()
    assert settings.full_path == "/data/runs/RUN001/output"
```

### Integration Tests
```python
def test_caching_with_settings_parameters():
    """Test integration with existing SettingsParameters caching."""
    
    @mountainash_settings(cache=True)
    class CachedSettings(BaseSettings):
        value: str = Field(default="test")
    
    # Create settings with same structural parameters
    settings1 = CachedSettings.get_settings(namespace="test")
    settings2 = CachedSettings.get_settings(namespace="test")
    
    # Should be same cached instance
    assert settings1 is settings2

def test_multi_format_config_loading():
    """Test loading from YAML/TOML/JSON configuration files."""
    
    @mountainash_settings(multi_format=True)
    class MultiFormatSettings(BaseSettings):
        app_name: str = Field(default="default")
        debug: bool = Field(default=False)
    
    settings = MultiFormatSettings(config_files=["test_config.yaml"])
    # Verify values loaded from YAML file
    assert settings.app_name == "test_app"
    assert settings.debug == True
```

This implementation preserves all the valuable features of mountainash-settings while making the user experience feel exactly like standard Pydantic BaseSettings.