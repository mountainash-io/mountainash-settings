"""
Centralized mock settings classes for testing.

This module provides reusable mock settings classes that can be used
across all test files to ensure consistency and reduce duplication.
"""

from typing import Optional, List, Union
from pydantic import Field
from pydantic_settings import BaseSettings
from upath import UPath

from mountainash_settings import MountainAshBaseSettings, SettingsParameters


class MockBaseSettings(BaseSettings):
    """
    Basic mock settings class for testing general functionality.

    Used for testing basic Pydantic settings behavior without
    MountainAshBaseSettings features.
    """
    test_field: str = "default_value"
    test_int: int = 42
    test_bool: bool = True


class MockSettings(BaseSettings):
    """
    Simple mock settings for parametrized testing.

    Similar to MockBaseSettings but with different field names
    for testing field-specific behavior.
    """
    field1: str = "default1"
    field2: int = 42
    field3: bool = True


class TestSettings(MountainAshBaseSettings):
    """
    Standard test settings class extending MountainAshBaseSettings.

    This is the primary mock class for testing MountainAshBaseSettings
    functionality including config files, templates, and parameters.
    """

    def __init__(
        self,
        config_files: Optional[Union[str, UPath, List[Union[str, UPath]]]] = None,
        settings_parameters: Optional[SettingsParameters] = None,
        **kwargs
    ) -> None:
        super().__init__(
            config_files=config_files,
            settings_parameters=settings_parameters,
            **kwargs
        )

    # Test fields
    TEST_VAL_1: str = Field(default=None)
    TEST_VAL_2: str = Field(default=None)
    TEST_VAR: str = Field(default="default_value")
    COMPLEX_VAR: dict = Field(default_factory=lambda: {"key": "value"})


class TemplateTestSettings(MountainAshBaseSettings):
    """
    Test settings class with template field support.

    Used for testing template resolution and substitution features.
    """

    app_name: str = Field(default="test_app")
    log_dir: str = Field(default="/var/log")
    log_file: str = Field(default="logs/{app_name}.log")
    full_log_path: str = Field(default="{log_dir}/{app_name}.log")

    def post_init(self, reinitialise: bool = False) -> None:
        """Initialize templated fields."""
        self.log_file = self.init_setting_from_template(
            self.log_file,
            self.log_file,
            reinitialise
        )
        self.full_log_path = self.init_setting_from_template(
            self.full_log_path,
            self.full_log_path,
            reinitialise
        )


class MultiFieldTestSettings(MountainAshBaseSettings):
    """
    Test settings with many fields for comprehensive testing.

    Used for testing field validation, kwargs filtering, and
    complex initialization scenarios.
    """

    # String fields
    string_field: str = Field(default="default_string")
    optional_string: Optional[str] = Field(default=None)

    # Numeric fields
    int_field: int = Field(default=42)
    float_field: float = Field(default=3.14)

    # Boolean fields
    bool_field: bool = Field(default=True)

    # Collection fields
    list_field: List[str] = Field(default_factory=list)
    dict_field: dict = Field(default_factory=dict)

    # Complex fields
    complex_nested: dict = Field(default_factory=lambda: {
        "level1": {"level2": {"value": "nested"}}
    })


class MinimalSettings(MountainAshBaseSettings):
    """
    Minimal settings class for testing basic initialization.

    Used for testing the simplest possible settings configuration.
    """
    value: str = Field(default="minimal")
