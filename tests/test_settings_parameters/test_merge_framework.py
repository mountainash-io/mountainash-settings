"""
Comprehensive tests for merge_framework module.

Tests cover:
- Helper functions: _merge_simple, _merge_config_files, _merge_kwargs, _merge_settings_class
- SettingsParameterMerger.merge_with_object()
- SettingsParameterMerger.merge_with_params()
- FieldMergeUtils static methods
- Global merger instance
- Legacy compatibility classes
- ValidationError scenarios
"""

import pytest
from typing import Dict, Any

from mountainash_settings.settings_parameters.merge_framework import (
    _merge_simple,
    _merge_config_files,
    _merge_kwargs,
    _merge_settings_class,
    SettingsParameterMerger,
    FieldMergeUtils,
    get_merger,
    ValidationError,
    MergePriority,
    GenericMerger,
)
from mountainash_settings import SettingsParameters
from fixtures.settings_classes import TestSettings, MockBaseSettings


class TestMergeSimple:
    """Test _merge_simple helper function."""

    @pytest.mark.unit
    def test_merge_both_none_returns_none(self):
        """Test that both None returns None."""
        result = _merge_simple(None, None)
        assert result is None

    @pytest.mark.unit
    def test_merge_first_none_returns_second(self):
        """Test that first None returns second."""
        result = _merge_simple(None, "second")
        assert result == "second"

    @pytest.mark.unit
    def test_merge_second_none_returns_first(self):
        """Test that second None returns first."""
        result = _merge_simple("first", None)
        assert result == "first"

    @pytest.mark.unit
    def test_merge_both_provided_returns_second(self):
        """Test that second wins by default."""
        result = _merge_simple("first", "second")
        assert result == "second"

    @pytest.mark.unit
    def test_merge_first_wins_returns_first(self):
        """Test that first_wins=True returns first."""
        result = _merge_simple("first", "second", first_wins=True)
        assert result == "first"

    @pytest.mark.unit
    def test_merge_first_wins_with_first_none(self):
        """Test that first_wins with first=None returns second."""
        result = _merge_simple(None, "second", first_wins=True)
        assert result == "second"

    @pytest.mark.unit
    def test_merge_empty_string_behavior(self):
        """Test behavior with empty strings (falsy values)."""
        result = _merge_simple("", "second")
        assert result == "second"

    @pytest.mark.unit
    def test_merge_zero_and_one(self):
        """Test behavior with 0 and 1 (falsy/truthy values)."""
        result = _merge_simple(0, 1)
        assert result == 1

    @pytest.mark.unit
    def test_merge_false_and_true(self):
        """Test behavior with False and True."""
        result = _merge_simple(False, True)
        assert result is True


class TestMergeConfigFiles:
    """Test _merge_config_files helper function."""

    @pytest.mark.unit
    def test_merge_both_none_returns_none(self):
        """Test that both None returns None."""
        result = _merge_config_files(None, None)
        assert result is None

    @pytest.mark.unit
    def test_merge_first_none_returns_second(self):
        """Test that first None returns second."""
        result = _merge_config_files(None, ("config2.yaml",))
        assert result == ("config2.yaml",)

    @pytest.mark.unit
    def test_merge_second_none_returns_first(self):
        """Test that second None returns first."""
        result = _merge_config_files(("config1.yaml",), None)
        assert result == ("config1.yaml",)

    @pytest.mark.unit
    def test_merge_combines_and_deduplicates(self):
        """Test that files are combined and deduplicated."""
        result = _merge_config_files(
            ("config1.yaml", "config2.yaml"),
            ("config2.yaml", "config3.yaml")
        )
        # Should deduplicate config2.yaml and sort
        assert result == ("config1.yaml", "config2.yaml", "config3.yaml")

    @pytest.mark.unit
    def test_merge_deduplication_only(self):
        """Test deduplication when files overlap."""
        result = _merge_config_files(
            ("config.yaml", "config.yaml"),
            ("config.yaml",)
        )
        assert result == ("config.yaml",)

    @pytest.mark.unit
    def test_merge_first_wins_returns_first(self):
        """Test that first_wins=True returns first."""
        result = _merge_config_files(
            ("config1.yaml",),
            ("config2.yaml",),
            first_wins=True
        )
        assert result == ("config1.yaml",)

    @pytest.mark.unit
    def test_merge_first_wins_with_first_none(self):
        """Test that first_wins with first=None returns second."""
        result = _merge_config_files(None, ("config2.yaml",), first_wins=True)
        assert result == ("config2.yaml",)

    @pytest.mark.unit
    def test_merge_sorting_behavior(self):
        """Test that merged files are sorted."""
        result = _merge_config_files(
            ("z.yaml", "a.yaml"),
            ("m.yaml",)
        )
        assert result == ("a.yaml", "m.yaml", "z.yaml")

    @pytest.mark.unit
    def test_merge_empty_tuples_returns_none(self):
        """Test that empty tuples result in None."""
        result = _merge_config_files((), ())
        assert result is None


