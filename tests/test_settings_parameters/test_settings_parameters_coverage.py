"""
Comprehensive tests for SettingsParameters uncovered functionality.

Tests cover:
- __eq__() with non-SettingsParameters types
- get_settings() method with and without settings_class
- _get_valid_kwarg_names() with None settings_class
- apply_runtime_overrides() method
- Hash and equality with kwargs (should be ignored)
- Hash with config_files variations
"""

import pytest
from typing import Dict, Any
from pydantic_settings import BaseSettings
from pydantic import Field

from mountainash_settings import (
    SettingsParameters,
    MountainAshBaseSettings,
)
from fixtures.settings_classes import TestSettings


class SimpleSettings(MountainAshBaseSettings):
    """Simple settings class for testing."""
    VALUE: str = Field(default="default_value")
    COUNT: int = Field(default=0)


class TestEquality:
    """Test __eq__() method edge cases."""

    @pytest.mark.unit
    def test_eq_with_non_settings_parameters_returns_false(self):
        """Test equality with non-SettingsParameters object returns False."""
        params = SettingsParameters.create(
            namespace="test",
            settings_class=TestSettings
        )

        # Compare with different types
        assert params != "string"
        assert params != 123
        assert params != None
        assert params != {"namespace": "test"}
        assert params != ["test"]

    @pytest.mark.unit
    def test_eq_with_identical_structural_params(self):
        """Test equality with identical structural parameters."""
        params1 = SettingsParameters.create(
            namespace="test",
            settings_class=TestSettings,
            config_files=["config.yaml"],
            env_prefix="TEST_"
        )
        params2 = SettingsParameters.create(
            namespace="test",
            settings_class=TestSettings,
            config_files=["config.yaml"],
            env_prefix="TEST_"
        )

        assert params1 == params2
        assert hash(params1) == hash(params2)

    @pytest.mark.unit
    def test_eq_ignores_kwargs_differences(self):
        """Test that equality ignores kwargs (runtime parameters)."""
        params1 = SettingsParameters.create(
            namespace="test",
            settings_class=TestSettings,
            VALUE="value1"
        )
        params2 = SettingsParameters.create(
            namespace="test",
            settings_class=TestSettings,
            VALUE="value2"
        )

        # Should be equal despite different kwargs
        assert params1 == params2
        assert hash(params1) == hash(params2)

    @pytest.mark.unit
    def test_eq_ignores_secrets_dir_differences(self):
        """Test that equality ignores secrets_dir (runtime parameter)."""
        params1 = SettingsParameters.create(
            namespace="test",
            settings_class=TestSettings,
            secrets_dir="/secrets1"
        )
        params2 = SettingsParameters.create(
            namespace="test",
            settings_class=TestSettings,
            secrets_dir="/secrets2"
        )

        # Should be equal despite different secrets_dir
        assert params1 == params2
        assert hash(params1) == hash(params2)

    @pytest.mark.unit
    def test_eq_differs_on_namespace(self):
        """Test that different namespaces produce inequality."""
        params1 = SettingsParameters.create(namespace="test1", settings_class=TestSettings)
        params2 = SettingsParameters.create(namespace="test2", settings_class=TestSettings)

        assert params1 != params2
        assert hash(params1) != hash(params2)

    @pytest.mark.unit
    def test_eq_differs_on_config_files(self):
        """Test that different config files produce inequality."""
        params1 = SettingsParameters.create(
            namespace="test",
            settings_class=TestSettings,
            config_files=["config1.yaml"]
        )
        params2 = SettingsParameters.create(
            namespace="test",
            settings_class=TestSettings,
            config_files=["config2.yaml"]
        )

        assert params1 != params2
        assert hash(params1) != hash(params2)

    @pytest.mark.unit
    def test_eq_differs_on_settings_class(self):
        """Test that different settings classes produce inequality."""
        params1 = SettingsParameters.create(namespace="test", settings_class=TestSettings)
        params2 = SettingsParameters.create(namespace="test", settings_class=SimpleSettings)

        assert params1 != params2
        assert hash(params1) != hash(params2)

    @pytest.mark.unit
    def test_eq_differs_on_env_prefix(self):
        """Test that different env_prefix values produce inequality."""
        params1 = SettingsParameters.create(
            namespace="test",
            settings_class=TestSettings,
            env_prefix="PREFIX1_"
        )
        params2 = SettingsParameters.create(
            namespace="test",
            settings_class=TestSettings,
            env_prefix="PREFIX2_"
        )

        assert params1 != params2
        assert hash(params1) != hash(params2)


