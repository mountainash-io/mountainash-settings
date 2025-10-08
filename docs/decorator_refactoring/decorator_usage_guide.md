# @mountainash_settings Decorator Usage Guide

## Overview

The `@mountainash_settings` decorator transforms standard Pydantic BaseSettings classes into powerful configuration management classes that leverage the full mountainash-settings infrastructure. This provides advanced features like smart caching, template resolution, multi-format configuration support, and metadata tracking while maintaining the familiar Pydantic interface.

## Quick Start

### Basic Usage

```python
from pydantic import Field
from pydantic_settings import BaseSettings
from mountainash_settings import mountainash_settings

@mountainash_settings()
class AppSettings(BaseSettings):
    debug: bool = Field(default=False)
    app_name: str = Field(default="MyApp")
    port: int = Field(default=8000)

# Use like any Pydantic BaseSettings class
settings = AppSettings()
print(settings.app_name)  # "MyApp"

# With runtime overrides
settings = AppSettings(debug=True, port=9000)
print(settings.debug)  # True
print(settings.port)   # 9000
```

### Without Parentheses

```python
@mountainash_settings
class SimpleSettings(BaseSettings):
    timeout: int = Field(default=30)
    retries: int = Field(default=3)

settings = SimpleSettings()
```

## Feature Configuration

The decorator accepts several parameters to control its behavior:

```python
@mountainash_settings(
    cache=True,           # Enable smart caching (default: True)
    templates=True,       # Enable template resolution (default: True)
    multi_format=True,    # Enable multi-format config files (default: True)
    namespace="my_app"    # Set namespace for caching (default: None)
)
class AdvancedSettings(BaseSettings):
    # Your fields here
    pass
```

### Feature Flags Explained

#### `cache` (default: True)
Enables integration with mountainash-settings smart caching system:
- **True**: Uses SettingsManager for efficient caching based on structural parameters
- **False**: Direct Pydantic instantiation without caching

```python
@mountainash_settings(cache=True)
class CachedSettings(BaseSettings):
    value: str = Field(default="test")

# These will use the same cached instance
settings1 = CachedSettings.get_settings()
settings2 = CachedSettings.get_settings()
assert settings1 is settings2  # True - same instance from cache
```

#### `templates` (default: True)
Enables template resolution for dynamic configuration values:
- **True**: Adds template methods and post-initialization template processing
- **False**: Standard Pydantic behavior without template features

```python
@mountainash_settings(templates=True)
class TemplateSettings(BaseSettings):
    app_name: str = Field(default="MyApp")
    log_file: str = Field(default="logs/{app_name}.log")

settings = TemplateSettings(app_name="ProductionApp")
formatted = settings.format_template_from_settings("logs/{app_name}_debug.log")
print(formatted)  # "logs/ProductionApp_debug.log"
```

#### `multi_format` (default: True)
Enables support for YAML, TOML, and JSON configuration files:
- **True**: Adds support for multiple configuration file formats
- **False**: Standard Pydantic file support only

```python
@mountainash_settings(multi_format=True)
class MultiSettings(BaseSettings):
    database_url: str = Field(default="sqlite:///app.db")
    
    model_config = SettingsConfigDict(
        yaml_file="config.yaml",
        toml_file="config.toml"
    )
```

#### `namespace` (default: None)
Sets a specific namespace for caching and configuration isolation:

```python
@mountainash_settings(namespace="production")
class ProductionSettings(BaseSettings):
    api_key: str = Field(default="")

@mountainash_settings(namespace="development")  
class DevelopmentSettings(BaseSettings):
    api_key: str = Field(default="dev-key")

# These will be cached separately due to different namespaces
```

## Advanced Usage Patterns

### Using with SettingsParameters

The decorator integrates seamlessly with the existing SettingsParameters infrastructure:

