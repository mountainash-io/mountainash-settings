# @mountainash_settings Feature Flags Reference

## Overview

The `@mountainash_settings` decorator provides fine-grained control over functionality through feature flags. This document provides detailed information about each flag, its effects, implementation details, and use cases.

## Feature Flag Summary

| Flag | Default | Purpose | Runtime Cost | Memory Impact |
|------|---------|---------|--------------|---------------|
| `cache` | `True` | Smart caching with SettingsManager | Low | Medium |
| `templates` | `True` | Template resolution and formatting | Low | Low |
| `multi_format` | `True` | YAML/TOML/JSON config file support | Medium | Low |
| `namespace` | `None` | Cache isolation and configuration grouping | None | Minimal |

## cache Flag

### Purpose
Controls integration with the mountainash-settings smart caching system for efficient settings instance management.

### Default Value
`True`

### When Enabled (`cache=True`)

#### Behavior Changes
- Settings instances are cached based on structural parameters
- Multiple calls with identical structural parameters return the same instance
- Runtime parameters don't affect cache identity
- Integrates with SettingsManager for cross-application caching

#### Performance Impact
- **First Access**: Slightly slower due to cache lookup overhead
- **Subsequent Access**: Significantly faster (cache hits)
- **Memory**: Moderate increase due to cached instances

#### Code Additions
```python
# Adds get_settings() classmethod that uses SettingsManager
settings1 = MySettings.get_settings()
settings2 = MySettings.get_settings()
assert settings1 is settings2  # True - same cached instance

# Adds fallback mechanisms for recursion/import failures
```

#### Implementation Details
```python
def enhanced_init(self, **kwargs):
    # Attempts cached retrieval via get_settings_func
    try:
        cached_instance = get_settings_func(
            settings_parameters=params,
            settings_class=cls,
            **kwargs
        )
        # Copy cached instance data to current instance
        self.__dict__.update(cached_instance.__dict__)
    except Exception:
        # Falls back to direct Pydantic initialization
        original_init(self, **kwargs)
```

#### Use Cases
- **Production Applications**: Efficient settings reuse across modules
- **Long-running Services**: Minimize initialization overhead
- **Multi-tenant Applications**: Separate caching by namespace
- **Resource-constrained Environments**: Reduce memory allocation

#### Structural vs Runtime Parameters
```python
# Structural parameters (affect cache identity):
# - namespace
# - config_files  
# - settings_class
# - env_prefix

# Runtime parameters (don't affect cache identity):
# - kwargs passed to __init__
# - secrets_dir

@mountainash_settings(cache=True)
class APISettings(BaseSettings):
    timeout: int = Field(default=30)
    
# These share the same cache entry
settings1 = APISettings(timeout=60)  # Runtime parameter
settings2 = APISettings(timeout=90)  # Different runtime, same cache
assert settings1.timeout != settings2.timeout  # False - runtime applied

# These use different cache entries  
settings3 = APISettings()  # Default namespace
settings4 = APISettings.get_settings(namespace="api_v2")  # Different namespace
```

### When Disabled (`cache=False`)

#### Behavior Changes
- Direct Pydantic BaseSettings instantiation
- Each call creates a new instance
- No SettingsManager integration
- Standard Pydantic performance characteristics

#### Performance Impact
- **Consistent Performance**: Same initialization time for all calls
- **Memory**: Lower baseline, but potentially higher with many instances
- **Simplicity**: No cache invalidation concerns

#### Use Cases
- **Testing**: Isolated instances for test cases
- **Temporary Settings**: Short-lived configuration objects
- **Development**: Avoid cache-related debugging complexity
- **Edge Cases**: Classes with complex initialization logic

### Cache Configuration Examples

```python
# Production service with caching
@mountainash_settings(cache=True, namespace="user_service")
class UserServiceSettings(BaseSettings):
    database_url: str = Field(default="sqlite:///users.db")
    redis_url: str = Field(default="redis://localhost")

# Test settings without caching
@mountainash_settings(cache=False)
class TestSettings(BaseSettings):
    test_database: str = Field(default="sqlite:///:memory:")
    
# Namespace-isolated caching
@mountainash_settings(cache=True, namespace="payment_service")
class PaymentSettings(BaseSettings):
    api_key: str = Field(default="")

@mountainash_settings(cache=True, namespace="notification_service") 
class NotificationSettings(BaseSettings):
    api_key: str = Field(default="")
```

## templates Flag

### Purpose
Enables template resolution capabilities for dynamic configuration values using Python's string formatting.

### Default Value
`True`

### When Enabled (`templates=True`)

