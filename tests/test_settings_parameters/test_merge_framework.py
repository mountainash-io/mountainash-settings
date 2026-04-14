"""
Tests for SettingsParameters.merge() classmethod.

Tests cover:
- merge with None base raises ValueError
- merge with None other returns base
- config files combine and deduplicate
- kwargs second wins by default
- kwargs combine (different keys)
- env_prefix second wins
- secrets_dir second wins
- incompatible classes raise ValueError
- same class succeeds
- prioritise_base flag works
- both None kwargs produces None
- both None config_files produces None
- full integration workflow
"""

import pytest

from mountainash_settings import SettingsParameters
from fixtures.settings_classes import TestSettings, MockBaseSettings


class TestMergeBasics:
    """Test basic merge behavior."""

    @pytest.mark.unit
    def test_merge_none_base_raises_valueerror(self):
        """Test that None base raises ValueError."""
        other = SettingsParameters.create(settings_class=TestSettings)
        with pytest.raises(ValueError, match="Base SettingsParameters cannot be None"):
            SettingsParameters.merge(None, other)

    @pytest.mark.unit
    def test_merge_none_other_returns_base(self):
        """Test that None other returns base unchanged."""
        base = SettingsParameters.create(settings_class=TestSettings, env_prefix="BASE_")
        result = SettingsParameters.merge(base, None)
        assert result is base
        assert result.env_prefix == "BASE_"


class TestMergeConfigFiles:
    """Test config file merging behavior."""

    @pytest.mark.unit
    def test_config_files_combine_and_deduplicate(self):
        """Test that config files are combined and deduplicated."""
        base = SettingsParameters.create(
            settings_class=TestSettings,
            config_files=["config1.yaml", "config2.yaml"]
        )
        other = SettingsParameters.create(
            settings_class=TestSettings,
            config_files=["config2.yaml", "config3.yaml"]
        )
        result = SettingsParameters.merge(base, other)
        config_files_str = tuple(str(f) for f in result.config_files)
        assert config_files_str == ("config1.yaml", "config2.yaml", "config3.yaml")

    @pytest.mark.unit
    def test_both_none_config_files_produces_none(self):
        """Test that both None config_files produces None."""
        base = SettingsParameters.create(settings_class=TestSettings)
        other = SettingsParameters.create(settings_class=TestSettings)
        result = SettingsParameters.merge(base, other)
        assert result.config_files is None

    @pytest.mark.unit
    def test_config_files_prioritise_base(self):
        """Test that prioritise_base returns base config files."""
        base = SettingsParameters.create(
            settings_class=TestSettings,
            config_files=["config1.yaml"]
        )
        other = SettingsParameters.create(
            settings_class=TestSettings,
            config_files=["config2.yaml"]
        )
        result = SettingsParameters.merge(base, other, prioritise_base=True)
        config_files_str = tuple(str(f) for f in result.config_files)
        assert config_files_str == ("config1.yaml",)


class TestMergeKwargs:
    """Test kwargs merging behavior."""

    @pytest.mark.unit
    def test_kwargs_second_wins(self):
        """Test that second kwargs take precedence for shared keys."""
        base = SettingsParameters.create(
            settings_class=TestSettings,
            TEST_VAL_1="base_value"
        )
        other = SettingsParameters.create(
            settings_class=TestSettings,
            TEST_VAL_1="other_value"
        )
        result = SettingsParameters.merge(base, other)
        assert result.kwargs["TEST_VAL_1"] == "other_value"

    @pytest.mark.unit
    def test_kwargs_combine_different_keys(self):
        """Test that kwargs with different keys are combined."""
        base = SettingsParameters.create(
            settings_class=TestSettings,
            TEST_VAL_1="base_value"
        )
        other = SettingsParameters.create(
            settings_class=TestSettings,
            TEST_VAL_2="other_value"
        )
        result = SettingsParameters.merge(base, other)
        assert result.kwargs["TEST_VAL_1"] == "base_value"
        assert result.kwargs["TEST_VAL_2"] == "other_value"

    @pytest.mark.unit
    def test_both_none_kwargs_produces_none(self):
        """Test that both None kwargs produces None."""
        base = SettingsParameters.create(settings_class=TestSettings)
        other = SettingsParameters.create(settings_class=TestSettings)
        result = SettingsParameters.merge(base, other)
        assert result.kwargs is None

    @pytest.mark.unit
    def test_kwargs_prioritise_base(self):
        """Test that prioritise_base returns base kwargs."""
        base = SettingsParameters.create(
            settings_class=TestSettings,
            TEST_VAL_1="base_value"
        )
        other = SettingsParameters.create(
            settings_class=TestSettings,
            TEST_VAL_1="other_value"
        )
        result = SettingsParameters.merge(base, other, prioritise_base=True)
        assert result.kwargs["TEST_VAL_1"] == "base_value"