```python
from mountainash_settings import SettingsParameters

@mountainash_settings()
class APISettings(BaseSettings):
    base_url: str = Field(default="https://api.example.com")
    api_key: str = Field(default="")
    timeout: int = Field(default=30)

# Traditional approach - explicit settings_class
params = SettingsParameters.create(
    namespace="api_service",
    settings_class=APISettings,
    config_files=["api_config.yaml"],
    base_url="https://prod-api.example.com",
    api_key="secret-key-123"
)

# Use parameters with decorated class
settings = APISettings(settings_parameters=params)
print(settings.base_url)  # "https://prod-api.example.com"
```

#### Smart SettingsParameters Merging

**🚀 New Feature**: The decorator can intelligently merge SettingsParameters even when `settings_class` is not specified:

```python
# No settings_class needed! The decorator handles it automatically
params = SettingsParameters.create(
    namespace="api_service",
    # settings_class=APISettings,  ← Not needed!
    config_files=["api_config.yaml"],
    base_url="https://prod-api.example.com", 
    api_key="secret-key-123"
)

# The decorator merges and validates automatically
settings = APISettings(settings_parameters=params)
print(settings.base_url)  # "https://prod-api.example.com" - Works perfectly!
```

This works through intelligent parameter merging - see [SettingsParameters Merging Guide](settings_parameters_merging.md) for detailed explanation of how this feature works.

#### Advanced: Dynamic Settings Class Resolution

For enterprise applications, SettingsParameters can carry class type information throughout your application, enabling powerful dynamic resolution patterns:

```python
# Setup: SettingsParameters with embedded class information
database_params = SettingsParameters.create(
    namespace="production_db",
    settings_class=DatabaseSettings,  # ← Type information travels with params
    host="prod-db.example.com"
)

redis_params = SettingsParameters.create(
    namespace="production_cache", 
    settings_class=RedisSettings,     # ← Different class type
    host="redis.example.com"
)

# Generic resolution - caller doesn't need to know the class type!
def get_settings_for_service(service_name: str, configs: dict) -> BaseSettings:
    params = configs[service_name]
    return get_settings(settings_parameters=params)  # Dynamic resolution!

# Usage
service_configs = {"database": database_params, "cache": redis_params}
db = get_settings_for_service("database", service_configs)    # Gets DatabaseSettings
cache = get_settings_for_service("cache", service_configs)   # Gets RedisSettings
```

