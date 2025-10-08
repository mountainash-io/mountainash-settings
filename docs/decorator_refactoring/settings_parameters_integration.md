# SettingsParameters Integration with @mountainash_settings

## Overview

`SettingsParameters` is the core infrastructure that makes mountainash-settings efficient and powerful. It's not just a configuration container - it's a sophisticated caching and configuration management system that must be preserved in the decorator approach.

## SettingsParameters: The Real Architecture

### Smart Caching Key System

`SettingsParameters` implements a brilliant caching strategy using custom `__hash__()` and `__eq__()` methods:

```python
# From SettingsParameters.__hash__()
def __hash__(self):
    # Only "structural" parameters affect cache identity
    hashable_attrs = tuple([
        self.namespace,
        hashable_config_files,
        self.settings_class,
        self.env_prefix,
        # Deliberately exclude: self.kwargs, self.secrets_dir
    ])
    return hash(hashable_attrs)
```

**Key Insight**: Runtime `kwargs` don't affect cache identity, allowing cache reuse with different runtime overrides.

### Runtime Override System

```python
def apply_runtime_overrides(self, cached_settings: BaseSettings) -> BaseSettings:
    if self.kwargs:
        settings_copy = cached_settings.model_copy()
        override_kwargs = self.get_attribute_settings_kwargs()
        if override_kwargs:
            settings_copy.update_settings_from_dict(settings_dict=override_kwargs)
        return settings_copy
    return cached_settings
```

This allows the same cached instance to serve multiple requests with different runtime parameters.

### Configuration Processing Pipeline

`SettingsParameters` handles complex configuration processing:

1. **File Type Separation**: Separates .env, YAML, TOML, JSON files
2. **Validation**: Ensures config files exist and are readable  
3. **Kwargs Processing**: Separates Pydantic kwargs from settings kwargs
4. **Precedence Handling**: Manages configuration source precedence

## Integration with Decorator Approach

### The @mountainash_settings Decorator Must Preserve SettingsParameters

The decorator should enhance Pydantic classes to work seamlessly with `SettingsParameters`, not replace it:

```python
@mountainash_settings(cache=True, templates=True)
class AppSettings(BaseSettings):
    debug: bool = Field(default=False)
    database_url: str = Field(default="sqlite:///app.db")

# These calls should work exactly like MountainAshBaseSettings:
settings_params = SettingsParameters.create(
    settings_class=AppSettings,
    namespace="production",
    config_files=["config.yaml"],
    kwargs={"debug": True}
)

settings = AppSettings.get_settings(settings_parameters=settings_params)
```

### Enhanced __init__ Method Integration

The decorator must integrate with `SettingsParameters` during initialization:

```python
def enhanced_init(self, 
                 config_files: Optional[List[str]] = None,
                 settings_parameters: Optional[SettingsParameters] = None,
                 namespace: Optional[str] = None,
                 env_prefix: Optional[str] = None,
                 **kwargs):
    """Enhanced __init__ that works with SettingsParameters system."""
    
    # 1. Handle SettingsParameters-based initialization
    if settings_parameters is not None:
        # Use provided SettingsParameters
        effective_params = settings_parameters
        
        # Merge with any additional parameters
        if any([config_files, namespace, env_prefix, kwargs]):
            local_params = SettingsParameters.create(
                settings_class=self.__class__,
                namespace=namespace,
                config_files=config_files,
                env_prefix=env_prefix,
                **kwargs
            )
            effective_params = SettingsUtils.merge_settings_parameter_objects(
                settings_parameters, local_params
            )
    else:
        # Create SettingsParameters from individual arguments
        effective_params = SettingsParameters.create(
            settings_class=self.__class__,
            namespace=namespace or default_namespace,
            config_files=config_files,
            env_prefix=env_prefix or default_env_prefix,
            **kwargs
        )
    
    # 2. Check cache if enabled
    if cache_enabled:
        cached_instance = _get_cached_settings(effective_params)
        if cached_instance is not None:
            # Apply runtime overrides and copy state
            final_instance = effective_params.apply_runtime_overrides(cached_instance)
            self.__dict__.update(final_instance.__dict__)
            return
    
    # 3. Process configuration through SettingsParameters
    config_kwargs = _process_settings_parameters(effective_params)
    
    # 4. Call original Pydantic __init__
    original_init(self, **config_kwargs)
    
    # 5. Apply template resolution if enabled
    if templates_enabled:
        self._apply_template_resolution()
    
    # 6. Cache the instance
    if cache_enabled:
        _cache_settings_instance(effective_params, self)
    
    # 7. Store SettingsParameters for introspection
    self._mountainash_settings_parameters = effective_params
```

