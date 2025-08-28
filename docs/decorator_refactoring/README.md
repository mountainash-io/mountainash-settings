# Decorator-Based Settings Architecture

## Overview

This document outlines a refactoring approach that preserves all the valuable features of mountainash-settings while making users feel like they're working with standard Pydantic classes. The decorator approach eliminates the class hierarchy distance between user code and Pydantic BaseSettings.

## Current Problem

Users must inherit from `MountainAshBaseSettings` which feels distant from standard Pydantic:

```python
# Current: Feels like a custom framework
from mountainash_settings import MountainAshBaseSettings

class MyAppSettings(MountainAshBaseSettings):  # Not standard Pydantic
    debug: bool = Field(default=False)
    database_url: str = Field(default="sqlite:///app.db")
```

## Proposed Solution: `@mountainash_settings` Decorator

The decorator approach keeps the class looking like standard Pydantic while injecting our advanced features:

```python
# Proposed: Feels like Pydantic with enhancements
from pydantic_settings import BaseSettings
from mountainash_settings import mountainash_settings

@mountainash_settings(cache=True, templates=True, multi_format=True)
class MyAppSettings(BaseSettings):  # Pure Pydantic class
    debug: bool = Field(default=False)
    database_url: str = Field(default="sqlite:///app.db")
    batch_file_path: str = Field(default="reports/{RUNDATE}/batch_{BATCH_ID}.csv")
```

## Core Infrastructure Preserved

The decorator enhances Pydantic classes to work seamlessly with mountainash-settings' sophisticated infrastructure:

### 1. SettingsParameters Framework (Core Architecture)
- **Smart Hash-based Caching**: Only structural parameters (namespace, config_files, settings_class, env_prefix) affect cache identity
- **Runtime Override System**: `apply_runtime_overrides()` applies kwargs to cached instances without cache invalidation  
- **Configuration Processing Pipeline**: File separation, validation, kwargs processing, precedence management
- **LRU Cache Integration**: Works with existing `@lru_cache` on `_get_settings()`

### 2. SettingsManager Integration  
- **Instance Caching**: `get_or_create_settings()` manages settings instances with namespace-based caching
- **Cache Lookup**: `is_namespace_initialised()` checks cache before creating new instances
- **Settings Object Cache**: `settings_object_cache` stores instances by SettingsParameters hash

### 3. Multi-Source Configuration (via SettingsParameters)
- **File Type Processing**: SettingsFileHandler separates .env, YAML, TOML, JSON files
- **Configuration Validation**: Ensures config files exist and are readable
- **Environment Variable Support**: Prefix-based environment variable loading
- **Kwargs Processing**: Separates Pydantic kwargs from settings field values

### 4. Template Resolution System
- **Dynamic Template Processing**: `{VARIABLE}` placeholder substitution using existing field values
- **post_init() Integration**: Template resolution during initialization phase  
- **Custom Template Logic**: Support for custom post-initialization processing

### 5. Configuration Precedence Management
- **Source Priority**: Defaults → config files → environment variables → runtime kwargs
- **Override Tracking**: Full traceability of configuration sources
- **Runtime vs Structural Separation**: Critical for cache efficiency

## Decorator Design

### Basic Usage

```python
@mountainash_settings()  # All features enabled by default
class AppSettings(BaseSettings):
    app_name: str = Field(default="MyApp")
    debug: bool = Field(default=False)
```

### Feature Selection

```python
@mountainash_settings(
    cache=True,           # Enable smart caching
    templates=True,       # Enable template resolution  
    multi_format=True,    # Enable YAML/TOML/JSON support
    namespace="my_app"    # Set default namespace
)
class AppSettings(BaseSettings):
    # Class definition remains pure Pydantic
    pass
```

### Disable All Features (Pure Pydantic)

```python
@mountainash_settings(cache=False, templates=False, multi_format=False)
class AppSettings(BaseSettings):
    # Behaves exactly like BaseSettings
    pass
```

## Implementation Architecture

### Decorator Function Structure

```python
def mountainash_settings(
    cache: bool = True,
    templates: bool = True,
    multi_format: bool = True,
    namespace: Optional[str] = None
):
    """
    Decorator that enhances Pydantic BaseSettings with mountainash-settings features.
    
    Args:
        cache: Enable SettingsParameters-based caching
        templates: Enable template string resolution
        multi_format: Enable YAML/TOML/JSON config file support
        namespace: Default settings namespace
    """
    def decorator(cls: Type[BaseSettings]) -> Type[BaseSettings]:
        # Enhancement logic here
        return enhanced_class
    return decorator
```

### Class Enhancement Process

The decorator performs the following enhancements:

1. **Preserve Original Class**: No inheritance changes
2. **Inject Methods**: Add `.get_settings()`, template resolution
3. **Enhance `__init__`**: Add SettingsParameters handling
4. **Add Metaclass Magic**: Handle caching and multi-format loading
5. **Maintain Pydantic Behavior**: All standard features work normally

### Method Injection Details

#### Enhanced `__init__` Method

```python
def enhanced_init(self, 
                 config_files: Optional[List[str]] = None,
                 settings_parameters: Optional[SettingsParameters] = None,
                 namespace: Optional[str] = None,
                 env_prefix: Optional[str] = None,
                 **kwargs):
    """Enhanced __init__ that integrates with SettingsParameters infrastructure."""
    
    # 1. Handle SettingsParameters-based initialization (preserves existing system)
    if settings_parameters is not None or cache_enabled:
        effective_params = settings_parameters or SettingsParameters.create(
            settings_class=self.__class__,
            namespace=namespace or default_namespace,
            config_files=config_files,
            env_prefix=env_prefix or default_env_prefix,
            **kwargs
        )
        
        # 2. Integrate with existing SettingsManager caching
        if cache_enabled:
            from mountainash_settings import get_settings_manager
            settings_manager = get_settings_manager()
            
            if settings_manager.is_namespace_initialised(effective_params):
                # Get cached instance and apply runtime overrides
                cached_instance = settings_manager.get_settings_object(effective_params)
                final_instance = effective_params.apply_runtime_overrides(cached_instance)
                self.__dict__.update(final_instance.__dict__)
                return
        
        # 3. Process configuration through SettingsParameters pipeline
        config_kwargs = _process_settings_parameters(effective_params)
        self._mountainash_settings_parameters = effective_params
    else:
        # Direct Pydantic initialization without SettingsParameters
        config_kwargs = kwargs
    
    # 4. Call original Pydantic __init__
    original_init(self, **config_kwargs)
    
    # 5. Apply template resolution and cache instance
    if templates_enabled:
        self._apply_template_resolution()
    
    if cache_enabled and hasattr(self, '_mountainash_settings_parameters'):
        settings_manager.settings_object_cache[self._mountainash_settings_parameters] = self
```

#### Injected `get_settings` Class Method

```python
@classmethod
def get_settings(cls, 
                settings_parameters: Optional[SettingsParameters] = None,
                settings_class: Optional[Type[BaseSettings]] = None,
                settings_namespace: Optional[str] = None,
                config_files: Optional[List[str]] = None,
                env_prefix: Optional[str] = None,
                **kwargs) -> Self:
    """
    Get settings instance using SettingsParameters infrastructure.
    
    This method provides identical API to MountainAshBaseSettings.get_settings()
    while delegating to the existing mountainash-settings infrastructure for
    consistency and to preserve all caching and configuration processing logic.
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
```

#### Template Resolution Support

```python
def post_init(self, reinitialise: bool = False):
    """
    Template string resolution - only injected if templates=True
    """
    for field_name, field_value in self.model_fields.items():
        if isinstance(field_value, str) and '{' in field_value:
            resolved_value = self.init_setting_from_template(
                template_str=field_value,
                current_value=getattr(self, field_name),
                reinitialise=reinitialise
            )
            setattr(self, field_name, resolved_value)
```

## Migration Strategy

### Phase 1: Backward Compatibility

Maintain `MountainAshBaseSettings` for existing code while introducing the decorator:

```python
# Existing code continues to work
class LegacySettings(MountainAshBaseSettings):
    pass

# New code uses decorator
@mountainash_settings()
class NewSettings(BaseSettings):
    pass
```

### Phase 2: Gradual Migration

Provide migration utilities:

```python
# Auto-convert existing classes
@convert_from_mountainash_base
class MigratedSettings(BaseSettings):  # Automatically enhanced
    pass
```

### Phase 3: Deprecation

Eventually deprecate `MountainAshBaseSettings` in favor of the decorator approach.

## Usage Examples

### Basic Application Settings

```python
from pydantic_settings import BaseSettings
from pydantic import Field
from mountainash_settings import mountainash_settings, SettingsParameters

@mountainash_settings(namespace="myapp")
class AppSettings(BaseSettings):
    # Standard Pydantic field definitions
    app_name: str = Field(default="MyApplication")
    debug: bool = Field(default=False)
    database_url: str = Field(default="sqlite:///app.db")
    
    # Template fields work seamlessly
    log_file: str = Field(default="logs/{RUNDATE}/app.log")
    report_path: str = Field(default="reports/{BATCH_ID}/summary.csv")

# Usage feels exactly like Pydantic
settings = AppSettings()
settings = AppSettings(debug=True, app_name="TestApp")

# SettingsParameters usage works identically to MountainAshBaseSettings
settings_params = SettingsParameters.create(
    settings_class=AppSettings,
    namespace="production",
    config_files=["config.yaml", "secrets.env"],
    kwargs={"debug": False}
)
settings = AppSettings.get_settings(settings_parameters=settings_params)

# Or individual parameters (delegates to SettingsParameters internally)
settings = AppSettings.get_settings(
    settings_namespace="production",
    config_files=["config.yaml", "secrets.env"],
    debug=False
)
```