class TestMergeKwargs:
    """Test _merge_kwargs helper function."""

    @pytest.mark.unit
    def test_merge_both_none_returns_none(self):
        """Test that both None returns None."""
        result = _merge_kwargs(None, None)
        assert result is None

    @pytest.mark.unit
    def test_merge_first_none_returns_second(self):
        """Test that first None returns second."""
        result = _merge_kwargs(None, {"key": "value"})
        assert result == {"key": "value"}

    @pytest.mark.unit
    def test_merge_second_none_returns_first(self):
        """Test that second None returns first."""
        result = _merge_kwargs({"key": "value"}, None)
        assert result == {"key": "value"}

    @pytest.mark.unit
    def test_merge_combines_dicts(self):
        """Test that dicts are combined with second taking precedence."""
        result = _merge_kwargs(
            {"key1": "value1", "shared": "first"},
            {"key2": "value2", "shared": "second"}
        )
        assert result == {"key1": "value1", "key2": "value2", "shared": "second"}

    @pytest.mark.unit
    def test_merge_nested_kwargs_extraction(self):
        """Test that nested 'kwargs' key is extracted."""
        result = _merge_kwargs(
            {"key1": "value1"},
            {"kwargs": {"key2": "value2"}}
        )
        # After merge, should extract the 'kwargs' nested dict
        assert result == {"key2": "value2"}

    @pytest.mark.unit
    def test_merge_first_wins_returns_first(self):
        """Test that first_wins=True returns first."""
        result = _merge_kwargs(
            {"key": "first"},
            {"key": "second"},
            first_wins=True
        )
        assert result == {"key": "first"}

    @pytest.mark.unit
    def test_merge_first_wins_with_first_none(self):
        """Test that first_wins with first=None returns second."""
        result = _merge_kwargs(None, {"key": "value"}, first_wins=True)
        assert result == {"key": "value"}

    @pytest.mark.unit
    def test_merge_empty_dicts_returns_none(self):
        """Test that empty dicts result in None."""
        result = _merge_kwargs({}, {})
        assert result is None


class TestMergeSettingsClass:
    """Test _merge_settings_class helper function."""

    @pytest.mark.unit
    def test_merge_both_none_returns_none(self):
        """Test that both None returns None."""
        result = _merge_settings_class(None, None)
        assert result is None

    @pytest.mark.unit
    def test_merge_first_none_returns_second(self):
        """Test that first None returns second."""
        result = _merge_settings_class(None, TestSettings)
        assert result is TestSettings

    @pytest.mark.unit
    def test_merge_second_none_returns_first(self):
        """Test that second None returns first."""
        result = _merge_settings_class(TestSettings, None)
        assert result is TestSettings

    @pytest.mark.unit
    def test_merge_same_class_returns_class(self):
        """Test that same class returns the class."""
        result = _merge_settings_class(TestSettings, TestSettings)
        assert result is TestSettings

    @pytest.mark.unit
    def test_merge_different_classes_raises_error(self):
        """Test that different classes raise ValidationError."""
        with pytest.raises(ValidationError, match="Settings class must match"):
            _merge_settings_class(TestSettings, MockBaseSettings)

    @pytest.mark.unit
    def test_merge_first_wins_same_class(self):
        """Test first_wins with same class."""
        result = _merge_settings_class(TestSettings, TestSettings, first_wins=True)
        assert result is TestSettings

    @pytest.mark.unit
    def test_merge_first_wins_with_first_none(self):
        """Test that first_wins with first=None returns second."""
        result = _merge_settings_class(None, TestSettings, first_wins=True)
        assert result is TestSettings


