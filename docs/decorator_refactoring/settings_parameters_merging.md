# SettingsParameters Merging with @mountainash_settings Decorator

## Overview

The `@mountainash_settings` decorator provides intelligent merging of SettingsParameters objects, allowing users to create incomplete SettingsParameters without specifying `settings_class`, which the decorator will automatically resolve and merge with class-specific parameters.

## The Merging Mechanism

### How It Works

When you pass a SettingsParameters object to a decorated class, the decorator performs a sophisticated merge operation:

1. **User provides SettingsParameters** (potentially incomplete)
2. **Decorator creates local SettingsParameters** with class-specific defaults
3. **Intelligent merge** combines both, resolving conflicts and filling gaps
4. **Final SettingsParameters** contains complete, validated parameters

### Visual Flow

```mermaid
graph TD
    A[User SettingsParameters<br/>settings_class=None<br/>kwargs={host: 'prod', port: 5432}] --> C[Decorator Merge Logic]
    B[Decorator SettingsParameters<br/>settings_class=MySettings<br/>kwargs={}] --> C
    C --> D[Final SettingsParameters<br/>settings_class=MySettings<br/>kwargs={host: 'prod', port: 5432}]
```

## Feature: SettingsParameters Without settings_class

### The "Impossible" Example That Works

```python
from mountainash_settings import mountainash_settings, SettingsParameters
from pydantic_settings import BaseSettings
from pydantic import Field

@mountainash_settings()
class DatabaseSettings(BaseSettings):
    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    username: str = Field(default="user")

# This works even without settings_class!
params = SettingsParameters.create(
    namespace="database",
    host="prod-db.example.com",
    port=5432,
    username="admin"
)

# The decorator intelligently merges and validates
db_settings = DatabaseSettings(settings_parameters=params)
print(db_settings.host)      # "prod-db.example.com"
print(db_settings.port)      # 5432
print(db_settings.username)  # "admin"
```

### Why This Works - Technical Deep Dive

#### Step 1: User Creates Incomplete SettingsParameters

```python
params = SettingsParameters.create(
    namespace="database",
    host="prod-db.example.com", 
    port=5432
)
# Result: SettingsParameters(
#   settings_class=None,  # ← Missing!
#   kwargs={"host": "prod-db.example.com", "port": 5432}
# )
```

#### Step 2: Decorator Detects Provided SettingsParameters

```python
def enhanced_init(self, settings_parameters=None, **kwargs):
    if settings_parameters is None:
        # Create new SettingsParameters
    else:
        # Merge with provided parameters ← This path is taken
```

#### Step 3: Decorator Creates Local SettingsParameters

```python
local_params = SettingsParameters.create(
    namespace=effective_namespace,      # From decorator logic
    config_files=config_files,          # From method parameters  
    settings_class=cls,                 # ← The missing piece!
    **kwargs
)
```

#### Step 4: Intelligent Merge Operation

```python
settings_parameters = SettingsUtils.merge_settings_parameter_objects(
    settings_parameters,  # User's params (settings_class=None)
    local_params         # Decorator's params (settings_class=DatabaseSettings)
)
```

**Merge Result:**
- `settings_class`: `DatabaseSettings` (from local_params)
- `kwargs`: `{"host": "prod-db.example.com", "port": 5432}` (from user params)
- `namespace`: Resolved from merge logic
- All other fields: Intelligently combined

#### Step 5: Validation Against Correct Class

```python
# Now this works because settings_class is set correctly
attribute_kwargs = settings_parameters.get_attribute_settings_kwargs(cls)
# Returns: {"host": "prod-db.example.com", "port": 5432}
```

## Usage Patterns

### Pattern 1: No settings_class (Recommended for Simplicity)

```python
@mountainash_settings()
class AppSettings(BaseSettings):
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")

# Cleanest approach - let decorator handle settings_class
params = SettingsParameters.create(
    namespace="app",
    debug=True,
    log_level="DEBUG"
)

settings = AppSettings(settings_parameters=params)
```

