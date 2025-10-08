"""
Comprehensive tests for MountainAshBaseSettings uncovered functionality.

Tests cover:
- get_settings() with settings_class=None (dynamic import)
- get_settings() TypeError validation
- __hash__() method
- _build_template_mapping() with missing attributes
- format_template_from_settings()
- init_setting_from_template()
- update_settings_from_dict() edge cases
- extract_settings_parameters()
- post_init() hook
"""

import pytest
from typing import Any, List, Optional
from pydantic import Field

from mountainash_settings import (
    MountainAshBaseSettings,
    SettingsParameters,
    get_settings,
)
from fixtures.settings_classes import TestSettings


class TemplateSettings(MountainAshBaseSettings):
    """Settings class for template testing."""
    APP_NAME: str = Field(default="myapp")
    ENVIRONMENT: str = Field(default="dev")
    LOG_FILE: str = Field(default="logs/{APP_NAME}_{ENVIRONMENT}.log")
    DATA_PATH: str = Field(default="/data/{APP_NAME}")


class CustomPostInitSettings(MountainAshBaseSettings):
    """Settings class with custom post_init."""
    VALUE: str = Field(default="initial")
    COMPUTED: str = Field(default=None)

    def post_init(self, reinitialise: bool = False) -> None:
        """Custom post_init that computes a value."""
        self.COMPUTED = f"computed_{self.VALUE}"


class TestGetSettingsWithNoneClass:
    """Test get_settings() when settings_class is None."""

    @pytest.mark.unit
    def test_get_settings_infers_class_from_caller(self, isolated_settings_manager):
        """Test that get_settings infers class when settings_class=None."""
        # Call get_settings from TestSettings class without specifying settings_class
        settings = TestSettings.get_settings(
            settings_namespace="test_infer_class",
            settings_class=None
        )

        assert isinstance(settings, TestSettings)
        assert settings.SETTINGS_CLASS is TestSettings
        assert settings.SETTINGS_CLASS_NAME == "TestSettings"

    @pytest.mark.unit
    def test_get_settings_with_explicit_class(self, isolated_settings_manager):
        """Test that get_settings works with explicit class."""
        settings = TestSettings.get_settings(
            settings_namespace="test_explicit_class",
            settings_class=TestSettings
        )

        assert isinstance(settings, TestSettings)
        assert settings.SETTINGS_CLASS is TestSettings

    @pytest.mark.unit
    def test_get_settings_type_validation_passes(self, isolated_settings_manager):
        """Test that get_settings validates instance type correctly."""
        settings = TestSettings.get_settings(
            settings_namespace="test_type_valid",
            settings_class=TestSettings
        )

        # Should not raise TypeError
        assert isinstance(settings, TestSettings)

    @pytest.mark.unit
    def test_get_settings_with_parameters_object(self, isolated_settings_manager):
        """Test get_settings with SettingsParameters object."""
        params = SettingsParameters.create(
            namespace="test_params_obj",
            settings_class=TestSettings,
            TEST_VAL_1="param_value"
        )

        settings = TestSettings.get_settings(settings_parameters=params)

        assert isinstance(settings, TestSettings)
        assert settings.TEST_VAL_1 == "param_value"


