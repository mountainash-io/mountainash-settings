"""
Comprehensive tests for SettingsManager.

Tests cover:
- Settings creation and caching
- Initialization checks
- Settings retrieval
- Runtime override application
- MountainAshBaseSettings and non-MountainAshBaseSettings paths
- Error handling
"""

import pytest
from pydantic_settings import BaseSettings
from pydantic import Field

from mountainash_settings import (
    SettingsManager,
    SettingsParameters,
    get_settings_manager,
)
from mountainash_settings.settings_parameters import SettingsFileHandler
from fixtures.settings_classes import TestSettings, MockBaseSettings


class TestSettingsManagerInitialization:
    """Test SettingsManager initialization."""

    def test_init_creates_empty_cache(self):
        """Test that __init__ creates an empty settings cache."""
        manager = SettingsManager()
        assert isinstance(manager.settings_object_cache, dict)
        assert len(manager.settings_object_cache) == 0

    def test_get_settings_manager_returns_singleton(self):
        """Test that get_settings_manager returns cached singleton."""
        manager1 = get_settings_manager()
        manager2 = get_settings_manager()
        assert manager1 is manager2


class TestIsInitialised:
    """Test is_initialised method."""

    def test_returns_false_for_new_params(self, isolated_settings_manager):
        """Test that new params returns False."""
        params = SettingsParameters.create(
            settings_class=TestSettings
        )
        assert isolated_settings_manager.is_initialised(params) is False

    def test_returns_true_after_initialization(self, isolated_settings_manager):
        """Test that initialized params returns True."""
        params = SettingsParameters.create(
            settings_class=TestSettings
        )

        # Create settings
        isolated_settings_manager.get_or_create_settings(params)

        # Should now be initialized
        assert isolated_settings_manager.is_initialised(params) is True

    def test_uses_hash_for_cache_key(self, isolated_settings_manager):
        """Test that cache key is based on SettingsParameters hash."""
        params1 = SettingsParameters.create(
            settings_class=TestSettings
        )
        params2 = SettingsParameters.create(
            settings_class=TestSettings
        )

        # Initialize with params1
        isolated_settings_manager.get_or_create_settings(params1)

        # params2 has same hash, should also be initialized
        assert isolated_settings_manager.is_initialised(params2) is True


class TestGetOrCreateSettings:
    """Test get_or_create_settings method."""

    @pytest.mark.unit
    def test_creates_new_settings_for_first_call(self, isolated_settings_manager):
        """Test that first call creates new settings instance."""
        params = SettingsParameters.create(
            settings_class=TestSettings,
            TEST_VAL_1="value1"
        )

        settings = isolated_settings_manager.get_or_create_settings(params)

        assert settings is not None
        assert isinstance(settings, TestSettings)
        assert settings.TEST_VAL_1 == "value1"

    @pytest.mark.unit
    def test_returns_cached_settings_for_second_call(self, isolated_settings_manager):
        """Test that second call returns cached instance."""
        params = SettingsParameters.create(
            settings_class=TestSettings
        )

        # First call
        settings1 = isolated_settings_manager.get_or_create_settings(params)

        # Second call should return same instance
        settings2 = isolated_settings_manager.get_or_create_settings(params)

        assert settings1 is settings2

    @pytest.mark.unit
    def test_raises_error_if_settings_class_missing(self, isolated_settings_manager):
        """Test that missing settings_class raises ValueError."""
        params = SettingsParameters.create(
            settings_class=None
        )

        with pytest.raises(ValueError, match="settings_class cannot be empty"):
            isolated_settings_manager.get_or_create_settings(params)

    @pytest.mark.unit
    def test_creates_mountainash_base_settings_subclass(self, isolated_settings_manager):
        """Test MountainAshBaseSettings subclass creation path."""
        params = SettingsParameters.create(
            settings_class=TestSettings,
            TEST_VAL_1="mountainash_value"
        )

        settings = isolated_settings_manager.get_or_create_settings(params)

        assert isinstance(settings, TestSettings)
        assert settings.TEST_VAL_1 == "mountainash_value"

    @pytest.mark.unit
    def test_creates_non_mountainash_settings_with_kwargs(self, isolated_settings_manager):
        """Test non-MountainAshBaseSettings class creation with kwargs."""
        params = SettingsParameters.create(
            settings_class=MockBaseSettings,
            env_prefix="NON_MA_WITH_KWARGS_",
            test_field="custom_value",
            test_int=100
        )

        settings = isolated_settings_manager.get_or_create_settings(params)

        assert isinstance(settings, MockBaseSettings)
        assert settings.test_field == "custom_value"
        assert settings.test_int == 100

    @pytest.mark.unit
    def test_creates_non_mountainash_settings_without_kwargs(self, isolated_settings_manager):
        """Test non-MountainAshBaseSettings class creation without kwargs."""
        params = SettingsParameters.create(
            settings_class=MockBaseSettings,
            env_prefix="NON_MA_NO_KWARGS_"
        )

        settings = isolated_settings_manager.get_or_create_settings(params)

        assert isinstance(settings, MockBaseSettings)
        # Should have default values
        assert settings.test_field == "default_value"
        assert settings.test_int == 42

    @pytest.mark.unit
    def test_different_env_prefixes_create_different_settings(self, isolated_settings_manager):
        """Test that different env_prefix values create separate settings instances."""
        params1 = SettingsParameters.create(
            settings_class=TestSettings,
            env_prefix="PREFIX1_",
            TEST_VAL_1="value_p1"
        )
        params2 = SettingsParameters.create(
            settings_class=TestSettings,
            env_prefix="PREFIX2_",
            TEST_VAL_1="value_p2"
        )

        settings1 = isolated_settings_manager.get_or_create_settings(params1)
        settings2 = isolated_settings_manager.get_or_create_settings(params2)

        assert settings1 is not settings2
        assert settings1.TEST_VAL_1 == "value_p1"
        assert settings2.TEST_VAL_1 == "value_p2"