class TestMergeScalars:
    """Test scalar field merging behavior."""

    @pytest.mark.unit
    def test_env_prefix_second_wins(self):
        """Test that second env_prefix wins by default."""
        base = SettingsParameters.create(
            settings_class=TestSettings,
            env_prefix="BASE_"
        )
        other = SettingsParameters.create(
            settings_class=TestSettings,
            env_prefix="OTHER_"
        )
        result = SettingsParameters.merge(base, other)
        assert result.env_prefix == "OTHER_"

    @pytest.mark.unit
    def test_secrets_dir_second_wins(self):
        """Test that second secrets_dir wins by default."""
        base = SettingsParameters.create(
            settings_class=TestSettings,
            secrets_dir="/base/secrets"
        )
        other = SettingsParameters.create(
            settings_class=TestSettings,
            secrets_dir="/other/secrets"
        )
        result = SettingsParameters.merge(base, other)
        assert result.secrets_dir == "/other/secrets"

    @pytest.mark.unit
    def test_env_prefix_prioritise_base(self):
        """Test that prioritise_base returns base env_prefix."""
        base = SettingsParameters.create(
            settings_class=TestSettings,
            env_prefix="BASE_"
        )
        other = SettingsParameters.create(
            settings_class=TestSettings,
            env_prefix="OTHER_"
        )
        result = SettingsParameters.merge(base, other, prioritise_base=True)
        assert result.env_prefix == "BASE_"

    @pytest.mark.unit
    def test_secrets_dir_prioritise_base(self):
        """Test that prioritise_base returns base secrets_dir."""
        base = SettingsParameters.create(
            settings_class=TestSettings,
            secrets_dir="/base/secrets"
        )
        other = SettingsParameters.create(
            settings_class=TestSettings,
            secrets_dir="/other/secrets"
        )
        result = SettingsParameters.merge(base, other, prioritise_base=True)
        assert result.secrets_dir == "/base/secrets"


class TestMergeSettingsClass:
    """Test settings_class merging and validation."""

    @pytest.mark.unit
    def test_incompatible_classes_raise_valueerror(self):
        """Test that incompatible settings classes raise ValueError."""
        base = SettingsParameters.create(settings_class=TestSettings)
        other = SettingsParameters.create(settings_class=MockBaseSettings)
        with pytest.raises(ValueError, match="Settings class must match"):
            SettingsParameters.merge(base, other)

    @pytest.mark.unit
    def test_same_class_succeeds(self):
        """Test that same class merges successfully."""
        base = SettingsParameters.create(settings_class=TestSettings)
        other = SettingsParameters.create(settings_class=TestSettings)
        result = SettingsParameters.merge(base, other)
        assert result.settings_class is TestSettings

    @pytest.mark.unit
    def test_one_none_class_uses_other(self):
        """Test that if one class is None, the other is used."""
        base = SettingsParameters.create(settings_class=TestSettings)
        other = SettingsParameters.create()
        result = SettingsParameters.merge(base, other)
        assert result.settings_class is TestSettings


class TestMergePrioritiseBase:
    """Test the prioritise_base flag across all fields."""

    @pytest.mark.unit
    def test_prioritise_base_full(self):
        """Test that prioritise_base=True keeps all base values."""
        base = SettingsParameters.create(
            settings_class=TestSettings,
            config_files=["base.yaml"],
            env_prefix="BASE_",
            secrets_dir="/base/secrets",
            TEST_VAL_1="base_value"
        )
        other = SettingsParameters.create(
            settings_class=TestSettings,
            config_files=["other.yaml"],
            env_prefix="OTHER_",
            secrets_dir="/other/secrets",
            TEST_VAL_1="other_value"
        )
        result = SettingsParameters.merge(base, other, prioritise_base=True)
        assert result.env_prefix == "BASE_"
        assert result.secrets_dir == "/base/secrets"
        assert result.kwargs["TEST_VAL_1"] == "base_value"
        config_files_str = tuple(str(f) for f in result.config_files)
        assert config_files_str == ("base.yaml",)


class TestMergeIntegration:
    """Integration tests for merge workflow."""

    @pytest.mark.integration
    def test_full_integration_workflow(self):
        """Test complete merge workflow with multiple operations."""
        # Create base parameters
        base = SettingsParameters.create(
            settings_class=TestSettings,
            config_files=["config1.yaml"],
            env_prefix="BASE_",
            TEST_VAL_1="base_value"
        )

        # Merge with another set of parameters
        other = SettingsParameters.create(
            settings_class=TestSettings,
            config_files=["config2.yaml"],
            TEST_VAL_2="other_value"
        )
        merged = SettingsParameters.merge(base, other)

        # Verify merged result
        config_files_str = set(str(f) for f in merged.config_files)
        assert config_files_str == {"config1.yaml", "config2.yaml"}
        assert merged.kwargs["TEST_VAL_1"] == "base_value"
        assert merged.kwargs["TEST_VAL_2"] == "other_value"
        assert merged.env_prefix == "BASE_"

        # Merge again with a third set
        third = SettingsParameters.create(
            settings_class=TestSettings,
            config_files=["config3.yaml"],
            TEST_VAL_3="final_value"
        )
        final = SettingsParameters.merge(merged, third)

        # Verify final result
        final_config_files_str = set(str(f) for f in final.config_files)
        assert final_config_files_str == {"config1.yaml", "config2.yaml", "config3.yaml"}
        assert final.kwargs["TEST_VAL_1"] == "base_value"
        assert final.kwargs["TEST_VAL_2"] == "other_value"
        assert final.kwargs["TEST_VAL_3"] == "final_value"