class TestHash:
    """Test __hash__() method."""

    @pytest.mark.unit
    def test_hash_with_basic_settings(self):
        """Test hash of basic settings object."""
        settings1 = TestSettings(
            settings_parameters=SettingsParameters.create(
                namespace="test_hash",
                settings_class=TestSettings
            )
        )
        settings2 = TestSettings(
            settings_parameters=SettingsParameters.create(
                namespace="test_hash",
                settings_class=TestSettings
            )
        )

        # Same namespace and class should produce same hash
        assert hash(settings1) == hash(settings2)

    @pytest.mark.unit
    def test_hash_different_namespaces(self):
        """Test that different namespaces produce different hashes."""
        settings1 = TestSettings(
            settings_parameters=SettingsParameters.create(
                namespace="namespace1",
                settings_class=TestSettings
            )
        )
        settings2 = TestSettings(
            settings_parameters=SettingsParameters.create(
                namespace="namespace2",
                settings_class=TestSettings
            )
        )

        assert hash(settings1) != hash(settings2)

    @pytest.mark.unit
    def test_hash_with_config_files(self, temp_yaml_file, temp_toml_file):
        """Test hash includes config files."""
        settings1 = TestSettings(
            settings_parameters=SettingsParameters.create(
                namespace="test_hash",
                settings_class=TestSettings,
                config_files=[temp_yaml_file]
            )
        )
        settings2 = TestSettings(
            settings_parameters=SettingsParameters.create(
                namespace="test_hash",
                settings_class=TestSettings,
                config_files=[temp_toml_file]
            )
        )

        # Different config files should produce different hashes
        assert hash(settings1) != hash(settings2)

    @pytest.mark.unit
    def test_hash_with_env_prefix(self):
        """Test hash includes env_prefix."""
        settings1 = TestSettings(
            settings_parameters=SettingsParameters.create(
                namespace="test_hash",
                settings_class=TestSettings,
                env_prefix="PREFIX1_"
            )
        )
        settings2 = TestSettings(
            settings_parameters=SettingsParameters.create(
                namespace="test_hash",
                settings_class=TestSettings,
                env_prefix="PREFIX2_"
            )
        )

        # Different env_prefix should produce different hashes
        assert hash(settings1) != hash(settings2)

    @pytest.mark.unit
    def test_hash_with_none_values(self):
        """Test hash handles None values correctly."""
        settings = TestSettings(
            settings_parameters=SettingsParameters.create(
                namespace="test_hash_none",
                settings_class=TestSettings
            )
        )

        # Should not raise error with None values
        hash_value = hash(settings)
        assert isinstance(hash_value, int)


class TestBuildTemplateMapping:
    """Test _build_template_mapping() method."""

    @pytest.mark.unit
    def test_build_mapping_with_valid_fields(self):
        """Test building template mapping with valid fields."""
        settings = TemplateSettings()

        mapping = settings._build_template_mapping("logs/{APP_NAME}_{ENVIRONMENT}.log")

        assert mapping == {"APP_NAME": "myapp", "ENVIRONMENT": "dev"}

    @pytest.mark.unit
    def test_build_mapping_with_missing_attribute(self):
        """Test that missing attribute raises AttributeError."""
        settings = TemplateSettings()

        with pytest.raises(AttributeError, match="does not have an attribute named 'MISSING_FIELD'"):
            settings._build_template_mapping("logs/{MISSING_FIELD}.log")

    @pytest.mark.unit
    def test_build_mapping_with_no_placeholders(self):
        """Test template with no placeholders."""
        settings = TemplateSettings()

        mapping = settings._build_template_mapping("logs/static.log")

        assert mapping == {}

    @pytest.mark.unit
    def test_build_mapping_with_multiple_fields(self):
        """Test template with multiple placeholders."""
        settings = TemplateSettings()

        mapping = settings._build_template_mapping("{APP_NAME}_{ENVIRONMENT}_{APP_NAME}")

        # Should have both fields
        assert "APP_NAME" in mapping
        assert "ENVIRONMENT" in mapping
        assert len(mapping) == 2


class TestFormatTemplateFromSettings:
    """Test format_template_from_settings() method."""

    @pytest.mark.unit
    def test_format_simple_template(self):
        """Test formatting a simple template."""
        settings = TemplateSettings()

        result = settings.format_template_from_settings("logs/{APP_NAME}.log")

        assert result == "logs/myapp.log"

    @pytest.mark.unit
    def test_format_complex_template(self):
        """Test formatting a complex template with multiple fields."""
        settings = TemplateSettings()

        result = settings.format_template_from_settings("logs/{APP_NAME}_{ENVIRONMENT}.log")

        assert result == "logs/myapp_dev.log"

    @pytest.mark.unit
    def test_format_template_with_custom_values(self):
        """Test formatting template with custom field values."""
        settings = TemplateSettings(APP_NAME="testapp", ENVIRONMENT="prod")

        result = settings.format_template_from_settings("/data/{APP_NAME}/{ENVIRONMENT}")

        assert result == "/data/testapp/prod"

    @pytest.mark.unit
    def test_format_template_missing_field_raises_error(self):
        """Test that missing field raises AttributeError."""
        settings = TemplateSettings()

        with pytest.raises(AttributeError, match="does not have an attribute named 'NONEXISTENT'"):
            settings.format_template_from_settings("{NONEXISTENT}")

    @pytest.mark.unit
    def test_format_template_no_placeholders(self):
        """Test template without placeholders."""
        settings = TemplateSettings()

        result = settings.format_template_from_settings("static/path/file.log")

        assert result == "static/path/file.log"


