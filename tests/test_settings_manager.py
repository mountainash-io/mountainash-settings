"""Behavioral regressions for structural-context cache isolation."""
from __future__ import annotations

from typing import Any, ClassVar

import pytest
from pydantic import AliasPath, BaseModel, Field, PrivateAttr, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from mountainash_settings import (
    CacheableSettingsSource,
    MountainAshBaseSettings,
    SettingsManager,
    SettingsParameters,
    get_settings,
    get_settings_manager,
)
from mountainash_settings.settings_parameters import SettingsFileHandler
from fixtures.settings_classes import MockBaseSettings, TestSettings


class _RequiredInvocationSettings(MountainAshBaseSettings):
    LEFT: int
    RIGHT: int

    @model_validator(mode="after")
    def require_matching_pair(self):
        if self.LEFT + self.RIGHT != 10:
            raise ValueError("LEFT and RIGHT must sum to ten")
        return self


class _TransformingSettings(MountainAshBaseSettings):
    VALUE: int = 0

    @field_validator("VALUE")
    @classmethod
    def increment_raw_value(cls, value: int) -> int:
        return value + 1


_VALIDATOR_GLOBAL = {"items": ["baseline"]}


class _RootOwnershipSettings(MountainAshBaseSettings):
    model_config = SettingsConfigDict(extra="allow")

    DATA: dict[str, list[str]]
    _private_data: dict[str, list[str]] | None = PrivateAttr(default=None)

    @field_validator("DATA")
    @classmethod
    def validator_returns_global(cls, value: dict[str, list[str]]) -> dict[str, list[str]]:
        return _VALIDATOR_GLOBAL

    def post_init(
        self,
        template_settings_parameters: SettingsParameters | None = None,
        reinitialise: bool | None = False,
    ) -> None:
        self._private_data = self.DATA
        self.extra_data = self.DATA
        object.__setattr__(self, "non_field_data", self.DATA)


class _CountingBackend:
    def __init__(self, value: str):
        self.value = value
        self.calls = 0

    def get(self, key: str) -> dict[str, str]:
        self.calls += 1
        return {"password": self.value}

    def set(self, key: str, data: dict[str, Any]) -> None:
        pass

    def delete(self, key: str) -> None:
        pass

    def transaction(self, key: str):
        from contextlib import nullcontext

        return nullcontext()


class _SimpleAliasSettings(MountainAshBaseSettings):
    value: str = Field(default="default", validation_alias="input")


class _SharedAliasSettings(MountainAshBaseSettings):
    left: dict[str, str] = Field(validation_alias=AliasPath("pair", "left"))
    right: str = Field(validation_alias=AliasPath("pair", "right"))


class _NestedDefault(BaseModel):
    value: int = 3


class _ExplicitDefaultSettings(BaseSettings):
    model_config = SettingsConfigDict(nested_model_default_partial_update=True)
    nested: _NestedDefault = _NestedDefault()


class _StaticAliasSecretSettings(MountainAshBaseSettings):
    PASSWORD: SecretStr = Field(
        default=SecretStr("secret:service.password"),
        validation_alias=AliasPath("credentials", "password"),
    )
    NAME: str = Field(validation_alias=AliasPath("credentials", "name"))


class _TransformingConstructorSettings(MountainAshBaseSettings):
    value: str

    def __init__(self, **kwargs):
        kwargs["value"] = "outer:" + kwargs["value"]
        super().__init__(**kwargs)


class _NestedConstructorSettings(MountainAshBaseSettings):
    value: str = "default"
    entering: ClassVar[bool] = False

    def __init__(self, **kwargs):
        if not type(self).entering:
            type(self).entering = True
            try:
                nested = type(self)(value="nested-direct")
                assert nested.value == "nested-direct"
            finally:
                type(self).entering = False
        super().__init__(**kwargs)


class _SecretSettings(MountainAshBaseSettings):
    PASSWORD: str


