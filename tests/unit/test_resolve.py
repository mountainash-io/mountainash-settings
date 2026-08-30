"""Unit tests for general reference resolution."""

import typing as t

import pytest
from pydantic import (
    AliasChoices,
    AliasPath,
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
)

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

    def test_list_values_resolve_recursively(self):
        data = {
            "items": [
                "secret:first.value",
                {"token": "secret:second.value"},
            ]
        }
        result = resolve_references_in_dict(data, _test_backend)
        assert result == {
            "items": [
                "resolved_first/value",
                {"token": "resolved_second/value"},
            ]
        }

    def test_tuple_values_preserve_tuple_type(self):
        data = {"items": ("secret:first.value", "plain")}
        result = resolve_references_in_dict(data, _test_backend)
        assert result == {"items": ("resolved_first/value", "plain")}
        assert isinstance(result["items"], tuple)

    def test_nested_containers_do_not_mutate_input(self):
        data = {"items": [{"token": "secret:api.token"}]}
        result = resolve_references_in_dict(data, _test_backend)
        assert data == {"items": [{"token": "secret:api.token"}]}
        assert result is not data
        assert result["items"] is not data["items"]

    def test_secretstr_values_remain_wrapped_in_containers(self):
        data = {
            "direct": SecretStr("secret:direct.value"),
            "items": [SecretStr("secret:list.value")],
            "pair": (SecretStr("secret:tuple.value"),),
        }

        result = resolve_references_in_dict(data, _test_backend)

        resolved = [
            result["direct"],
            result["items"][0],
            result["pair"][0],
        ]
        assert all(isinstance(value, SecretStr) for value in resolved)
        assert [value.get_secret_value() for value in resolved] == [
            "resolved_direct/value",
            "resolved_list/value",
            "resolved_tuple/value",
        ]

    def test_secretstr_custom_prefix_remains_wrapped(self):
        data = {"token": SecretStr("vault:api.token")}

        result = resolve_references_in_dict(
            data,
            _test_backend,
            prefix="vault:",
        )

        assert isinstance(result["token"], SecretStr)
        assert result["token"].get_secret_value() == "resolved_api/token"

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


class _ContainerSecretModel(BaseModel):
    model_config = ConfigDict(frozen=True)
    token: SecretStr


class _SettingsWithContainers(MountainAshBaseSettings):
    mapping: dict[str, t.Any]
    items: list[t.Any]
    pair: tuple[t.Any, ...]
    models: list[_ContainerSecretModel]


class _AliasOnlySecretModel(BaseModel):
    model_config = ConfigDict(frozen=True)
    token: SecretStr = Field(validation_alias="TOKEN")


class _AliasPathSecretModel(BaseModel):
    model_config = ConfigDict(frozen=True)
    token: SecretStr = Field(
        validation_alias=AliasPath("auth", "TOKEN"),
    )
    choice: SecretStr = Field(
        validation_alias=AliasChoices("CHOICE", "choice"),
    )


class _SettingsWithAliasedContainers(MountainAshBaseSettings):
    aliases: list[_AliasOnlySecretModel]
    paths: list[_AliasPathSecretModel]



class _AliasChoicesCollisionModel(BaseModel):
    model_config = ConfigDict(frozen=True)
    first: SecretStr = Field(
        validation_alias=AliasChoices("shared", "first"),
    )
    second: SecretStr = Field(
        validation_alias=AliasChoices("shared", "second"),
    )


class _SettingsWithAliasChoicesCollision(MountainAshBaseSettings):
    values: list[_AliasChoicesCollisionModel]


class _PositiveIndexedAliasModel(BaseModel):
    model_config = ConfigDict(frozen=True)
    token: SecretStr = Field(
        validation_alias=AliasPath("items", 1),
    )


class _SettingsWithPositiveIndexedAlias(MountainAshBaseSettings):
    values: list[_PositiveIndexedAliasModel]


class _NegativeIndexedAliasModel(BaseModel):
    model_config = ConfigDict(frozen=True)
    token: SecretStr = Field(
        validation_alias=AliasPath("items", -1),
    )


class _SettingsWithNegativeIndexedAlias(MountainAshBaseSettings):
    values: list[_NegativeIndexedAliasModel]


class _PositiveNegativeIndexedAliasModel(BaseModel):
    model_config = ConfigDict(frozen=True)
    positive: SecretStr = Field(
        validation_alias=AliasPath("items", 1),
    )
    negative: SecretStr = Field(
        validation_alias=AliasPath("items", -1),
    )