### Pattern 2: Explicit settings_class (Traditional Approach)

```python
# Explicit approach - full control
params = SettingsParameters.create(
    namespace="app",
    settings_class=AppSettings,  # ← Explicitly specified
    debug=True,
    log_level="DEBUG" 
)

settings = AppSettings(settings_parameters=params)
```

### Pattern 3: Class Method (Most Concise)

```python
# Most concise - no SettingsParameters needed
settings = AppSettings.get_settings(
    settings_namespace="app",
    debug=True,
    log_level="DEBUG"
)
```

## Advanced Merging Scenarios

### Scenario 1: Namespace Override

```python
@mountainash_settings(namespace="default_namespace")
class Settings(BaseSettings):
    value: str = Field(default="default")

# User namespace takes precedence
params = SettingsParameters.create(
    namespace="user_namespace",  # ← This wins
    value="user_value"
)

settings = Settings(settings_parameters=params)
print(settings.SETTINGS_NAMESPACE)  # "user_namespace"
```

### Scenario 2: Config File Merging

```python
# User provides some config files
user_params = SettingsParameters.create(
    config_files=["user.yaml"],
    database_host="user-db"
)

# Method call provides additional config files
settings = DatabaseSettings(
    settings_parameters=user_params,
    config_files=["override.yaml"]  # ← Gets merged
)

# Final result has both config files
reconstructed = settings.extract_settings_parameters()
print(reconstructed.config_files)  # ["user.yaml", "override.yaml"]
```

### Scenario 3: Runtime Override Handling

```python
params = SettingsParameters.create(
    namespace="base",
    host="base-host",
    port=5432
)

# Runtime overrides don't affect cached settings
settings = DatabaseSettings(
    settings_parameters=params,
    port=8080  # ← Runtime override
)

print(settings.host)  # "base-host" (from params)
print(settings.port)  # 8080 (runtime override)
```

## Error Handling and Validation

### Invalid Field Names Are Caught

```python
@mountainash_settings()
class StrictSettings(BaseSettings):
    valid_field: str = Field(default="default")

# Invalid field names are filtered out during merge
params = SettingsParameters.create(
    valid_field="good",
    invalid_field="bad"  # ← Will be ignored
)

settings = StrictSettings(settings_parameters=params)
print(settings.valid_field)  # "good" 
# invalid_field is silently ignored (not set on instance)
```

### Type Validation Still Works

```python
@mountainash_settings() 
class TypedSettings(BaseSettings):
    port: int = Field(default=8000)

params = SettingsParameters.create(
    port="8080"  # String value
)

settings = TypedSettings(settings_parameters=params)
print(type(settings.port))  # <class 'int'> - Pydantic converted it
```

## Performance Considerations

### Caching Behavior

The merge operation respects caching settings:

```python
@mountainash_settings(cache=True)  # Caching enabled
class CachedSettings(BaseSettings):
    expensive_computation: str = Field(default="default")

# First call - creates and caches
params1 = SettingsParameters.create(namespace="cache_test")
settings1 = CachedSettings(settings_parameters=params1)

# Second call - retrieves from cache
params2 = SettingsParameters.create(namespace="cache_test")  
settings2 = CachedSettings(settings_parameters=params2)

# Same cached instance (structural parameters identical)
assert settings1 is settings2
```

### Merge Operation Cost

- **Lightweight**: Merge operation is fast and efficient
- **Lazy Evaluation**: Only validates kwargs against class when needed  
- **Memory Efficient**: Reuses existing SettingsParameters structure

## Best Practices

### ✅ Recommended Patterns

```python
# 1. Let decorator handle settings_class
params = SettingsParameters.create(namespace="app", debug=True)
settings = AppSettings(settings_parameters=params)

# 2. Use class method for simple cases  
settings = AppSettings.get_settings(settings_namespace="app", debug=True)

# 3. Explicit settings_class for shared parameters
shared_params = SettingsParameters.create(
    namespace="shared",
    settings_class=AppSettings,
    config_files=["shared.yaml"]
)
```