### SettingsParameters Processing Function

```python
def _process_settings_parameters(settings_params: SettingsParameters) -> Dict[str, Any]:
    """
    Convert SettingsParameters into kwargs for Pydantic __init__.
    
    This function replicates the configuration processing logic from
    MountainAshBaseSettings while working with standard Pydantic initialization.
    """
    config_kwargs = {}
    
    # 1. Process configuration files
    if settings_params.config_files:
        separated_files = SettingsFileHandler.separate_config_files(settings_params.config_files)
        
        # Validate files exist
        SettingsFileHandler.validate_config_files_exist(separated_files.env_files)
        SettingsFileHandler.validate_config_files_exist(separated_files.yaml_files)
        SettingsFileHandler.validate_config_files_exist(separated_files.toml_files)
        SettingsFileHandler.validate_config_files_exist(separated_files.json_files)
        
        # Add to Pydantic initialization
        if separated_files.env_files:
            config_kwargs['_env_file'] = separated_files.env_files
        
        # Multi-format files will be handled through model_config
    
    # 2. Process environment prefix
    if settings_params.env_prefix:
        config_kwargs['_env_prefix'] = settings_params.env_prefix
    
    # 3. Process secrets directory
    if settings_params.secrets_dir:
        config_kwargs['_secrets_dir'] = settings_params.secrets_dir
    
    # 4. Process runtime kwargs
    if settings_params.kwargs:
        # Get valid Pydantic settings kwargs
        pydantic_kwargs = settings_params.get_pydantic_settings_kwargs()
        config_kwargs.update(pydantic_kwargs)
        
        # Get attribute settings kwargs (for field values)
        attribute_kwargs = settings_params.get_attribute_settings_kwargs(settings_params.settings_class)
        config_kwargs.update(attribute_kwargs)
    
    return config_kwargs
```

### get_settings Class Method Implementation

The decorator must inject a `get_settings` method that works exactly like `MountainAshBaseSettings.get_settings()`:

```python
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
    Get settings instance with SettingsParameters-based caching and configuration.
    
    This method provides identical API to MountainAshBaseSettings.get_settings()
    while working with the decorated Pydantic class.
    
    The method integrates with the existing SettingsManager and caching system,
    ensuring that decorated classes work seamlessly with mountainash-settings infrastructure.
    """
    
    # 1. Resolve settings class
    effective_settings_class = settings_class or cls
    
    # 2. Create or merge SettingsParameters
    if settings_parameters is not None:
        if not isinstance(settings_parameters, SettingsParameters):
            raise ValueError("settings_parameters must be an instance of SettingsParameters")
        
        # Merge with any additional parameters provided
        if any([settings_namespace, config_files, env_prefix, kwargs]):
            local_params = SettingsParameters.create(
                settings_class=effective_settings_class,
                namespace=settings_namespace,
                config_files=config_files,
                env_prefix=env_prefix,
                **kwargs
            )
            final_params = SettingsUtils.merge_settings_parameter_objects(
                settings_parameters, local_params
            )
        else:
            final_params = settings_parameters
    else:
        # Create SettingsParameters from arguments
        final_params = SettingsParameters.create(
            settings_class=effective_settings_class,
            namespace=settings_namespace or default_namespace,
            config_files=config_files,
            env_prefix=env_prefix or default_env_prefix,
            **kwargs
        )
    
    # 3. Use existing mountainash-settings infrastructure
    from mountainash_settings import get_settings
    return get_settings(settings_parameters=final_params)
```

## Caching Integration

### LRU Cache Compatibility

The decorator must work with the existing `@lru_cache` on `_get_settings()`:

```python
# Existing caching function in settings_functions.py
@lru_cache(maxsize=None)
def _get_settings(settings_parameters: SettingsParameters) -> BaseSettings:
    settings_manager = get_settings_manager()
    return settings_manager.get_or_create_settings(settings_parameters=settings_parameters)
```

The decorator's `get_settings()` method should delegate to this existing infrastructure.

### SettingsManager Integration

The decorator must work with `SettingsManager.get_or_create_settings()`:

```python
def _get_cached_settings(settings_params: SettingsParameters) -> Optional[BaseSettings]:
    """Get cached settings using existing SettingsManager."""
    settings_manager = get_settings_manager()
    
    if settings_manager.is_namespace_initialised(settings_params):
        return settings_manager.get_settings_object(settings_params)
    return None

def _cache_settings_instance(settings_params: SettingsParameters, instance: BaseSettings):
    """Cache settings instance using existing SettingsManager."""
    settings_manager = get_settings_manager()
    settings_manager.settings_object_cache[settings_params] = instance
```