class TestGetSettingsObject:
    """Test get_settings_object method."""

    @pytest.mark.unit
    def test_retrieves_cached_settings(self, isolated_settings_manager):
        """Test retrieving settings from cache."""
        params = SettingsParameters.create(
            settings_class=TestSettings
        )

        # Create and cache settings
        created_settings = isolated_settings_manager.get_or_create_settings(params)

        # Retrieve from cache
        retrieved_settings = isolated_settings_manager.get_settings_object(params)

        assert retrieved_settings is created_settings

    @pytest.mark.unit
    def test_raises_error_for_non_mountainash_settings(self, isolated_settings_manager):
        """Test that non-MountainAshBaseSettings in cache raises ValueError."""
        params = SettingsParameters.create(
            settings_class=MockBaseSettings,
            env_prefix="NON_MA_ERR_"
        )

        # Manually add non-MountainAshBaseSettings to cache
        isolated_settings_manager.settings_object_cache[params] = MockBaseSettings()

        with pytest.raises(ValueError, match="is not a MountainAshBaseSettings object"):
            isolated_settings_manager.get_settings_object(params)

    @pytest.mark.unit
    def test_applies_runtime_override_kwargs(self, isolated_settings_manager):
        """Test that runtime override kwargs are applied to a copy, not the cached instance."""
        params_create = SettingsParameters.create(
            settings_class=TestSettings,
            TEST_VAL_1="original_value"
        )
        created_settings = isolated_settings_manager.get_or_create_settings(params_create)
        assert created_settings.TEST_VAL_1 == "original_value"

        params_override = SettingsParameters.create(
            settings_class=TestSettings,
            TEST_VAL_1="overridden_value"
        )
        retrieved_settings = isolated_settings_manager.get_settings_object(params_override)

        # Retrieved copy has the override
        assert retrieved_settings.TEST_VAL_1 == "overridden_value"
        # Original cached instance is untouched
        assert created_settings.TEST_VAL_1 == "original_value"

    @pytest.mark.unit
    def test_runtime_overrides_do_not_mutate_cached_instance(self, isolated_settings_manager):
        """Test that runtime override kwargs do NOT mutate the cached instance."""
        params_create = SettingsParameters.create(
            settings_class=TestSettings,
            TEST_VAL_1="original_value"
        )
        created_settings = isolated_settings_manager.get_or_create_settings(params_create)
        assert created_settings.TEST_VAL_1 == "original_value"

        params_override = SettingsParameters.create(
            settings_class=TestSettings,
            TEST_VAL_1="overridden_value"
        )
        retrieved_settings = isolated_settings_manager.get_settings_object(params_override)
        assert retrieved_settings.TEST_VAL_1 == "overridden_value"

        # The CACHED instance must NOT have been mutated
        cached_directly = isolated_settings_manager.settings_object_cache[params_create]
        assert cached_directly.TEST_VAL_1 == "original_value"