#### Behavior Changes
- Adds template resolution methods to decorated classes
- Enables post-initialization template processing
- Supports dynamic field value generation

#### Performance Impact
- **Initialization**: Slight overhead for template scanning
- **Runtime**: Fast template resolution using `string.Formatter`
- **Memory**: Minimal increase for template metadata

#### Methods Added

##### `format_template_from_settings(template_str: str) -> str`
Format template strings using current settings values:

```python
@mountainash_settings(templates=True)
class LogSettings(BaseSettings):
    app_name: str = Field(default="myapp")
    environment: str = Field(default="dev")

settings = LogSettings(app_name="webapi", environment="prod")
log_path = settings.format_template_from_settings("logs/{app_name}/{environment}.log")
# Returns: "logs/webapi/prod.log"
```

##### `init_setting_from_template(template_str: str, current_value=None, reinitialise=False) -> str`
Initialize setting values from templates during object creation:

```python
@mountainash_settings(templates=True)
class StorageSettings(BaseSettings):
    service_name: str = Field(default="storage")
    environment: str = Field(default="dev")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Set bucket name from template if not provided
        if not hasattr(self, 'bucket_name'):
            self.bucket_name = self.init_setting_from_template(
                "{service_name}-{environment}-bucket"
            )
```

##### `update_settings_from_dict(settings_dict: Dict[str, Any]) -> None`
Update multiple settings from a dictionary with validation:

```python
settings = LogSettings()
updates = {
    "app_name": "updated_app",
    "environment": "staging"
}
settings.update_settings_from_dict(updates)
```

#### Template Syntax
Uses Python's standard string formatting with field access:

```python
# Simple field substitution
template = "logs/{app_name}.log"

# Multiple fields
template = "config/{service_name}/{environment}/settings.yaml"

# Nested access (if supported by your fields)
template = "data/{database.host}/{database.name}/dump.sql"
```

#### Error Handling
```python
try:
    formatted = settings.format_template_from_settings("path/{missing_field}/file")
except AttributeError as e:
    # "The object does not have an attribute named 'missing_field'"
    print(f"Template error: {e}")
```

### When Disabled (`templates=False`)

#### Behavior Changes
- No template methods added to decorated classes
- Standard Pydantic field behavior only
- No post-initialization template processing

#### Use Cases
- **Simple Configuration**: Static values without dynamic generation
- **Performance Optimization**: Eliminate template resolution overhead
- **Security**: Avoid potential template injection if templates contain user input
- **Legacy Compatibility**: Match standard Pydantic behavior exactly

### Template Use Cases and Patterns

#### Dynamic File Paths
```python
@mountainash_settings(templates=True)
class FileSettings(BaseSettings):
    environment: str = Field(default="dev")
    service: str = Field(default="api")
    log_dir: str = Field(default="/var/log/{service}/{environment}")
    config_file: str = Field(default="/etc/{service}/{environment}/config.yaml")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Resolve templates after initialization
        self.log_dir = self.init_setting_from_template(self.log_dir)
        self.config_file = self.init_setting_from_template(self.config_file)
```

#### Database Connection Strings
```python
@mountainash_settings(templates=True)
class DatabaseSettings(BaseSettings):
    host: str = Field(default="localhost")
    port: int = Field(default=5432) 
    database_name: str = Field(default="myapp")
    username: str = Field(default="user")
    
    def get_connection_string(self, password: str) -> str:
        template = "postgresql://{username}:{password}@{host}:{port}/{database_name}"
        # Add password to template context
        temp_dict = self.__dict__.copy()
        temp_dict['password'] = password
        return template.format(**temp_dict)
```

#### Environment-specific Configuration
```python
@mountainash_settings(templates=True, namespace="{environment}")
class EnvironmentSettings(BaseSettings):
    environment: str = Field(default="development")
    api_base_url: str = Field(default="https://{environment}-api.example.com")
    s3_bucket: str = Field(default="myapp-{environment}-data")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs) 
        # Resolve all template fields
        for field_name, field_info in self.__class__.model_fields.items():
            current_value = getattr(self, field_name)
            if isinstance(current_value, str) and '{' in current_value:
                resolved_value = self.format_template_from_settings(current_value)
                setattr(self, field_name, resolved_value)
```

## multi_format Flag

### Purpose
Enables support for YAML, TOML, and JSON configuration files in addition to standard Pydantic sources.

### Default Value
`True`

### When Enabled (`multi_format=True`)

#### Behavior Changes
- Injects custom `settings_customise_sources()` method
- Adds YamlConfigSettingsSource, TomlConfigSettingsSource, JsonConfigSettingsSource
- Enables configuration loading from multiple file formats