### ❌ Patterns to Avoid

```python
# Don't: Try to use SettingsParameters with wrong class
db_params = SettingsParameters.create(
    settings_class=DatabaseSettings,
    invalid_web_field="value"  # Wrong class fields
)
web_settings = WebSettings(settings_parameters=db_params)  # Confusing!

# Don't: Rely on merge behavior for incompatible types
params = SettingsParameters.create(port="not-a-number")
# Better to catch type errors early
```

## Integration with Existing Code

### Drop-in Replacement for MountainAshBaseSettings

```python
# Before: Using subclass
class OldSettings(MountainAshBaseSettings):
    host: str = Field(default="localhost")

params = SettingsParameters.create(
    settings_class=OldSettings,
    host="prod-host"
)

# After: Using decorator (identical behavior)
@mountainash_settings()
class NewSettings(BaseSettings):
    host: str = Field(default="localhost")

# Same SettingsParameters work identically!
# Just omit settings_class for cleaner code
params = SettingsParameters.create(
    # settings_class not needed anymore!
    host="prod-host"
)
```

### Library Integration

```python
# Library function that creates SettingsParameters
def create_database_params(environment: str):
    if environment == "prod":
        return SettingsParameters.create(
            namespace="production",
            # No settings_class - works with any decorated class!
            host="prod-db.internal", 
            port=5432,
            ssl_mode="require"
        )
    else:
        return SettingsParameters.create(
            namespace="development", 
            host="localhost",
            port=5432
        )

# Works with any decorated database settings class
@mountainash_settings()
class DatabaseSettings(BaseSettings):
    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    ssl_mode: str = Field(default="prefer")

prod_params = create_database_params("prod")
db_settings = DatabaseSettings(settings_parameters=prod_params)
```

## Troubleshooting

### Common Issues and Solutions

#### Issue: "Settings fields not being set"

```python
# Problem: Fields seem to be ignored
params = SettingsParameters.create(unknown_field="value")
settings = MySettings(settings_parameters=params)
# unknown_field is not set on settings instance
```

**Solution**: Ensure field names match your settings class definition.

#### Issue: "Unexpected caching behavior"  

```python
# Problem: Changes not reflected
params = SettingsParameters.create(namespace="test", value="old")
settings1 = CachedSettings(settings_parameters=params)

params.kwargs["value"] = "new"  # Don't modify existing params!
settings2 = CachedSettings(settings_parameters=params)
# settings2.value is still "old"
```

**Solution**: Create new SettingsParameters instead of modifying existing ones.

#### Issue: "Merge conflicts"

```python
# Problem: Unclear which value takes precedence
params = SettingsParameters.create(namespace="conflict")
settings = MySettings(
    settings_parameters=params,
    namespace="different"  # Which namespace wins?
)
```

**Solution**: Understand merge precedence (runtime parameters override SettingsParameters).

## Implementation Details

### Merge Algorithm

The merge operation follows these precedence rules:

1. **Runtime parameters** (method arguments) have highest priority
2. **User SettingsParameters** take precedence over defaults  
3. **Decorator SettingsParameters** provide fallback values
4. **Class defaults** are used when nothing else is specified

### Field Validation Process

1. **Parse user kwargs** into valid and invalid field names
2. **Merge with decorator defaults** 
3. **Validate against target class** field definitions
4. **Filter out invalid fields** (silently ignored)
5. **Apply Pydantic validation** for type conversion and constraints

This sophisticated merging system provides the flexibility to omit `settings_class` while maintaining full compatibility with the existing SettingsParameters infrastructure.

## Advanced Pattern: Dynamic Settings Class Resolution

### Overview

Beyond the smart merging capability, SettingsParameters can carry class type information throughout your application, enabling powerful dynamic resolution patterns where calling code doesn't need to know the specific settings class type.

