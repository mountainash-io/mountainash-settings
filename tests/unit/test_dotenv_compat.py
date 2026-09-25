from __future__ import annotations

from enum import Enum

import pytest
from pydantic import AliasChoices, BaseModel, Field
from pydantic_settings import SettingsConfigDict

from mountainash_settings import MountainAshBaseSettings, SettingsManager, SettingsParameters


class _DotenvSettings(MountainAshBaseSettings):
    VALUE: str | None = None


class _AliasDotenvSettings(MountainAshBaseSettings):
    model_config = SettingsConfigDict(env_prefix_target="all")
    VALUE: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ALIAS", "VALUE"),
    )


class _NestedValues(BaseModel):
    FIRST: str | None = None
    SECOND: str | None = None


class _NestedDotenvSettings(MountainAshBaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="__")
    NESTED: _NestedValues


class _ParsingMode(Enum):
    DEV = "development"
    PROD = "production"


class _ParsingSettings(MountainAshBaseSettings):
    CASE: str = "default"
    EMPTY: str = "fallback"
    NULL: str | None = "present"
    MODE: _ParsingMode = _ParsingMode.DEV


def _load(settings_class, env_file, *, env_prefix="PREFIX_"):
    return settings_class(
        settings_parameters=SettingsParameters.create(
            settings_class=settings_class,
            config_files=[env_file],
            env_prefix=env_prefix,
        )
    )


def test_os_environment_beats_both_dotenv_sources(tmp_path, monkeypatch):
    env_file = tmp_path / "values.env"
    env_file.write_text('VALUE="fallback"\nPREFIX_VALUE="prefixed"\n')
    monkeypatch.setenv("PREFIX_VALUE", "operating-system")

    settings = _load(_DotenvSettings, env_file)

    assert settings.VALUE == "operating-system"


def test_alias_prefix_target_prefers_prefixed_value(tmp_path):
    env_file = tmp_path / "aliases.env"
    env_file.write_text('ALIAS="fallback"\nPREFIX_ALIAS="prefixed"\n')

    settings = _load(_AliasDotenvSettings, env_file)

    assert settings.VALUE == "prefixed"


def test_nested_delimiter_merges_prefixed_and_fallback_values(tmp_path):
    env_file = tmp_path / "nested.env"
    env_file.write_text(
        'PREFIX_NESTED__FIRST="prefixed"\n'
        'NESTED__SECOND="fallback"\n'
    )

    settings = _load(_NestedDotenvSettings, env_file)

    assert settings.NESTED == _NestedValues(
        FIRST="prefixed",
        SECOND="fallback",
    )


def test_cached_sources_preserve_mountainash_environment_parsing(monkeypatch):
    monkeypatch.delenv("MAS002_CASE", raising=False)
    monkeypatch.setenv("mas002_case", "lowercase")
    monkeypatch.setenv("MAS002_EMPTY", "")
    monkeypatch.setenv("MAS002_NULL", "None")
    monkeypatch.setenv("MAS002_MODE", "PROD")
    settings = SettingsManager().get_or_create_settings(
        SettingsParameters.create(settings_class=_ParsingSettings, env_prefix="MAS002_"),
    )
    assert (settings.CASE, settings.EMPTY, settings.NULL, settings.MODE) == (
        "default", "fallback", None, _ParsingMode.PROD,
    )


def test_cached_dotenv_filtering_ignores_unrelated_values(tmp_path):
    class _FilteringSettings(_DotenvSettings):
        model_config = SettingsConfigDict(extra="forbid", dotenv_filtering="only_existing")

    env_file = tmp_path / "filtering.env"
    env_file.write_text("VALUE=fallback\nUNRELATED=ignored\n")
    settings = SettingsManager().get_or_create_settings(
        SettingsParameters.create(
            settings_class=_FilteringSettings, config_files=[env_file], env_prefix="PREFIX_",
        ),
    )
    assert settings.VALUE == "fallback"


def test_cached_enum_with_mutable_value_is_rejected():
    class MutableMode(Enum):
        SELECTED = ["enum-private-canary"]

    class EnumSettings(MountainAshBaseSettings):
        MODE: MutableMode = MutableMode.SELECTED

    assert EnumSettings().MODE is MutableMode.SELECTED
    with pytest.raises(ValueError) as error:
        SettingsManager().get_or_create_settings(SettingsParameters.create(settings_class=EnumSettings))
    assert "enum-private-canary" not in str(error.value)


@pytest.mark.parametrize(
    "kwarg_name",
    [
        "_env_prefix",
        "_env_file",
        "_case_sensitive",
        "_cli_prog_name",
        "_secrets_dir",
        "_env_prefix_target",
    ],
)
def test_direct_construction_rejects_every_underscore_source_control(tmp_path, kwarg_name):
    """M5 (MAS-SEC-004): every underscore-prefixed kwarg -- enumerated in the
    old 23-name list or not -- fails value-free before sources open on direct
    construction, naming only the key, and a later instance is unaffected."""
    with pytest.raises(ValueError, match=kwarg_name):
        _DotenvSettings(**{kwarg_name: "irrelevant"})

    # No residual state from the rejected construction; class behavior is normal.
    env_file = tmp_path / "after_rejection.env"
    env_file.write_text('VALUE="still-works"\n')
    assert _DotenvSettings(config_files=[env_file]).VALUE == "still-works"


def test_cached_enum_with_mutable_slots_is_rejected():
    class SlottedMode(Enum):
        __slots__ = ("payload",)
        SELECTED = "selected"

        def __init__(self, value):
            self.payload = ["enum-slot-private-canary"]

    class EnumSettings(MountainAshBaseSettings):
        MODE: SlottedMode = SlottedMode.SELECTED

    assert EnumSettings().MODE is SlottedMode.SELECTED
    with pytest.raises(ValueError) as error:
        SettingsManager().get_or_create_settings(SettingsParameters.create(settings_class=EnumSettings))
    assert "enum-slot-private-canary" not in str(error.value)
