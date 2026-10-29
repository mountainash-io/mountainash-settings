"""Regressions for invocation-local settings source configuration (MAS-SEC-004, M5).

These tests prove that overlapping, nested, and failing direct construction of
declared MountainAshBaseSettings subclasses never lets one invocation observe
another invocation's YAML/TOML/JSON source configuration, and that the
default ``settings_customise_sources`` hook keeps its documented fallback and
override contracts. Assertions target loaded values, provenance metadata, and
observable errors -- never ContextVar tokens or private source object
identity.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest
from pydantic import ValidationError
from pydantic_settings import (
    DotEnvSettingsSource,
    EnvSettingsSource,
    InitSettingsSource,
    SecretsSettingsSource,
)

from mountainash_settings import MountainAshBaseSettings, SettingsParameters
from mountainash_settings.settings_cache import SettingsManager

_PROVENANCE_ATTR = {
    "yaml": "SETTINGS_SOURCE_YAML_FILES",
    "toml": "SETTINGS_SOURCE_TOML_FILES",
    "json": "SETTINGS_SOURCE_JSON_FILES",
}


def _write_marker(path: Path, suffix: str, marker: str) -> Path:
    if suffix == "yaml":
        path.write_text(f"marker: {marker}\n")
    elif suffix == "toml":
        path.write_text(f'marker = "{marker}"\n')
    else:
        path.write_text(json.dumps({"marker": marker}))
    return path


class TestConcurrentConstructionIsolation:
    """The historical vulnerability: B must never make A observe B's source."""

    @pytest.mark.parametrize("suffix", ["yaml", "toml", "json"])
    def test_overlapping_same_class_construction_isolates_source_paths(self, tmp_path, suffix):
        path_a = _write_marker(tmp_path / f"a.{suffix}", suffix, "a")
        path_b = _write_marker(tmp_path / f"b.{suffix}", suffix, "b")

        pause_before_source_build = threading.Event()
        resume_a = threading.Event()
        results: dict[str, object] = {}
        errors: dict[str, BaseException] = {}

        class _PausingSettings(MountainAshBaseSettings):
            marker: str = "unset"

            @classmethod
            def settings_customise_sources(
                cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
            ):
                if threading.current_thread().name == "construct-a":
                    pause_before_source_build.set()
                    assert resume_a.wait(timeout=5), "test deadlocked waiting to resume A"
                return super().settings_customise_sources(
                    settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
                )

        def construct_a():
            try:
                results["a"] = _PausingSettings(config_files=[path_a])
            except BaseException as exc:  # noqa: BLE001 - surfaced via errors dict
                errors["a"] = exc

        thread_a = threading.Thread(target=construct_a, name="construct-a")
        thread_a.start()
        assert pause_before_source_build.wait(timeout=5), "A never reached its pause point"

        # B must fully construct, using its own path, while A is paused with
        # its own frame installed and no source objects built yet.
        settings_b = _PausingSettings(config_files=[path_b])

        resume_a.set()
        thread_a.join(timeout=5)
        assert not thread_a.is_alive(), "construction thread A did not finish"

        assert not errors, errors
        settings_a = results["a"]
        assert settings_a.marker == "a"
        assert settings_b.marker == "b"

        attr = _PROVENANCE_ATTR[suffix]
        assert [str(p) for p in getattr(settings_a, attr)] == [str(path_a)]
        assert [str(p) for p in getattr(settings_b, attr)] == [str(path_b)]


class TestNestedConstruction:
    def test_outer_hook_constructing_a_different_class_restores_outer_frame(self, tmp_path):
        outer_path = _write_marker(tmp_path / "outer.yaml", "yaml", "outer")
        inner_path = _write_marker(tmp_path / "inner.yaml", "yaml", "inner")

        class _InnerSettings(MountainAshBaseSettings):
            marker: str = "unset"

        class _OuterSettings(MountainAshBaseSettings):
            marker: str = "unset"

            @classmethod
            def settings_customise_sources(
                cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
            ):
                inner = _InnerSettings(config_files=[inner_path])
                assert inner.marker == "inner"
                # Inner's frame has been installed and torn down by this
                # point; the outer frame must still resolve outer's own path.
                return super().settings_customise_sources(
                    settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
                )

        outer = _OuterSettings(config_files=[outer_path])
        assert outer.marker == "outer"
        assert [str(p) for p in outer.SETTINGS_SOURCE_YAML_FILES] == [str(outer_path)]

    def test_outer_hook_recursively_constructing_same_class_restores_outer_frame(self, tmp_path):
        outer_path = _write_marker(tmp_path / "outer_same.yaml", "yaml", "outer_same")
        inner_path = _write_marker(tmp_path / "inner_same.yaml", "yaml", "inner_same")

        class _RecursiveSettings(MountainAshBaseSettings):
            marker: str = "unset"

            @classmethod
            def settings_customise_sources(
                cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
            ):
                if not getattr(cls, "_recursion_guard", False):
                    cls._recursion_guard = True
                    try:
                        nested = _RecursiveSettings(config_files=[inner_path])
                        assert nested.marker == "inner_same"
                    finally:
                        cls._recursion_guard = False
                return super().settings_customise_sources(
                    settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
                )

        outer = _RecursiveSettings(config_files=[outer_path])
        assert outer.marker == "outer_same"

    def test_failed_nested_construction_leaks_no_frame_to_a_later_unrelated_call(self, tmp_path):
        good_path = _write_marker(tmp_path / "good.yaml", "yaml", "good")

        class _StrictInner(MountainAshBaseSettings):
            required_value: int

        class _OuterWithFailingNested(MountainAshBaseSettings):
            marker: str = "unset"

            @classmethod
            def settings_customise_sources(
                cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
            ):
                with pytest.raises(ValidationError):
                    _StrictInner()
                return super().settings_customise_sources(
                    settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
                )

        outer = _OuterWithFailingNested(config_files=[good_path])
        assert outer.marker == "good"

        class _LaterSettings(MountainAshBaseSettings):
            marker: str = "unset"

        later = _LaterSettings(config_files=[good_path])
        assert later.marker == "good"