class TestSettingsParameterMergerObject:
    """Test SettingsParameterMerger.merge_with_object method."""

    @pytest.mark.unit
    def test_merge_raises_error_if_base_none(self):
        """Test that None base raises ValidationError."""
        merger = SettingsParameterMerger()
        other = SettingsParameters.create(settings_class=TestSettings)

        with pytest.raises(ValidationError, match="Base SettingsParameters cannot be None"):
            merger.merge_with_object(None, other)

    @pytest.mark.unit
    def test_merge_with_none_other_returns_base(self):
        """Test that None other returns base unchanged."""
        merger = SettingsParameterMerger()
        base = SettingsParameters.create(settings_class=TestSettings, env_prefix="BASE_")

        result = merger.merge_with_object(base, None)
        assert result.env_prefix == "BASE_"

    @pytest.mark.unit
    def test_merge_config_files_combines(self):
        """Test that config files are combined and deduplicated."""
        merger = SettingsParameterMerger()
        base = SettingsParameters.create(
            settings_class=TestSettings,
            config_files=["config1.yaml", "config2.yaml"]
        )
        other = SettingsParameters.create(
            settings_class=TestSettings,
            config_files=["config2.yaml", "config3.yaml"]
        )

        result = merger.merge_with_object(base, other)
        # Convert UPath to strings for comparison
        config_files_str = tuple(str(f) for f in result.config_files)
        assert config_files_str == ("config1.yaml", "config2.yaml", "config3.yaml")

    @pytest.mark.unit
    def test_merge_kwargs_second_wins(self):
        """Test that second kwargs take precedence."""
        merger = SettingsParameterMerger()
        base = SettingsParameters.create(
            settings_class=TestSettings,
            TEST_VAL_1="base_value"
        )
        other = SettingsParameters.create(
            settings_class=TestSettings,
            TEST_VAL_1="other_value"
        )

        result = merger.merge_with_object(base, other)
        assert result.kwargs["TEST_VAL_1"] == "other_value"

    @pytest.mark.unit
    def test_merge_env_prefix_second_wins(self):
        """Test that second env_prefix wins by default."""
        merger = SettingsParameterMerger()
        base = SettingsParameters.create(
            settings_class=TestSettings,
            env_prefix="BASE_"
        )
        other = SettingsParameters.create(
            settings_class=TestSettings,
            env_prefix="OTHER_"
        )

        result = merger.merge_with_object(base, other)
        assert result.env_prefix == "OTHER_"

    @pytest.mark.unit
    def test_merge_secrets_dir_second_wins(self):
        """Test that second secrets_dir wins by default."""
        merger = SettingsParameterMerger()
        base = SettingsParameters.create(
            settings_class=TestSettings,
            secrets_dir="/base/secrets"
        )
        other = SettingsParameters.create(
            settings_class=TestSettings,
            secrets_dir="/other/secrets"
        )

        result = merger.merge_with_object(base, other)
        assert result.secrets_dir == "/other/secrets"


