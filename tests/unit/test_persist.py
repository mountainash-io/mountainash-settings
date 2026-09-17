"""Tests for MountainAshBaseSettings.persist() and persist_key()."""
from __future__ import annotations

import typing as t
from contextlib import contextmanager

import pytest
from pydantic import AliasChoices, AliasPath, BaseModel, Field, SecretStr

from mountainash_settings import MountainAshBaseSettings
from mountainash_settings.secrets.registry import (
    clear_secrets_registry,
    register_secrets_backend,
)


class _InMemoryBackend:
    def __init__(self):
        self._store: dict[str, dict[str, t.Any]] = {}
        self._cleared: set[str] = set()

    def get(self, key: str) -> dict[str, t.Any] | None:
        return self._store.get(key)

    def set(self, key: str, data: dict[str, t.Any]) -> None:
        self._store[key] = data
        self._cleared.discard(key)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)
        self._cleared.add(key)

    def is_cleared(self, key: str) -> bool:
        return key in self._cleared

    @contextmanager
    def transaction(self, key: str):
        yield


class _TestSettings(MountainAshBaseSettings):
    TOKEN: str = Field(default=None)
    REFRESH: str = Field(default=None)


@pytest.fixture(autouse=True)
def clean():
    clear_secrets_registry()
    yield
    clear_secrets_registry()


@pytest.mark.unit
class TestPersistKey:
    def test_key_from_class_name_only(self):
        instance = _TestSettings()
        key = instance.persist_key()
        assert key == "_testsettings"

    def test_key_from_env_prefix_and_class(self):
        instance = _TestSettings(env_prefix="STRAVA_")
        key = instance.persist_key()
        assert key == "strava._testsettings"


@pytest.mark.unit
class TestPersist:
    def test_persist_writes_to_backend(self):
        backend = _InMemoryBackend()
        register_secrets_backend("memory", backend)
        instance = _TestSettings(
            TOKEN="old",
            env_prefix="APP_",
            secrets_provider="memory",
        )
        instance.persist({"TOKEN": "new_token", "REFRESH": "new_refresh"})
        stored = backend.get("app._testsettings")
        assert stored["TOKEN"] == "new_token"
        assert stored["REFRESH"] == "new_refresh"

    def test_persist_updates_in_memory(self):
        backend = _InMemoryBackend()
        register_secrets_backend("memory", backend)
        instance = _TestSettings(
            TOKEN="old",
            env_prefix="APP_",
            secrets_provider="memory",
        )
        instance.persist({"TOKEN": "updated"})
        assert instance.TOKEN == "updated"

    def test_persist_with_explicit_key(self):
        backend = _InMemoryBackend()
        register_secrets_backend("memory", backend)
        instance = _TestSettings(
            TOKEN="old",
            secrets_provider="memory",
        )
        instance.persist({"TOKEN": "val"}, key="custom.key")
        assert backend.get("custom.key") == {"TOKEN": "val"}

    def test_persist_raises_without_secrets_provider(self):
        instance = _TestSettings(TOKEN="old")
        with pytest.raises(ValueError, match="secrets_provider"):
            instance.persist({"TOKEN": "new"})


class _ProvenanceSettings(MountainAshBaseSettings):
    HOST: str = "default"
    TOKEN: SecretStr = SecretStr("")
    VALUES: dict[str, t.Any] = Field(default_factory=dict)
    OPAQUE: t.Any = None


@pytest.mark.unit
def test_provenance_diagnostics_do_not_duplicate_secret_values():
    instance = _ProvenanceSettings(TOKEN="caller-private-marker")
    assert instance.TOKEN.get_secret_value() == "caller-private-marker"
    params = instance.extract_settings_parameters()
    assert params.kwargs["TOKEN"] == "caller-private-marker"
    for diagnostic in (repr(instance), repr(instance.model_dump()), repr(params), str(params)):
        assert "caller-private-marker" not in diagnostic
    assert "caller-private-marker" not in instance.model_dump_json(exclude={"SETTINGS_CLASS"})


