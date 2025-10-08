#!/usr/bin/env python3
"""
Comprehensive example demonstrating advanced SettingsParameters patterns with MountainAshBaseSettings.
Shows different configuration patterns for enterprise applications.
"""

from pydantic import Field
from mountainash_settings import MountainAshBaseSettings, SettingsParameters, get_settings

print("=== Comprehensive SettingsParameters Patterns Example ===\n")

# Define our settings classes with MountainAshBaseSettings
class DatabaseSettings(MountainAshBaseSettings):
    """Database configuration settings."""
    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    username: str = Field(default="user")
    database: str = Field(default="myapp")
    connection_pool_size: int = Field(default=10)

class RedisSettings(MountainAshBaseSettings):
    """Redis cache configuration."""
    host: str = Field(default="localhost")
    port: int = Field(default=6379)
    password: str = Field(default="")
    db: int = Field(default=0)
    max_connections: int = Field(default=100)

class ApiSettings(MountainAshBaseSettings):
    """External API configuration.""" 
    base_url: str = Field(default="https://api.example.com")
    api_key: str = Field(default="dev-key")
    timeout: int = Field(default=30)
    rate_limit: int = Field(default=100)

print("=== Pattern 1: Direct Instantiation (for known target classes) ===")
print("Use when you know what settings class you're targeting\n")

# Direct instantiation with SettingsParameters
def setup_database_connection():
    """Setup function that knows it needs DatabaseSettings."""
    # Create parameters with explicit settings class
    params = SettingsParameters.create(
        namespace="production_db",
        settings_class=DatabaseSettings,
        host="prod-db.cluster.example.com",
        port=5432,
        username="prod_user",
        database="production",
        connection_pool_size=50
    )
    
    # Direct instantiation with SettingsParameters
    db_settings = DatabaseSettings(settings_parameters=params)
    
    print(f"1. Database Setup:")
    print(f"   Host: {db_settings.host}")
    print(f"   Database: {db_settings.database}")
    print(f"   Pool Size: {db_settings.connection_pool_size}")
    print(f"   Settings Class: {db_settings.SETTINGS_CLASS.__name__}")
    print(f"   Namespace: {db_settings.SETTINGS_NAMESPACE}")
    
    return db_settings

def setup_redis_cache():
    """Setup function that knows it needs RedisSettings."""
    # Create parameters with explicit settings class
    params = SettingsParameters.create(
        namespace="production_cache",
        settings_class=RedisSettings,
        host="redis-cluster.example.com", 
        port=6379,
        password="redis-secret",
        db=1,
        max_connections=200
    )
    
    # Direct instantiation with SettingsParameters
    redis_settings = RedisSettings(settings_parameters=params)
    
    print(f"2. Redis Setup:")
    print(f"   Host: {redis_settings.host}")
    print(f"   DB: {redis_settings.db}")
    print(f"   Max Connections: {redis_settings.max_connections}")
    print(f"   Settings Class: {redis_settings.SETTINGS_CLASS.__name__}")
    print(f"   Namespace: {redis_settings.SETTINGS_NAMESPACE}")
    
    return redis_settings

# Execute direct instantiation examples
db_settings = setup_database_connection()
redis_settings = setup_redis_cache()

print("\n=== Pattern 2: Dynamic Resolution (for unknown target classes) ===")
print("Use when target class is determined at runtime\n")

# Dynamic resolution - settings_class needed for type information
service_registry = {
    "database": SettingsParameters.create(
        namespace="production_db",
        settings_class=DatabaseSettings,  # ← Type info for dynamic resolution
        host="prod-db.cluster.example.com",
        port=5432,
        username="prod_user",
        database="production"
    ),
    "cache": SettingsParameters.create(
        namespace="production_cache",
        settings_class=RedisSettings,     # ← Different type
        host="redis-cluster.example.com",
        port=6379,
        password="redis-secret",
        db=1
    ),
    "external_api": SettingsParameters.create(
        namespace="external_api",
        settings_class=ApiSettings,       # ← Another type
        base_url="https://api.production.com",
        api_key="prod-api-key-xyz",
        timeout=60,
        rate_limit=1000
    )
}

def initialize_service(service_name: str) -> MountainAshBaseSettings:
    """Generic service initializer - doesn't know what settings class it will get!"""
    if service_name not in service_registry:
        raise ValueError(f"Unknown service: {service_name}")
    
    params = service_registry[service_name]
    
    print(f"3. Initializing {service_name}:")
    print(f"   Target class: {params.settings_class.__name__}")
    print(f"   Namespace: {params.namespace}")
    
    # Dynamic resolution - get_settings uses the embedded type information
    settings = get_settings(settings_parameters=params)
    
    print(f"   Resolved to: {type(settings).__name__}")
    return settings