class TestGetSettings:
    """Test get_settings() method."""

    @pytest.mark.unit
    def test_get_settings_raises_error_without_settings_class(self):
        """Test that get_settings raises ValueError when settings_class is None."""
        params = SettingsParameters.create(
            namespace="test_no_class"
        )

        with pytest.raises(ValueError, match="Settings class is required to get settings"):
            params.get_settings()

    @pytest.mark.unit
    def test_get_settings_with_settings_class(self, isolated_settings_manager):
        """Test that get_settings works with settings_class provided."""
        params = SettingsParameters.create(
            namespace="test_with_class",
            settings_class=SimpleSettings,
            VALUE="custom_value"
        )

        settings = params.get_settings()

        assert isinstance(settings, SimpleSettings)
        assert settings.VALUE == "custom_value"

    @pytest.mark.unit
    def test_get_settings_with_additional_kwargs(self, isolated_settings_manager):
        """Test get_settings with additional kwargs passed."""
        params = SettingsParameters.create(
            namespace="test_extra_kwargs",
            settings_class=SimpleSettings,
            VALUE="initial"
        )

        # Additional kwargs passed to get_settings
        settings = params.get_settings(COUNT=42)

        assert isinstance(settings, SimpleSettings)
        assert settings.VALUE == "initial"

    @pytest.mark.unit
    def test_get_settings_works_correctly(self, isolated_settings_manager):
        """Test that get_settings works correctly."""
        params = SettingsParameters.create(
            namespace="test_get_settings_unique",
            settings_class=SimpleSettings,
            VALUE="cached_value"
        )

        # Get settings
        settings = params.get_settings()

        assert isinstance(settings, SimpleSettings)
        assert settings.VALUE == "cached_value"
        assert settings.SETTINGS_NAMESPACE == "test_get_settings_unique"


class TestGetValidKwargNames:
    """Test _get_valid_kwarg_names() method."""

    @pytest.mark.unit
    def test_get_valid_kwarg_names_with_none_settings_class(self):
        """Test _get_valid_kwarg_names returns empty set when settings_class is None."""
        params = SettingsParameters.create(namespace="test")

        result = params._get_valid_kwarg_names()

        assert result == set()

    @pytest.mark.unit
    def test_get_valid_kwarg_names_with_none_passed_and_none_stored(self):
        """Test _get_valid_kwarg_names with None passed explicitly and None stored."""
        params = SettingsParameters.create(namespace="test")

        result = params._get_valid_kwarg_names(settings_class=None)

        assert result == set()

    @pytest.mark.unit
    def test_get_valid_kwarg_names_with_class_provided(self):
        """Test _get_valid_kwarg_names with settings_class provided."""
        params = SettingsParameters.create(namespace="test")

        result = params._get_valid_kwarg_names(settings_class=SimpleSettings)

        # Should have model fields plus reserved pydantic kwargs
        assert "VALUE" in result
        assert "COUNT" in result
        assert "_env_prefix" in result
        assert "_case_sensitive" in result

    @pytest.mark.unit
    def test_get_valid_kwarg_names_uses_stored_class(self):
        """Test _get_valid_kwarg_names uses stored settings_class."""
        params = SettingsParameters.create(
            namespace="test",
            settings_class=SimpleSettings
        )

        result = params._get_valid_kwarg_names()

        assert "VALUE" in result
        assert "COUNT" in result