#### Performance Impact
- **Initialization**: Moderate overhead for additional source processing
- **File I/O**: Additional file reads if config files are specified
- **Memory**: Minimal increase for source management

#### Implementation Details
```python
@classmethod 
def settings_customise_sources(cls, settings_cls, init_settings, env_settings, 
                              dotenv_settings, file_secret_settings):
    return (
        init_settings,           # Runtime parameters (highest priority)
        env_settings,            # Environment variables  
        dotenv_settings,         # .env files
        YamlConfigSettingsSource(settings_cls),  # YAML files
        TomlConfigSettingsSource(settings_cls),  # TOML files  
        JsonConfigSettingsSource(settings_cls),  # JSON files
        file_secret_settings     # Secret files (lowest priority)
    )
```

#### Configuration Files Setup
```python
@mountainash_settings(multi_format=True)
class AppSettings(BaseSettings):
    debug: bool = Field(default=False)
    database_url: str = Field(default="sqlite:///app.db")
    
    model_config = SettingsConfigDict(
        yaml_file="config.yaml",
        toml_file="config.toml", 
        json_file="config.json",
        env_prefix="APP_"
    )
```

#### Source Priority Order (highest to lowest)
1. **init_settings**: Runtime parameters passed to `__init__()`
2. **env_settings**: Environment variables
3. **dotenv_settings**: Values from .env files
4. **YamlConfigSettingsSource**: YAML configuration files
5. **TomlConfigSettingsSource**: TOML configuration files
6. **JsonConfigSettingsSource**: JSON configuration files  
7. **file_secret_settings**: Docker secrets and secret files

#### File Format Examples

**config.yaml:**
```yaml
debug: true
database_url: "postgresql://localhost/myapp_prod"
redis:
  host: "redis.example.com"
  port: 6379
logging:
  level: "INFO"
  handlers:
    - console
    - file
```

**config.toml:**
```toml
debug = true
database_url = "postgresql://localhost/myapp_prod"

[redis]
host = "redis.example.com"
port = 6379

[logging]
level = "INFO"
handlers = ["console", "file"]
```

**config.json:**
```json
{
  "debug": true,
  "database_url": "postgresql://localhost/myapp_prod",
  "redis": {
    "host": "redis.example.com",
    "port": 6379
  },
  "logging": {
    "level": "INFO", 
    "handlers": ["console", "file"]
  }
}
```

### When Disabled (`multi_format=False`)

#### Behavior Changes
- Uses standard Pydantic source configuration
- Only supports env files (.env) and environment variables
- No YAML, TOML, or JSON configuration file support

#### Performance Impact
- **Faster Initialization**: Fewer sources to process
- **Reduced I/O**: No additional config file reads
- **Lower Memory**: Fewer source objects

#### Source Configuration (4 sources instead of 7)
```python
# Standard Pydantic sources only:
# 1. init_settings (runtime parameters)
# 2. env_settings (environment variables) 
# 3. dotenv_settings (.env files)
# 4. file_secret_settings (secret files)
```

### Multi-format Use Cases

#### Microservices Configuration
```python
@mountainash_settings(multi_format=True, namespace="service_{service_name}")
class ServiceSettings(BaseSettings):
    service_name: str = Field(default="unknown")
    port: int = Field(default=8000)
    database_url: str = Field(default="sqlite:///service.db")
    
    model_config = SettingsConfigDict(
        yaml_file="config/{service_name}.yaml",
        env_prefix="{service_name}_".upper()
    )
```

#### Development vs Production
```python
@mountainash_settings(multi_format=True)
class EnvironmentSettings(BaseSettings):
    environment: str = Field(default="development")
    
    model_config = SettingsConfigDict(
        yaml_file=["base.yaml", "{environment}.yaml"],
        env_prefix="APP_"
    )
        
# Uses base.yaml + development.yaml for dev
# Uses base.yaml + production.yaml for prod
```

#### Complex Configuration Hierarchies
```python
@mountainash_settings(multi_format=True)
class HierarchicalSettings(BaseSettings):
    # Load from multiple sources with precedence
    model_config = SettingsConfigDict(
        yaml_file=[
            "defaults.yaml",      # Base defaults
            "environment.yaml",   # Environment overrides
            "local.yaml"          # Local development overrides
        ],
        toml_file="service.toml",   # Service-specific config
        json_file="runtime.json",   # Runtime configuration
        env_prefix="SERVICE_"
    )
```

## namespace Parameter

### Purpose
Provides cache isolation and configuration grouping for settings instances.

### Default Value
`None` (uses class name as default namespace)