class TestSettingsParameterMergerParams:
    """Test SettingsParameterMerger.merge_with_params method."""

    @pytest.mark.unit
    def test_merge_raises_error_if_base_none(self):
        """Test that None base raises ValidationError."""
        merger = SettingsParameterMerger()

        with pytest.raises(ValidationError, match="Base SettingsParameters cannot be None"):
            merger.merge_with_params(None)

    @pytest.mark.unit
    def test_merge_with_no_params_returns_base(self):
        """Test that merging with no params returns base."""
        merger = SettingsParameterMerger()
        base = SettingsParameters.create(settings_class=TestSettings, env_prefix="BASE_")

        result = merger.merge_with_params(base)
        assert result.env_prefix == "BASE_"
        assert result.settings_class is TestSettings

    @pytest.mark.unit
    def test_merge_config_files_param(self):
        """Test merging with config_files parameter."""
        merger = SettingsParameterMerger()
        base = SettingsParameters.create(
            settings_class=TestSettings,
            config_files=["config1.yaml"]
        )

        result = merger.merge_with_params(base, config_files=["config2.yaml", "config3.yaml"])
        # Should combine and deduplicate - convert UPath to strings for comparison
        config_files_str = set(str(f) for f in result.config_files)
        assert config_files_str == {"config1.yaml", "config2.yaml", "config3.yaml"}

    @pytest.mark.unit
    def test_merge_kwargs_param(self):
        """Test merging with kwargs parameter."""
        merger = SettingsParameterMerger()
        base = SettingsParameters.create(
            settings_class=TestSettings,
            TEST_VAL_1="base_value"
        )

        result = merger.merge_with_params(base, kwargs={"TEST_VAL_2": "new_value"})
        assert result.kwargs["TEST_VAL_1"] == "base_value"
        assert result.kwargs["TEST_VAL_2"] == "new_value"

    @pytest.mark.unit
    def test_merge_env_prefix_param(self):
        """Test merging with env_prefix parameter."""
        merger = SettingsParameterMerger()
        base = SettingsParameters.create(
            settings_class=TestSettings,
            env_prefix="BASE_"
        )

        result = merger.merge_with_params(base, env_prefix="NEW_")
        assert result.env_prefix == "NEW_"

    @pytest.mark.unit
    def test_merge_secrets_dir_param(self):
        """Test merging with secrets_dir parameter."""
        merger = SettingsParameterMerger()
        base = SettingsParameters.create(
            settings_class=TestSettings,
            secrets_dir="/base/secrets"
        )

        result = merger.merge_with_params(base, secrets_dir="/new/secrets")
        assert result.secrets_dir == "/new/secrets"

    @pytest.mark.unit
    def test_merge_prioritise_base_true(self):
        """Test that prioritise_base=True keeps base values."""
        merger = SettingsParameterMerger()
        base = SettingsParameters.create(
            settings_class=TestSettings,
            env_prefix="BASE_"
        )

        result = merger.merge_with_params(
            base,
            env_prefix="NEW_",
            prioritise_base=True
        )
        assert result.env_prefix == "BASE_"

    @pytest.mark.unit
    def test_merge_multiple_params_at_once(self):
        """Test merging multiple parameters simultaneously."""
        merger = SettingsParameterMerger()
        base = SettingsParameters.create(settings_class=TestSettings)

        result = merger.merge_with_params(
            base,
            config_files=["config.yaml"],
            kwargs={"TEST_VAL_1": "value"},
            env_prefix="NEW_",
            secrets_dir="/secrets"
        )
        assert result.config_files == ("config.yaml",)
        assert result.kwargs["TEST_VAL_1"] == "value"
        assert result.env_prefix == "NEW_"
        assert result.secrets_dir == "/secrets"

    @pytest.mark.unit
    def test_merge_settings_class_preserved(self):
        """Test that settings_class is preserved from base."""
        merger = SettingsParameterMerger()
        base = SettingsParameters.create(settings_class=TestSettings)

        result = merger.merge_with_params(base)
        assert result.settings_class is TestSettings


class TestFieldMergeUtils:
    """Test FieldMergeUtils static methods."""

    @pytest.mark.unit
    def test_merge_env_prefixes_both_provided(self):
        """Test merge_env_prefixes with both values."""
        result = FieldMergeUtils.merge_env_prefixes("FIRST_", "SECOND_")
        assert result == "FIRST_"

    @pytest.mark.unit
    def test_merge_env_prefixes_first_none(self):
        """Test merge_env_prefixes with first None."""
        result = FieldMergeUtils.merge_env_prefixes(None, "SECOND_")
        assert result == "SECOND_"

    @pytest.mark.unit
    def test_merge_env_prefixes_both_none(self):
        """Test merge_env_prefixes with both None."""
        result = FieldMergeUtils.merge_env_prefixes(None, None)
        assert result is None

    @pytest.mark.unit
    def test_merge_config_files_simple(self):
        """Test merge_config_files_simple combines and deduplicates."""
        result = FieldMergeUtils.merge_config_files_simple(
            ("config1.yaml", "config2.yaml"),
            ("config2.yaml", "config3.yaml")
        )
        assert result == ("config1.yaml", "config2.yaml", "config3.yaml")

    @pytest.mark.unit
    def test_merge_config_files_simple_both_none(self):
        """Test merge_config_files_simple with both None."""
        result = FieldMergeUtils.merge_config_files_simple(None, None)
        assert result is None

    @pytest.mark.unit
    def test_merge_kwargs_simple(self):
        """Test merge_kwargs_simple with second taking precedence."""
        result = FieldMergeUtils.merge_kwargs_simple(
            {"key1": "value1", "shared": "first"},
            {"key2": "value2", "shared": "second"}
        )
        assert result == {"key1": "value1", "key2": "value2", "shared": "second"}

    @pytest.mark.unit
    def test_merge_kwargs_simple_both_none(self):
        """Test merge_kwargs_simple with both None."""
        result = FieldMergeUtils.merge_kwargs_simple(None, None)
        assert result is None