class TestInitSettingFromTemplate:
    """Test init_setting_from_template() method."""

    @pytest.mark.unit
    def test_init_with_none_current_value(self):
        """Test initialization when current_value is None."""
        settings = TemplateSettings()

        result = settings.init_setting_from_template(
            "logs/{APP_NAME}.log",
            current_value=None
        )

        assert result == "logs/myapp.log"

    @pytest.mark.unit
    def test_init_preserves_existing_value(self):
        """Test that existing value is preserved by default."""
        settings = TemplateSettings()

        result = settings.init_setting_from_template(
            "logs/{APP_NAME}.log",
            current_value="existing.log",
            reinitialise=False
        )

        assert result == "existing.log"

    @pytest.mark.unit
    def test_init_reinitialises_when_flag_set(self):
        """Test that reinitialise=True forces re-initialization."""
        settings = TemplateSettings()

        result = settings.init_setting_from_template(
            "logs/{APP_NAME}.log",
            current_value="existing.log",
            reinitialise=True
        )

        assert result == "logs/myapp.log"

    @pytest.mark.unit
    def test_init_with_complex_template(self):
        """Test initialization with complex template."""
        settings = TemplateSettings(APP_NAME="myapp", ENVIRONMENT="staging")

        result = settings.init_setting_from_template(
            "/data/{APP_NAME}/{ENVIRONMENT}/output",
            current_value=None
        )

        assert result == "/data/myapp/staging/output"


class TestUpdateSettingsFromDict:
    """Test update_settings_from_dict() method."""

    @pytest.mark.unit
    def test_update_with_valid_dict(self):
        """Test updating settings with valid dictionary."""
        settings = TestSettings()

        settings.update_settings_from_dict({"TEST_VAL_1": "updated1", "TEST_VAL_2": "updated2"})

        assert settings.TEST_VAL_1 == "updated1"
        assert settings.TEST_VAL_2 == "updated2"
        assert settings.SETTINGS_SOURCE_KWARGS == {"TEST_VAL_1": "updated1", "TEST_VAL_2": "updated2"}

    @pytest.mark.unit
    def test_update_with_none_returns_none(self):
        """Test that None settings_dict returns None."""
        settings = TestSettings()

        result = settings.update_settings_from_dict(None)

        assert result is None

    @pytest.mark.unit
    def test_update_with_empty_dict(self):
        """Test updating with empty dictionary."""
        settings = TestSettings()

        settings.update_settings_from_dict({})

        # SETTINGS_SOURCE_KWARGS should be set to empty dict
        assert settings.SETTINGS_SOURCE_KWARGS == {}

    @pytest.mark.unit
    def test_update_with_invalid_attribute_raises_error(self):
        """Test that invalid attribute raises AttributeError."""
        settings = TestSettings()

        with pytest.raises(AttributeError, match="does not have an attribute named 'NONEXISTENT'"):
            settings.update_settings_from_dict({"NONEXISTENT": "value"})

    @pytest.mark.unit
    def test_update_with_nested_kwargs_key(self):
        """Test updating with nested kwargs key."""
        settings = TestSettings()

        settings.update_settings_from_dict({"kwargs": {"TEST_VAL_1": "nested_value"}})

        # Should extract nested kwargs
        assert settings.TEST_VAL_1 == "nested_value"

    @pytest.mark.unit
    def test_update_partial_attributes(self):
        """Test updating only some attributes."""
        settings = TestSettings(TEST_VAL_1="original1", TEST_VAL_2="original2")

        settings.update_settings_from_dict({"TEST_VAL_1": "updated1"})

        assert settings.TEST_VAL_1 == "updated1"
        assert settings.TEST_VAL_2 == "original2"  # Should remain unchanged