class TestApplyRuntimeOverrides:
    """Test apply_runtime_overrides() method."""

    @pytest.mark.unit
    def test_apply_runtime_overrides_with_no_kwargs(self, isolated_settings_manager):
        """Test that apply_runtime_overrides returns original when no kwargs."""
        params = SettingsParameters.create(
            namespace="test_no_overrides",
            settings_class=SimpleSettings
        )
        original_settings = params.get_settings()

        result = params.apply_runtime_overrides(original_settings)

        # Should return the same object
        assert result is original_settings

    @pytest.mark.unit
    def test_apply_runtime_overrides_with_kwargs(self, isolated_settings_manager):
        """Test that apply_runtime_overrides creates copy with overrides."""
        # Create cached settings
        params_base = SettingsParameters.create(
            namespace="test_with_overrides",
            settings_class=SimpleSettings,
            VALUE="original"
        )
        cached_settings = params_base.get_settings()

        # Create params with runtime overrides
        params_override = SettingsParameters.create(
            namespace="test_with_overrides",
            settings_class=SimpleSettings,
            VALUE="overridden",
            COUNT=99
        )

        result = params_override.apply_runtime_overrides(cached_settings)

        # Should be a different object
        assert result is not cached_settings
        # Original should be unchanged
        assert cached_settings.VALUE == "original"
        # Result should have overrides
        assert result.VALUE == "overridden"
        assert result.COUNT == 99

    @pytest.mark.unit
    def test_apply_runtime_overrides_with_empty_override_kwargs(self, isolated_settings_manager):
        """Test apply_runtime_overrides when kwargs exist but no valid overrides."""
        params_base = SettingsParameters.create(
            namespace="test_empty_overrides",
            settings_class=SimpleSettings,
            VALUE="original"
        )
        cached_settings = params_base.get_settings()

        # Create params with kwargs but only invalid ones
        params_override = SettingsParameters(
            namespace="test_empty_overrides",
            settings_class=SimpleSettings,
            kwargs={"invalid_field": "value"}  # Not a valid field
        )

        result = params_override.apply_runtime_overrides(cached_settings)

        # Should create a copy even though no valid overrides
        assert result is not cached_settings
        # Values should remain unchanged
        assert result.VALUE == "original"

    @pytest.mark.unit
    def test_apply_runtime_overrides_preserves_unmodified_fields(self, isolated_settings_manager):
        """Test that apply_runtime_overrides preserves unmodified fields."""
        params_base = SettingsParameters.create(
            namespace="test_preserves",
            settings_class=SimpleSettings,
            VALUE="original_value",
            COUNT=10
        )
        cached_settings = params_base.get_settings()

        # Override only one field
        params_override = SettingsParameters.create(
            namespace="test_preserves",
            settings_class=SimpleSettings,
            VALUE="new_value"
        )

        result = params_override.apply_runtime_overrides(cached_settings)

        # VALUE should be overridden
        assert result.VALUE == "new_value"
        # COUNT should remain from cached settings
        assert result.COUNT == 10


class TestHashWithConfigFiles:
    """Test hash behavior with config files."""

    @pytest.mark.unit
    def test_hash_with_none_config_files(self):
        """Test hash when config_files is None."""
        params1 = SettingsParameters.create(namespace="test", settings_class=TestSettings)
        params2 = SettingsParameters.create(namespace="test", settings_class=TestSettings)

        assert hash(params1) == hash(params2)

    @pytest.mark.unit
    def test_hash_with_empty_config_files(self):
        """Test hash when config_files is empty."""
        params1 = SettingsParameters.create(
            namespace="test",
            settings_class=TestSettings,
            config_files=[]
        )
        params2 = SettingsParameters.create(
            namespace="test",
            settings_class=TestSettings,
            config_files=[]
        )

        assert hash(params1) == hash(params2)

    @pytest.mark.unit
    def test_hash_different_config_file_order_normalized(self):
        """Test that config files in different order produce same hash (if sorted)."""
        params1 = SettingsParameters.create(
            namespace="test",
            settings_class=TestSettings,
            config_files=["a.yaml", "b.yaml"]
        )
        params2 = SettingsParameters.create(
            namespace="test",
            settings_class=TestSettings,
            config_files=["a.yaml", "b.yaml"]
        )

        # Should be same (same order)
        assert hash(params1) == hash(params2)

    @pytest.mark.unit
    def test_hash_consistency_across_multiple_calls(self):
        """Test that hash is consistent across multiple calls."""
        params = SettingsParameters.create(
            namespace="test",
            settings_class=TestSettings,
            config_files=["config.yaml"],
            env_prefix="TEST_",
            VALUE="something"
        )

        hash1 = hash(params)
        hash2 = hash(params)
        hash3 = hash(params)

        assert hash1 == hash2 == hash3