class TestGlobalMerger:
    """Test global merger instance."""

    @pytest.mark.unit
    def test_get_merger_returns_instance(self):
        """Test that get_merger returns SettingsParameterMerger instance."""
        merger = get_merger()
        assert isinstance(merger, SettingsParameterMerger)

    @pytest.mark.unit
    def test_get_merger_returns_singleton(self):
        """Test that get_merger returns same instance."""
        merger1 = get_merger()
        merger2 = get_merger()
        assert merger1 is merger2

    @pytest.mark.unit
    def test_global_merger_functional(self):
        """Test that global merger works for merging."""
        merger = get_merger()
        base = SettingsParameters.create(settings_class=TestSettings, env_prefix="BASE_")
        other = SettingsParameters.create(settings_class=TestSettings, env_prefix="OTHER_")

        result = merger.merge_with_object(base, other)
        assert result.env_prefix == "OTHER_"


class TestLegacyCompatibility:
    """Test legacy compatibility classes and enums."""

    @pytest.mark.unit
    def test_merge_priority_enum_exists(self):
        """Test that MergePriority enum exists with expected values."""
        assert hasattr(MergePriority, "FIRST_WINS")
        assert hasattr(MergePriority, "SECOND_WINS")
        assert hasattr(MergePriority, "COMBINE")
        assert MergePriority.FIRST_WINS == "first_wins"
        assert MergePriority.SECOND_WINS == "second_wins"
        assert MergePriority.COMBINE == "combine"

    @pytest.mark.unit
    def test_generic_merger_instantiation(self):
        """Test that GenericMerger can be instantiated."""
        merger = GenericMerger()
        assert isinstance(merger, GenericMerger)

    @pytest.mark.unit
    def test_generic_merger_merge_field(self):
        """Test GenericMerger.merge_field method."""
        merger = GenericMerger()
        result = merger.merge_field("test_field", "first", "second")
        assert result == "second"

    @pytest.mark.unit
    def test_generic_merger_merge_field_prioritise_first(self):
        """Test GenericMerger.merge_field with prioritise_first=True."""
        merger = GenericMerger()
        result = merger.merge_field("test_field", "first", "second", prioritise_first=True)
        assert result == "first"

    @pytest.mark.unit
    def test_generic_merger_merge_fields(self):
        """Test GenericMerger.merge_fields method."""
        merger = GenericMerger()
        field_specs = {
            "field1": {"first": "value1", "second": "value2"},
            "field2": {"first": "value3", "second": "value4"}
        }
        result = merger.merge_fields(field_specs)
        assert result["field1"] == "value2"
        assert result["field2"] == "value4"

    @pytest.mark.unit
    def test_generic_merger_merge_fields_prioritise_first(self):
        """Test GenericMerger.merge_fields with prioritise_first=True."""
        merger = GenericMerger()
        field_specs = {
            "field1": {"first": "value1", "second": "value2"},
            "field2": {"first": "value3", "second": "value4"}
        }
        result = merger.merge_fields(field_specs, prioritise_first=True)
        assert result["field1"] == "value1"
        assert result["field2"] == "value3"


