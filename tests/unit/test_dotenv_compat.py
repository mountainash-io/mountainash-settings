from __future__ import annotations

import pytest
from pydantic import AliasChoices, BaseModel, Field
from pydantic_settings import (
    DotEnvSettingsSource,
    EnvSettingsSource,
    InitSettingsSource,
    SecretsSettingsSource,
    SettingsConfigDict,
)

from mountainash_settings import MountainAshBaseSettings, SettingsParameters


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


@pytest.mark.parametrize("filtering", [None, "only_existing", "match_prefix"])
def test_fallback_copies_filtering_and_shared_state(tmp_path, filtering):
    env_file = tmp_path / "filtering.env"
    env_file.write_text('VALUE="fallback"\n')

    class _FilteringSettings(_DotenvSettings):
        pass

    init = InitSettingsSource(_FilteringSettings, {})
    env = EnvSettingsSource(_FilteringSettings, env_prefix="PREFIX_")
    dotenv = DotEnvSettingsSource(
        _FilteringSettings,
        env_file=env_file,
        env_prefix="PREFIX_",
        dotenv_filtering=filtering,
    )
    secrets = SecretsSettingsSource(_FilteringSettings)

    sources = _FilteringSettings.settings_customise_sources(
        _FilteringSettings,
        init,
        env,
        dotenv,
        secrets,
    )
    fallback = sources[3]

    assert isinstance(fallback, DotEnvSettingsSource)
    assert fallback.dotenv_filtering == filtering
    assert fallback._init_state is dotenv._init_state