class TestCacheBehavior:
    """Test caching behavior and cache key logic."""

    @pytest.mark.unit
    def test_cache_key_based_on_structural_params(self, isolated_settings_manager):
        """Test that cache key is based on structural parameters only."""
        # Same structural params (class) but different kwargs
        params1 = SettingsParameters.create(
            settings_class=TestSettings,
            TEST_VAL_1="value1"
        )
        params2 = SettingsParameters.create(
            settings_class=TestSettings,
            TEST_VAL_1="value2"
        )

        # Both should have the same hash (structural params are identical)
        assert hash(params1) == hash(params2)

        # First creation
        settings1 = isolated_settings_manager.get_or_create_settings(params1)

        # Second call with different kwargs but same structural params
        # Should return from cache (as a copy since override kwargs differ)
        settings2 = isolated_settings_manager.get_or_create_settings(params2)

        # Both resolve to the same cache entry (same structural hash)
        assert len(isolated_settings_manager.settings_object_cache) == 1
        # But the returned object has the override applied
        assert settings2.TEST_VAL_1 == "value2"
        # Original cached instance is untouched
        assert settings1.TEST_VAL_1 == "value1"

    @pytest.mark.unit
    def test_cache_stores_by_settings_parameters(self, isolated_settings_manager):
        """Test that cache uses SettingsParameters as key."""
        params = SettingsParameters.create(
            settings_class=TestSettings
        )

        settings = isolated_settings_manager.get_or_create_settings(params)

        # Check cache has the SettingsParameters as key
        assert params in isolated_settings_manager.settings_object_cache
        # And the value should be the settings instance
        assert isolated_settings_manager.settings_object_cache[params] is settings

    @pytest.mark.unit
    def test_multiple_settings_in_cache(self, isolated_settings_manager):
        """Test that cache can hold multiple settings instances."""
        params1 = SettingsParameters.create(
            settings_class=TestSettings,
            env_prefix="MULTI1_"
        )
        params2 = SettingsParameters.create(
            settings_class=TestSettings,
            env_prefix="MULTI2_"
        )
        params3 = SettingsParameters.create(
            settings_class=TestSettings,
            env_prefix="MULTI3_"
        )

        settings1 = isolated_settings_manager.get_or_create_settings(params1)
        settings2 = isolated_settings_manager.get_or_create_settings(params2)
        settings3 = isolated_settings_manager.get_or_create_settings(params3)

        # All should be in cache
        assert isolated_settings_manager.is_initialised(params1)
        assert isolated_settings_manager.is_initialised(params2)
        assert isolated_settings_manager.is_initialised(params3)

        # All should be different instances
        assert settings1 is not settings2
        assert settings2 is not settings3
        assert settings1 is not settings3


class TestIntegration:
    """Integration tests for SettingsManager with realistic scenarios."""

    @pytest.mark.integration
    def test_full_workflow_create_retrieve_reuse(self, isolated_settings_manager):
        """Test complete workflow: create, retrieve, reuse."""
        # Step 1: Create new settings
        params = SettingsParameters.create(
            settings_class=TestSettings,
            TEST_VAL_1="initial_value"
        )

        # Should not be initialized yet
        assert not isolated_settings_manager.is_initialised(params)

        # Create settings
        settings1 = isolated_settings_manager.get_or_create_settings(params)
        assert settings1.TEST_VAL_1 == "initial_value"

        # Should now be initialized
        assert isolated_settings_manager.is_initialised(params)

        # Step 2: Retrieve cached settings (returns copy when kwargs present)
        settings2 = isolated_settings_manager.get_or_create_settings(params)
        assert settings2.TEST_VAL_1 == "initial_value"

        # Step 3: Get settings object directly (returns copy when kwargs present)
        settings3 = isolated_settings_manager.get_settings_object(params)
        assert settings3.TEST_VAL_1 == "initial_value"

        # Cache should still have only one entry
        assert len(isolated_settings_manager.settings_object_cache) == 1

    @pytest.mark.integration
    def test_with_config_files(self, isolated_settings_manager, temp_yaml_file):
        """Test SettingsManager with config files."""
        from mountainash_settings.settings.app.app_settings import AppSettings

        params = SettingsParameters.create(
            settings_class=AppSettings,
            config_files=temp_yaml_file
        )

        settings = isolated_settings_manager.get_or_create_settings(params)

        assert settings.DEBUG is True
        assert settings.LOCALE_TIMEZONE == "EST"


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.edge_case
    def test_validate_config_files_exist_raises_error(self, settings_manager):
        """Test that non-existing config files raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            SettingsFileHandler.validate_config_files_exist(
                config_files=["non_existing_file.yaml"]
            )

    @pytest.mark.edge_case
    def test_none_params_handled_correctly(self, isolated_settings_manager):
        """Test that params with no namespace are handled correctly."""
        params = SettingsParameters.create(
            settings_class=TestSettings
        )

        settings = isolated_settings_manager.get_or_create_settings(params)

        # Should create successfully
        assert settings is not None
        assert isinstance(settings, TestSettings)