class _CapturedProjectSource(CacheableSettingsSource):
    __name__ = "named_capture"
    source_value = "captured"
    captures = 0


    def get_field_value(self, field, field_name: str):
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        return self.project(self.capture(), self.current_state, self.settings_sources_data)

    def capture(self) -> dict[str, Any]:
        type(self).captures += 1
        return {"VALUE": self.source_value}

    @staticmethod
    def project(
        owned_resolved_snapshot: dict[str, Any],
        owned_current_state: dict[str, Any],
        owned_sources_data: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "VALUE": owned_resolved_snapshot["VALUE"] + ":" + owned_current_state["REQUEST"],
            "LITERAL": "secret:terminal.value",
        }


class _NamedDependencySource(_CapturedProjectSource):
    __name__ = "named_dependency"

    def capture(self) -> dict[str, Any]:
        return {}

    @staticmethod
    def project(snapshot, current_state, sources_data):
        return {"MIRROR": sources_data["named_capture"]["VALUE"]}


class _CaptureProjectSettings(MountainAshBaseSettings):
    VALUE: str
    REQUEST: str
    LITERAL: str
    MIRROR: str

    @classmethod
    def settings_capture_sources(cls, sources):
        return sources[:1] + (_CapturedProjectSource(cls), _NamedDependencySource(cls)) + sources[1:]


class _LegacyHookSettings(MountainAshBaseSettings):
    VALUE: str = "direct"

    @classmethod
    def settings_customise_sources(
        cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings
    ):
        return init_settings, env_settings, dotenv_settings, file_secret_settings


class _PlainCustomConstructorSettings(BaseSettings):
    VALUE: str = "default"

    def __init__(self, **kwargs):
        if "VALUE" in kwargs:
            kwargs["VALUE"] = f"direct:{kwargs['VALUE']}"
        super().__init__(**kwargs)


class _ReinitialiseSettings(MountainAshBaseSettings):
    REINITIALISED: bool = False

    def post_init(self, template_settings_parameters: SettingsParameters | None = None, reinitialise: bool | None = False) -> None:
        self.REINITIALISED = bool(reinitialise)


class _DerivedSettings(MountainAshBaseSettings):
    HOST: str = "primary"
    URL: str = ""

    @field_validator("URL")
    @classmethod
    def transform_url(cls, value: str) -> str:
        return value + "!"

    def post_init(self, template_settings_parameters: SettingsParameters | None = None, reinitialise: bool | None = False) -> None:
        self.URL = "https://" + self.HOST


class _FieldNamedExtraSettings(MountainAshBaseSettings):
    extra: str


class TestSettingsManagerRoutes:
    def test_manager_factory_returns_singleton(self):
        assert get_settings_manager() is get_settings_manager()

    def test_manager_reports_context_only_after_capture(self):
        manager = SettingsManager()
        params = SettingsParameters.create(settings_class=TestSettings)

        assert manager.is_initialised(params) is False
        manager.get_or_create_settings(params)
        assert manager.is_initialised(SettingsParameters.create(settings_class=TestSettings)) is True

    def test_direct_manager_rejects_missing_settings_class(self):
        with pytest.raises(ValueError, match="settings_class"):
            SettingsManager().get_or_create_settings(SettingsParameters.create())

    def test_existing_context_route_fails_without_context(self):
        params = SettingsParameters.create(settings_class=TestSettings)
        with pytest.raises(ValueError):
            SettingsManager().get_settings_object(params)

    def test_direct_manager_and_existing_context_return_declared_class(self):
        manager = SettingsManager()
        params = SettingsParameters.create(settings_class=TestSettings, TEST_VAR="current")

        created = manager.get_or_create_settings(params)
        existing = manager.get_settings_object(params)

        assert isinstance(created, TestSettings)
        assert isinstance(existing, TestSettings)
        assert existing.TEST_VAR == "current"

    def test_reinitialise_is_keyword_only_manager_control(self):
        params = SettingsParameters.create(settings_class=TestSettings)
        with pytest.raises(TypeError):
            SettingsManager().get_or_create_settings(params, True)

    def test_structural_selectors_choose_independent_source_contexts(self):
        manager = SettingsManager()
        first = manager.get_or_create_settings(
            SettingsParameters.create(
                settings_class=TestSettings,
                env_prefix="FIRST_",
                TEST_VAR="first",
            )
        )
        second = manager.get_or_create_settings(
            SettingsParameters.create(
                settings_class=TestSettings,
                env_prefix="SECOND_",
                TEST_VAR="second",
            )
        )

        assert first.TEST_VAR == "first"
        assert second.TEST_VAR == "second"

    def test_public_retrieval_routes_reinitialise_as_operation_control(self, monkeypatch):
        manager = SettingsManager()
        monkeypatch.setattr(
            "mountainash_settings.settings_cache.settings_functions.get_settings_manager",
            lambda: manager,
        )

        settings = get_settings(settings_class=_ReinitialiseSettings, reinitialise=True)

        assert settings.REINITIALISED is True

    def test_standard_plain_base_settings_is_materialized_on_warm_retrieval(self):
        manager = SettingsManager()
        params = SettingsParameters.create(
            settings_class=MockBaseSettings,
            env_prefix="PLAIN_STANDARD_",
            test_field="configured",
        )

        first = manager.get_or_create_settings(params)
        second = manager.get_or_create_settings(params)

        assert isinstance(first, MockBaseSettings)
        assert isinstance(second, MockBaseSettings)
        assert second.test_field == "configured"

    def test_cached_plain_custom_constructor_is_rejected_without_changing_direct_use(self):
        assert _PlainCustomConstructorSettings(VALUE="value").VALUE == "direct:value"

        with pytest.raises(ValueError, match="BaseSettings.__init__"):
            SettingsManager().get_or_create_settings(
                SettingsParameters.create(
                    settings_class=_PlainCustomConstructorSettings,
                    VALUE="value",
                )
            )


