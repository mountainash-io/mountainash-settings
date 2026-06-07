"""Unit tests for general reference resolution."""

import typing as t

import pytest
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from mountainash_settings.resolve import (
    resolve_references_in_dict,
    resolve_references_in_model_tree,
)
from mountainash_settings.settings.base_settings import MountainAshBaseSettings


class _TestBackendData(dict):
    """Dict that returns 'resolved_key/field' for any field lookup."""
    def __init__(self, key: str):
        super().__init__()
        self._key = key

    def __contains__(self, field):
        return True

    def __getitem__(self, field):
        return f"resolved_{self._key}/{field}"

    def __len__(self):
        return 2  # Not 1, so _resolve_value doesn't try single-value extraction


class _TestBackend:
    def get(self, key: str) -> dict[str, t.Any] | None:
        return _TestBackendData(key)

    def set(self, key: str, data: dict[str, t.Any]) -> None:
        pass

    def delete(self, key: str) -> None:
        pass

    def transaction(self, key: str):
        from contextlib import nullcontext
        return nullcontext()


_test_backend = _TestBackend()


@pytest.mark.unit
class TestResolveReferencesInDict:
    def test_flat_dict_resolves_prefixed_value(self):
        data = {"PASSWORD": "secret:db.password"}
        result = resolve_references_in_dict(data, _test_backend)
        assert result == {"PASSWORD": "resolved_db/password"}

    def test_nested_dict_resolved_recursively(self):
        data = {"outer": {"inner": "secret:nested.key"}}
        result = resolve_references_in_dict(data, _test_backend)
        assert result == {"outer": {"inner": "resolved_nested/key"}}

    def test_non_string_values_passed_through(self):
        data = {"count": 42, "flag": True, "items": [1, 2, 3]}
        result = resolve_references_in_dict(data, _test_backend)
        assert result == data

    def test_non_prefixed_strings_passed_through(self):
        data = {"name": "plain_value", "host": "localhost"}
        result = resolve_references_in_dict(data, _test_backend)
        assert result == data

    def test_empty_dict_returns_empty(self):
        assert resolve_references_in_dict({}, _test_backend) == {}

    def test_custom_prefix(self):
        data = {"TOKEN": "vault:api.token"}
        result = resolve_references_in_dict(data, _test_backend, prefix="vault:")
        assert result == {"TOKEN": "resolved_api/token"}

    def test_does_not_mutate_input(self):
        data = {"PASSWORD": "secret:db.password"}
        original = dict(data)
        resolve_references_in_dict(data, _test_backend)
        assert data == original


class _FlatTestSettings(MountainAshBaseSettings):
    USERNAME: str = Field(default="admin")
    PASSWORD: str = Field(default="changeme")
    PORT: int = Field(default=5432)


@pytest.mark.unit
class TestResolveReferencesInModelTreeFlat:
    def test_resolves_prefixed_string_fields(self):
        instance = _FlatTestSettings(USERNAME="admin", PASSWORD="secret:db.pass")
        resolve_references_in_model_tree(instance, _test_backend)
        assert instance.PASSWORD == "resolved_db/pass"

    def test_skips_non_string_fields(self):
        instance = _FlatTestSettings(PORT=5432)
        resolve_references_in_model_tree(instance, _test_backend)
        assert instance.PORT == 5432

    def test_skips_non_prefixed_strings(self):
        instance = _FlatTestSettings(USERNAME="admin", PASSWORD="plaintext")
        resolve_references_in_model_tree(instance, _test_backend)
        assert instance.PASSWORD == "plaintext"

    def test_resolves_secretstr_field(self):
        class WithSecretStr(MountainAshBaseSettings):
            TOKEN: SecretStr = Field(default=SecretStr("default"))

        instance = WithSecretStr(TOKEN="secret:api.token")
        resolve_references_in_model_tree(instance, _test_backend)
        assert instance.TOKEN.get_secret_value() == "resolved_api/token"

    def test_skips_settings_source_bookkeeping_fields(self):
        instance = _FlatTestSettings(USERNAME="admin")
        resolve_references_in_model_tree(instance, _test_backend)
        assert instance.SETTINGS_CLASS is not None


class _NestedModel(BaseModel):
    """Non-frozen nested model for testing."""
    host: str = "localhost"
    password: str = "changeme"


class _FrozenNestedModel(BaseModel):
    """Frozen nested model (like AuthSpec)."""
    model_config = ConfigDict(frozen=True)
    kind: str = "test"
    token: SecretStr


class _DeepNestedInner(BaseModel):
    model_config = ConfigDict(frozen=True)
    api_key: str = "default"


class _DeepNestedOuter(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str = "outer"
    inner: _DeepNestedInner


class _SettingsWithNested(MountainAshBaseSettings):
    APP_NAME: str = Field(default="test")
    nested: _NestedModel = Field(default_factory=_NestedModel)


class _SettingsWithFrozenNested(MountainAshBaseSettings):
    APP_NAME: str = Field(default="test")
    frozen_nested: _FrozenNestedModel


class _SettingsWithDeepNesting(MountainAshBaseSettings):
    APP_NAME: str = Field(default="test")
    deep: _DeepNestedOuter


@pytest.mark.unit
class TestResolveReferencesInModelTreeNested:
    def test_resolves_nested_model_str_field(self):
        instance = _SettingsWithNested(
            nested={"host": "localhost", "password": "secret:db.pass"}
        )
        resolve_references_in_model_tree(instance, _test_backend)
        assert instance.nested.password == "resolved_db/pass"
        assert instance.nested.host == "localhost"

    def test_resolves_frozen_nested_model_secretstr_field(self):
        instance = _SettingsWithFrozenNested(
            frozen_nested={"kind": "test", "token": "secret:api.token"}
        )
        resolve_references_in_model_tree(instance, _test_backend)
        assert instance.frozen_nested.token.get_secret_value() == "resolved_api/token"
        assert instance.frozen_nested.kind == "test"

    def test_frozen_nested_is_new_instance(self):
        instance = _SettingsWithFrozenNested(
            frozen_nested={"kind": "test", "token": "secret:api.token"}
        )
        original_nested = instance.frozen_nested
        resolve_references_in_model_tree(instance, _test_backend)
        assert instance.frozen_nested is not original_nested

    def test_no_rebuild_when_no_secrets(self):
        instance = _SettingsWithFrozenNested(
            frozen_nested={"kind": "test", "token": "plain_token"}
        )
        original_nested = instance.frozen_nested
        resolve_references_in_model_tree(instance, _test_backend)
        assert instance.frozen_nested is original_nested

    def test_two_levels_of_nesting(self):
        instance = _SettingsWithDeepNesting(
            deep={"name": "outer", "inner": {"api_key": "secret:deep.key"}}
        )
        resolve_references_in_model_tree(instance, _test_backend)
        assert instance.deep.inner.api_key == "resolved_deep/key"
        assert instance.deep.name == "outer"

    def test_custom_prefix_on_nested(self):
        instance = _SettingsWithNested(
            nested={"host": "localhost", "password": "vault:db.pass"}
        )
        resolve_references_in_model_tree(instance, _test_backend, prefix="vault:")
        assert instance.nested.password == "resolved_db/pass"
