"""
Settings instance fixtures for testing.

This module provides reusable fixtures for creating settings instances
with various configurations for integration testing.
"""

from typing import Optional, Type
import pytest
from unittest.mock import patch

from mountainash_settings import get_settings, SettingsManager, get_settings_manager
from mountainash_settings.settings.app.app_settings import AppSettings

from .settings_classes import (
    TestSettings,
    TemplateTestSettings,
    MultiFieldTestSettings,
    MinimalSettings
)


@pytest.fixture
def test_settings_instance():
    """Provides a basic TestSettings instance."""
    return TestSettings()


@pytest.fixture
def test_settings_with_kwargs():
    """Provides TestSettings instance initialized with kwargs."""
    return TestSettings(
        TEST_VAL_1="instance_value_1",
        TEST_VAL_2="instance_value_2"
    )


@pytest.fixture
def test_settings_with_config(temp_yaml_file):
    """Provides TestSettings instance initialized with config file."""
    return TestSettings(config_files=temp_yaml_file)


@pytest.fixture
def test_settings_with_parameters(basic_settings_parameters):
    """Provides TestSettings instance initialized with SettingsParameters."""
    return TestSettings(settings_parameters=basic_settings_parameters)


@pytest.fixture
def template_settings_instance():
    """Provides a TemplateTestSettings instance for template testing."""
    return TemplateTestSettings(
        app_name="test_app",
        log_dir="/var/log/test"
    )


@pytest.fixture
def multifield_settings_instance():
    """Provides a MultiFieldTestSettings instance for comprehensive testing."""
    return MultiFieldTestSettings(
        string_field="test",
        int_field=100,
        bool_field=False,
        list_field=["item1", "item2"],
        dict_field={"key": "value"}
    )


@pytest.fixture
def minimal_settings_instance():
    """Provides a MinimalSettings instance."""
    return MinimalSettings()


@pytest.fixture
def app_settings_instance():
    """
    Provides an AppSettings instance for testing.

    Uses mocked datetime for consistent results.
    """
    return AppSettings()


@pytest.fixture
def app_settings_with_config(temp_yaml_file):
    """Provides AppSettings instance with config file."""
    return AppSettings(config_files=temp_yaml_file)


@pytest.fixture
def settings_manager() -> SettingsManager:
    """Provides a SettingsManager instance."""
    return get_settings_manager()


@pytest.fixture
def mock_get_platform_slash():
    """Mock the get_platform_slash function."""
    with patch('mountainash_settings.settings.app.app_settings.get_platform_slash') as mock:
        mock.return_value = "/"
        yield mock


@pytest.fixture(autouse=True)
def mock_datetime_for_tests():
    """
    Auto-use fixture to mock datetime for consistent test results.

    This ensures that date/time-dependent fields (like RUNDATE, RUNTIME)
    have predictable values across all tests.
    """
    from datetime import datetime
    with patch('mountainash_settings.settings.app.app_settings.datetime') as mock_datetime:
        # Set a fixed datetime for predictable testing
        mock_datetime.now.return_value = datetime(2024, 1, 15, 14, 30, 45)
        yield mock_datetime


@pytest.fixture
def create_settings_instance():
    """
    Factory fixture for creating custom settings instances.

    Usage:
        settings = create_settings_instance(
            TestSettings,
            config_files="config.yaml",
            TEST_VAL_1="value"
        )
    """
    def _create(
        settings_class: Type = TestSettings,
        config_files: Optional[str] = None,
        settings_parameters=None,
        **kwargs
    ):
        """
        Create a settings instance with custom configuration.

        Args:
            settings_class: The settings class to instantiate
            config_files: Configuration files to use
            settings_parameters: SettingsParameters object
            **kwargs: Additional initialization kwargs

        Returns:
            Initialized settings instance
        """
        return settings_class(
            config_files=config_files,
            settings_parameters=settings_parameters,
            **kwargs
        )

    return _create


@pytest.fixture
def cached_settings(basic_settings_parameters):
    """
    Provides a settings instance retrieved through the caching system.

    This fixture tests the full caching workflow.
    """
    return get_settings(settings_parameters=basic_settings_parameters)


@pytest.fixture(scope="function")
def isolated_settings_manager():
    """
    Provides an isolated SettingsManager for tests that need clean state.

    Note: This doesn't fully isolate the global cache, but provides
    a fresh manager instance. For true isolation, tests should use
    unique namespaces.
    """
    return SettingsManager()


@pytest.fixture
def settings_with_runtime_override(basic_settings_parameters):
    """
    Provides settings with runtime kwargs applied via SettingsParameters.

    This tests the runtime override functionality.
    """
    params_with_override = basic_settings_parameters.__class__.create(
        namespace=basic_settings_parameters.namespace,
        settings_class=basic_settings_parameters.settings_class,
        TEST_VAL_1="runtime_override_value"
    )
    return get_settings(settings_parameters=params_with_override)