This enables powerful enterprise patterns like microservices configuration, multi-tenant setups, and plugin architectures. See the [Dynamic Class Resolution section](settings_parameters_merging.md#advanced-pattern-dynamic-settings-class-resolution) for comprehensive examples.

### get_settings() Class Method

All decorated classes gain a `get_settings()` class method that integrates with the caching system:

```python
@mountainash_settings()
class DatabaseSettings(BaseSettings):
    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    database: str = Field(default="myapp")

# Using get_settings with caching
settings = DatabaseSettings.get_settings(
    host="prod-db.example.com",
    port=5432,
    database="production"
)

# Alternative syntax with SettingsParameters
params = SettingsParameters.create(
    settings_class=DatabaseSettings,
    namespace="database",
    host="prod-db.example.com"
)
settings = DatabaseSettings.get_settings(settings_parameters=params)
```

### Template Resolution Features

When `templates=True`, decorated classes gain several template-related methods:

#### format_template_from_settings()
Format template strings using values from the settings instance:

```python
@mountainash_settings(templates=True)
class AppSettings(BaseSettings):
    environment: str = Field(default="dev")
    app_name: str = Field(default="myapp")
    version: str = Field(default="1.0.0")

settings = AppSettings(environment="production", app_name="webapp")

# Format templates
log_path = settings.format_template_from_settings("logs/{environment}/{app_name}.log")
config_path = settings.format_template_from_settings("config/{app_name}-{version}.yaml")

print(log_path)    # "logs/production/webapp.log"  
print(config_path) # "config/webapp-1.0.0.yaml"
```

#### init_setting_from_template()
Initialize setting values from templates during object creation:

```python
@mountainash_settings(templates=True)
class StorageSettings(BaseSettings):
    bucket_prefix: str = Field(default="myapp")
    environment: str = Field(default="dev")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Use template to set derived values
        self.bucket_name = self.init_setting_from_template(
            "{bucket_prefix}-{environment}-data",
            getattr(self, 'bucket_name', None)
        )
```

#### update_settings_from_dict()
Dynamically update multiple settings from a dictionary:

```python
settings = AppSettings()
updates = {
    "environment": "staging",
    "app_name": "updated-app",
    "version": "2.0.0"
}
settings.update_settings_from_dict(updates)
```

### Multi-Format Configuration

When `multi_format=True`, decorated classes support YAML, TOML, and JSON configuration files:

```python
@mountainash_settings(multi_format=True)
class ConfigSettings(BaseSettings):
    database_url: str = Field(default="sqlite:///default.db")
    redis_url: str = Field(default="redis://localhost")
    api_timeout: int = Field(default=30)
    
    model_config = SettingsConfigDict(
        yaml_file="settings.yaml",
        toml_file="settings.toml", 
        json_file="settings.json"
    )

# Will load from YAML, TOML, and JSON files in addition to environment variables
settings = ConfigSettings()
```

Example configuration files:

**settings.yaml:**
```yaml
database_url: "postgresql://localhost/myapp"
redis_url: "redis://cache-server:6379"
api_timeout: 60
```

**settings.toml:**
```toml
database_url = "postgresql://localhost/myapp"
redis_url = "redis://cache-server:6379" 
api_timeout = 60
```

**settings.json:**
```json
{
  "database_url": "postgresql://localhost/myapp",
  "redis_url": "redis://cache-server:6379",
  "api_timeout": 60
}
```

### Metadata Tracking

Decorated classes automatically track configuration metadata for traceability:

```python
@mountainash_settings()
class TrackedSettings(BaseSettings):
    service_name: str = Field(default="myservice")
    
settings = TrackedSettings(service_name="production-service")

# Access metadata
print(settings.SETTINGS_NAMESPACE)        # Namespace used
print(settings.SETTINGS_CLASS_NAME)       # "TrackedSettings"
print(settings.SETTINGS_SOURCE_KWARGS)    # Runtime overrides used
print(settings.SETTINGS_SOURCE_ENV_PREFIX) # Environment prefix if any

# Extract SettingsParameters for reuse
params = settings.extract_settings_parameters()
print(params.namespace)        # Original namespace
print(params.settings_class)   # TrackedSettings class
```

## Configuration File Examples

### Environment Variables
```bash
# Standard Pydantic environment variable support
export MY_APP_DEBUG=true
export MY_APP_PORT=8080
export MY_APP_DATABASE_URL="postgresql://localhost/myapp"
```

### YAML Configuration
```yaml
# config.yaml
debug: false
port: 8000
database:
  host: localhost
  port: 5432
  name: myapp
logging:
  level: INFO
  file: "logs/{app_name}.log"  # Templates supported
```

### TOML Configuration  
```toml
# config.toml
debug = false
port = 8000

[database]
host = "localhost"
port = 5432
name = "myapp"

[logging]
level = "INFO"
file = "logs/{app_name}.log"
```

### JSON Configuration
```json
{
  "debug": false,
  "port": 8000,
  "database": {
    "host": "localhost", 
    "port": 5432,
    "name": "myapp"
  },
  "logging": {
    "level": "INFO",
    "file": "logs/{app_name}.log"
  }
}
```

## Best Practices

### 1. Use Feature Flags Appropriately

```python
# For simple settings without templates or multi-format needs
@mountainash_settings(templates=False, multi_format=False)
class SimpleSettings(BaseSettings):
    debug: bool = Field(default=False)

# For complex applications with dynamic configuration  
@mountainash_settings(
    cache=True,
    templates=True,
    multi_format=True,
    namespace="complex_app"
)
class ComplexSettings(BaseSettings):
    # Complex configuration here
    pass
```

### 2. Namespace Your Settings

```python
# Use namespaces to avoid cache collisions
@mountainash_settings(namespace="user_service")
class UserSettings(BaseSettings):
    pass

@mountainash_settings(namespace="order_service") 
class OrderSettings(BaseSettings):
    pass
```

### 3. Combine with SettingsParameters for Advanced Use Cases

```python
# Build settings parameters programmatically
def create_service_settings(service_name: str, environment: str):
    return SettingsParameters.create(
        namespace=f"{service_name}_{environment}",
        settings_class=ServiceSettings,
        config_files=[f"config/{service_name}/{environment}.yaml"],
        env_prefix=f"{service_name.upper()}_{environment.upper()}",
        service_name=service_name,
        environment=environment
    )

params = create_service_settings("auth", "production")
settings = ServiceSettings(settings_parameters=params)
```

### 4. Use Templates for Dynamic Configuration

```python
@mountainash_settings(templates=True)
class DeploymentSettings(BaseSettings):
    environment: str = Field(default="dev")
    service_name: str = Field(default="myservice")
    
    # Templates will be resolved automatically
    log_file: str = Field(default="logs/{environment}/{service_name}.log")
    config_path: str = Field(default="config/{service_name}/{environment}.yaml")
    database_name: str = Field(default="{service_name}_{environment}")

settings = DeploymentSettings(environment="prod", service_name="userservice")
print(settings.log_file)        # "logs/prod/userservice.log"
print(settings.database_name)   # "userservice_prod"
```

## Performance Considerations

### Caching Behavior
- Cached instances are shared based on structural parameters (namespace, config files, settings class)
- Runtime parameters (kwargs) don't affect cache identity
- Use `cache=False` for temporary or test settings that shouldn't be cached

### Memory Usage
- Template resolution happens post-initialization
- Multi-format file loading is lazy - files are only read when needed
- Metadata tracking adds minimal memory overhead

### Template Performance
- Template resolution uses Python's built-in `string.Formatter`
- Templates are resolved once during initialization or when explicitly called
- For high-frequency template formatting, consider caching formatted results

## Error Handling

### Common Errors and Solutions

#### AttributeError in Templates
```python
# Error: Template references non-existent field
settings.format_template_from_settings("path/{missing_field}/file.log")
# AttributeError: The object does not have an attribute named 'missing_field'

# Solution: Ensure all template fields exist or provide defaults
@mountainash_settings(templates=True)
class SafeSettings(BaseSettings):
    missing_field: str = Field(default="default_value")
```

#### Configuration File Not Found
```python
# Error: Config file doesn't exist
@mountainash_settings(multi_format=True)
class Settings(BaseSettings):
    model_config = SettingsConfigDict(yaml_file="nonexistent.yaml")
    
# Solution: Use optional files or ensure files exist
model_config = SettingsConfigDict(yaml_file="optional.yaml")
```

#### Circular Dependencies
```python
# Error: Settings classes that reference each other can cause recursion
# Solution: Use cache=False for one of the classes or restructure dependencies

@mountainash_settings(cache=False)  # Disable caching to prevent recursion
class DependentSettings(BaseSettings):
    pass
```

## Testing with the Decorator

### Unit Testing
```python
import pytest
from your_app.settings import AppSettings

def test_basic_settings():
    settings = AppSettings(debug=True, port=9000)
    assert settings.debug is True
    assert settings.port == 9000

def test_template_formatting():
    settings = AppSettings(app_name="testapp")
    result = settings.format_template_from_settings("logs/{app_name}.log")
    assert result == "logs/testapp.log"
```

### Integration Testing
```python
def test_settings_parameters_integration():
    params = SettingsParameters.create(
        settings_class=AppSettings,
        namespace="test",
        debug=True
    )
    settings = AppSettings(settings_parameters=params)
    assert settings.debug is True
    assert settings.SETTINGS_NAMESPACE == "test"
```

### Test Configuration
```python
@mountainash_settings(cache=False)  # Disable caching for tests
class TestSettings(BaseSettings):
    test_value: str = Field(default="test")

# Or use temporary namespaces
@mountainash_settings(namespace=f"test_{uuid4()}")
class IsolatedTestSettings(BaseSettings):
    pass
```

This guide provides a comprehensive overview of using the `@mountainash_settings` decorator effectively. For more advanced use cases and migration from MountainAshBaseSettings, see the migration guide and API reference documentation.