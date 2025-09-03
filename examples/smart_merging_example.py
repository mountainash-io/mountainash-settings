#!/usr/bin/env python3
"""
Example demonstrating SettingsParameters with MountainAshBaseSettings.

This shows how MountainAshBaseSettings works seamlessly with SettingsParameters
for flexible configuration management patterns.
"""

from pydantic import Field
from mountainash_settings import MountainAshBaseSettings, SettingsParameters

print("=== SettingsParameters with MountainAshBaseSettings Example ===\n")

class DatabaseSettings(MountainAshBaseSettings):
    """Database settings with SettingsParameters support."""
    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    username: str = Field(default="user")
    password: str = Field(default="password")
    database: str = Field(default="myapp")

# 1. Basic SettingsParameters usage
print("1. Basic SettingsParameters Usage:")
basic_params = SettingsParameters.create(
    namespace="database_prod",
    settings_class=DatabaseSettings,
    host="prod-db.example.com",
    port=5432,
    username="admin", 
    database="production_db"
)

basic_settings = DatabaseSettings(settings_parameters=basic_params)
print(f"   Host: {basic_settings.host}")
print(f"   Database: {basic_settings.database}")
print(f"   Namespace: {basic_settings.SETTINGS_NAMESPACE}")
print(f"   Settings Class: {basic_settings.SETTINGS_CLASS.__name__}")

print()

# 2. Runtime overrides with SettingsParameters
print("2. Runtime Overrides with SettingsParameters:")
override_params = SettingsParameters.create(
    namespace="database_staging",
    settings_class=DatabaseSettings,
    host="staging-db.example.com",
    port=5432,
    username="staging_user",
    database="staging_db"
)

# Apply runtime overrides
override_settings = DatabaseSettings(
    settings_parameters=override_params,
    password="runtime_password",  # Runtime override
    port=3306  # Runtime override
)
print(f"   Host: {override_settings.host}")
print(f"   Port: {override_settings.port} (overridden)")
print(f"   Database: {override_settings.database}")
print(f"   Password: {override_settings.password} (overridden)")
print(f"   Namespace: {override_settings.SETTINGS_NAMESPACE}")

print()

# 3. Parameter extraction and reconstruction
print("3. Parameter Extraction and Reconstruction:")
print(f"   Original params namespace: {override_params.namespace}")
print(f"   Original params settings_class: {override_params.settings_class.__name__}")

# Extract the parameters from the final settings
reconstructed = override_settings.extract_settings_parameters()
print(f"   Reconstructed namespace: {reconstructed.namespace}")
print(f"   Reconstructed settings_class: {reconstructed.settings_class.__name__}")

print()

# 4. Advanced features with templates
print("4. Advanced Features with Templates:")

class AppSettings(MountainAshBaseSettings):
    """Full-featured settings class with templates."""
    app_name: str = Field(default="MyApp")
    environment: str = Field(default="development")
    log_path: str = Field(default="logs/{app_name}-{environment}.log")
    debug: bool = Field(default=False)

# Templates work, caching works, metadata tracking works!
app_params = SettingsParameters.create(
    namespace="production",
    settings_class=AppSettings,
    app_name="SuperApp",
    environment="production", 
    debug=False
)

app_settings = AppSettings(settings_parameters=app_params)
print(f"   App Name: {app_settings.app_name}")
print(f"   Environment: {app_settings.environment}")
print(f"   Log Path Template: {app_settings.log_path}")
print(f"   Formatted Log Path: {app_settings.format_template_from_settings(app_settings.log_path)}")
print(f"   Has Template Methods: {hasattr(app_settings, 'format_template_from_settings')}")
print(f"   Namespace: {app_settings.SETTINGS_NAMESPACE}")

print()

# 5. Environment-based configuration factory
print("5. Environment-Based Configuration Factory:")

def create_database_config(environment: str, settings_class=DatabaseSettings):
    """Factory function that creates SettingsParameters for different environments."""
    config = {
        "development": {
            "host": "localhost",
            "database": "dev_db",
            "username": "dev_user"
        },
        "production": {
            "host": "prod-cluster.example.com", 
            "database": "prod_db",
            "username": "prod_user"
        }
    }
    
    env_config = config.get(environment, config["development"])
    
    return SettingsParameters.create(
        namespace=f"db_{environment}",
        settings_class=settings_class,
        **env_config
    )

# Use factory function with our MountainAshBaseSettings class
dev_params = create_database_config("development")
prod_params = create_database_config("production")

dev_settings = DatabaseSettings(settings_parameters=dev_params)
prod_settings = DatabaseSettings(settings_parameters=prod_params)

print(f"   Dev Database: {dev_settings.database} @ {dev_settings.host}")
print(f"   Dev Namespace: {dev_settings.SETTINGS_NAMESPACE}")
print(f"   Prod Database: {prod_settings.database} @ {prod_settings.host}")
print(f"   Prod Namespace: {prod_settings.SETTINGS_NAMESPACE}")

print("\n=== SettingsParameters provides flexible configuration patterns with MountainAshBaseSettings! ===")