class _NegativePositiveIndexedAliasModel(BaseModel):
    model_config = ConfigDict(frozen=True)
    negative: SecretStr = Field(
        validation_alias=AliasPath("items", -1),
    )
    positive: SecretStr = Field(
        validation_alias=AliasPath("items", 1),
    )


class _SettingsWithSharedIndexedAliases(MountainAshBaseSettings):
    forward: list[_PositiveNegativeIndexedAliasModel]
    reverse: list[_NegativePositiveIndexedAliasModel]


class _CompatibleSharedAliasModel(BaseModel):
    model_config = ConfigDict(frozen=True)
    first: SecretStr = Field(validation_alias="shared")
    second: SecretStr = Field(validation_alias="shared")


class _SettingsWithCompatibleSharedAlias(MountainAshBaseSettings):
    values: list[_CompatibleSharedAliasModel]


class _CompatibleOverlappingAliasModel(BaseModel):
    model_config = ConfigDict(frozen=True)
    auth: dict[str, t.Any] = Field(validation_alias="auth")
    token: SecretStr = Field(
        validation_alias=AliasPath("auth", "token"),
    )


class _SettingsWithCompatibleOverlappingAlias(MountainAshBaseSettings):
    values: list[_CompatibleOverlappingAliasModel]


class _RejectResolvedNestedModel(BaseModel):
    model_config = ConfigDict(frozen=True)
    token: str

    @field_validator("token")
    @classmethod
    def reject_resolved_value(cls, value: str) -> str:
        if value == "resolved_nested/value":
            raise ValueError(f"resolved value rejected: {value}")
        return value


class _SettingsWithRejectResolvedNested(MountainAshBaseSettings):
    values: list[_RejectResolvedNestedModel]


class _RejectResolvedRootSettings(MountainAshBaseSettings):
    token: str

    @field_validator("token")
    @classmethod
    def reject_resolved_value(cls, value: str) -> str:
        if value == "resolved_root/value":
            raise ValueError(f"resolved value rejected: {value}")
        return value

class _RejectTypeErrorNestedModel(BaseModel):
    model_config = ConfigDict(frozen=True)
    token: str

    @field_validator("token")
    @classmethod
    def reject_resolved_value(cls, value: str) -> str:
        if value == "resolved_type_nested/value":
            raise TypeError(f"resolved value rejected: {value}")
        return value


class _SettingsWithRejectTypeErrorNested(MountainAshBaseSettings):
    values: list[_RejectTypeErrorNestedModel]