@pytest.mark.unit
def test_partial_update_and_persist_reconstruct_untouched_reference():
    backend = _InMemoryBackend()
    backend.set("login", {"token": "backend-private-marker"})
    register_secrets_backend("memory", backend)
    instance = _ProvenanceSettings(
        HOST="original", TOKEN=SecretStr("secret:login.token"),
        VALUES={"old": [1]}, secrets_provider="memory",
    )
    instance.update_settings_from_dict({"HOST": "updated"})
    instance.persist({"VALUES": {"new": [2]}}, key="saved")
    backend.delete("login")
    params = instance.extract_settings_parameters()
    assert params.kwargs["TOKEN"].get_secret_value() == "secret:login.token"
    assert params.kwargs["HOST"] == "updated"
    assert params.kwargs["VALUES"] == {"new": [2]}
    assert "backend-private-marker" not in repr(instance)
    backend.set("login", {"token": "rotated"})
    rebuilt = _ProvenanceSettings(settings_parameters=params)
    assert rebuilt.TOKEN.get_secret_value() == "rotated"
    assert rebuilt.HOST == "updated"
    assert rebuilt.VALUES == {"new": [2]}
    assert backend.get("saved") == {"VALUES": {"new": [2]}}


@pytest.mark.unit
def test_extracted_nested_inputs_are_independently_owned():
    supplied = {"nested": [{"value": "original"}]}
    instance = _ProvenanceSettings(VALUES=supplied)
    first = instance.extract_settings_parameters()
    other = _ProvenanceSettings(settings_parameters=first)
    first.kwargs["VALUES"]["nested"][0]["value"] = "changed"
    supplied["nested"][0]["value"] = "caller changed"
    assert instance.extract_settings_parameters().kwargs["VALUES"] == {
        "nested": [{"value": "original"}]
    }
    assert other.VALUES == {"nested": [{"value": "original"}]}


@pytest.mark.unit
def test_unsupported_input_only_prevents_extraction():
    class Opaque:
        def __repr__(self):
            return "opaque-private-marker"

        def __deepcopy__(self, memo):
            return self

    value = Opaque()
    instance = _ProvenanceSettings(OPAQUE=value)
    assert instance.OPAQUE is value
    instance.update_settings_from_dict({"HOST": "updated"})
    assert instance.HOST == "updated"
    with pytest.raises(TypeError) as error:
        instance.extract_settings_parameters()
    assert "opaque-private-marker" not in str(error.value)
    assert error.value.__context__ is None


@pytest.mark.unit
def test_failed_persist_keeps_prior_recipe_without_rolling_back_live_fields():
    backend = _InMemoryBackend()
    register_secrets_backend("memory", backend)
    instance = _ProvenanceSettings(HOST="original", secrets_provider="memory")
    with pytest.raises(AttributeError):
        instance.persist({"HOST": "partial", "UNKNOWN": "invalid"}, key="partial")
    assert instance.HOST == "partial"
    assert backend.get("partial") == {"HOST": "partial", "UNKNOWN": "invalid"}
    assert instance.extract_settings_parameters().kwargs["HOST"] == "original"


@pytest.mark.unit
def test_update_replaces_accepted_shared_alias_path_without_losing_sibling():
    class Aliased(MountainAshBaseSettings):
        auth: dict[str, str] = Field(default_factory=dict, validation_alias="carrier")
        token: SecretStr = Field(validation_alias=AliasPath("auth", "token"))
        host: str = Field(validation_alias=AliasChoices(AliasPath("auth", "host"), "host"))

    instance = Aliased(auth={"token": "first", "host": "server"})
    instance.update_settings_from_dict({"token": "second"})
    rebuilt = Aliased(settings_parameters=instance.extract_settings_parameters())
    assert rebuilt.token.get_secret_value() == "second"
    assert rebuilt.host == "server"