class TestExtractSettingsParameters:
    """Test extract_settings_parameters() method."""

    @pytest.mark.unit
    def test_extract_basic_parameters(self):
        """Test extracting basic parameters."""
        original_params = SettingsParameters.create(
            namespace="test_extract",
            settings_class=TestSettings,
            TEST_VAL_1="value1"
        )
        settings = TestSettings(settings_parameters=original_params)

        extracted = settings.extract_settings_parameters()

        assert extracted.namespace == "test_extract"
        assert extracted.settings_class is TestSettings
        assert extracted.kwargs["TEST_VAL_1"] == "value1"

    @pytest.mark.unit
    def test_extract_with_config_files(self, temp_yaml_file, temp_toml_file):
        """Test extracting parameters with config files."""
        original_params = SettingsParameters.create(
            namespace="test_extract",
            settings_class=TestSettings,
            config_files=[temp_yaml_file, temp_toml_file]
        )
        settings = TestSettings(settings_parameters=original_params)

        extracted = settings.extract_settings_parameters()

        assert extracted.namespace == "test_extract"
        assert extracted.config_files is not None
        # Config files should be separated and included
        config_files_str = [str(f) for f in extracted.config_files]
        assert any("yaml" in f or "yml" in f for f in config_files_str)
        assert any("toml" in f for f in config_files_str)

    @pytest.mark.unit
    def test_extract_with_env_prefix(self):
        """Test extracting parameters with env_prefix."""
        original_params = SettingsParameters.create(
            namespace="test_extract",
            settings_class=TestSettings,
            env_prefix="TEST_"
        )
        settings = TestSettings(settings_parameters=original_params)

        extracted = settings.extract_settings_parameters()

        assert extracted.env_prefix == "TEST_"

    @pytest.mark.unit
    def test_extract_with_all_file_types(self, temp_env_file, temp_yaml_file, temp_toml_file, temp_json_file):
        """Test extracting parameters with multiple file types."""
        original_params = SettingsParameters.create(
            namespace="test_extract_all",
            settings_class=TestSettings,
            config_files=[temp_env_file, temp_yaml_file, temp_toml_file, temp_json_file]
        )
        settings = TestSettings(settings_parameters=original_params)

        extracted = settings.extract_settings_parameters()

        # All file types should be included
        config_files_str = [str(f) for f in extracted.config_files]
        assert len(config_files_str) == 4

    @pytest.mark.unit
    def test_extract_with_none_values(self):
        """Test extracting parameters with None values."""
        original_params = SettingsParameters.create(
            namespace="test_extract_none",
            settings_class=TestSettings
        )
        settings = TestSettings(settings_parameters=original_params)

        extracted = settings.extract_settings_parameters()

        assert extracted.namespace == "test_extract_none"
        assert extracted.settings_class is TestSettings
        # None values should be handled gracefully

    @pytest.mark.unit
    def test_extract_preserves_kwargs(self):
        """Test that extract preserves kwargs."""
        original_params = SettingsParameters.create(
            namespace="test_extract_kwargs",
            settings_class=TestSettings,
            TEST_VAL_1="value1",
            TEST_VAL_2="value2"
        )
        settings = TestSettings(settings_parameters=original_params)

        extracted = settings.extract_settings_parameters()

        assert extracted.kwargs["TEST_VAL_1"] == "value1"
        assert extracted.kwargs["TEST_VAL_2"] == "value2"


class TestPostInit:
    """Test post_init() hook."""

    @pytest.mark.unit
    def test_post_init_default_does_nothing(self):
        """Test that default post_init does nothing."""
        settings = TestSettings()

        # Should not raise error
        settings.post_init()

        # Should not modify anything
        assert hasattr(settings, "SETTINGS_NAMESPACE")

    @pytest.mark.unit
    def test_post_init_custom_implementation(self):
        """Test custom post_init implementation."""
        settings = CustomPostInitSettings(VALUE="test")

        # post_init should have been called during __init__
        assert settings.COMPUTED == "computed_test"

    @pytest.mark.unit
    def test_post_init_reinitialise_flag(self):
        """Test post_init with reinitialise flag."""
        settings = CustomPostInitSettings(VALUE="initial")
        assert settings.COMPUTED == "computed_initial"

        # Manually call with reinitialise
        settings.VALUE = "updated"
        settings.post_init(reinitialise=True)

        assert settings.COMPUTED == "computed_updated"

    @pytest.mark.unit
    def test_post_init_called_during_init(self):
        """Test that post_init is called during initialization."""
        settings = CustomPostInitSettings(VALUE="auto")

        # COMPUTED should be set by post_init
        assert settings.COMPUTED == "computed_auto"