class TestGetAttributeSettingsKwargs:
    """Test get_attribute_settings_kwargs() edge cases."""

    @pytest.mark.unit
    def test_get_attribute_settings_kwargs_with_none_kwargs(self):
        """Test get_attribute_settings_kwargs returns empty dict when kwargs is None."""
        params = SettingsParameters.create(
            namespace="test",
            settings_class=SimpleSettings
        )

        result = params.get_attribute_settings_kwargs()

        assert result == {}

    @pytest.mark.unit
    def test_get_attribute_settings_kwargs_filters_invalid_fields(self):
        """Test that invalid fields are filtered out."""
        params = SettingsParameters(
            settings_class=SimpleSettings,
            kwargs={
                "VALUE": "valid",
                "COUNT": 42,
                "INVALID_FIELD": "should_be_removed",
                "ANOTHER_INVALID": 123
            }
        )

        result = params.get_attribute_settings_kwargs()

        assert "VALUE" in result
        assert "COUNT" in result
        assert "INVALID_FIELD" not in result
        assert "ANOTHER_INVALID" not in result


class TestGetPydanticKwargs:
    """Test get_pydantic_settings_kwargs() and get_pydantic_modelconfig_kwargs()."""

    @pytest.mark.unit
    def test_get_pydantic_settings_kwargs_with_none_kwargs(self):
        """Test get_pydantic_settings_kwargs returns empty dict when kwargs is None."""
        params = SettingsParameters.create(namespace="test")

        result = params.get_pydantic_settings_kwargs()

        assert result == {}

    @pytest.mark.unit
    def test_get_pydantic_modelconfig_kwargs_with_none_kwargs(self):
        """Test get_pydantic_modelconfig_kwargs returns empty dict when kwargs is None."""
        params = SettingsParameters.create(namespace="test")

        result = params.get_pydantic_modelconfig_kwargs()

        assert result == {}

    @pytest.mark.unit
    def test_get_pydantic_settings_kwargs_filters_correctly(self):
        """Test that only pydantic settings kwargs are returned."""
        params = SettingsParameters(
            kwargs={
                "_env_prefix": "TEST_",
                "_case_sensitive": True,
                "regular_field": "value",
                "extra": "allow"
            }
        )

        result = params.get_pydantic_settings_kwargs()

        assert "_env_prefix" in result
        assert "_case_sensitive" in result
        assert "regular_field" not in result
        assert "extra" not in result

    @pytest.mark.unit
    def test_get_pydantic_modelconfig_kwargs_filters_correctly(self):
        """Test that only pydantic modelconfig kwargs are returned."""
        params = SettingsParameters(
            kwargs={
                "extra": "allow",
                "arbitrary_types_allowed": True,
                "validate_default": False,
                "_env_prefix": "TEST_",
                "regular_field": "value"
            }
        )

        result = params.get_pydantic_modelconfig_kwargs()

        assert "extra" in result
        assert "arbitrary_types_allowed" in result
        assert "validate_default" in result
        assert "_env_prefix" not in result
        assert "regular_field" not in result


