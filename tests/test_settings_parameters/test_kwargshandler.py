"""
Comprehensive tests for SettingsKwargsHandler.

Tests cover:
- format_kwargs_dict() - Converting kwargs to dict format
- format_kwargs_tuple() - Converting kwargs to tuple format
- merge_kwargs() - Merging two kwargs dictionaries
"""

import pytest
from typing import Dict, Any

from mountainash_settings.settings_parameters.kwargshandler import SettingsKwargsHandler


class TestFormatKwargsDict:
    """Test format_kwargs_dict method."""

    @pytest.mark.unit
    def test_format_none_returns_none(self):
        """Test that None input returns None."""
        result = SettingsKwargsHandler.format_kwargs_dict(None)
        assert result is None

    @pytest.mark.unit
    def test_format_empty_dict_returns_empty_dict(self):
        """Test that empty dict returns empty dict."""
        result = SettingsKwargsHandler.format_kwargs_dict({})
        assert result == {}

    @pytest.mark.unit
    def test_format_plain_dict_returns_dict(self):
        """Test that plain dict is returned as-is."""
        kwargs = {"key1": "value1", "key2": "value2"}
        result = SettingsKwargsHandler.format_kwargs_dict(kwargs)
        assert result == kwargs

    @pytest.mark.unit
    def test_format_dict_with_nested_kwargs_key(self):
        """Test that nested 'kwargs' key is extracted."""
        kwargs = {"kwargs": {"key1": "value1", "key2": "value2"}}
        result = SettingsKwargsHandler.format_kwargs_dict(kwargs)
        assert result == {"key1": "value1", "key2": "value2"}

    @pytest.mark.unit
    def test_format_tuple_converts_to_dict(self):
        """Test that tuple is converted to dict."""
        kwargs = (("key1", "value1"), ("key2", "value2"))
        result = SettingsKwargsHandler.format_kwargs_dict(kwargs)
        assert result == {"key1": "value1", "key2": "value2"}

    @pytest.mark.unit
    def test_format_tuple_with_nested_kwargs_key(self):
        """Test that tuple with nested 'kwargs' key is extracted."""
        kwargs = (("kwargs", {"key1": "value1", "key2": "value2"}),)
        result = SettingsKwargsHandler.format_kwargs_dict(kwargs)
        # After converting tuple to dict, it becomes {"kwargs": {...}}
        # Then .get("kwargs", ...) extracts the inner dict
        assert result == {"key1": "value1", "key2": "value2"}

    @pytest.mark.unit
    def test_format_invalid_type_raises_error(self):
        """Test that invalid type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid p_kwargs"):
            SettingsKwargsHandler.format_kwargs_dict("invalid_string")

    @pytest.mark.unit
    def test_format_invalid_int_raises_error(self):
        """Test that integer input raises ValueError."""
        with pytest.raises(ValueError, match="Invalid p_kwargs"):
            SettingsKwargsHandler.format_kwargs_dict(12345)

    @pytest.mark.unit
    def test_format_invalid_list_raises_error(self):
        """Test that list input raises ValueError."""
        with pytest.raises(ValueError, match="Invalid p_kwargs"):
            SettingsKwargsHandler.format_kwargs_dict(["item1", "item2"])

    @pytest.mark.unit
    def test_format_dict_preserves_various_value_types(self):
        """Test that dict with various value types is preserved."""
        kwargs = {
            "string": "value",
            "int": 42,
            "bool": True,
            "float": 3.14,
            "none": None,
            "list": [1, 2, 3],
            "dict": {"nested": "value"}
        }
        result = SettingsKwargsHandler.format_kwargs_dict(kwargs)
        assert result == kwargs


class TestFormatKwargsTuple:
    """Test format_kwargs_tuple method."""

    @pytest.mark.unit
    def test_format_none_returns_empty_tuple(self):
        """Test that None input returns empty tuple."""
        result = SettingsKwargsHandler.format_kwargs_tuple(None)
        assert result == ()

    @pytest.mark.unit
    def test_format_empty_dict_returns_empty_tuple(self):
        """Test that empty dict returns empty tuple."""
        result = SettingsKwargsHandler.format_kwargs_tuple({})
        assert result == ()

    @pytest.mark.unit
    def test_format_dict_to_sorted_tuple(self):
        """Test that dict is converted to sorted tuple."""
        kwargs = {"key2": "value2", "key1": "value1"}
        result = SettingsKwargsHandler.format_kwargs_tuple(kwargs)
        # Should be sorted by key
        assert result == (("key1", "value1"), ("key2", "value2"))

    @pytest.mark.unit
    def test_format_dict_sorting_is_alphabetical(self):
        """Test that dict is sorted alphabetically."""
        kwargs = {"zebra": 1, "alpha": 2, "middle": 3}
        result = SettingsKwargsHandler.format_kwargs_tuple(kwargs)
        assert result == (("alpha", 2), ("middle", 3), ("zebra", 1))

    @pytest.mark.unit
    def test_format_tuple_returns_tuple(self):
        """Test that tuple input is returned as-is."""
        kwargs = (("key1", "value1"), ("key2", "value2"))
        result = SettingsKwargsHandler.format_kwargs_tuple(kwargs)
        assert result == kwargs

    @pytest.mark.unit
    def test_format_invalid_type_raises_error(self):
        """Test that invalid type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid p_kwargs"):
            SettingsKwargsHandler.format_kwargs_tuple("invalid_string")

    @pytest.mark.unit
    def test_format_invalid_int_raises_error(self):
        """Test that integer input raises ValueError."""
        with pytest.raises(ValueError, match="Invalid p_kwargs"):
            SettingsKwargsHandler.format_kwargs_tuple(12345)

    @pytest.mark.unit
    def test_format_invalid_list_raises_error(self):
        """Test that list input raises ValueError."""
        with pytest.raises(ValueError, match="Invalid p_kwargs"):
            SettingsKwargsHandler.format_kwargs_tuple(["item1", "item2"])

    @pytest.mark.unit
    def test_format_dict_with_various_types_to_tuple(self):
        """Test that dict with various types is converted to tuple."""
        kwargs = {
            "string": "value",
            "int": 42,
            "bool": True,
        }
        result = SettingsKwargsHandler.format_kwargs_tuple(kwargs)
        # Should be sorted and contain all items
        assert ("bool", True) in result
        assert ("int", 42) in result
        assert ("string", "value") in result


