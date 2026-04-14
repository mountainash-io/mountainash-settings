import pytest
from typing import Dict, Any
from dataclasses import FrozenInstanceError
from pydantic_settings import BaseSettings
from upath import UPath

from mountainash_settings.settings_parameters.settings_parameters import SettingsParameters


class MockSettings(BaseSettings):
    field1: str = "default1"
    field2: int = 42
    field3: bool = True


class TestSettingsParameters:

    def test_initialization_with_defaults_succeeds(self):
        params = SettingsParameters()
        assert params.config_files is None
        assert params.settings_class is None
        assert params.env_prefix is None
        assert params.secrets_dir is None
        assert params.kwargs is None

    def test_initialization_with_all_parameters_succeeds(self):
        config_files = ["config.yaml"]
        kwargs = {"DEBUG": True}

        params = SettingsParameters(
            config_files=config_files,
            settings_class=MockSettings,
            env_prefix="TEST_",
            secrets_dir="/secrets",
            kwargs=kwargs
        )

        assert params.config_files == config_files
        assert params.settings_class == MockSettings
        assert params.env_prefix == "TEST_"
        assert params.secrets_dir == "/secrets"
        assert params.kwargs == kwargs

    def test_dataclass_is_frozen(self):
        params = SettingsParameters()
        with pytest.raises(FrozenInstanceError):
            params.config_files = ("new_config.yaml",)

    def test_hash_returns_consistent_value(self):
        params1 = SettingsParameters(settings_class=MockSettings)
        params2 = SettingsParameters(settings_class=MockSettings)

        assert hash(params1) == hash(params2)

    def test_hash_different_for_different_params(self):
        params1 = SettingsParameters(env_prefix="PREFIX1_")
        params2 = SettingsParameters(env_prefix="PREFIX2_")

        assert hash(params1) != hash(params2)

    def test_create_with_all_parameters_succeeds(self):
        params = SettingsParameters.create(
            config_files="config.yaml",
            settings_class=MockSettings,
            env_prefix="TEST_",
            secrets_dir="/secrets",
            DEBUG=True,
            VERBOSE=False
        )

        assert isinstance(params.config_files, tuple)
        assert params.settings_class == MockSettings
        assert params.env_prefix == "TEST_"
        assert params.secrets_dir == "/secrets"
        assert params.kwargs["DEBUG"] is True
        assert params.kwargs["VERBOSE"] is False

    def test_create_with_single_config_file_converts_to_tuple(self):
        params = SettingsParameters.create(config_files="single_config.yaml")
        assert isinstance(params.config_files, tuple)
        assert len(params.config_files) == 1

    def test_create_with_list_config_files_converts_to_tuple(self):
        config_files = ["config1.yaml", "config2.yaml"]
        params = SettingsParameters.create(config_files=config_files)
        assert isinstance(params.config_files, tuple)
        assert len(params.config_files) == 2

    def test_create_with_no_kwargs_sets_kwargs_to_none(self):
        params = SettingsParameters.create()
        assert params.kwargs is None

    def test_to_dict_with_all_fields_populated(self):
        kwargs = {"DEBUG": True, "VERBOSE": False}
        params = SettingsParameters(
            config_files=("config.yaml",),
            settings_class=MockSettings,
            env_prefix="TEST_",
            secrets_dir="/secrets",
            kwargs=kwargs
        )

        result = params.to_dict()

        assert result["config_files"] == ["config.yaml"]
        assert result["kwargs"] == kwargs
        assert result["settings_class"] == MockSettings
        assert result["env_prefix"] == "TEST_"
        assert result["secrets_dir"] == "/secrets"

    def test_to_dict_with_none_values(self):
        params = SettingsParameters()
        result = params.to_dict()

        assert result["config_files"] is None
        assert result["kwargs"] is None
        assert result["settings_class"] is None
        assert result["env_prefix"] is None
        assert result["secrets_dir"] is None

    def test_get_settings_kwarg_names_with_mock_settings(self):
        params = SettingsParameters(settings_class=MockSettings)
        result = params._get_settings_kwarg_names()

        expected_fields = {"field1", "field2", "field3"}
        assert result == expected_fields

    def test_get_settings_kwarg_names_with_none_settings_class(self):
        params = SettingsParameters()
        result = params._get_settings_kwarg_names()
        assert result == set()

    def test_get_settings_kwarg_names_with_provided_class(self):
        params = SettingsParameters()
        result = params._get_settings_kwarg_names(MockSettings)

        expected_fields = {"field1", "field2", "field3"}
        assert result == expected_fields

    def test_get_valid_kwarg_names_includes_reserved_pydantic_kwargs(self):
        params = SettingsParameters(settings_class=MockSettings)
        result = params._get_valid_kwarg_names()

        assert "field1" in result
        assert "field2" in result
        assert "field3" in result
        assert "_case_sensitive" in result
        assert "_env_prefix" in result

    def test_get_attribute_settings_kwargs_filters_correctly(self):
        kwargs = {
            "field1": "value1",
            "field2": 100,
            "_env_prefix": "TEST_",
            "invalid_field": "should_be_filtered"
        }

        params = SettingsParameters(settings_class=MockSettings, kwargs=kwargs)
        result = params.get_attribute_settings_kwargs()

        assert "field1" in result
        assert "field2" in result
        assert "_env_prefix" in result
        assert "invalid_field" not in result

    def test_get_pydantic_settings_kwargs_returns_only_pydantic_kwargs(self):
        kwargs = {
            "field1": "value1",
            "_env_prefix": "TEST_",
            "_case_sensitive": True,
            "custom_field": "value"
        }

        params = SettingsParameters(kwargs=kwargs)
        result = params.get_pydantic_settings_kwargs()

        assert "_env_prefix" in result
        assert "_case_sensitive" in result
        assert "field1" not in result
        assert "custom_field" not in result

    def test_get_pydantic_modelconfig_kwargs_returns_only_modelconfig_kwargs(self):
        kwargs = {
            "extra": "allow",
            "arbitrary_types_allowed": True,
            "field1": "value1",
            "_env_prefix": "TEST_"
        }

        params = SettingsParameters(kwargs=kwargs)
        result = params.get_pydantic_modelconfig_kwargs()

        assert "extra" in result
        assert "arbitrary_types_allowed" in result
        assert "field1" not in result
        assert "_env_prefix" not in result

    def test_get_all_kwargs_returns_all_kwargs(self):
        kwargs = {
            "field1": "value1",
            "_env_prefix": "TEST_",
            "custom": "value"
        }

        params = SettingsParameters(kwargs=kwargs)
        result = params.get_all_kwargs()

        assert result == kwargs

    def test_get_all_kwargs_returns_empty_dict_when_none(self):
        params = SettingsParameters()
        result = params.get_all_kwargs()
        assert result == {}
