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

    def test_get_valid_kwarg_names_only_includes_declared_fields(self):
        """M5 (MAS-SEC-004): only declared fields are valid attribute kwargs;
        underscore source-control names are no longer treated as valid."""
        params = SettingsParameters(settings_class=MockSettings)
        result = params._get_valid_kwarg_names()

        assert "field1" in result
        assert "field2" in result
        assert "field3" in result
        assert "_case_sensitive" not in result
        assert "_env_prefix" not in result

    def test_get_attribute_settings_kwargs_filters_correctly(self):
        kwargs = {
            "field1": "value1",
            "field2": 100,
            "invalid_field": "should_be_filtered"
        }

        params = SettingsParameters(settings_class=MockSettings, kwargs=kwargs)
        result = params.get_attribute_settings_kwargs()

        assert "field1" in result
        assert "field2" in result
        assert "invalid_field" not in result

    def test_get_attribute_settings_kwargs_rejects_underscore_source_control(self):
        """M5 (MAS-SEC-004): every underscore-prefixed kwarg fails value-free
        before sources open, by the leading-underscore rule."""
        params = SettingsParameters(
            settings_class=MockSettings,
            kwargs={"field1": "value1", "_env_prefix": "TEST_"},
        )

        with pytest.raises(ValueError, match="_env_prefix"):
            params.get_attribute_settings_kwargs()

    def test_get_attribute_settings_kwargs_rejects_undeclared_legacy_schema_control(self):
        """A legacy schema-control name is rejected unless the settings class
        declares a field of that name; it never mutates shared class config."""
        params = SettingsParameters(
            settings_class=MockSettings,
            kwargs={"extra": "allow"},
        )

        with pytest.raises(ValueError, match="extra"):
            params.get_attribute_settings_kwargs()

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


class _Reader:
    def __init__(self, records=None):
        self.records = records or {}
    def get(self, key):
        return self.records.get(key)

class _FalseyReader(_Reader):
    def __bool__(self):
        return False

class _HostileReader(_Reader):
    def __eq__(self, other):
        raise AssertionError("store __eq__ called")
    def __hash__(self):
        raise AssertionError("store __hash__ called")
    def __repr__(self):
        raise AssertionError("store __repr__ called")


class TestSecretStore:

    def test_secret_store_defaults_to_none(self):
        assert SettingsParameters().secret_store is None

    def test_distinct_stores_are_distinct_identities(self):
        a = SettingsParameters.create(settings_class=MockSettings, secret_store=_Reader())
        b = SettingsParameters.create(settings_class=MockSettings, secret_store=_Reader())
        assert a != b

    def test_same_store_object_is_equal(self):
        store = _Reader()
        a = SettingsParameters.create(settings_class=MockSettings, secret_store=store)
        b = SettingsParameters.create(settings_class=MockSettings, secret_store=store)
        assert a == b and hash(a) == hash(b)

    def test_hostile_store_methods_never_called(self):
        store = _HostileReader()
        a = SettingsParameters.create(settings_class=MockSettings, secret_store=store)
        b = SettingsParameters.create(settings_class=MockSettings, secret_store=store)
        hash(a); assert a == b; repr(a)
        assert SettingsParameters.merge(a, b).secret_store is store

    def test_store_absent_from_to_dict_and_repr(self):
        params = SettingsParameters.create(settings_class=MockSettings, secret_store=_Reader())
        assert "secret_store" not in params.to_dict()
        assert "_Reader" not in repr(params)

    def test_merge_last_non_none_wins(self):
        first, second = _Reader(), _Reader()
        base = SettingsParameters.create(settings_class=MockSettings, secret_store=first)
        other = SettingsParameters.create(settings_class=MockSettings, secret_store=second)
        assert SettingsParameters.merge(base, other).secret_store is second
        assert SettingsParameters.merge(base, other, prioritise_base=True).secret_store is first

    def test_merge_none_does_not_detach(self):
        store = _Reader()
        base = SettingsParameters.create(settings_class=MockSettings, secret_store=store)
        other = SettingsParameters.create(settings_class=MockSettings)
        assert SettingsParameters.merge(base, other).secret_store is store

    def test_merge_falsey_store_is_still_bound(self):
        store = _FalseyReader()
        base = SettingsParameters.create(settings_class=MockSettings, secret_store=_Reader())
        other = SettingsParameters.create(settings_class=MockSettings, secret_store=store)
        assert SettingsParameters.merge(base, other).secret_store is store

    def test_dataclasses_replace_preserves_identity(self):
        import dataclasses
        store = _Reader()
        params = SettingsParameters.create(settings_class=MockSettings, secret_store=store)
        assert dataclasses.replace(params, env_prefix="X_").secret_store is store