@pytest.mark.unit
class TestOwnedStructuralContexts:
    def test_cold_runtime_value_does_not_become_source_default(self):
        manager = SettingsManager()
        overridden = manager.get_or_create_settings(SettingsParameters.create(
            settings_class=TestSettings, TEST_VAR="request-only",
        ))
        baseline = manager.get_or_create_settings(SettingsParameters.create(
            settings_class=TestSettings,
        ))
        assert overridden.TEST_VAR == "request-only"
        assert baseline.TEST_VAR == "default_value"

    def test_returned_nested_mutation_does_not_reach_next_caller(self):
        manager = SettingsManager()
        params = SettingsParameters.create(settings_class=TestSettings)
        first = manager.get_or_create_settings(params)
        first.COMPLEX_VAR["key"] = "caller-mutation"
        second = manager.get_or_create_settings(params)
        assert second.COMPLEX_VAR == {"key": "value"}

    def test_file_snapshot_survives_cold_runtime_override_and_source_deletion(self, tmp_path):
        path = tmp_path / "settings.yaml"
        path.write_text("TEST_VAR: captured-source\nCOMPLEX_VAR:\n  key: captured\n")
        manager = SettingsManager()
        first = manager.get_or_create_settings(SettingsParameters.create(
            settings_class=TestSettings, config_files=str(path), TEST_VAR="request-only",
        ))
        path.unlink()
        second = manager.get_or_create_settings(SettingsParameters.create(
            settings_class=TestSettings, config_files=str(path),
        ))
        assert first.TEST_VAR == "request-only"
        assert second.TEST_VAR == "captured-source"
        assert second.COMPLEX_VAR == {"key": "captured"}


