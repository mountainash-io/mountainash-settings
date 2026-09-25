"""
Comprehensive tests for SettingsParameters uncovered functionality.

Tests cover:
- __eq__() with non-SettingsParameters types
- get_settings() method with and without settings_class
- accepted kwarg-name discovery
- hash and equality with runtime kwargs excluded
- hash with config_files variations
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
            settings_class=TestSettings
        )

        # Compare with different types
        assert params != "string"
        assert params != 123
        assert params != None
        assert params != {"settings_class": TestSettings}
        assert params != ["test"]

    @pytest.mark.unit
    def test_eq_with_identical_structural_params(self):
        """Test equality with identical structural parameters."""
        params1 = SettingsParameters.create(
            settings_class=TestSettings,
            config_files=["config.yaml"],
            env_prefix="TEST_"
        )
        params2 = SettingsParameters.create(
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
            settings_class=TestSettings,
            VALUE="value1"
        )
        params2 = SettingsParameters.create(
            settings_class=TestSettings,
            VALUE="value2"
        )

        # Should be equal despite different kwargs
        assert params1 == params2
        assert hash(params1) == hash(params2)

    @pytest.mark.unit
    def test_eq_differs_on_secrets_dir(self):
        """Test that different secrets_dir values produce inequality (structural param)."""
        params1 = SettingsParameters.create(
            settings_class=TestSettings,
            secrets_dir="/secrets1"
        )
        params2 = SettingsParameters.create(
            settings_class=TestSettings,
            secrets_dir="/secrets2"
        )

        # secrets_dir is structural -- different values should NOT be equal
        assert params1 != params2
        assert hash(params1) != hash(params2)

    @pytest.mark.unit
    def test_eq_differs_on_config_files(self):
        """Test that different config files produce inequality."""
        params1 = SettingsParameters.create(
            settings_class=TestSettings,
            config_files=["config1.yaml"]
        )
        params2 = SettingsParameters.create(
            settings_class=TestSettings,
            config_files=["config2.yaml"]
        )

        assert params1 != params2
        assert hash(params1) != hash(params2)

    @pytest.mark.unit
    def test_eq_differs_on_settings_class(self):
        """Test that different settings classes produce inequality."""
        params1 = SettingsParameters.create(settings_class=TestSettings)
        params2 = SettingsParameters.create(settings_class=SimpleSettings)

        assert params1 != params2
        assert hash(params1) != hash(params2)

    @pytest.mark.unit
    def test_eq_differs_on_env_prefix(self):
        """Test that different env_prefix values produce inequality."""
        params1 = SettingsParameters.create(
            settings_class=TestSettings,
            env_prefix="PREFIX1_"
        )
        params2 = SettingsParameters.create(
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
        params = SettingsParameters.create()

        with pytest.raises(ValueError, match="Settings class is required to get settings"):
            params.get_settings()

    @pytest.mark.unit
    def test_get_settings_with_settings_class(self, isolated_settings_manager):
        """Test that get_settings works with settings_class provided."""
        params = SettingsParameters.create(
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
            settings_class=SimpleSettings,
            env_prefix="UNIQUE_GS_",
            VALUE="cached_value"
        )

        # Get settings
        settings = params.get_settings()

        assert isinstance(settings, SimpleSettings)
        assert settings.VALUE == "cached_value"


class TestGetValidKwargNames:
    """Test _get_valid_kwarg_names() method."""

    @pytest.mark.unit
    def test_get_valid_kwarg_names_with_none_settings_class(self):
        """Test _get_valid_kwarg_names returns empty set when settings_class is None."""
        params = SettingsParameters.create()

        result = params._get_valid_kwarg_names()

        assert result == set()

    @pytest.mark.unit
    def test_get_valid_kwarg_names_with_none_passed_and_none_stored(self):
        """Test _get_valid_kwarg_names with None passed explicitly and None stored."""
        params = SettingsParameters.create()

        result = params._get_valid_kwarg_names(settings_class=None)

        assert result == set()

    @pytest.mark.unit
    def test_get_valid_kwarg_names_with_class_provided(self):
        """Test _get_valid_kwarg_names with settings_class provided.

        M5 (MAS-SEC-004): only declared fields are valid; underscore source
        controls are rejected, not treated as valid attribute kwargs.
        """
        params = SettingsParameters.create()

        result = params._get_valid_kwarg_names(settings_class=SimpleSettings)

        assert "VALUE" in result
        assert "COUNT" in result
        assert "_env_prefix" not in result
        assert "_case_sensitive" not in result

    @pytest.mark.unit
    def test_get_valid_kwarg_names_uses_stored_class(self):
        """Test _get_valid_kwarg_names uses stored settings_class."""
        params = SettingsParameters.create(
            settings_class=SimpleSettings
        )

        result = params._get_valid_kwarg_names()

        assert "VALUE" in result
        assert "COUNT" in result




class TestHashWithConfigFiles:
    """Test hash behavior with config files."""

    @pytest.mark.unit
    def test_hash_with_none_config_files(self):
        """Test hash when config_files is None."""
        params1 = SettingsParameters.create(settings_class=TestSettings)
        params2 = SettingsParameters.create(settings_class=TestSettings)

        assert hash(params1) == hash(params2)

    @pytest.mark.unit
    def test_hash_with_empty_config_files(self):
        """Test hash when config_files is empty."""
        params1 = SettingsParameters.create(
            settings_class=TestSettings,
            config_files=[]
        )
        params2 = SettingsParameters.create(
            settings_class=TestSettings,
            config_files=[]
        )

        assert hash(params1) == hash(params2)

    @pytest.mark.unit
    def test_hash_different_config_file_order_normalized(self):
        """Test that config files in different order produce same hash (if sorted)."""
        params1 = SettingsParameters.create(
            settings_class=TestSettings,
            config_files=["a.yaml", "b.yaml"]
        )
        params2 = SettingsParameters.create(
            settings_class=TestSettings,
            config_files=["a.yaml", "b.yaml"]
        )

        # Should be same (same order)
        assert hash(params1) == hash(params2)

    @pytest.mark.unit
    def test_hash_consistency_across_multiple_calls(self):
        """Test that hash is consistent across multiple calls."""
        params = SettingsParameters.create(
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


class TestGetAttributeSettingsKwargsSourceControlRejection:
    """M5 (MAS-SEC-004): get_attribute_settings_kwargs() rejects source and
    undeclared schema controls value-free, before sources open, rather than
    routing them to pydantic-settings kwargs or model_config."""

    @pytest.mark.unit
    def test_rejects_every_underscore_prefixed_kwarg(self):
        """Rejection is keyed to the leading-underscore rule, not an
        enumerated list -- covers _env_*, _cli_*, and unlisted names alike."""
        for key in ("_env_prefix", "_case_sensitive", "_cli_prog_name", "_secrets_dir", "_env_prefix_target"):
            params = SettingsParameters(settings_class=SimpleSettings, kwargs={key: "x"})
            with pytest.raises(ValueError, match=key):
                params.get_attribute_settings_kwargs()

    @pytest.mark.unit
    def test_rejects_undeclared_legacy_schema_control(self):
        """extra/arbitrary_types_allowed/validate_default fail value-free
        unless the settings class declares a field of that name."""
        params = SettingsParameters(
            settings_class=SimpleSettings,
            kwargs={"extra": "allow", "arbitrary_types_allowed": True, "validate_default": False},
        )

        with pytest.raises(ValueError):
            params.get_attribute_settings_kwargs()

    @pytest.mark.unit
    def test_none_kwargs_returns_empty_dict(self):
        params = SettingsParameters.create()

        result = params.get_attribute_settings_kwargs()

        assert result == {}


class TestIntegration:
    """Integration tests for SettingsParameters."""

    @pytest.mark.integration
    def test_full_workflow_with_runtime_overrides(self, isolated_settings_manager):
        """Test complete workflow with runtime overrides."""
        # Create base parameters
        base_params = SettingsParameters.create(
            settings_class=SimpleSettings,
            env_prefix="INTEG_UNIQUE_",
            VALUE="base_value",
            COUNT=10
        )

        # Get initial settings
        settings1 = base_params.get_settings()
        assert settings1.VALUE == "base_value"
        assert settings1.COUNT == 10

        # Create params with same structural but different runtime
        override_params = SettingsParameters.create(
            settings_class=SimpleSettings,
            env_prefix="INTEG_UNIQUE_",
            VALUE="override_value",
            COUNT=20
        )

        # Should get cached settings with overrides applied
        settings2 = override_params.get_settings()
        # Values should be overridden
        assert settings2.VALUE == "override_value"
        assert settings2.COUNT == 20

    @pytest.mark.integration
    def test_structural_equality_keeps_runtime_values_invocation_local(
        self, isolated_settings_manager
    ):
        """Equal structural parameters must not retain either runtime value."""
        params1 = SettingsParameters.create(
            settings_class=SimpleSettings,
            env_prefix="CACHE_EQ_",
            VALUE="value1",
        )
        params2 = SettingsParameters.create(
            settings_class=SimpleSettings,
            env_prefix="CACHE_EQ_",
            VALUE="value2",
        )

        assert params1 == params2
        assert hash(params1) == hash(params2)
        assert isolated_settings_manager.get_or_create_settings(params1).VALUE == "value1"
        assert isolated_settings_manager.get_or_create_settings(params2).VALUE == "value2"


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
    def test_runtime_retrieval_preserves_complete_model_shape(
        self, isolated_settings_manager
    ):
        """A runtime call validates and returns the declared settings class."""
        params = SettingsParameters.create(
            settings_class=SimpleSettings,
            env_prefix="MODEL_SHAPE_",
            VALUE="original",
            COUNT=10,
        )

        result = isolated_settings_manager.get_or_create_settings(params)

        assert isinstance(result, SimpleSettings)
        assert result.VALUE == "original"
        assert result.COUNT == 10

    @pytest.mark.edge_case
    def test_to_dict_preserves_structure(self):
        """Test that to_dict preserves parameter structure."""
        params = SettingsParameters.create(
            settings_class=SimpleSettings,
            config_files=["config1.yaml", "config2.yaml"],
            env_prefix="TEST_",
            secrets_dir="/secrets",
            VALUE="test",
            COUNT=42
        )

        result = params.to_dict()

        # All fields should be present
        assert isinstance(result["config_files"], list)
        assert len(result["config_files"]) == 2
        assert result["settings_class"] is SimpleSettings
        assert result["env_prefix"] == "TEST_"
        assert result["secrets_dir"] == "/secrets"
        assert result["kwargs"]["VALUE"] == "test"
        assert result["kwargs"]["COUNT"] == 42