class TestIntegration:
    """Integration tests for MountainAshBaseSettings."""

    @pytest.mark.integration
    def test_full_workflow_with_templates(self):
        """Test complete workflow with template fields."""
        params_obj = SettingsParameters.create(
            namespace="template_workflow",
            settings_class=TemplateSettings,
            APP_NAME="myapp",
            ENVIRONMENT="production"
        )
        settings = TemplateSettings(settings_parameters=params_obj)

        # Format template
        log_path = settings.format_template_from_settings("{APP_NAME}_{ENVIRONMENT}.log")
        assert log_path == "myapp_production.log"

        # Extract parameters
        params = settings.extract_settings_parameters()
        assert params.namespace == "template_workflow"

        # Hash should work
        hash_value = hash(settings)
        assert isinstance(hash_value, int)

    @pytest.mark.integration
    def test_full_workflow_with_updates(self):
        """Test complete workflow with updates."""
        # Create initial settings
        params = SettingsParameters.create(
            namespace="test_workflow",
            settings_class=TestSettings,
            TEST_VAL_1="initial"
        )
        settings = TestSettings(settings_parameters=params)

        assert settings.TEST_VAL_1 == "initial"

        # Update settings
        settings.update_settings_from_dict({"TEST_VAL_1": "updated", "TEST_VAL_2": "new"})
        assert settings.TEST_VAL_1 == "updated"
        assert settings.TEST_VAL_2 == "new"

        # Extract and verify
        extracted = settings.extract_settings_parameters()
        assert extracted.kwargs["TEST_VAL_1"] == "updated"
        assert extracted.kwargs["TEST_VAL_2"] == "new"

    @pytest.mark.integration
    def test_get_settings_multiple_calls(self, isolated_settings_manager):
        """Test that get_settings works correctly across multiple calls."""
        # First call - create settings
        params1 = SettingsParameters.create(
            namespace="multi_call_test",
            settings_class=TestSettings,
            TEST_VAL_1="value1"
        )
        settings1 = isolated_settings_manager.get_or_create_settings(params1)
        assert settings1.TEST_VAL_1 == "value1"

        # Second call with different kwargs - returns cached instance
        params2 = SettingsParameters.create(
            namespace="multi_call_test",
            settings_class=TestSettings,
            TEST_VAL_1="value2"
        )
        settings2 = isolated_settings_manager.get_or_create_settings(params2)

        # Should be same instance (cache key based on structural params)
        assert settings1 is settings2


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.edge_case
    def test_template_with_special_characters(self):
        """Test template with special characters."""
        settings = TemplateSettings()

        result = settings.format_template_from_settings("path/to/{APP_NAME}-file.log")

        assert result == "path/to/myapp-file.log"

    @pytest.mark.edge_case
    def test_hash_consistency(self):
        """Test that hash is consistent across multiple calls."""
        settings = TestSettings(
            settings_parameters=SettingsParameters.create(
                namespace="hash_test",
                settings_class=TestSettings
            )
        )

        hash1 = hash(settings)
        hash2 = hash(settings)
        hash3 = hash(settings)

        assert hash1 == hash2 == hash3

    @pytest.mark.edge_case
    def test_update_with_mixed_valid_invalid_attributes(self):
        """Test update with both valid and invalid attributes."""
        settings = TestSettings()

        # Should raise error on first invalid attribute
        with pytest.raises(AttributeError):
            settings.update_settings_from_dict({
                "TEST_VAL_1": "valid",
                "INVALID_FIELD": "invalid"
            })

    @pytest.mark.edge_case
    def test_extract_parameters_idempotent(self):
        """Test that extract_settings_parameters is idempotent."""
        original_params = SettingsParameters.create(
            namespace="idempotent_test",
            settings_class=TestSettings,
            TEST_VAL_1="value1"
        )
        settings = TestSettings(settings_parameters=original_params)

        extracted1 = settings.extract_settings_parameters()
        extracted2 = settings.extract_settings_parameters()

        # Should produce equivalent parameters
        assert extracted1.namespace == extracted2.namespace
        assert extracted1.settings_class == extracted2.settings_class
        assert extracted1.kwargs == extracted2.kwargs