class TestCompleteInvocationAndOwnership:
    def test_required_and_model_policy_inputs_validate_as_one_runtime_invocation(self):
        settings = SettingsManager().get_or_create_settings(
            SettingsParameters.create(
                settings_class=_RequiredInvocationSettings,
                LEFT=4,
                RIGHT=6,
            )
        )

        assert (settings.LEFT, settings.RIGHT) == (4, 6)

    def test_non_idempotent_validator_receives_raw_runtime_input_each_time(self):
        manager = SettingsManager()
        first = manager.get_or_create_settings(
            SettingsParameters.create(settings_class=_TransformingSettings, VALUE=4)
        )
        second = manager.get_or_create_settings(
            SettingsParameters.create(settings_class=_TransformingSettings, VALUE=4)
        )

        assert first.VALUE == 5
        assert second.VALUE == 5

    def test_raw_derived_carry_preserves_flag_off_and_explicit_precedence(self):
        manager = SettingsManager()
        selectors = {"settings_class": _DerivedSettings}
        baseline = manager.get_or_create_settings(SettingsParameters.create(**selectors))
        off = manager.get_or_create_settings(SettingsParameters.create(**selectors, HOST="alternate"))
        on = manager.get_or_create_settings(
            SettingsParameters.create(**selectors, HOST="alternate"), reinitialise=True,
        )
        explicit = manager.get_or_create_settings(
            SettingsParameters.create(**selectors, HOST="alternate", URL="custom"), reinitialise=True,
        )
        later = manager.get_or_create_settings(SettingsParameters.create(**selectors))

        assert (baseline.URL, off.URL, on.URL, explicit.URL, later.URL) == (
            "https://primary!", "https://primary!", "https://alternate!", "custom!", "https://primary!",
        )

    def test_final_owned_root_detaches_globals_and_preserves_internal_aliases(self):
        _VALIDATOR_GLOBAL["items"][:] = ["baseline"]
        manager = SettingsManager()
        params = SettingsParameters.create(settings_class=_RootOwnershipSettings, DATA={})

        first = manager.get_or_create_settings(params)
        assert first.DATA is first._private_data
        assert first.DATA is first.__pydantic_extra__["extra_data"]
        assert first.DATA is first.non_field_data

        first.DATA["items"].append("caller")
        second = manager.get_or_create_settings(params)

        assert _VALIDATOR_GLOBAL == {"items": ["baseline"]}
        assert second.DATA == {"items": ["baseline"]}
        assert second.DATA is second._private_data
        assert second.DATA is second.__pydantic_extra__["extra_data"]
        assert second.DATA is second.non_field_data


class TestSourceCaptureContracts:
    def test_explicit_runtime_reference_is_fresh_while_baseline_reference_stays_retained(
        self, tmp_path
    ):
        config = tmp_path / "settings.yaml"
        config.write_text("PASSWORD: secret:service.password\n")
        backend = _CountingBackend("baseline")
        manager = SettingsManager()
        baseline_params = SettingsParameters.create(
            settings_class=_SecretSettings,
            secret_store=backend,
            config_files=[config],
        )
        baseline = manager.get_or_create_settings(baseline_params)
        assert baseline.PASSWORD == "baseline"

        backend.value = "runtime-one"
        assert manager.get_or_create_settings(baseline.extract_settings_parameters()).PASSWORD == "baseline"
        runtime_params = SettingsParameters.create(
            settings_class=_SecretSettings,
            secret_store=backend,
            config_files=[config],
            PASSWORD="secret:service.password",
        )
        assert manager.get_or_create_settings(runtime_params).PASSWORD == "runtime-one"

        backend.value = "runtime-two"
        assert manager.get_or_create_settings(runtime_params).PASSWORD == "runtime-two"
        assert manager.get_or_create_settings(baseline_params).PASSWORD == "baseline"
        assert backend.calls == 3

    def test_capture_project_source_is_selected_once_and_projects_terminal_values(self, monkeypatch):
        _CapturedProjectSource.captures = 0
        monkeypatch.setattr(_CapturedProjectSource, "source_value", "captured")
        backend = _CountingBackend("should-not-resolve")
        manager = SettingsManager()
        selectors = {"settings_class": _CaptureProjectSettings, "secret_store": backend}

        first = manager.get_or_create_settings(SettingsParameters.create(**selectors, REQUEST="first"))
        monkeypatch.setattr(_CapturedProjectSource, "source_value", "changed")
        second = manager.get_or_create_settings(SettingsParameters.create(**selectors, REQUEST="second"))
        assert first.VALUE == first.MIRROR == "captured:first"
        assert second.VALUE == second.MIRROR == "captured:second"
        assert first.LITERAL == second.LITERAL == "secret:terminal.value"
        assert _CapturedProjectSource.captures == 1
        assert backend.calls == 0

    def test_legacy_source_hook_requires_explicit_cached_capture_adaptation(self):
        manager = SettingsManager()
        params = SettingsParameters.create(settings_class=_LegacyHookSettings)
        with pytest.raises(ValueError):
            manager.get_or_create_settings(params)
        assert not manager.is_initialised(params)
        assert _LegacyHookSettings(VALUE="direct-input").VALUE == "direct-input"

    def test_declared_nonunderscore_control_name_remains_a_runtime_field(self):
        settings = SettingsManager().get_or_create_settings(
            SettingsParameters.create(
                settings_class=_FieldNamedExtraSettings,
                extra="field-value",
            )
        )

        assert settings.extra == "field-value"

    def test_cached_source_controls_are_rejected_before_retrieval(self, tmp_path):
        with pytest.raises(ValueError):
            SettingsManager().get_or_create_settings(
                SettingsParameters.create(
                    settings_class=TestSettings,
                    _env_file=tmp_path / "other.env",
                )
            )


