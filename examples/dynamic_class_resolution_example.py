#!/usr/bin/env python3
"""
Example demonstrating dynamic settings class resolution pattern with MountainAshBaseSettings.

This pattern allows SettingsParameters to carry the class information
throughout the application, enabling dynamic resolution at runtime without
the caller needing to know the specific settings class type.
"""

from pydantic import Field
from mountainash_settings import MountainAshBaseSettings, SettingsParameters, get_settings

print("=== Dynamic Settings Class Resolution Pattern ===\n")

# Step 1: Define different settings classes with MountainAshBaseSettings
class DatabaseSettings(MountainAshBaseSettings):
    """Database configuration settings."""
    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    username: str = Field(default="user")
    password: str = Field(default="password")
    database: str = Field(default="myapp")

class RedisSettings(MountainAshBaseSettings):
    """Redis configuration settings."""
    host: str = Field(default="localhost")
    port: int = Field(default=6379)
    password: str = Field(default="")
    db: int = Field(default=0)

class ApiSettings(MountainAshBaseSettings):
    """API service configuration."""
    base_url: str = Field(default="http://localhost:8000")
    api_key: str = Field(default="dev-key")
    timeout: int = Field(default=30)
    rate_limit: int = Field(default=100)

print("1. Setup Phase - Create SettingsParameters with class information:")

# Step 2: Setup phase - create SettingsParameters that know their target class
database_params = SettingsParameters.create(
    namespace="production_db",
    settings_class=DatabaseSettings,  # ← Class information embedded!
    host="prod-db-cluster.example.com",
    port=5432,
    username="prod_user",
    database="production"
)

redis_params = SettingsParameters.create(
    namespace="production_cache", 
    settings_class=RedisSettings,     # ← Different class!
    host="redis-cluster.example.com",
    port=6379,
    password="redis-secret",
    db=1
)

api_params = SettingsParameters.create(
    namespace="external_api",
    settings_class=ApiSettings,       # ← Another class!
    base_url="https://api.production.com",
    api_key="prod-api-key-xyz",
    timeout=60,
    rate_limit=1000
)

print(f"   Database params target: {database_params.settings_class.__name__}")
print(f"   Redis params target: {redis_params.settings_class.__name__}")
print(f"   API params target: {api_params.settings_class.__name__}")

print("\n2. Optional: Pre-populate cache during setup:")

# Step 2 (optional): Pre-populate cache during application startup
db_settings = get_settings(settings_parameters=database_params)
redis_settings = get_settings(settings_parameters=redis_params)  
api_settings = get_settings(settings_parameters=api_params)

print(f"   ✅ DatabaseSettings cached: {db_settings.host}")
print(f"   ✅ RedisSettings cached: {redis_settings.host}")
print(f"   ✅ ApiSettings cached: {api_settings.base_url}")

print("\n3. Runtime - Pass SettingsParameters throughout the app:")

# Step 3: SettingsParameters flow through the application
def application_layer():
    """Simulate application layer passing parameters around."""
    # In real app, these might come from config files, environment, etc.
    service_configs = {
        "database": database_params,
        "cache": redis_params,
        "external_api": api_params
    }
    
    # Pass to business logic
    business_logic_layer(service_configs)

def business_logic_layer(configs):
    """Simulate business logic that needs different settings."""
    print("   📋 Business logic received configuration parameters")
    
    # Pass specific configs to service layers
    database_service(configs["database"])
    cache_service(configs["cache"]) 
    api_client_service(configs["external_api"])

def database_service(db_params: SettingsParameters):
    """Database service that needs database settings."""
    print(f"   🗄️  Database service received params for: {db_params.settings_class.__name__}")
    
    # This method doesn't know what specific class it needs!
    # But the SettingsParameters knows and get_settings resolves it dynamically
    settings = get_settings(settings_parameters=db_params)
    
    print(f"      → Connected to: {settings.host}:{settings.port}/{settings.database}")
    print(f"      → Settings type: {type(settings).__name__}")
    return settings