### Behavior and Effects

#### Cache Isolation
```python
@mountainash_settings(cache=True, namespace="service_a")
class SettingsA(BaseSettings):
    value: str = Field(default="a")

@mountainash_settings(cache=True, namespace="service_b") 
class SettingsB(BaseSettings):
    value: str = Field(default="b")

# These are cached separately despite identical structure
settings_a1 = SettingsA()
settings_a2 = SettingsA()  # Same cache entry
settings_b = SettingsB()   # Different cache entry

assert settings_a1 is settings_a2  # True
assert settings_a1 is not settings_b  # True
```

#### Configuration Grouping
```python
@mountainash_settings(namespace="api_v1")
class APIv1Settings(BaseSettings):
    endpoint: str = Field(default="/api/v1")

@mountainash_settings(namespace="api_v2")
class APIv2Settings(BaseSettings):
    endpoint: str = Field(default="/api/v2")
```

#### Dynamic Namespacing
```python
def create_tenant_settings(tenant_id: str):
    @mountainash_settings(namespace=f"tenant_{tenant_id}")
    class TenantSettings(BaseSettings):
        database_url: str = Field(default="sqlite:///default.db")
    
    return TenantSettings

# Each tenant gets isolated configuration
tenant_1_settings = create_tenant_settings("tenant_001")()
tenant_2_settings = create_tenant_settings("tenant_002")()
```

#### Metadata Integration
```python
@mountainash_settings(namespace="user_service")
class UserSettings(BaseSettings):
    pass

settings = UserSettings()
print(settings.SETTINGS_NAMESPACE)  # "user_service"

# Extract for reuse
params = settings.extract_settings_parameters()
print(params.namespace)  # "user_service"
```

### Namespace Best Practices

#### Service-based Namespacing
```python
@mountainash_settings(namespace="auth_service")
class AuthSettings(BaseSettings):
    pass

@mountainash_settings(namespace="payment_service")
class PaymentSettings(BaseSettings):
    pass

@mountainash_settings(namespace="notification_service")
class NotificationSettings(BaseSettings):
    pass
```

#### Environment-based Namespacing
```python
@mountainash_settings(namespace=f"app_{os.getenv('ENVIRONMENT', 'dev')}")
class AppSettings(BaseSettings):
    pass
```

#### Feature-based Namespacing  
```python
@mountainash_settings(namespace="feature_flags")
class FeatureSettings(BaseSettings):
    new_ui_enabled: bool = Field(default=False)
    beta_features: bool = Field(default=False)

@mountainash_settings(namespace="database_config")
class DatabaseSettings(BaseSettings):
    pass

@mountainash_settings(namespace="cache_config")
class CacheSettings(BaseSettings):
    pass
```

## Feature Flag Combinations

### Recommended Combinations

#### Production Service (All Features)
```python
@mountainash_settings(
    cache=True,           # Efficient instance reuse
    templates=True,       # Dynamic configuration
    multi_format=True,    # Flexible config files
    namespace="prod_api"  # Isolated caching
)
class ProductionAPISettings(BaseSettings):
    pass
```

#### Development/Testing (Minimal Overhead)
```python
@mountainash_settings(
    cache=False,          # Avoid cache pollution
    templates=False,      # Simple static config
    multi_format=False,   # Reduce complexity
    namespace="test"      # Test isolation
)
class TestSettings(BaseSettings):
    pass
```

#### Simple Application (Balanced)
```python
@mountainash_settings(
    cache=True,           # Basic caching benefits
    templates=False,      # No dynamic needs
    multi_format=True,    # Config file flexibility
    namespace="simple_app"
)
class SimpleAppSettings(BaseSettings):
    pass
```

#### High-performance Service (Optimized)
```python  
@mountainash_settings(
    cache=True,           # Maximum reuse
    templates=False,      # Eliminate template overhead
    multi_format=False,   # Minimal source processing
    namespace="high_perf"
)
class HighPerformanceSettings(BaseSettings):
    pass
```

### Incompatible Combinations
None - all feature flags are designed to work together harmoniously.

### Performance Matrix

| Combination | Init Time | Memory | Runtime | Use Case |
|-------------|-----------|---------|---------|----------|
| All True | Medium | Medium | Fast | Production apps |
| All False | Fast | Low | Medium | Simple/test apps |
| Cache+Multi only | Medium | Low | Fast | Config-heavy apps |
| Cache+Templates only | Low | Low | Fast | Dynamic simple apps |
| Templates+Multi only | Medium | Low | Medium | Complex dev environments |

This comprehensive reference should help developers choose the right feature flag combination for their specific use cases and performance requirements.