@pytest.mark.unit
def test_nested_model_source_form_is_owned_before_resolution():
    class Nested(BaseModel):
        token: SecretStr
        items: list[int]

    backend = _InMemoryBackend()
    backend.set("login", {"token": "resolved"})
    register_secrets_backend("memory", backend)
    supplied = Nested(token="secret:login.token", items=[1])
    instance = _ProvenanceSettings(OPAQUE=supplied, secrets_provider="memory")
    first = instance.extract_settings_parameters()
    assert first.kwargs["OPAQUE"].token.get_secret_value() == "secret:login.token"
    first.kwargs["OPAQUE"].items.append(2)
    assert instance.extract_settings_parameters().kwargs["OPAQUE"].items == [1]
    assert instance.OPAQUE.token.get_secret_value() == "resolved"


@pytest.mark.unit
def test_runtime_overlay_extraction_preserves_original_reference():
    from mountainash_settings import SettingsParameters

    backend = _InMemoryBackend()
    backend.set("login", {"token": "first"})
    register_secrets_backend("memory", backend)
    baseline = _ProvenanceSettings(HOST="baseline", secrets_provider="memory")
    params = SettingsParameters.create(
        settings_class=_ProvenanceSettings, secrets_provider="memory",
        TOKEN="secret:login.token",
    )
    overlay = params.apply_runtime_overrides(baseline)
    backend.delete("login")
    extracted = overlay.extract_settings_parameters()
    assert overlay.TOKEN.get_secret_value() == "first"
    assert extracted.kwargs == {"HOST": "baseline", "TOKEN": "secret:login.token"}
    assert baseline.extract_settings_parameters().kwargs == {"HOST": "baseline"}


@pytest.mark.unit
def test_update_retains_owned_patch_after_caller_mutation():
    instance = _ProvenanceSettings()
    patch = {"VALUES": {"items": [1]}}
    instance.update_settings_from_dict(patch)
    patch["VALUES"]["items"].append(2)
    assert instance.extract_settings_parameters().kwargs["VALUES"] == {"items": [1]}


@pytest.mark.unit
def test_extraction_preserves_secret_directory_selector(tmp_path):
    (tmp_path / "HOST").write_text("from-directory")
    instance = _ProvenanceSettings(secrets_dir=str(tmp_path))
    rebuilt = _ProvenanceSettings(settings_parameters=instance.extract_settings_parameters())
    assert rebuilt.HOST == "from-directory"


@pytest.mark.unit
def test_update_preserves_alias_path_root_matching_field_name():
    class Aliased(MountainAshBaseSettings):
        token: SecretStr = Field(validation_alias=AliasPath("token", "value"))

    instance = Aliased(token={"value": "old"})
    instance.update_settings_from_dict({"token": "new"})
    rebuilt = Aliased(settings_parameters=instance.extract_settings_parameters())
    assert rebuilt.token.get_secret_value() == "new"


@pytest.mark.unit
def test_update_can_supply_alias_path_previously_loaded_from_file(tmp_path):
    class Aliased(MountainAshBaseSettings):
        auth: dict[str, str] = Field(default_factory=dict, validation_alias="carrier")
        token: SecretStr = Field(validation_alias=AliasPath("auth", "token"))
        host: str = Field(validation_alias=AliasPath("auth", "host"))

    config = tmp_path / "settings.json"
    config.write_text('{"auth": {"token": "old", "host": "server"}}')
    instance = Aliased(config_files=[str(config)])
    instance.update_settings_from_dict({"token": "new"})
    rebuilt = Aliased(settings_parameters=instance.extract_settings_parameters())
    assert rebuilt.token.get_secret_value() == "new"
    assert rebuilt.host == "server"