# Generic service initialization - completely type-agnostic
database_svc = initialize_service("database")
cache_svc = initialize_service("cache") 
api_svc = initialize_service("external_api")

print(f"   Database: {database_svc.host}:{database_svc.port}")
print(f"   Cache: {cache_svc.host}:{cache_svc.port}")
print(f"   API: {api_svc.base_url}")

print("\n=== Pattern Combination: Best of Both Worlds ===")
print("Combine patterns for maximum flexibility\n")

def create_tenant_config(tenant_id: str, service_type: str):
    """Factory that creates tenant-specific configurations."""
    service_classes = {
        "database": DatabaseSettings,
        "cache": RedisSettings,
        "api": ApiSettings
    }
    
    if service_type not in service_classes:
        raise ValueError(f"Unknown service type: {service_type}")
    
    # All patterns use explicit settings_class with MountainAshBaseSettings
    return SettingsParameters.create(
        namespace=f"tenant_{tenant_id}_{service_type}",
        settings_class=service_classes[service_type],
        host=f"{service_type}-{tenant_id}.example.com",
        **({"database": f"tenant_{tenant_id}", "username": f"tenant_{tenant_id}_user"} if service_type == "database" else {})
    )

def provision_tenant_services(tenant_id: str):
    """Provision all services for a tenant using different instantiation patterns."""
    print(f"4. Provisioning services for tenant '{tenant_id}':")
    
    # Database: Direct instantiation
    db_params = create_tenant_config(tenant_id, "database")
    tenant_db = DatabaseSettings(settings_parameters=db_params)
    
    # Cache & API: Dynamic resolution via get_settings
    cache_params = create_tenant_config(tenant_id, "cache")
    api_params = create_tenant_config(tenant_id, "api")
    
    tenant_cache = get_settings(settings_parameters=cache_params)
    tenant_api = get_settings(settings_parameters=api_params)
    
    print(f"   Database: {tenant_db.host} (via direct instantiation)")
    print(f"   Cache: {tenant_cache.host} (via get_settings)")
    print(f"   API: {tenant_api.base_url} (via get_settings)")
    
    return tenant_db, tenant_cache, tenant_api

# Provision services for multiple tenants
acme_db, acme_cache, acme_api = provision_tenant_services("acme")
globex_db, globex_cache, globex_api = provision_tenant_services("globex")

print("\n=== Pattern Selection Guidelines ===")
print()
print("🎯 Use DIRECT INSTANTIATION when:")
print("   ✅ Target settings class is known at compile time")
print("   ✅ Direct instantiation pattern (MySettings(settings_parameters=...))")
print("   ✅ Simple configuration loading for specific services")
print("   ✅ Single-purpose configuration functions")
print()
print("🔄 Use DYNAMIC RESOLUTION (get_settings) when:")  
print("   ✅ Target settings class determined at runtime")
print("   ✅ Generic functions that work with multiple settings types")
print("   ✅ Service registries and plugin architectures")
print("   ✅ Multi-tenant systems with varying service types")
print("   ✅ Configuration routing and dispatching")
print("   ✅ Caching optimization is critical")
print()
print("🏗️ COMBINE PATTERNS for:")
print("   ✅ Enterprise applications with mixed use cases")
print("   ✅ Microservices with both fixed and dynamic configurations")
print("   ✅ Plugin systems with core and extension settings")
print("   ✅ Multi-tenant platforms with service variations")

print("\n=== Performance Verification ===")

# Verify caching works correctly for both patterns
print("5. Cache behavior verification:")

# Create params for testing
test_db_params = create_tenant_config("test", "database")
test_cache_params = create_tenant_config("test", "cache")

# Direct instantiation caching
db1 = DatabaseSettings(settings_parameters=test_db_params)
db2 = DatabaseSettings(settings_parameters=test_db_params)
print(f"   Direct instantiation cache hit: {db1 is db2}")

# Dynamic resolution caching  
cache1 = get_settings(settings_parameters=test_cache_params)
cache2 = get_settings(settings_parameters=test_cache_params)
print(f"   Dynamic resolution cache hit: {cache1 is cache2}")

# Different patterns, same result for compatible params
compatible_db_params = SettingsParameters.create(
    namespace=f"tenant_test_database",
    settings_class=DatabaseSettings,
    host="database-test.example.com",
    database="tenant_test", 
    username="tenant_test_user"
)

db_via_direct = DatabaseSettings(settings_parameters=compatible_db_params)
db_via_get_settings = get_settings(settings_parameters=compatible_db_params)
print(f"   Cross-pattern cache hit: {db_via_direct is db_via_get_settings}")

print("\n=== MountainAshBaseSettings provides flexible, powerful configuration management! ===")