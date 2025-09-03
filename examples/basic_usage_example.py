#!/usr/bin/env python3
"""
Example demonstrating MountainAshBaseSettings usage.

This example shows how MountainAshBaseSettings provides advanced configuration
management with smart caching, template resolution, and multi-format support.
"""

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from mountainash_settings import MountainAshBaseSettings, SettingsParameters


# Example 1: Basic usage with MountainAshBaseSettings
class BasicSettings(MountainAshBaseSettings):
    """Basic settings example with all mountainash-settings features."""
    debug: bool = Field(default=False)
    app_name: str = Field(default="MyApp")
    port: int = Field(default=8000)


# Example 2: Settings with custom namespace
class CustomSettings(MountainAshBaseSettings):
    """Settings with custom namespace and configuration."""
    environment: str = Field(default="development")
    database_url: str = Field(default="sqlite:///app.db")
    
    @classmethod
    def get_namespace(cls):
        return "custom"


# Example 3: Simple settings with template support
class SimpleSettings(MountainAshBaseSettings):
    """Simple settings with template field support."""
    timeout: int = Field(default=30)
    retries: int = Field(default=3)
    log_file: str = Field(default="logs/simple_{timeout}s.log")


def main():
    """Demonstrate MountainAshBaseSettings functionality."""
    print("=== MountainAshBaseSettings Examples ===\n")
    
    # Example 1: Basic usage
    print("1. Basic Settings:")
    basic = BasicSettings()
    print(f"   Debug: {basic.debug}")
    print(f"   App Name: {basic.app_name}")
    print(f"   Port: {basic.port}")
    print(f"   Namespace: {basic.SETTINGS_NAMESPACE}")
    print()
    
    # Example 2: With runtime overrides
    print("2. Basic Settings with runtime overrides:")
    basic_override = BasicSettings(debug=True, app_name="OverrideApp", port=9000)
    print(f"   Debug: {basic_override.debug}")
    print(f"   App Name: {basic_override.app_name}")
    print(f"   Port: {basic_override.port}")
    print()
    
    # Example 3: Using get_settings classmethod
    print("3. Using get_settings() classmethod with caching:")
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
    print(f"   Namespace: {basic_params.SETTINGS_NAMESPACE}")
    print()
    
    # Example 5: Custom settings with namespace
    print("5. Custom Settings with namespace:")
    custom = CustomSettings()
    print(f"   Environment: {custom.environment}")
    print(f"   Database URL: {custom.database_url}")
    print(f"   Namespace: {custom.SETTINGS_NAMESPACE}")
    print()
    
    # Example 6: Simple settings with template
    print("6. Simple Settings with template field:")
    simple = SimpleSettings(timeout=45)
    print(f"   Timeout: {simple.timeout}")
    print(f"   Retries: {simple.retries}")
    print(f"   Log File: {simple.log_file}")
    print()
    
    # Example 7: Template resolution
    print("7. Template Resolution:")
    class TemplateSettings(MountainAshBaseSettings):
        app_name: str = Field(default="MyTemplateApp")
        log_file: str = Field(default="logs/{app_name}.log")
        config_path: str = Field(default="config/{app_name}/settings.yaml")
        
    template_settings = TemplateSettings(app_name="ProductionApp")
    formatted_log = template_settings.format_template_from_settings("logs/{app_name}.log")
    formatted_config = template_settings.format_template_from_settings("config/{app_name}/settings.yaml")
    
    print(f"   App Name: {template_settings.app_name}")
    print(f"   Log File (from field): {template_settings.log_file}")
    print(f"   Config Path (from field): {template_settings.config_path}")
    print(f"   Formatted Log Path: {formatted_log}")
    print(f"   Formatted Config Path: {formatted_config}")
    print()
    
    # Example 8: Multi-format configuration
    print("8. Multi-format Configuration Support:")
    class MultiFormatSettings(MountainAshBaseSettings):
        database_url: str = Field(default="sqlite:///app.db")
        redis_url: str = Field(default="redis://localhost:6379")
        
        model_config = SettingsConfigDict(
            yaml_file="config.yaml",
            toml_file="config.toml",
            json_file="config.json"
        )
        
    multi_settings = MultiFormatSettings()
    print(f"   Database URL: {multi_settings.database_url}")
    print(f"   Redis URL: {multi_settings.redis_url}")
    print(f"   Has Custom Sources: {hasattr(MultiFormatSettings, 'settings_customise_sources')}")
    print()
    
    # Example 9: Metadata tracking
    print("9. Metadata Tracking:")
    class MetadataSettings(MountainAshBaseSettings):
        service_name: str = Field(default="MetadataService")
        version: str = Field(default="1.0.0")
        
    metadata_params = SettingsParameters.create(
        namespace="metadata_demo",
        settings_class=MetadataSettings,
        env_prefix="META_",
        service_name="TrackedService",
        version="2.1.0"
    )
    metadata_settings = MetadataSettings(settings_parameters=metadata_params)
    
    print(f"   Service Name: {metadata_settings.service_name}")
    print(f"   Version: {metadata_settings.version}")
    print(f"   Namespace: {metadata_settings.SETTINGS_NAMESPACE}")
    print(f"   Class Name: {metadata_settings.SETTINGS_CLASS_NAME}")
    print(f"   Env Prefix: {getattr(metadata_settings, 'SETTINGS_SOURCE_ENV_PREFIX', 'Not Set')}")
    print(f"   Has Extraction Method: {hasattr(metadata_settings, 'extract_settings_parameters')}")
    print()
    
    # Example 10: All features combined
    print("10. All Features Combined:")
    class CombinedSettings(MountainAshBaseSettings):
        app_name: str = Field(default="CombinedApp")
        log_path: str = Field(default="logs/{app_name}.log")
        database_url: str = Field(default="sqlite:///app.db")
        
        @classmethod
        def get_namespace(cls):
            return "combined_demo"
        
    combined_settings = CombinedSettings.get_settings(
        app_name="SuperApp",
        database_url="postgresql://localhost/superapp"
    )
    
    formatted_log_path = combined_settings.format_template_from_settings("logs/{app_name}_combined.log")
    
    print(f"   App Name: {combined_settings.app_name}")
    print(f"   Database URL: {combined_settings.database_url}")
    print(f"   Log Path (from field): {combined_settings.log_path}")
    print(f"   Formatted Log Path: {formatted_log_path}")
    print(f"   Namespace: {combined_settings.SETTINGS_NAMESPACE}")
    print()

    print("\n=== All examples completed successfully! ===")
    print("MountainAshBaseSettings provides all the features you need! ✅")


if __name__ == "__main__":
    main()