### The Dynamic Resolution Pattern

This enterprise-grade pattern consists of four phases:

1. **Setup Phase**: Define decorated settings classes and create SettingsParameters with embedded class information
2. **Optional Caching Phase**: Pre-populate cache during application startup
3. **Parameter Flow Phase**: Pass SettingsParameters throughout application layers
4. **Dynamic Resolution Phase**: Use `get_settings()` to dynamically resolve the correct class type

### Pattern Implementation

```python
from mountainash_settings import mountainash_settings, SettingsParameters, get_settings

# Phase 1: Setup - Define settings classes with embedded type information
@mountainash_settings(cache=True)
class DatabaseSettings(BaseSettings):
    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    database: str = Field(default="myapp")

@mountainash_settings(cache=True)
class RedisSettings(BaseSettings):
    host: str = Field(default="localhost")
    port: int = Field(default=6379)
    db: int = Field(default=0)

# Create SettingsParameters with class information embedded
database_params = SettingsParameters.create(
    namespace="production_db",
    settings_class=DatabaseSettings,  # ← Type information travels with params
    host="prod-db.example.com",
    database="production"
)

redis_params = SettingsParameters.create(
    namespace="production_cache",
    settings_class=RedisSettings,     # ← Different class type
    host="redis.example.com",
    db=1
)

# Phase 2: Optional pre-population (during app startup)
db_settings = get_settings(settings_parameters=database_params)    # Cached
redis_settings = get_settings(settings_parameters=redis_params)   # Cached

# Phase 3: Parameters flow through application
def business_logic(db_params: SettingsParameters, cache_params: SettingsParameters):
    database_service(db_params)    # Pass parameters, not instances
    cache_service(cache_params)

# Phase 4: Dynamic resolution without type knowledge
def database_service(params: SettingsParameters):
    # This function doesn't know it's getting DatabaseSettings!
    settings = get_settings(settings_parameters=params)  # Returns DatabaseSettings
    connect_to_database(settings.host, settings.port, settings.database)

def cache_service(params: SettingsParameters):  
    # This function doesn't know it's getting RedisSettings!
    settings = get_settings(settings_parameters=params)  # Returns RedisSettings
    connect_to_cache(settings.host, settings.port, settings.db)
```

### Generic Settings Resolver

The pattern enables completely generic settings resolution:

```python
def get_settings_for_service(service_name: str, all_configs: dict[str, SettingsParameters]) -> BaseSettings:
    """Generic resolver - caller doesn't know what settings class they'll get!"""
    if service_name not in all_configs:
        raise ValueError(f"Unknown service: {service_name}")
        
    params = all_configs[service_name]
    
    # Magic! get_settings uses settings_class from SettingsParameters
    # to dynamically resolve and return the correct settings instance
    return get_settings(settings_parameters=params)

# Usage - completely dynamic
configs = {
    "database": database_params,    # Will resolve to DatabaseSettings
    "cache": redis_params,         # Will resolve to RedisSettings
    "api": api_params             # Will resolve to ApiSettings
}

# These calls are completely type-agnostic
db = get_settings_for_service("database", configs)    # Gets DatabaseSettings
cache = get_settings_for_service("cache", configs)    # Gets RedisSettings  
api = get_settings_for_service("api", configs)        # Gets ApiSettings
```

### Pattern Benefits

#### 🎯 **Type Safety with Dynamic Resolution**
- SettingsParameters carries concrete type information
- `get_settings()` returns the exact class type specified in `settings_class`
- No casting or type guessing required

#### 🔄 **Decoupled Architecture**
- Services receive SettingsParameters, not concrete settings instances
- Business logic doesn't depend on specific settings classes
- Easy to swap settings implementations

#### ⚡ **Efficient Caching**
- Automatic cache management based on SettingsParameters identity
- Pre-population during startup for hot paths
- Cache hits across different call sites for same parameters