## Usage Patterns Preservation

### Existing API Compatibility

All existing usage patterns must continue to work:

```python
# Pattern 1: Direct SettingsParameters usage
settings_params = SettingsParameters.create(
    settings_class=AppSettings,
    namespace="production",
    config_files=["config.yaml"],
    kwargs={"debug": True}
)
settings = AppSettings.get_settings(settings_parameters=settings_params)

# Pattern 2: Individual parameters
settings = AppSettings.get_settings(
    namespace="production",
    config_files=["config.yaml"],
    debug=True
)

# Pattern 3: Mixed usage
base_params = SettingsParameters.create(
    settings_class=AppSettings,
    namespace="production",
    config_files=["base_config.yaml"]
)
settings = AppSettings.get_settings(
    settings_parameters=base_params,
    config_files=["override_config.yaml"],  # Additional config
    debug=True  # Runtime override
)
```

### Runtime Override Behavior

The decorator must preserve the runtime override behavior:

```python
@mountainash_settings(cache=True)
class CachedSettings(BaseSettings):
    debug: bool = Field(default=False)
    database_url: str = Field(default="sqlite:///app.db")

# These calls share the same cached base but have different runtime overrides
settings1 = CachedSettings.get_settings(
    namespace="prod", 
    config_files=["config.yaml"],
    debug=True  # Runtime override
)

settings2 = CachedSettings.get_settings(
    namespace="prod",
    config_files=["config.yaml"], 
    debug=False,  # Different runtime override
    database_url="postgresql://prod-db/app"  # Additional runtime override
)

# settings1 and settings2 are based on the same cached instance
# but have different runtime values applied
```

## Template Resolution Integration

### SettingsParameters and Templates

Template resolution must work with `SettingsParameters` configuration:

```python
@mountainash_settings(templates=True)
class TemplateSettings(BaseSettings):
    batch_id: str = Field(default="B001")
    run_date: str = Field(default="20241201")
    output_path: str = Field(default="data/{run_date}/batch_{batch_id}/")

settings_params = SettingsParameters.create(
    settings_class=TemplateSettings,
    namespace="batch_processing",
    kwargs={"batch_id": "B999", "run_date": "20241210"}
)

settings = TemplateSettings.get_settings(settings_parameters=settings_params)
# output_path resolves to "data/20241210/batch_B999/"
```

### post_init Integration

Custom `post_init` methods must work with the template resolution system:

```python
@mountainash_settings(templates=True)
class CustomTemplateSettings(BaseSettings):
    base_path: str = Field(default="/data")
    project_id: str = Field(default="PROJECT001")
    data_path: str = Field(default="{base_path}/{project_id}/data")
    
    def post_init(self, reinitialise=False):
        # Call template resolution first
        super().post_init(reinitialise)
        
        # Then custom logic
        self.working_directory = f"{self.data_path}/working"
        self.archive_directory = f"{self.data_path}/archive"
```

## Multi-Format Configuration Integration

### SettingsParameters File Processing

Multi-format configuration must use `SettingsParameters` file processing:

```python
@mountainash_settings(multi_format=True)
class MultiFormatSettings(BaseSettings):
    app_name: str = Field(default="MyApp")
    debug: bool = Field(default=False)

# File processing handled through SettingsParameters
settings_params = SettingsParameters.create(
    settings_class=MultiFormatSettings,
    config_files=["base_config.yaml", "secrets.env", "overrides.toml"]
)

settings = MultiFormatSettings.get_settings(settings_parameters=settings_params)
```

### model_config Enhancement

The decorator must enhance `model_config` based on `SettingsParameters` configuration:

```python
def _enhance_model_config_from_settings_parameters(
    original_config: Dict[str, Any],
    settings_params: SettingsParameters
) -> Dict[str, Any]:
    """Enhance model_config based on SettingsParameters configuration."""
    enhanced_config = original_config.copy()
    
    if settings_params.config_files:
        separated_files = SettingsFileHandler.separate_config_files(settings_params.config_files)
        
        if separated_files.yaml_files:
            enhanced_config['yaml_file'] = separated_files.yaml_files
        if separated_files.toml_files:
            enhanced_config['toml_file'] = separated_files.toml_files
        if separated_files.json_files:
            enhanced_config['json_file'] = separated_files.json_files
    
    # Add Pydantic model config kwargs
    pydantic_model_config_kwargs = settings_params.get_pydantic_modelconfig_kwargs()
    enhanced_config.update(pydantic_model_config_kwargs)
    
    return enhanced_config
```