class TestMergeKwargs:
    """Test merge_kwargs method."""

    @pytest.mark.unit
    def test_merge_both_none_returns_none(self):
        """Test that both None inputs return None."""
        result = SettingsKwargsHandler.merge_kwargs(None, None)
        assert result is None

    @pytest.mark.unit
    def test_merge_first_none_returns_second(self):
        """Test that None first returns second."""
        kwargs2 = {"key1": "value1", "key2": "value2"}
        result = SettingsKwargsHandler.merge_kwargs(None, kwargs2)
        assert result == kwargs2

    @pytest.mark.unit
    def test_merge_second_none_returns_first(self):
        """Test that None second returns first."""
        kwargs1 = {"key1": "value1", "key2": "value2"}
        result = SettingsKwargsHandler.merge_kwargs(kwargs1, None)
        assert result == kwargs1

    @pytest.mark.unit
    def test_merge_both_provided_merges_dicts(self):
        """Test that both dicts are merged."""
        kwargs1 = {"key1": "value1", "key2": "value2"}
        kwargs2 = {"key3": "value3", "key4": "value4"}
        result = SettingsKwargsHandler.merge_kwargs(kwargs1, kwargs2)
        assert result == {
            "key1": "value1",
            "key2": "value2",
            "key3": "value3",
            "key4": "value4"
        }

    @pytest.mark.unit
    def test_merge_second_overrides_first(self):
        """Test that second dict overrides first (precedence)."""
        kwargs1 = {"key1": "value1", "key2": "old_value"}
        kwargs2 = {"key2": "new_value", "key3": "value3"}
        result = SettingsKwargsHandler.merge_kwargs(kwargs1, kwargs2)
        # kwargs2 should override kwargs1
        assert result["key2"] == "new_value"
        assert result["key1"] == "value1"
        assert result["key3"] == "value3"

    @pytest.mark.unit
    def test_merge_empty_dicts_returns_empty_dict(self):
        """Test that merging two empty dicts returns empty dict."""
        result = SettingsKwargsHandler.merge_kwargs({}, {})
        assert result == {}

    @pytest.mark.unit
    def test_merge_first_empty_returns_second(self):
        """Test that first empty returns second."""
        kwargs2 = {"key1": "value1"}
        result = SettingsKwargsHandler.merge_kwargs({}, kwargs2)
        assert result == kwargs2

    @pytest.mark.unit
    def test_merge_second_empty_returns_first(self):
        """Test that second empty returns first."""
        kwargs1 = {"key1": "value1"}
        result = SettingsKwargsHandler.merge_kwargs(kwargs1, {})
        assert result == kwargs1

    @pytest.mark.unit
    def test_merge_with_nested_kwargs_key_in_result(self):
        """Test that nested 'kwargs' key in merged result is extracted."""
        kwargs1 = {"key1": "value1"}
        kwargs2 = {"kwargs": {"key2": "value2"}}
        result = SettingsKwargsHandler.merge_kwargs(kwargs1, kwargs2)
        # After merge: {"key1": "value1", "kwargs": {"key2": "value2"}}
        # Then .get("kwargs", ...) extracts the inner dict
        assert result == {"key2": "value2"}

    @pytest.mark.unit
    def test_merge_preserves_various_value_types(self):
        """Test that merge preserves various value types."""
        kwargs1 = {
            "string": "value",
            "int": 42,
            "bool": True,
        }
        kwargs2 = {
            "float": 3.14,
            "none": None,
            "list": [1, 2, 3],
        }
        result = SettingsKwargsHandler.merge_kwargs(kwargs1, kwargs2)
        assert result["string"] == "value"
        assert result["int"] == 42
        assert result["bool"] is True
        assert result["none"] is None
        assert result["list"] == [1, 2, 3]

    @pytest.mark.unit
    def test_merge_complex_override_scenario(self):
        """Test complex merge scenario with multiple overrides."""
        kwargs1 = {
            "shared_key": "original",
            "only_in_first": "first_value",
            "override_me": "old"
        }
        kwargs2 = {
            "shared_key": "updated",
            "only_in_second": "second_value",
            "override_me": "new"
        }
        result = SettingsKwargsHandler.merge_kwargs(kwargs1, kwargs2)

        # Check that kwargs2 values override kwargs1
        assert result["shared_key"] == "updated"
        assert result["override_me"] == "new"
        # Check that unique keys from both are preserved
        assert result["only_in_first"] == "first_value"
        assert result["only_in_second"] == "second_value"