class TestCacheMaterializationPrecedence:
    """A direct-construction frame active during nested cache materialization
    must never leak into the cache's own captured source paths."""

    def test_nested_cache_materialization_for_a_different_class_resolves_its_own_paths(self, tmp_path):
        outer_path = _write_marker(tmp_path / "outer_direct.yaml", "yaml", "outer_direct")
        cached_path = _write_marker(tmp_path / "cached_other.yaml", "yaml", "cached_other")

        class _CachedSettings(MountainAshBaseSettings):
            marker: str = "unset"

        class _OuterSettings(MountainAshBaseSettings):
            marker: str = "unset"

            @classmethod
            def settings_customise_sources(
                cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
            ):
                cached = SettingsManager().get_or_create_settings(
                    SettingsParameters.create(settings_class=_CachedSettings, config_files=[cached_path]),
                )
                assert cached.marker == "cached_other"
                return super().settings_customise_sources(
                    settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
                )

        outer = _OuterSettings(config_files=[outer_path])
        assert outer.marker == "outer_direct"

    def test_nested_cache_materialization_for_the_same_class_resolves_its_own_paths(self, tmp_path):
        outer_path = _write_marker(tmp_path / "outer_self.yaml", "yaml", "outer_self")
        cached_path = _write_marker(tmp_path / "cached_self.yaml", "yaml", "cached_self")

        class _SelfCachedSettings(MountainAshBaseSettings):
            marker: str = "unset"

            @classmethod
            def settings_capture_sources(cls, sources):
                # Opts this legacy settings_customise_sources override in to
                # cache-safe retrieval; the nested cache lookup below is for
                # this same class, so it must be cache-admissible.
                return super().settings_capture_sources(sources)

            @classmethod
            def settings_customise_sources(
                cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
            ):
                if not getattr(cls, "_nested_guard", False):
                    cls._nested_guard = True
                    try:
                        cached = SettingsManager().get_or_create_settings(
                            SettingsParameters.create(
                                settings_class=_SelfCachedSettings, config_files=[cached_path],
                            ),
                        )
                        assert cached.marker == "cached_self"
                    finally:
                        cls._nested_guard = False
                return super().settings_customise_sources(
                    settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
                )

        outer = _SelfCachedSettings(config_files=[outer_path])
        assert outer.marker == "outer_self"


class TestCustomHookCompatibility:
    def test_subclass_hook_calling_super_receives_invocation_local_sources(self, tmp_path):
        path = _write_marker(tmp_path / "super_call.yaml", "yaml", "super-value")

        class _SuperCallingSettings(MountainAshBaseSettings):
            marker: str = "unset"

            @classmethod
            def settings_customise_sources(
                cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
            ):
                return super().settings_customise_sources(
                    settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
                )

        settings = _SuperCallingSettings(config_files=[path])
        assert settings.marker == "super-value"

    def test_subclass_hook_replacing_a_source_remains_authoritative(self, tmp_path):
        path = _write_marker(tmp_path / "ignored.yaml", "yaml", "should-be-ignored")

        class _ReplacingSettings(MountainAshBaseSettings):
            marker: str = "unset"

            @classmethod
            def settings_customise_sources(
                cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
            ):
                return (InitSettingsSource(settings_cls, init_kwargs={"marker": "overridden"}),)

        settings = _ReplacingSettings(config_files=[path])
        assert settings.marker == "overridden"


class TestDirectHookFallback:
    def test_manual_hook_call_without_active_frame_uses_static_class_config(self, tmp_path):
        path = _write_marker(tmp_path / "static.yaml", "yaml", "static-value")

        class _StaticSettings(MountainAshBaseSettings):
            marker: str = "unset"

        _StaticSettings.model_config["yaml_file"] = path
        try:
            init_settings = InitSettingsSource(_StaticSettings, init_kwargs={})
            env_settings = EnvSettingsSource(_StaticSettings)
            dotenv_settings = DotEnvSettingsSource(_StaticSettings)
            secrets_settings = SecretsSettingsSource(_StaticSettings, secrets_dir=None)

            sources = _StaticSettings.settings_customise_sources(
                _StaticSettings, init_settings, env_settings, dotenv_settings, secrets_settings,
            )
            yaml_source = next(s for s in sources if type(s).__name__ == "YamlConfigSettingsSource")
            assert yaml_source() == {"marker": "static-value"}
        finally:
            _StaticSettings.model_config.pop("yaml_file", None)

    def test_construction_never_mutates_class_model_config(self, tmp_path):
        path = _write_marker(tmp_path / "no_mutation.yaml", "yaml", "no-mutation")

        class _NoMutationSettings(MountainAshBaseSettings):
            marker: str = "unset"

        before = dict(_NoMutationSettings.model_config)
        settings = _NoMutationSettings(config_files=[path])
        assert settings.marker == "no-mutation"
        assert dict(_NoMutationSettings.model_config) == before