### Multi-Environment Configuration

```python
@mountainash_settings(cache=True, namespace="webapp")
class WebAppSettings(BaseSettings):
    environment: str = Field(default="development")
    secret_key: str = Field(default="dev-secret")
    database_url: str = Field(default="sqlite:///dev.db")
    redis_url: str = Field(default="redis://localhost:6379")

# Development
dev_settings = WebAppSettings()

# Production with config files
prod_settings = WebAppSettings.get_settings(
    config_files=["production.yaml", "secrets.env"],
    environment="production"
)

# Testing with overrides
test_settings = WebAppSettings(
    environment="testing",
    database_url="sqlite:///:memory:"
)
```

### Template-Heavy Configuration

```python
@mountainash_settings(templates=True)
class BatchJobSettings(BaseSettings):
    job_name: str = Field(default="data_processor")
    run_date: str = Field(default="20241201")
    batch_id: str = Field(default="B001")
    
    # Template fields resolve automatically
    input_path: str = Field(default="data/input/{run_date}/batch_{batch_id}/")
    output_path: str = Field(default="data/output/{run_date}/{job_name}/")
    log_file: str = Field(default="logs/{run_date}/{job_name}_{batch_id}.log")
    
    # Custom template method (optional)
    def get_working_directory(self) -> str:
        return f"tmp/{self.job_name}_{self.run_date}_{self.batch_id}"
```

## Benefits

### For Users
1. **Familiar API**: Classes look like standard Pydantic
2. **Optional Enhancement**: Choose which features to use
3. **No Learning Curve**: Existing Pydantic knowledge applies
4. **Gradual Adoption**: Can migrate incrementally

### For Developers
1. **Preserve Investment**: All existing features retained
2. **Cleaner Architecture**: No forced inheritance hierarchy
3. **Modular Design**: Features can be enabled/disabled independently
4. **Future Flexibility**: Easy to add new features

### For the Ecosystem
1. **Standards Compliance**: Aligns with Pydantic best practices
2. **Interoperability**: Works with other Pydantic-based tools
3. **Community Adoption**: Familiar patterns increase adoption
4. **Maintenance**: Easier to maintain and extend

## Technical Implementation Notes

### Decorator Pattern Benefits
- **Non-invasive**: Original class behavior preserved
- **Composable**: Multiple decorators can be combined
- **Testable**: Easy to test enhanced vs non-enhanced behavior
- **Debuggable**: Clear separation between base and enhanced functionality

### Performance Considerations
- **Lazy Enhancement**: Features only activate when used
- **Cache Efficiency**: Existing caching strategy preserved
- **Memory Usage**: No additional memory overhead for unused features
- **Startup Time**: Minimal impact on application startup

### Compatibility Matrix

| Feature | Pure BaseSettings | @mountainash_settings | MountainAshBaseSettings |
|---------|------------------|----------------------|------------------------|
| Standard Pydantic | ✅ Full | ✅ Full | ✅ Full |
| Smart Caching | ❌ None | ✅ Optional | ✅ Always |
| Multi-Format Config | ❌ Limited | ✅ Optional | ✅ Always |
| Template Resolution | ❌ None | ✅ Optional | ✅ Always |
| Configuration Precedence | ❌ Basic | ✅ Optional | ✅ Always |
| Class Hierarchy | ✅ Direct | ✅ Direct | ❌ Extended |
| Migration Effort | N/A | ⚡ Minimal | 🔧 Major |

## Implementation Roadmap

### Phase 1: Core Decorator (2 weeks)
- [ ] Implement basic `@mountainash_settings` decorator
- [ ] Method injection for `get_settings()` 
- [ ] Enhanced `__init__` with SettingsParameters
- [ ] Basic caching integration

### Phase 2: Feature Integration (3 weeks)  
- [ ] Multi-format configuration support
- [ ] Template resolution system
- [ ] Configuration precedence handling
- [ ] Comprehensive testing

### Phase 3: Migration Tools (2 weeks)
- [ ] Backward compatibility layer
- [ ] Migration utilities
- [ ] Documentation and examples
- [ ] Performance benchmarking

### Phase 4: Deprecation Path (Ongoing)
- [ ] Gradual deprecation of MountainAshBaseSettings
- [ ] Community feedback integration
- [ ] Long-term maintenance plan

This approach preserves the technical excellence of mountainash-settings while making it feel like standard Pydantic to users.