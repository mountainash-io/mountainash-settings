#!/usr/bin/env python3
"""
Example demonstrating the smart SettingsParameters merging feature.

This shows how the @mountainash_settings decorator can intelligently merge
SettingsParameters even when settings_class is not specified.
"""

from pydantic import Field
from pydantic_settings import BaseSettings
from mountainash_settings import mountainash_settings, SettingsParameters

print("=== Smart SettingsParameters Merging Example ===\n")

@mountainash_settings()
class DatabaseSettings(BaseSettings):
    """Database settings with smart parameter merging."""
    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    username: str = Field(default="user")
    password: str = Field(default="password")
    database: str = Field(default="myapp")

# 1. Traditional approach - explicit settings_class
print("1. Traditional Approach (explicit settings_class):")
traditional_params = SettingsParameters.create(
    namespace="database_prod",
    settings_class=DatabaseSettings,  # ← Explicitly specified
    host="prod-db.example.com",
    port=5432,
    username="admin", 
    database="production_db"
)

traditional_settings = DatabaseSettings(settings_parameters=traditional_params)
print(f"   Host: {traditional_settings.host}")
print(f"   Database: {traditional_settings.database}")
print(f"   Namespace: {traditional_settings.SETTINGS_NAMESPACE}")
print(f"   Settings Class: {traditional_settings.SETTINGS_CLASS.__name__}")

print()

# 2. Smart merging approach - no settings_class needed!
print("2. Smart Merging Approach (no settings_class needed!):")
smart_params = SettingsParameters.create(
    namespace="database_staging", 
    # settings_class=DatabaseSettings,  ← Not needed! 
    host="staging-db.example.com",
    port=5432,
    username="staging_user",
    database="staging_db"
)

# This works even though settings_class was not specified!
smart_settings = DatabaseSettings(settings_parameters=smart_params)
print(f"   Host: {smart_settings.host}")
print(f"   Database: {smart_settings.database}")
print(f"   Namespace: {smart_settings.SETTINGS_NAMESPACE}")
print(f"   Settings Class: {smart_settings.SETTINGS_CLASS.__name__}")

print()

# 3. Demonstrate the merging magic
print("3. How The Magic Works:")
print(f"   Original params.settings_class: {smart_params.settings_class}")
print(f"   Original params.kwargs: {smart_params.kwargs}")

# Extract the merged parameters from the final settings
reconstructed = smart_settings.extract_settings_parameters()
print(f"   Final params.settings_class: {reconstructed.settings_class.__name__}")
print(f"   Final params.namespace: {reconstructed.namespace}")

print()

# 4. Show it works with all decorator features
print("4. Works With All Decorator Features:")

@mountainash_settings(cache=True, templates=True, multi_format=True)
class AppSettings(BaseSettings):
    """Full-featured settings class."""
    app_name: str = Field(default="MyApp")
    environment: str = Field(default="development")
    log_path: str = Field(default="logs/{app_name}-{environment}.log")
    debug: bool = Field(default=False)

# No settings_class needed, templates work, caching works, metadata tracking works!
app_params = SettingsParameters.create(
    namespace="production",
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
print(f"   Cache Enabled: {AppSettings._mountainash_cache_enabled}")

print()

# 5. Library integration example
print("5. Library Integration Example:")

def create_database_config(environment: str):
    """Library function that creates SettingsParameters without knowing the target class."""
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
    
    # Library doesn't know about DatabaseSettings class!
    return SettingsParameters.create(
        namespace=f"db_{environment}",
        # No settings_class - works with any decorated class!
        **env_config
    )

# Use library function with our decorated class
dev_params = create_database_config("development")
prod_params = create_database_config("production")

dev_settings = DatabaseSettings(settings_parameters=dev_params)
prod_settings = DatabaseSettings(settings_parameters=prod_params)

print(f"   Dev Database: {dev_settings.database} @ {dev_settings.host}")
print(f"   Prod Database: {prod_settings.database} @ {prod_settings.host}")

print("\n=== Smart merging makes SettingsParameters more flexible and user-friendly! ===")