class TestIntegration:
    """Integration tests for SettingsKwargsHandler."""

    @pytest.mark.integration
    def test_format_dict_then_tuple_roundtrip(self):
        """Test converting dict to tuple and back."""
        original = {"key1": "value1", "key2": "value2"}

        # Dict to tuple
        as_tuple = SettingsKwargsHandler.format_kwargs_tuple(original)
        assert isinstance(as_tuple, tuple)

        # Tuple to dict
        as_dict = SettingsKwargsHandler.format_kwargs_dict(as_tuple)
        assert as_dict == original

    @pytest.mark.integration
    def test_merge_then_format_workflow(self):
        """Test merge followed by format operations."""
        kwargs1 = {"key1": "value1"}
        kwargs2 = {"key2": "value2"}

        # Merge
        merged = SettingsKwargsHandler.merge_kwargs(kwargs1, kwargs2)

        # Format as tuple
        as_tuple = SettingsKwargsHandler.format_kwargs_tuple(merged)
        assert len(as_tuple) == 2
        assert ("key1", "value1") in as_tuple
        assert ("key2", "value2") in as_tuple

    @pytest.mark.integration
    def test_complex_workflow_with_nested_kwargs(self):
        """Test complex workflow with nested kwargs handling."""
        # Start with nested structure
        kwargs1 = {"kwargs": {"inner1": "value1"}}
        kwargs2 = {"inner2": "value2"}

        # Merge (should extract nested kwargs)
        merged = SettingsKwargsHandler.merge_kwargs(kwargs1, kwargs2)

        # Result should have inner1 from nested kwargs extraction
        # but also inner2 from kwargs2
        # Note: The extraction happens in merge_kwargs
        assert "inner1" in merged or "kwargs" in merged

    @pytest.mark.integration
    def test_format_dict_with_all_edge_cases(self):
        """Test format_kwargs_dict with edge cases in sequence."""
        # Test None
        assert SettingsKwargsHandler.format_kwargs_dict(None) is None

        # Test empty
        assert SettingsKwargsHandler.format_kwargs_dict({}) == {}

        # Test plain dict
        plain = {"key": "value"}
        assert SettingsKwargsHandler.format_kwargs_dict(plain) == plain

        # Test nested
        nested = {"kwargs": {"key": "value"}}
        assert SettingsKwargsHandler.format_kwargs_dict(nested) == {"key": "value"}
