"""
SettingsParameters fixtures for testing.

This module provides reusable fixtures for creating and testing
SettingsParameters objects with various configurations.
"""

from typing import Dict, Any
import pytest

from mountainash_settings import SettingsParameters
from .settings_classes import (
    MockBaseSettings,
    MockSettings,
    TestSettings,
    TemplateTestSettings,
    MultiFieldTestSettings,
    MinimalSettings
)


@pytest.fixture
def basic_settings_parameters():
    """Provides basic SettingsParameters for simple testing."""
    return SettingsParameters.create(
        namespace="test",
        settings_class=TestSettings
    )


@pytest.fixture
def settings_parameters_with_namespace():
    """Provides SettingsParameters with a specific namespace."""
    return SettingsParameters.create(
        namespace="custom_namespace",
        settings_class=TestSettings
    )


@pytest.fixture
def settings_parameters_with_prefix():
    """Provides SettingsParameters with environment prefix."""
    return SettingsParameters.create(
        namespace="test",
        settings_class=TestSettings,
        env_prefix="TEST_"
    )


@pytest.fixture
def settings_parameters_with_config_file(temp_yaml_file):
    """Provides SettingsParameters with a config file."""
    return SettingsParameters.create(
        namespace="test",
        settings_class=TestSettings,
        config_files=temp_yaml_file
    )


@pytest.fixture
def settings_parameters_with_multiple_files(temp_multiple_yaml_files):
    """Provides SettingsParameters with multiple config files."""
    return SettingsParameters.create(
        namespace="test",
        settings_class=TestSettings,
        config_files=temp_multiple_yaml_files
    )


@pytest.fixture
def settings_parameters_with_kwargs():
    """Provides SettingsParameters with kwargs."""
    return SettingsParameters.create(
        namespace="test",
        settings_class=TestSettings,
        TEST_VAL_1="kwarg_value_1",
        TEST_VAL_2="kwarg_value_2"
    )


@pytest.fixture
def settings_parameters_with_secrets_dir(temp_dir):
    """Provides SettingsParameters with secrets directory."""
    secrets_dir = temp_dir / "secrets"
    secrets_dir.mkdir()
    return SettingsParameters.create(
        namespace="test",
        settings_class=TestSettings,
        secrets_dir=str(secrets_dir)
    )


@pytest.fixture
def settings_parameters_full_config(temp_yaml_file, temp_dir):
    """Provides SettingsParameters with all parameters configured."""
    secrets_dir = temp_dir / "secrets"
    secrets_dir.mkdir()

    return SettingsParameters.create(
        namespace="full_test",
        config_files=temp_yaml_file,
        settings_class=TestSettings,
        env_prefix="FULL_",
        secrets_dir=str(secrets_dir),
        TEST_VAL_1="full_value_1",
        TEST_VAL_2="full_value_2",
        DEBUG=True
    )


@pytest.fixture
def sample_settings_parameters():
    """
    Provides sample settings parameters for testing.

    This is an alias for backwards compatibility with existing tests.
    """
    return SettingsParameters.create(
        namespace="test",
        config_files="test_config.yaml",
        env_prefix="TEST_"
    )


@pytest.fixture
def sample_kwargs():
    """Provides sample kwargs for testing."""
    return {
        "DEBUG": True,
        "VERBOSE": False,
        "_env_prefix": "TEST_",
        "custom_field": "value"
    }


@pytest.fixture
def create_settings_parameters():
    """
    Factory fixture for creating custom SettingsParameters.

    Usage:
        params = create_settings_parameters(
            namespace="my_test",
            settings_class=TestSettings,
            custom_key="custom_value"
        )
    """
    def _create(
        namespace: str = None,
        config_files: Any = None,
        settings_class: type = TestSettings,
        env_prefix: str = None,
        secrets_dir: str = None,
        **kwargs
    ) -> SettingsParameters:
        """
        Create a SettingsParameters object with custom configuration.

        Args:
            namespace: Namespace for settings
            config_files: Configuration files to use
            settings_class: Settings class to use
            env_prefix: Environment variable prefix
            secrets_dir: Secrets directory path
            **kwargs: Additional kwargs for settings

        Returns:
            Configured SettingsParameters object
        """
        return SettingsParameters.create(
            namespace=namespace,
            config_files=config_files,
            settings_class=settings_class,
            env_prefix=env_prefix,
            secrets_dir=secrets_dir,
            **kwargs
        )

    return _create


# Parametrized fixtures for testing different settings classes
@pytest.fixture(params=[
    MockBaseSettings,
    MockSettings,
    TestSettings,
    MinimalSettings
])
def parametrized_settings_class(request):
    """Provides different settings classes for parametrized testing."""
    return request.param


@pytest.fixture(params=[
    None,
    "test_namespace",
    "production",
    "development"
])
def parametrized_namespace(request):
    """Provides different namespaces for parametrized testing."""
    return request.param


@pytest.fixture(params=[
    None,
    "TEST_",
    "APP_",
    "CUSTOM_PREFIX_"
])
def parametrized_env_prefix(request):
    """Provides different environment prefixes for parametrized testing."""
    return request.param


@pytest.fixture(params=[
    {},
    {"DEBUG": True},
    {"DEBUG": True, "VERBOSE": False},
    {"TEST_VAL_1": "value1", "TEST_VAL_2": "value2"}
])
def parametrized_kwargs(request):
    """Provides different kwargs configurations for parametrized testing."""
    return request.param