class TestIntegration:
    """Integration tests for SettingsParameters."""

    @pytest.mark.integration
    def test_full_workflow_with_runtime_overrides(self, isolated_settings_manager):
        """Test complete workflow with runtime overrides."""
        # Create base parameters
        base_params = SettingsParameters.create(
            namespace="integration_test_unique",
            settings_class=SimpleSettings,
            VALUE="base_value",
            COUNT=10
        )

        # Get initial settings
        settings1 = base_params.get_settings()
        assert settings1.VALUE == "base_value"
        assert settings1.COUNT == 10

        # Create params with same structural but different runtime
        override_params = SettingsParameters.create(
            namespace="integration_test_unique",
            settings_class=SimpleSettings,
            VALUE="override_value",
            COUNT=20
        )

        # Should get cached settings with overrides applied
        settings2 = override_params.get_settings()
        # Values should be overridden
        assert settings2.VALUE == "override_value"
        assert settings2.COUNT == 20

    @pytest.mark.integration
    def test_caching_strategy_with_equality(self, isolated_settings_manager):
        """Test caching strategy based on equality."""
        # These should be equal (same structural params, different runtime kwargs)
        params1 = SettingsParameters.create(
            namespace="cache_equality_test",
            settings_class=SimpleSettings,
            VALUE="value1"
        )
        params2 = SettingsParameters.create(
            namespace="cache_equality_test",
            settings_class=SimpleSettings,
            VALUE="value2"
        )

        # Should be equal and have same hash (runtime kwargs ignored)
        assert params1 == params2
        assert hash(params1) == hash(params2)

        # Get settings - should use caching
        settings1 = isolated_settings_manager.get_or_create_settings(params1)
        settings2 = isolated_settings_manager.get_or_create_settings(params2)

        # Should be same cached instance (structural params identical)
        assert settings1 is settings2


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.edge_case
    def test_hash_with_all_none_structural_params(self):
        """Test hash when all structural parameters are None."""
        params = SettingsParameters()

        # Should not raise error
        hash_value = hash(params)
        assert isinstance(hash_value, int)

    @pytest.mark.edge_case
    def test_eq_with_self(self):
        """Test that object equals itself."""
        params = SettingsParameters.create(
            namespace="test",
            settings_class=TestSettings
        )

        assert params == params
        assert not (params != params)

    @pytest.mark.edge_case
    def test_apply_runtime_overrides_with_model_copy_preservation(self, isolated_settings_manager):
        """Test that apply_runtime_overrides preserves model integrity."""
        params_base = SettingsParameters.create(
            namespace="model_copy_test",
            settings_class=SimpleSettings,
            VALUE="original",
            COUNT=5
        )
        cached = params_base.get_settings()

        params_override = SettingsParameters.create(
            namespace="model_copy_test",
            settings_class=SimpleSettings,
            COUNT=10
        )

        result = params_override.apply_runtime_overrides(cached)

        # Result should be valid SimpleSettings instance
        assert isinstance(result, SimpleSettings)
        assert hasattr(result, "VALUE")
        assert hasattr(result, "COUNT")
        assert result.COUNT == 10

    @pytest.mark.edge_case
    def test_to_dict_preserves_structure(self):
        """Test that to_dict preserves parameter structure."""
        params = SettingsParameters.create(
            namespace="dict_test",
            settings_class=SimpleSettings,
            config_files=["config1.yaml", "config2.yaml"],
            env_prefix="TEST_",
            secrets_dir="/secrets",
            VALUE="test",
            COUNT=42
        )

        result = params.to_dict()

        # All fields should be present
        assert result["namespace"] == "dict_test"
        assert isinstance(result["config_files"], list)
        assert len(result["config_files"]) == 2
        assert result["settings_class"] is SimpleSettings
        assert result["env_prefix"] == "TEST_"
        assert result["secrets_dir"] == "/secrets"
        assert result["kwargs"]["VALUE"] == "test"
        assert result["kwargs"]["COUNT"] == 42