class _RejectTypeErrorRootSettings(MountainAshBaseSettings):
    token: str

    @field_validator("token")
    @classmethod
    def reject_resolved_value(cls, value: str) -> str:
        if value == "resolved_type_root/value":
            raise TypeError(f"resolved value rejected: {value}")
        return value


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

    def test_resolves_dict_list_tuple_and_models(self):
        settings = _SettingsWithContainers(
            mapping={"token": "secret:mapping.token"},
            items=["secret:list.token", {"inner": "secret:list.inner"}],
            pair=("secret:tuple.token", "plain"),
            models=[{"token": "secret:model.token"}],
        )

        resolve_references_in_model_tree(settings, _test_backend)

        assert settings.mapping == {"token": "resolved_mapping/token"}
        assert settings.items == [
            "resolved_list/token",
            {"inner": "resolved_list/inner"},
        ]
        assert settings.pair == ("resolved_tuple/token", "plain")
        assert settings.models[0].token.get_secret_value() == "resolved_model/token"

    def test_rebuilds_alias_only_and_alias_path_models_inside_lists(self):
        settings = _SettingsWithAliasedContainers(
            aliases=[{"TOKEN": "secret:alias.token"}],
            paths=[{
                "auth": {"TOKEN": "secret:path.token"},
                "CHOICE": "secret:choice.token",
            }],
        )

        resolve_references_in_model_tree(settings, _test_backend)

        assert settings.aliases[0].token.get_secret_value() == "resolved_alias/token"
        assert settings.paths[0].token.get_secret_value() == "resolved_path/token"
        assert settings.paths[0].choice.get_secret_value() == "resolved_choice/token"

    def test_alias_choices_rebuild_without_colliding_paths(self):
        settings = _SettingsWithAliasChoicesCollision(
            values=[{
                "first": "secret:first.token",
                "second": "secret:second.token",
            }],
        )

        resolve_references_in_model_tree(settings, _test_backend)

        assert settings.values[0].first.get_secret_value() == "resolved_first/token"
        assert settings.values[0].second.get_secret_value() == "resolved_second/token"

    def test_positive_alias_path_index_rebuilds(self):
        settings = _SettingsWithPositiveIndexedAlias(
            values=[{"items": [None, "secret:positive.token"]}],
        )

        resolve_references_in_model_tree(settings, _test_backend)

        assert settings.values[0].token.get_secret_value() == "resolved_positive/token"

    def test_negative_alias_path_index_rebuilds(self):
        settings = _SettingsWithNegativeIndexedAlias(
            values=[{"items": ["secret:negative.token"]}],
        )

        resolve_references_in_model_tree(settings, _test_backend)

        assert settings.values[0].token.get_secret_value() == "resolved_negative/token"

    def test_shared_positive_and_negative_alias_paths_are_order_independent(self):
        settings = _SettingsWithSharedIndexedAliases(
            forward=[{
                "items": [
                    "unused",
                    "secret:positive.token",
                    "secret:negative.token",
                ],
            }],
            reverse=[{
                "items": [
                    "unused",
                    "secret:positive.token",
                    "secret:negative.token",
                ],
            }],
        )

        resolve_references_in_model_tree(settings, _test_backend)

        assert settings.forward[0].positive.get_secret_value() == "resolved_positive/token"
        assert settings.forward[0].negative.get_secret_value() == "resolved_negative/token"
        assert settings.reverse[0].positive.get_secret_value() == "resolved_positive/token"
        assert settings.reverse[0].negative.get_secret_value() == "resolved_negative/token"

    def test_compatible_identical_alias_paths_coalesce(self):
        settings = _SettingsWithCompatibleSharedAlias(
            values=[{"shared": "secret:shared.token"}],
        )

        resolve_references_in_model_tree(settings, _test_backend)

        assert settings.values[0].first.get_secret_value() == "resolved_shared/token"
        assert settings.values[0].second.get_secret_value() == "resolved_shared/token"

    def test_compatible_overlapping_alias_paths_merge(self):
        settings = _SettingsWithCompatibleOverlappingAlias(
            values=[{"auth": {"token": "secret:shared.token"}}],
        )

        resolve_references_in_model_tree(settings, _test_backend)

        assert settings.values[0].auth == {"token": "resolved_shared/token"}
        assert settings.values[0].token.get_secret_value() == "resolved_shared/token"

    def test_nested_validation_errors_are_sanitized(self):
        settings = _SettingsWithRejectResolvedNested(
            values=[{"token": "secret:nested.value"}],
        )

        with pytest.raises(ValueError) as caught:
            resolve_references_in_model_tree(settings, _test_backend)

        error = caught.value
        assert "_RejectResolvedNestedModel" in str(error)
        assert "token" in str(error)
        assert "resolved_nested/value" not in str(error)
        assert "resolved value rejected" not in str(error)
        assert error.__cause__ is None
        assert error.__context__ is None

    def test_root_assignment_validation_errors_are_sanitized(self):
        settings = _RejectResolvedRootSettings(token="secret:root.value")

        with pytest.raises(ValueError) as caught:
            resolve_references_in_model_tree(settings, _test_backend)

        error = caught.value
        assert "_RejectResolvedRootSettings" in str(error)
        assert "token" in str(error)
        assert "resolved_root/value" not in str(error)
        assert "resolved value rejected" not in str(error)
        assert error.__cause__ is None
        assert error.__context__ is None

    def test_nested_type_errors_are_sanitized(self):
        settings = _SettingsWithRejectTypeErrorNested(
            values=[{"token": "secret:type_nested.value"}],
        )

        with pytest.raises(ValueError) as caught:
            resolve_references_in_model_tree(settings, _test_backend)

        error = caught.value
        assert "_RejectTypeErrorNestedModel" in str(error)
        assert "token" in str(error)
        assert "resolved_type_nested/value" not in str(error)
        assert "resolved value rejected" not in str(error)
        assert error.__cause__ is None
        assert error.__context__ is None

    def test_root_assignment_type_errors_are_sanitized(self):
        settings = _RejectTypeErrorRootSettings(token="secret:type_root.value")

        with pytest.raises(ValueError) as caught:
            resolve_references_in_model_tree(settings, _test_backend)

        error = caught.value
        assert "_RejectTypeErrorRootSettings" in str(error)
        assert "token" in str(error)
        assert "resolved_type_root/value" not in str(error)
        assert "resolved value rejected" not in str(error)
        assert error.__cause__ is None
        assert error.__context__ is None
