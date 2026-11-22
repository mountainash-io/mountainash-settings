from __future__ import annotations

import os
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



@pytest.fixture(params=["local", "memory"])
def env_dir(request, tmp_path):
    """The same dotenv semantics must hold for local and memory-backed sources."""
    if request.param == "local":
        return tmp_path
    return request.getfixturevalue("memory_config_root")


def _build(settings_class, route, *env_files, env_prefix="PREFIX_"):
    """Direct construction and cached capture build their sources separately."""
    parameters = SettingsParameters.create(
        settings_class=settings_class, config_files=list(env_files), env_prefix=env_prefix,
    )
    if route == "direct":
        return settings_class(settings_parameters=parameters)
    return SettingsManager().get_or_create_settings(parameters)


@pytest.mark.parametrize("route", ["direct", "cached"])
def test_os_environment_beats_both_dotenv_sources(env_dir, route, monkeypatch):
    env_file = env_dir / "values.env"
    env_file.write_text('VALUE="fallback"\nPREFIX_VALUE="prefixed"\n')
    monkeypatch.setenv("PREFIX_VALUE", "operating-system")

    settings = _build(_DotenvSettings, route, env_file)

    assert settings.VALUE == "operating-system"


@pytest.mark.parametrize("route", ["direct", "cached"])
def test_alias_prefix_target_prefers_prefixed_value(env_dir, route):
    env_file = env_dir / "aliases.env"
    env_file.write_text('ALIAS="fallback"\nPREFIX_ALIAS="prefixed"\n')

    assert _build(_AliasDotenvSettings, route, env_file).VALUE == "prefixed"


@pytest.mark.parametrize("route", ["direct", "cached"])
def test_nested_delimiter_merges_prefixed_and_fallback_values(env_dir, route):
    env_file = env_dir / "nested.env"
    env_file.write_text(
        'PREFIX_NESTED__FIRST="prefixed"\n'
        'NESTED__SECOND="fallback"\n'
    )

    assert _build(_NestedDotenvSettings, route, env_file).NESTED == _NestedValues(
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
        "lowercase" if os.name == "nt" else "default",
        "fallback",
        None,
        _ParsingMode.PROD,
    )


@pytest.mark.parametrize("route", ["direct", "cached"])
def test_dotenv_filtering_ignores_unrelated_values(env_dir, route):
    class _FilteringSettings(_DotenvSettings):
        model_config = SettingsConfigDict(extra="forbid", dotenv_filtering="only_existing")

    env_file = env_dir / "filtering.env"
    env_file.write_text("VALUE=fallback\nUNRELATED=ignored\n")

    assert _build(_FilteringSettings, route, env_file).VALUE == "fallback"


@pytest.mark.parametrize("route", ["direct", "cached"])
def test_dotenv_interpolates_within_selected_file(env_dir, route):
    env_file = env_dir / "interpolate.env"
    env_file.write_text("BASE=root\nVALUE=${BASE}/child\n")

    assert _build(_DotenvSettings, route, env_file).VALUE == "root/child"


@pytest.mark.parametrize("route", ["direct", "cached"])
@pytest.mark.parametrize("extra", ["ignore", "allow"])
def test_dotenv_ignores_empty_values_and_parses_none_and_enums(env_dir, route, extra):
    class ParsingSettings(_ParsingSettings):
        model_config = SettingsConfigDict(extra=extra)

    env_file = env_dir / "parsing.env"
    env_file.write_text("MAS002_EMPTY=\nMAS002_NULL=None\nMAS002_MODE=PROD\n")

    settings = _build(ParsingSettings, route, env_file, env_prefix="MAS002_")

    assert (settings.EMPTY, settings.NULL, settings.MODE) == (
        "fallback", None, _ParsingMode.PROD,
    )
    if extra == "allow":
        assert settings.model_extra["MAS002_NULL"] == "None"


@pytest.mark.parametrize("remote_last", [True, False])
@pytest.mark.parametrize("route", ["direct", "cached"])
def test_mixed_local_and_remote_dotenv_files_override_in_caller_order(
    tmp_path, memory_config_root, remote_last, route,
):
    local = tmp_path / "local.env"
    remote = memory_config_root / "remote.env"
    local.write_text("VALUE=local\nFALLBACK=local-only\n")
    remote.write_text("VALUE=remote\n")
    files = [local, remote] if remote_last else [remote, local]

    class _Mixed(_DotenvSettings):
        FALLBACK: str | None = None

    settings = _build(_Mixed, route, *files)

    assert (settings.VALUE, settings.FALLBACK) == (
        "remote" if remote_last else "local", "local-only",
    )


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