class TestEdgeCases:
    def test_validate_config_files_exist_raises_error(self):
        with pytest.raises(FileNotFoundError):
            SettingsFileHandler.validate_config_files_exist(
                config_files=["non_existing_file.yaml"]
            )


class TestReviewedCacheBoundaries:
    def test_named_override_preserves_lower_indexed_source_and_sibling(self, tmp_path):
        from pydantic import AliasChoices

        class IndexedAliasSettings(MountainAshBaseSettings):
            value: str = Field(validation_alias=AliasChoices("named", AliasPath("items", 0)))
            sibling: str = Field(validation_alias=AliasPath("items", 1))

        path = tmp_path / "indexed.yaml"
        path.write_text("items: [source, sibling]\n")
        settings = SettingsManager().get_or_create_settings(SettingsParameters.create(
            settings_class=IndexedAliasSettings, config_files=[path], named="override",
        ))
        assert settings.value == "override"
        assert settings.sibling == "sibling"

    def test_aliased_derived_value_survives_warm_retrieval(self):
        class AliasedDerivedSettings(MountainAshBaseSettings):
            value: str = Field(default="default", validation_alias="input")

            def post_init(self, template_settings_parameters: SettingsParameters | None = None, reinitialise: bool | None = False) -> None:
                self.value = "derived"

        manager = SettingsManager()
        parameters = SettingsParameters.create(settings_class=AliasedDerivedSettings)
        assert manager.get_or_create_settings(parameters).value == "derived"
        assert manager.get_or_create_settings(parameters).value == "derived"

    def test_plain_nested_partial_defaults_survive_source_and_runtime_inputs(self, monkeypatch):
        class Nested(BaseModel):
            a: int = 1
            b: int = 2

        class PartialSettings(BaseSettings):
            model_config = SettingsConfigDict(nested_model_default_partial_update=True)
            nested: Nested = Nested(a=1, b=9)

        monkeypatch.setenv("MASPARTIAL_nested", '{"a":5}')
        manager = SettingsManager()
        parameters = SettingsParameters.create(settings_class=PartialSettings, env_prefix="MASPARTIAL_")
        assert manager.get_or_create_settings(parameters).nested == Nested(a=5, b=9)
        assert manager.get_or_create_settings(SettingsParameters.create(
            settings_class=PartialSettings, env_prefix="MASPARTIAL_", nested={"a": 7},
        )).nested == Nested(a=7, b=9)

    def test_named_override_allows_absent_indexed_alias_alternative(self):
        from pydantic import AliasChoices

        class IndexedAliasSettings(MountainAshBaseSettings):
            value: str = Field(validation_alias=AliasChoices("named", AliasPath("items", 0)))

        settings = SettingsManager().get_or_create_settings(
            SettingsParameters.create(settings_class=IndexedAliasSettings, named="override"),
        )
        assert settings.value == "override"

    def test_caught_invalid_assignment_does_not_poison_later_calls(self):
        from pydantic import ValidationError

        class CatchingSettings(MountainAshBaseSettings):
            VALUE: int = Field(default=3, gt=0)

            def post_init(
                self,
                template_settings_parameters: SettingsParameters | None = None,
                reinitialise: bool | None = False,
            ) -> None:
                try:
                    self.VALUE = -1
                except ValidationError:
                    pass

        manager = SettingsManager()
        parameters = SettingsParameters.create(settings_class=CatchingSettings)
        assert manager.get_or_create_settings(parameters).VALUE == 3
        assert manager.get_or_create_settings(parameters).VALUE == 3

    @pytest.mark.parametrize("record_first", [False, True])
    def test_unrecorded_postinit_mutation_is_rejected(self, record_first):
        class BypassSettings(MountainAshBaseSettings):
            VALUE: str = "original"

            def post_init(
                self,
                template_settings_parameters: SettingsParameters | None = None,
                reinitialise: bool | None = False,
            ) -> None:
                if record_first:
                    self.VALUE = "recorded"
                object.__setattr__(self, "VALUE", "bypass-private-canary")

        assert BypassSettings().VALUE == "bypass-private-canary"
        with pytest.raises(ValueError) as error:
            SettingsManager().get_or_create_settings(SettingsParameters.create(settings_class=BypassSettings))
        assert "bypass-private-canary" not in str(error.value)

    def test_runtime_simple_alias_keeps_validation_alias_semantics(self):
        settings = SettingsManager().get_or_create_settings(
            SettingsParameters.create(settings_class=_SimpleAliasSettings, input="override"),
        )
        assert settings.value == "override"

    def test_shared_alias_root_preserves_sibling_and_replaces_logical_field(self, tmp_path):
        path = tmp_path / "shared.yaml"
        path.write_text("pair:\n  left:\n    old: source\n  right: sibling\n")
        settings = SettingsManager().get_or_create_settings(
            SettingsParameters.create(
                settings_class=_SharedAliasSettings, config_files=[path],
                pair={"left": {"new": "runtime"}},
            ),
        )
        assert settings.left == {"new": "runtime"}
        assert settings.right == "sibling"

    def test_explicit_source_equal_to_default_remains_in_exclude_unset_dump(self, tmp_path):
        path = tmp_path / "defaults.env"
        path.write_text('nested={"value":3}\n')
        params = SettingsParameters.create(settings_class=_ExplicitDefaultSettings, config_files=[path])
        manager = SettingsManager()
        first = manager.get_or_create_settings(params)
        path.unlink()
        second = manager.get_or_create_settings(params)
        assert first.model_dump(exclude_unset=True) == {"nested": {"value": 3}}
        assert second.model_dump(exclude_unset=True) == {"nested": {"value": 3}}

    def test_first_reinitialise_only_call_does_not_seed_baseline_carry(self):
        manager = SettingsManager()
        params = SettingsParameters.create(settings_class=_ReinitialiseSettings)
        first = manager.get_or_create_settings(params, reinitialise=True)
        baseline = manager.get_or_create_settings(params)
        assert first.REINITIALISED is True
        assert baseline.REINITIALISED is False

    def test_same_class_nested_constructor_cannot_consume_outer_capture(self, tmp_path):
        path = tmp_path / "nested-constructor.yaml"
        path.write_text("value: captured\n")
        params = SettingsParameters.create(settings_class=_NestedConstructorSettings, config_files=[path])
        manager = SettingsManager()
        first = manager.get_or_create_settings(params)
        path.unlink()
        second = manager.get_or_create_settings(params)
        assert (first.value, second.value) == ("captured", "captured")

    def test_extraction_does_not_replay_custom_constructor_transform(self):
        manager = SettingsManager()
        original = manager.get_or_create_settings(
            SettingsParameters.create(settings_class=_TransformingConstructorSettings, value="input"),
        )
        reconstructed = manager.get_or_create_settings(original.extract_settings_parameters())
        assert original.value == reconstructed.value == "outer:input"

    @pytest.mark.parametrize("controls", [{"reinitialise": True}, {"env_prefix": "OTHER_"}])
    def test_nested_operation_and_source_controls_fail_before_capture(self, tmp_path, controls):
        params = SettingsParameters.create(
            settings_class=TestSettings, config_files=[tmp_path / "must-not-read.yaml"], kwargs=controls,
        )
        manager = SettingsManager()
        with pytest.raises(ValueError):
            manager.get_or_create_settings(params)
        assert not manager.is_initialised(params)

    def test_shared_root_static_secret_is_resolved_and_pinned(self, tmp_path):
        path = tmp_path / "static-default.yaml"
        path.write_text("credentials:\n  name: caller\n")
        backend = _CountingBackend("baseline")
        manager = SettingsManager()
        params = SettingsParameters.create(
            settings_class=_StaticAliasSecretSettings, config_files=[path], secret_store=backend,
        )
        first = manager.get_or_create_settings(params)
        backend.value = "changed"
        second = manager.get_or_create_settings(params)
        assert first.NAME == second.NAME == "caller"
        assert first.PASSWORD.get_secret_value() == second.PASSWORD.get_secret_value() == "baseline"
        assert backend.calls == 1