class TestIntegration:
    """Integration tests for merge_framework."""

    @pytest.mark.integration
    def test_full_merge_workflow(self):
        """Test complete merge workflow with multiple operations."""
        merger = get_merger()

        # Create base parameters
        base = SettingsParameters.create(
            settings_class=TestSettings,
            config_files=["config1.yaml"],
            env_prefix="BASE_",
            TEST_VAL_1="base_value"
        )

        # Merge with object
        other = SettingsParameters.create(
            settings_class=TestSettings,
            config_files=["config2.yaml"],
            TEST_VAL_2="other_value"
        )
        merged_obj = merger.merge_with_object(base, other)

        # Verify merged result
        # Convert UPath to strings for comparison
        config_files_str = set(str(f) for f in merged_obj.config_files)
        assert config_files_str == {"config1.yaml", "config2.yaml"}
        assert merged_obj.kwargs["TEST_VAL_1"] == "base_value"
        assert merged_obj.kwargs["TEST_VAL_2"] == "other_value"

        # Merge again with params
        final = merger.merge_with_params(
            merged_obj,
            config_files=["config3.yaml"],
            kwargs={"TEST_VAL_3": "final_value"}
        )

        # Verify final result
        # Convert UPath to strings for comparison
        final_config_files_str = set(str(f) for f in final.config_files)
        assert final_config_files_str == {"config1.yaml", "config2.yaml", "config3.yaml"}
        assert final.kwargs["TEST_VAL_1"] == "base_value"
        assert final.kwargs["TEST_VAL_2"] == "other_value"
        assert final.kwargs["TEST_VAL_3"] == "final_value"

    @pytest.mark.integration
    def test_prioritise_base_workflow(self):
        """Test merge workflow with prioritise_base=True."""
        merger = get_merger()

        base = SettingsParameters.create(
            settings_class=TestSettings,
            env_prefix="BASE_",
            TEST_VAL_1="base_value"
        )

        other = SettingsParameters.create(
            settings_class=TestSettings,
            env_prefix="OTHER_",
            TEST_VAL_1="other_value"
        )

        # Merge with prioritise_base=True
        result = merger.merge_with_object(base, other, prioritise_base=True)

        # Base values should win
        assert result.env_prefix == "BASE_"
        assert result.kwargs["TEST_VAL_1"] == "base_value"

    @pytest.mark.integration
    def test_field_merge_utils_integration(self):
        """Test FieldMergeUtils with realistic data."""
        # Merge config files
        config_files = FieldMergeUtils.merge_config_files_simple(
            ("base.yaml", "prod.yaml"),
            ("prod.yaml", "override.yaml")
        )
        assert config_files == ("base.yaml", "override.yaml", "prod.yaml")

        # Merge kwargs
        kwargs = FieldMergeUtils.merge_kwargs_simple(
            {"DEBUG": False, "LOG_LEVEL": "INFO"},
            {"LOG_LEVEL": "DEBUG", "FEATURE_FLAG": True}
        )
        assert kwargs == {"DEBUG": False, "LOG_LEVEL": "DEBUG", "FEATURE_FLAG": True}


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.edge_case
    def test_merge_incompatible_settings_classes(self):
        """Test that merging incompatible settings classes raises error."""
        merger = SettingsParameterMerger()
        base = SettingsParameters.create(settings_class=TestSettings)
        other = SettingsParameters.create(settings_class=MockBaseSettings)

        with pytest.raises(ValidationError, match="Settings class must match"):
            merger.merge_with_object(base, other)

    @pytest.mark.edge_case
    def test_merge_with_empty_config_files(self):
        """Test merging with empty config file tuples."""
        merger = SettingsParameterMerger()
        base = SettingsParameters.create(
            settings_class=TestSettings,
            config_files=[]
        )
        other = SettingsParameters.create(
            settings_class=TestSettings,
            config_files=[]
        )

        result = merger.merge_with_object(base, other)
        assert result.config_files is None

    @pytest.mark.edge_case
    def test_merge_with_empty_kwargs(self):
        """Test merging with empty kwargs dicts."""
        result = _merge_kwargs({}, {})
        assert result is None

    @pytest.mark.edge_case
    def test_merge_config_files_with_duplicates(self):
        """Test merging config files with many duplicates."""
        result = _merge_config_files(
            ("file.yaml", "file.yaml", "file.yaml"),
            ("file.yaml", "file.yaml")
        )
        assert result == ("file.yaml",)

    @pytest.mark.edge_case
    def test_merge_kwargs_nested_extraction(self):
        """Test that nested kwargs key is properly extracted."""
        result = _merge_kwargs(
            {"outer_key": "value"},
            {"kwargs": {"inner_key": "inner_value"}}
        )
        # Should extract the nested kwargs dict
        assert result == {"inner_key": "inner_value"}
        assert "outer_key" not in result
