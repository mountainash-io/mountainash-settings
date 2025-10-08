#!/usr/bin/env python3
"""
Example demonstrating the @mountainash_settings decorator usage.

This example shows how the decorator makes Pydantic BaseSettings classes
work seamlessly with mountainash-settings infrastructure.
"""

from pydantic import Field
from pydantic_settings import BaseSettings

from mountainash_settings import mountainash_settings, SettingsParameters


# Example 1: Basic usage with default settings
@mountainash_settings()
class BasicSettings(BaseSettings):
    """Basic settings example with default mountainash-settings features."""
    debug: bool = Field(default=False)
    app_name: str = Field(default="MyApp")
    port: int = Field(default=8000)


# Example 2: Customized feature flags
@mountainash_settings(cache=False, templates=False, namespace="custom")
class CustomSettings(BaseSettings):
    """Settings with customized feature flags."""
    environment: str = Field(default="development")
    database_url: str = Field(default="sqlite:///app.db")


# Example 3: Using without parentheses (default settings)
@mountainash_settings
class SimpleSettings(BaseSettings):
    """Simple settings using decorator without parentheses."""
    timeout: int = Field(default=30)
    retries: int = Field(default=3)


def main():
    """Demonstrate decorator functionality."""
    print("=== @mountainash_settings Decorator Examples ===\n")
    
    # Example 1: Basic usage
    print("1. Basic Settings (default decorator options):")
    basic = BasicSettings()
    print(f"   Debug: {basic.debug}")
    print(f"   App Name: {basic.app_name}")
    print(f"   Port: {basic.port}")
    print(f"   Cache Enabled: {BasicSettings._mountainash_cache_enabled}")
    print(f"   Templates Enabled: {BasicSettings._mountainash_templates_enabled}")
    print()
    
    # Example 2: With runtime overrides
    print("2. Basic Settings with runtime overrides:")
    basic_override = BasicSettings(debug=True, app_name="OverrideApp", port=9000)
    print(f"   Debug: {basic_override.debug}")
    print(f"   App Name: {basic_override.app_name}")
    print(f"   Port: {basic_override.port}")
    print()
    
    # Example 3: Using get_settings classmethod
    print("3. Using get_settings() classmethod:")
    basic_get = BasicSettings.get_settings(debug=True, port=8080)
    print(f"   Debug: {basic_get.debug}")
    print(f"   App Name: {basic_get.app_name}")
    print(f"   Port: {basic_get.port}")
    print()
    
    # Example 4: Using SettingsParameters
    print("4. Using with SettingsParameters:")
    params = SettingsParameters.create(
        namespace="demo",
        settings_class=BasicSettings,
        debug=True,
        app_name="ParamsApp"
    )
    basic_params = BasicSettings(settings_parameters=params)
    print(f"   Debug: {basic_params.debug}")
    print(f"   App Name: {basic_params.app_name}")
    print(f"   Port: {basic_params.port}")
    print()
    
    # Example 5: Custom settings with disabled features
    print("5. Custom Settings (cache=False, templates=False):")
    custom = CustomSettings()
    print(f"   Environment: {custom.environment}")
    print(f"   Database URL: {custom.database_url}")
    print(f"   Cache Enabled: {CustomSettings._mountainash_cache_enabled}")
    print(f"   Templates Enabled: {CustomSettings._mountainash_templates_enabled}")
    print(f"   Namespace: {CustomSettings._mountainash_namespace}")
    print()
    
    # Example 6: Simple settings without parentheses
    print("6. Simple Settings (no parentheses decorator):")
    simple = SimpleSettings()
    print(f"   Timeout: {simple.timeout}")
    print(f"   Retries: {simple.retries}")
    print(f"   Cache Enabled: {SimpleSettings._mountainash_cache_enabled}")
    print()
    
    # Example 7: Standard Pydantic validation still works
    print("7. Pydantic validation still works:")
    try:
        BasicSettings(port=-1)  # Should work, no validation on port
        print("   Port=-1 accepted (no validation configured)")
    except Exception as e:
        print(f"   Validation error: {e}")
    
    # Example 8: Phase 2 Features - Template resolution
    print("8. Phase 2: Template Resolution:")
    @mountainash_settings(templates=True, cache=False)
    class TemplateSettings(BaseSettings):
        app_name: str = Field(default="MyTemplateApp")
        log_file: str = Field(default="logs/{app_name}.log")
        config_path: str = Field(default="config/{app_name}/settings.yaml")
        
    template_settings = TemplateSettings(app_name="ProductionApp")
    formatted_log = template_settings.format_template_from_settings("logs/{app_name}.log")
    formatted_config = template_settings.format_template_from_settings("config/{app_name}/settings.yaml")
    
    print(f"   App Name: {template_settings.app_name}")
    print(f"   Formatted Log Path: {formatted_log}")
    print(f"   Formatted Config Path: {formatted_config}")
    print(f"   Has Template Methods: {hasattr(template_settings, 'format_template_from_settings')}")
    print()
    
    # Example 9: Phase 2 Features - Multi-format configuration
    print("9. Phase 2: Multi-format Configuration Support:")
    @mountainash_settings(multi_format=True, templates=False, cache=False)
    class MultiFormatSettings(BaseSettings):
        database_url: str = Field(default="sqlite:///app.db")
        redis_url: str = Field(default="redis://localhost:6379")
        
    multi_settings = MultiFormatSettings()
    print(f"   Database URL: {multi_settings.database_url}")
    print(f"   Redis URL: {multi_settings.redis_url}")
    print(f"   Has Custom Sources: {hasattr(MultiFormatSettings, 'settings_customise_sources')}")
    print()
    
    # Example 10: Phase 2 Features - Metadata tracking
    print("10. Phase 2: Metadata Tracking:")
    @mountainash_settings(templates=True, cache=False)
    class MetadataSettings(BaseSettings):
        service_name: str = Field(default="MetadataService")
        version: str = Field(default="1.0.0")
        
    metadata_params = SettingsParameters.create(
        namespace="metadata_demo",
        settings_class=MetadataSettings,
        env_prefix="META",
        service_name="TrackedService",
        version="2.1.0"
    )
    metadata_settings = MetadataSettings(settings_parameters=metadata_params)
    
    print(f"   Service Name: {metadata_settings.service_name}")
    print(f"   Version: {metadata_settings.version}")
    print(f"   Tracked Namespace: {getattr(metadata_settings, 'SETTINGS_NAMESPACE', 'Not Set')}")
    print(f"   Tracked Class: {getattr(metadata_settings, 'SETTINGS_CLASS_NAME', 'Not Set')}")
    print(f"   Tracked Env Prefix: {getattr(metadata_settings, 'SETTINGS_SOURCE_ENV_PREFIX', 'Not Set')}")
    print(f"   Has Extraction Method: {hasattr(metadata_settings, 'extract_settings_parameters')}")
    print()
    
    # Example 11: Phase 2 Features - All features combined
    print("11. Phase 2: All Features Combined:")
    @mountainash_settings(
        cache=True,
        templates=True,
        multi_format=True,
        namespace="combined_demo"
    )
    class CombinedSettings(BaseSettings):
        app_name: str = Field(default="CombinedApp")
        log_path: str = Field(default="logs/{app_name}.log")
        database_url: str = Field(default="sqlite:///app.db")
        
    combined_settings = CombinedSettings.get_settings(
        app_name="SuperApp",
        database_url="postgresql://localhost/superapp"
    )
    
    formatted_log_path = combined_settings.format_template_from_settings("logs/{app_name}_combined.log")
    
    print(f"   App Name: {combined_settings.app_name}")
    print(f"   Database URL: {combined_settings.database_url}")
    print(f"   Formatted Log Path: {formatted_log_path}")
    print(f"   Namespace: {getattr(combined_settings, 'SETTINGS_NAMESPACE', 'Not Set')}")
    print(f"   Cache Enabled: {CombinedSettings._mountainash_cache_enabled}")
    print(f"   Templates Enabled: {CombinedSettings._mountainash_templates_enabled}")
    print(f"   Multi-format Enabled: {CombinedSettings._mountainash_multi_format_enabled}")
    print()

    print("\n=== All examples completed successfully! ===")
    print("Phase 1 (Core Infrastructure) ✅")
    print("Phase 2 (Feature Integration) ✅")


if __name__ == "__main__":
    main()