#### 📊 **Configuration Flow**
- SettingsParameters flow naturally through application layers
- Clean separation between configuration and business logic
- Easy to trace configuration sources and transformations

#### 🔧 **Runtime Flexibility**
- Override capabilities preserved at resolution time
- Dynamic configuration changes without code changes
- A/B testing and feature flag integration

### Enterprise Use Cases

#### Microservices Configuration

```python
# Service registry pattern
service_configs = {
    "user-service": SettingsParameters.create(
        settings_class=DatabaseSettings,
        namespace="user_db",
        host="user-db.cluster.local"
    ),
    "order-service": SettingsParameters.create(
        settings_class=DatabaseSettings, 
        namespace="order_db",
        host="order-db.cluster.local"
    ),
    "cache-service": SettingsParameters.create(
        settings_class=RedisSettings,
        namespace="shared_cache", 
        host="redis.cluster.local"
    )
}

def get_service_settings(service_name: str):
    return get_settings(settings_parameters=service_configs[service_name])
```

#### Multi-Tenant Configuration

```python
def create_tenant_database_config(tenant_id: str) -> SettingsParameters:
    return SettingsParameters.create(
        settings_class=DatabaseSettings,
        namespace=f"tenant_{tenant_id}",
        host=f"db-{tenant_id}.example.com",
        database=f"tenant_{tenant_id}_db"
    )

# Usage
tenant_params = create_tenant_database_config("acme_corp")
tenant_db = get_settings(settings_parameters=tenant_params)  # DatabaseSettings for ACME Corp
```

#### Plugin Architecture

```python
# Plugin system where plugins register their settings types
plugin_registry = {
    "payment_processor": SettingsParameters.create(
        settings_class=PaymentSettings,
        namespace="payment_prod",
        api_key="pk_live_...",
        webhook_secret="whsec_..."
    ),
    "email_service": SettingsParameters.create(
        settings_class=EmailSettings,
        namespace="email_prod", 
        smtp_host="smtp.example.com",
        api_key="email_api_key"
    )
}

def load_plugin_settings(plugin_name: str):
    """Plugin loader that works with any settings type."""
    return get_settings(settings_parameters=plugin_registry[plugin_name])
```

### Performance Characteristics

#### Cache Efficiency
- **First Resolution**: Creates and caches instance based on SettingsParameters identity
- **Subsequent Resolutions**: Cache hit returns same instance (O(1) lookup)
- **Memory Usage**: One instance per unique SettingsParameters configuration

#### Resolution Speed
- **Type Resolution**: Zero overhead - class type embedded in SettingsParameters
- **Instance Creation**: Only on cache miss, leverages Pydantic's optimized instantiation
- **Parameter Validation**: Occurs once during SettingsParameters creation

### Troubleshooting

#### Common Issues

**Issue**: `AttributeError` when resolving settings
```python
# Problem: settings_class not set in SettingsParameters
params = SettingsParameters.create(namespace="test")  # Missing settings_class
settings = get_settings(settings_parameters=params)   # Error!
```
**Solution**: Always specify `settings_class` for dynamic resolution patterns.

**Issue**: Unexpected cache behavior
```python  
# Problem: Modifying SettingsParameters after creation affects cache identity
params = SettingsParameters.create(settings_class=MySettings, host="localhost")
get_settings(settings_parameters=params)  # Cached
params.kwargs["host"] = "remote"           # Don't modify after creation!
```
**Solution**: Create new SettingsParameters instead of modifying existing ones.

**Issue**: Type confusion in generic code
```python
# Problem: Assuming specific type in generic function
def process_settings(params: SettingsParameters):
    settings = get_settings(settings_parameters=params)
    return settings.database_url  # Error if settings is RedisSettings!
```
**Solution**: Use isinstance checks or access only common BaseSettings attributes.

This dynamic resolution pattern transforms SettingsParameters from simple parameter containers into powerful, type-aware configuration objects that enable sophisticated enterprise architecture patterns.