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
    
    print("\n=== All examples completed successfully! ===")


if __name__ == "__main__":
    main()