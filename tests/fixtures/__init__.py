"""
Centralized test fixtures for mountainash-settings.

This package provides reusable fixtures organized by category:
- settings_classes: Mock settings classes for testing
- config_files: Temporary configuration file fixtures
- parameters: SettingsParameters fixtures
- instances: Settings instance fixtures

All fixtures are exposed through conftest.py for use in tests.
"""

# Import all settings classes for direct use in tests
from .settings_classes import (
    MockBaseSettings,
    MockSettings,
    TestSettings,
    TemplateTestSettings,
    MultiFieldTestSettings,
    MinimalSettings
)

# Fixtures are automatically discovered by pytest from the modules
# They don't need to be imported here, but we list them for documentation

__all__ = [
    # Settings Classes
    "MockBaseSettings",
    "MockSettings",
    "TestSettings",
    "TemplateTestSettings",
    "MultiFieldTestSettings",
    "MinimalSettings",

    # Config File Fixtures (from config_files.py)
    # "temp_yaml_file",
    # "temp_toml_file",
    # "temp_json_file",
    # "temp_env_file",
    # "temp_config_file",
    # "temp_multiple_yaml_files",
    # "temp_config_files",
    # "temp_mixed_config_files",
    # "temp_template_config_file",
    # "temp_dir",
    # "test_data_dir",
    # "create_config_file",

    # # Parameters Fixtures (from parameters.py)
    # "basic_settings_parameters",
    # (removed: settings_parameters_with_namespace)
    # "settings_parameters_with_prefix",
    # "settings_parameters_with_config_file",
    # "settings_parameters_with_multiple_files",
    # "settings_parameters_with_kwargs",
    # "settings_parameters_with_secrets_dir",
    # "settings_parameters_full_config",
    # "sample_settings_parameters",
    # "sample_kwargs",
    # "create_settings_parameters",
    # "parametrized_settings_class",
    # (removed: parametrized_namespace)
    # "parametrized_env_prefix",
    # "parametrized_kwargs",

    # # Instance Fixtures (from instances.py)
    # "test_settings_instance",
    # "test_settings_with_kwargs",
    # "test_settings_with_config",
    # "test_settings_with_parameters",
    # "template_settings_instance",
    # "multifield_settings_instance",
    # "minimal_settings_instance",
    # "app_settings_instance",
    # "app_settings_with_config",
    # "settings_manager",
    # "mock_get_platform_slash",
    # "mock_datetime_for_tests",
    # "create_settings_instance",
    # "cached_settings",
    # "isolated_settings_manager",
    # "settings_with_runtime_override",
]