def cache_service(cache_params: SettingsParameters):
    """Cache service that needs Redis settings.""" 
    print(f"   🏃 Cache service received params for: {cache_params.settings_class.__name__}")
    
    # Dynamic resolution - get_settings knows to return RedisSettings!
    settings = get_settings(settings_parameters=cache_params)
    
    print(f"      → Cache at: {settings.host}:{settings.port}/db{settings.db}")
    print(f"      → Settings type: {type(settings).__name__}")
    return settings

def api_client_service(api_params: SettingsParameters):
    """API client that needs API settings."""
    print(f"   🌐 API client received params for: {api_params.settings_class.__name__}")
    
    # Dynamic resolution - get_settings returns ApiSettings!
    settings = get_settings(settings_parameters=api_params)
    
    print(f"      → API endpoint: {settings.base_url}")
    print(f"      → Rate limit: {settings.rate_limit}/min")
    print(f"      → Settings type: {type(settings).__name__}")
    return settings

# Step 4: Run the application flow
application_layer()

print("\n4. Advanced: Generic settings resolver function:")

def get_settings_for_service(service_name: str, all_configs: dict) -> MountainAshBaseSettings:
    """
    Generic function that can resolve any settings class dynamically.
    The caller doesn't need to know what specific settings class they'll get!
    """
    if service_name not in all_configs:
        raise ValueError(f"Unknown service: {service_name}")
        
    params = all_configs[service_name]
    
    # Magic! get_settings uses the settings_class from SettingsParameters
    # to dynamically resolve and return the correct settings instance
    resolved_settings = get_settings(settings_parameters=params)
    
    print(f"   🔍 Resolved {service_name} → {type(resolved_settings).__name__}")
    return resolved_settings

# Demonstrate generic resolution
configs = {
    "database": database_params,
    "cache": redis_params, 
    "external_api": api_params
}

# These calls don't know what class they'll get - it's all dynamic!
db = get_settings_for_service("database", configs)
cache = get_settings_for_service("cache", configs) 
api = get_settings_for_service("external_api", configs)

print(f"   → Database host: {db.host}")
print(f"   → Cache db: {cache.db}")  
print(f"   → API timeout: {api.timeout}")

print("\n5. Caching behavior verification:")

# Step 5: Verify caching works correctly
print("   Testing cache hits...")

# These should return the same cached instances
db1 = get_settings(settings_parameters=database_params)
db2 = get_settings(settings_parameters=database_params)
cache1 = get_settings(settings_parameters=redis_params)
cache2 = get_settings(settings_parameters=redis_params)

print(f"   Database instances identical: {db1 is db2}")  # Should be True
print(f"   Cache instances identical: {cache1 is cache2}")      # Should be True
print(f"   Different types are different: {db1 is cache1}")     # Should be False

print("\n6. Configuration override at runtime:")

# Step 6: Runtime configuration override
override_db_params = SettingsParameters.create(
    namespace="production_db",  # Same namespace for cache key
    settings_class=DatabaseSettings,
    host="prod-db-cluster.example.com", 
    port=5432,
    username="prod_user",
    database="production",
    # Runtime override:
    timeout=300  # Not a real field, just for demo
)

# With runtime overrides
override_settings = get_settings(
    settings_parameters=override_db_params,
    password="runtime-password"  # Runtime override
)

print(f"   Runtime override host: {override_settings.host}")
print(f"   Runtime override password: {override_settings.password}")

print("\n=== Pattern enables powerful, type-safe, dynamic configuration! ===")

print("\n📊 Pattern Benefits:")
print("   ✅ Type safety - SettingsParameters carries class information")
print("   ✅ Dynamic resolution - Callers don't need to know specific types")
print("   ✅ Caching efficiency - Automatic cache management")
print("   ✅ Configuration flow - Parameters flow naturally through app layers")
print("   ✅ Runtime flexibility - Override capabilities preserved")
print("   ✅ Decoupling - Services don't depend on specific settings classes")