@pytest.mark.unit
def test_owned_value_models_preserve_aliasing_without_running_copy_hooks():
    class Nested(BaseModel):
        items: list[int]

        def __deepcopy__(self, memo=None):
            raise AssertionError("copy hook must not run")

    shared = Nested(items=[1])
    instance = _ProvenanceSettings(VALUES={"left": shared, "right": shared})
    params = instance.extract_settings_parameters()
    params.kwargs["VALUES"]["left"].items.append(2)
    assert params.kwargs["VALUES"]["right"].items == [1, 2]
    assert instance.extract_settings_parameters().kwargs["VALUES"]["left"].items == [1]


@pytest.mark.unit
def test_cyclic_input_only_disables_extraction():
    cyclic = []
    cyclic.append(cyclic)
    instance = _ProvenanceSettings(OPAQUE=cyclic)
    assert instance.OPAQUE is cyclic
    with pytest.raises(TypeError):
        instance.extract_settings_parameters()


@pytest.mark.unit
def test_local_path_and_wrapped_container_source_shapes_are_preserved():
    from upath import UPath

    instance = _ProvenanceSettings(VALUES={
        "path": UPath("local/data"),
        "nested": ([SecretStr("literal")], {"value": (1, 2)}),
    })
    params = instance.extract_settings_parameters()
    assert params.kwargs["VALUES"]["path"] == UPath("local/data")
    assert type(params.kwargs["VALUES"]["nested"]) is tuple
    assert params.kwargs["VALUES"]["nested"][0][0].get_secret_value() == "literal"
    params.kwargs["VALUES"]["nested"][0].append("changed")
    assert len(instance.extract_settings_parameters().kwargs["VALUES"]["nested"][0]) == 1


@pytest.mark.unit
def test_datetime_with_mutable_custom_timezone_is_not_shared_by_extraction():
    from datetime import datetime, timedelta, tzinfo

    class MutableTimezone(tzinfo):
        hours = 1

        def utcoffset(self, dt):
            return timedelta(hours=self.hours)

    value = datetime(2026, 1, 1, tzinfo=MutableTimezone())
    instance = _ProvenanceSettings(OPAQUE=value)
    assert instance.OPAQUE is value
    with pytest.raises(TypeError):
        instance.extract_settings_parameters()


@pytest.mark.unit
def test_overlapping_independent_field_is_not_silently_changed_on_reconstruction():
    class Aliased(MountainAshBaseSettings):
        auth: dict[str, str]
        token: SecretStr = Field(validation_alias=AliasPath("auth", "token"))

    instance = Aliased(auth={"token": "old"})
    instance.update_settings_from_dict({"token": "new"})
    assert instance.auth == {"token": "old"}
    assert instance.token.get_secret_value() == "new"
    with pytest.raises(TypeError):
        instance.extract_settings_parameters()


@pytest.mark.unit
def test_snapshot_does_not_execute_custom_model_key_hash():
    class Key(BaseModel):
        armed: t.ClassVar[bool] = False
        value: str

        def __hash__(self):
            if self.armed:
                raise ValueError("hash-private-marker")
            return 1

    key = Key(value="key")
    supplied = {key: "value"}
    Key.armed = True
    instance = _ProvenanceSettings(OPAQUE=supplied)
    assert instance.OPAQUE is supplied
    with pytest.raises(TypeError) as error:
        instance.extract_settings_parameters()
    assert "hash-private-marker" not in str(error.value)


@pytest.mark.unit
def test_unused_alias_choice_does_not_block_independent_patch():
    class Aliased(MountainAshBaseSettings):
        auth: dict[str, str] = Field(default_factory=dict, validation_alias="carrier")
        token: SecretStr = Field(validation_alias=AliasPath("auth", "token"))
        label: str = Field(validation_alias=AliasChoices("label", AliasPath("auth", "token")))

    instance = Aliased(auth={"token": "old"}, label="independent")
    instance.update_settings_from_dict({"token": "new"})
    rebuilt = Aliased(settings_parameters=instance.extract_settings_parameters())
    assert rebuilt.token.get_secret_value() == "new"
    assert rebuilt.label == "independent"