## Error Handling and Validation

### SettingsParameters Validation

The decorator must use existing `SettingsParameters` validation:

```python
def _validate_settings_parameters_integration(cls, settings_params: SettingsParameters):
    """Validate SettingsParameters compatibility with decorated class."""
    
    # Ensure settings_class matches
    if settings_params.settings_class and settings_params.settings_class != cls:
        raise ValueError(
            f"SettingsParameters.settings_class ({settings_params.settings_class}) "
            f"does not match decorated class ({cls})"
        )
    
    # Validate configuration files exist
    if settings_params.config_files:
        separated_files = SettingsFileHandler.separate_config_files(settings_params.config_files)
        SettingsFileHandler.validate_config_files_exist(separated_files.env_files)
        SettingsFileHandler.validate_config_files_exist(separated_files.yaml_files)
        SettingsFileHandler.validate_config_files_exist(separated_files.toml_files)
        SettingsFileHandler.validate_config_files_exist(separated_files.json_files)
    
    # Validate kwargs compatibility
    if settings_params.kwargs:
        valid_kwargs = settings_params.get_attribute_settings_kwargs(cls)
        invalid_kwargs = set(settings_params.kwargs.keys()) - set(valid_kwargs.keys())
        if invalid_kwargs:
            raise ValueError(f"Invalid kwargs for {cls.__name__}: {invalid_kwargs}")
```

## Testing Integration

### SettingsParameters-Based Tests

Tests must verify that the decorator preserves `SettingsParameters` functionality:

```python
def test_decorator_preserves_settings_parameters_caching():
    """Test that SettingsParameters caching works with decorated classes."""
    
    @mountainash_settings(cache=True)
    class TestSettings(BaseSettings):
        value: str = Field(default="test")
    
    # Create SettingsParameters
    params1 = SettingsParameters.create(
        settings_class=TestSettings,
        namespace="cache_test",
        config_files=["config.yaml"],
        kwargs={"value": "override1"}
    )
    
    params2 = SettingsParameters.create(
        settings_class=TestSettings,
        namespace="cache_test",
        config_files=["config.yaml"],
        kwargs={"value": "override2"}  # Different runtime override
    )
    
    # Should share same cache key (same structural parameters)
    assert params1.__hash__() == params2.__hash__()
    assert params1 == params2
    
    # Get settings instances
    settings1 = TestSettings.get_settings(settings_parameters=params1)
    settings2 = TestSettings.get_settings(settings_parameters=params2)
    
    # Should be based on same cached instance but with different runtime overrides
    assert settings1.value == "override1"
    assert settings2.value == "override2"

def test_decorator_runtime_override_behavior():
    """Test runtime override behavior through SettingsParameters."""
    
    @mountainash_settings(cache=True)
    class TestSettings(BaseSettings):
        debug: bool = Field(default=False)
        timeout: int = Field(default=30)
    
    base_params = SettingsParameters.create(
        settings_class=TestSettings,
        namespace="test"
    )
    
    # Get base settings
    base_settings = TestSettings.get_settings(settings_parameters=base_params)
    assert base_settings.debug == False
    assert base_settings.timeout == 30
    
    # Get settings with runtime overrides
    override_params = SettingsParameters.create(
        settings_class=TestSettings,
        namespace="test",  # Same structural parameters
        kwargs={"debug": True, "timeout": 60}  # Runtime overrides
    )
    
    override_settings = TestSettings.get_settings(settings_parameters=override_params)
    assert override_settings.debug == True
    assert override_settings.timeout == 60
    
    # Verify they share the same cache key
    assert base_params.__hash__() == override_params.__hash__()
```

## Summary

The `@mountainash_settings` decorator must be built as an **enhancement layer** over the existing `SettingsParameters` infrastructure, not a replacement. The decorator should:

1. **Preserve SettingsParameters**: Use it as the core configuration and caching system
2. **Integrate with SettingsManager**: Work with existing caching and instance management
3. **Maintain API Compatibility**: All existing usage patterns continue to work
4. **Enhance Pydantic Classes**: Make them work seamlessly with mountainash-settings infrastructure
5. **Support All Features**: Caching, templates, multi-format configs, runtime overrides

This approach ensures that the decorator provides the "feels like Pydantic" experience while preserving all the sophisticated infrastructure that makes mountainash-settings valuable.