@pytest.mark.unit
def test_updated_alias_choice_shadows_earlier_file_path(tmp_path):
    class Aliased(MountainAshBaseSettings):
        auth: dict[str, str] = Field(default_factory=dict, validation_alias="carrier")
        token: SecretStr = Field(validation_alias=AliasChoices(AliasPath("auth", "token"), "token"))

    config = tmp_path / "settings.json"
    config.write_text('{"auth": {"token": "file"}}')
    instance = Aliased(config_files=[str(config)], token="caller")
    instance.update_settings_from_dict({"token": "updated"})
    rebuilt = Aliased(settings_parameters=instance.extract_settings_parameters())
    assert rebuilt.token.get_secret_value() == "updated"


@pytest.mark.unit
def test_backend_normalization_does_not_replace_supplied_persistence_recipe():
    class NormalizingBackend(_InMemoryBackend):
        def set(self, key, data):
            data["HOST"] = "backend-normalized"
            super().set(key, data)

    backend = NormalizingBackend()
    register_secrets_backend("normalizing", backend)
    instance = _ProvenanceSettings(secrets_provider="normalizing")
    supplied = {"HOST": "caller"}
    instance.persist(supplied, key="record")
    assert backend.get("record") == {"HOST": "backend-normalized"}
    assert instance.extract_settings_parameters().kwargs["HOST"] == "caller"
    assert supplied == {"HOST": "caller"}


@pytest.mark.unit
def test_alias_choice_update_promotes_scalar_to_preferred_path():
    class Aliased(MountainAshBaseSettings):
        token: SecretStr = Field(validation_alias=AliasChoices(AliasPath("token", "value"), "token"))

    instance = Aliased(token="old")
    instance.update_settings_from_dict({"token": "new"})
    rebuilt = Aliased(settings_parameters=instance.extract_settings_parameters())
    assert rebuilt.token.get_secret_value() == "new"


@pytest.mark.unit
def test_positive_and_negative_aliases_cannot_change_untouched_same_item():
    class Aliased(MountainAshBaseSettings):
        items: list[str] = Field(default_factory=list, validation_alias="carrier")
        first: SecretStr = Field(validation_alias=AliasPath("items", 0))
        last: SecretStr = Field(validation_alias=AliasPath("items", -1))

    instance = Aliased(items=["old"])
    instance.update_settings_from_dict({"first": "new"})
    assert instance.last.get_secret_value() == "old"
    with pytest.raises(TypeError):
        instance.extract_settings_parameters()


@pytest.mark.unit
def test_tuple_alias_path_rebuild_preserves_unrelated_item():
    class Aliased(MountainAshBaseSettings):
        items: tuple[str, ...] = Field(default=(), validation_alias="carrier")
        first: SecretStr = Field(validation_alias=AliasPath("items", 0))
        last: SecretStr = Field(validation_alias=AliasPath("items", -1))

    instance = Aliased(items=("old", "untouched"))
    instance.update_settings_from_dict({"first": "new"})
    params = instance.extract_settings_parameters()
    assert params.kwargs["items"] == ("new", "untouched")
    rebuilt = Aliased(settings_parameters=params)
    assert rebuilt.first.get_secret_value() == "new"
    assert rebuilt.last.get_secret_value() == "untouched"


@pytest.mark.unit
def test_compatible_shared_alias_patch_reconstructs_both_requested_fields():
    class Aliased(MountainAshBaseSettings):
        auth: dict[str, str] = Field(default_factory=dict, validation_alias="carrier")
        first: SecretStr = Field(validation_alias=AliasPath("auth", "token"))
        second: SecretStr = Field(validation_alias=AliasPath("auth", "token"))

    instance = Aliased(auth={"token": "old"})
    instance.update_settings_from_dict({
        "first": "".join(["new", "-value"]),
        "second": "".join(["new-", "value"]),
    })
    rebuilt = Aliased(settings_parameters=instance.extract_settings_parameters())
    assert rebuilt.first.get_secret_value() == "new-value"
    assert rebuilt.second.get_secret_value() == "new-value"

