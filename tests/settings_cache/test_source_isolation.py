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

import builtins
import errno
import io
import json
import os
import threading
import traceback
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError
from pydantic._internal._utils import deep_update
from pydantic_settings import (
    DotEnvSettingsSource,
    EnvSettingsSource,
    InitSettingsSource,
    SettingsConfigDict,
    JsonConfigSettingsSource,
    TomlConfigSettingsSource,
    YamlConfigSettingsSource,
    SecretsSettingsSource,
)

from mountainash_settings import CacheableSettingsSource, MountainAshBaseSettings, SettingsParameters

_PROVENANCE_ATTR = {
    "yaml": "SETTINGS_SOURCE_YAML_FILES",
    "toml": "SETTINGS_SOURCE_TOML_FILES",
    "json": "SETTINGS_SOURCE_JSON_FILES",
    "env": "SETTINGS_SOURCE_ENV_FILES",
}


def _write_marker(path: Path, suffix: str, marker: str) -> Path:
    if suffix == "yaml":
        path.write_text(f"marker: {marker}\n")
    elif suffix == "toml":
        path.write_text(f'marker = "{marker}"\n')
    elif suffix == "env":
        path.write_text(f"marker={marker}\n")
    else:
        path.write_text(json.dumps({"marker": marker}))
    return path


def _standalone_state(settings_cls, dotenv_settings=None):
    """Consume the real hook as a manual caller would, returning the merged values."""
    sources = settings_cls.settings_customise_sources(
        settings_cls,
        InitSettingsSource(settings_cls, {}),
        EnvSettingsSource(settings_cls),
        DotEnvSettingsSource(settings_cls) if dotenv_settings is None else dotenv_settings,
        SecretsSettingsSource(settings_cls),
    )
    state: dict = {}
    for source in sources:
        source._set_current_state(state)
        state = deep_update(source(), state)
    return state


@pytest.fixture
def memory_reads(monkeypatch, memory_config_root):
    """Count real stream opens of a memory-backed file, by unique file name."""
    reads: list[str] = []
    filesystem_class = type(memory_config_root.fs)
    original = filesystem_class._open

    def counting(self, path, mode="rb", *args, **kwargs):
        if "r" in mode:
            reads.append(str(path))
        return original(self, path, mode, *args, **kwargs)

    monkeypatch.setattr(filesystem_class, "_open", counting)
    return lambda path: sum(1 for read in reads if read.endswith("/" + path.name))


_NATIVE_DETAIL = "P8_NATIVE_" + "DETAIL"


class _LocalOpens:
    """Count or fail real opens of chosen local files; every other open runs untouched."""

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}
        self._native: dict[str, BaseException] = {}

    def watch(self, path) -> None:
        self._counts.setdefault(os.fspath(path), 0)

    def fail(self, path) -> OSError:
        """Make every open of ``path`` raise one native error; returns that exact object."""
        key = os.fspath(path)
        self.watch(path)
        # Only the filename and note carry the sentinel: a safe cause may repeat strerror.
        error = PermissionError(errno.EACCES, "Permission denied", f"{key}?{_NATIVE_DETAIL}#fragment")
        error.add_note(_NATIVE_DETAIL)
        self._native[key] = error
        return error

    def count(self, path) -> int:
        return self._counts[os.fspath(path)]

    def observe(self, file) -> None:
        if isinstance(file, (str, os.PathLike)):
            key = os.fspath(file)
            if key in self._counts:
                self._counts[key] += 1
                if key in self._native:
                    raise self._native[key]


@pytest.fixture
def local_opens(monkeypatch):
    """Observe opens of watched local files through both the builtin and pathlib/UPath routes."""
    opens = _LocalOpens()
    real_open = io.open

    def watching_open(file, *args, **kwargs):
        opens.observe(file)
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(io, "open", watching_open)
    monkeypatch.setattr(builtins, "open", watching_open)
    return opens


def _assert_native_unreachable(error: BaseException, native: BaseException) -> None:
    """Walk the cause/context graph: the injected native error and its text must be gone."""
    pending, seen = [error], set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        assert current is not native
        for text in (str(current), repr(current), repr(current.args), repr(vars(current)),
                     "".join(traceback.format_exception(current))):
            assert _NATIVE_DETAIL not in text
        pending.extend(link for link in (current.__cause__, current.__context__) if link is not None)


_HOOK_SHAPES = ["inherited", "no-super", "super", "two-level", "staticmethod", "function"]
# Hook bodies a successful construction runs, outermost first.
_EXPECTED_ENTRIES = {
    "inherited": [], "no-super": ["hook"], "super": ["hook"],
    "two-level": ["child", "parent"], "staticmethod": ["hook"], "function": ["hook"],
}


def _hooked_settings(shape: str, entered: list[str]):
    """Settings class whose source hook has the named shape; ``entered`` records hook bodies run."""

    class _Plain(MountainAshBaseSettings):
        marker: str = "unset"
        other: str = "unset"

    def no_super(settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings):
        entered.append("hook")
        return (init_settings, dotenv_settings)

    if shape == "inherited":
        return _Plain
    if shape == "no-super":
        class _NoSuper(_Plain):
            @classmethod
            def settings_customise_sources(
                cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
            ):
                entered.append("hook")
                return (init_settings, dotenv_settings)
        return _NoSuper
    if shape == "super":
        class _Super(_Plain):
            @classmethod
            def settings_customise_sources(
                cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
            ):
                entered.append("hook")
                return super().settings_customise_sources(
                    settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
                )
        return _Super
    if shape == "two-level":
        class _Parent(_Plain):
            @classmethod
            def settings_customise_sources(
                cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
            ):
                entered.append("parent")
                return super().settings_customise_sources(
                    settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
                )

        class _Child(_Parent):
            @classmethod
            def settings_customise_sources(
                cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
            ):
                entered.append("child")
                return super().settings_customise_sources(
                    settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
                )
        return _Child
    if shape == "staticmethod":
        class _Static(_Plain):
            settings_customise_sources = cast(Any, staticmethod(no_super))
        return _Static
    class _Function(_Plain):
        settings_customise_sources = cast(Any, no_super)
    return _Function


def _pausing_settings_class(paused: threading.Event, resume: threading.Event):
    class _Pausing(MountainAshBaseSettings):
        marker: str = "unset"
        other: str = "unset"
        count: int = 0

        @classmethod
        def settings_customise_sources(
            cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
        ):
            if threading.current_thread().name == "construct-a":
                paused.set()
                assert resume.wait(timeout=5), "test deadlocked waiting to resume A"
            return super().settings_customise_sources(
                settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
            )

    return _Pausing


def _construct_a_paused_around(settings_cls, paused, resume, files_a, during):
    """Build A on a thread paused inside its hook; run ``during`` before resuming it."""
    results: dict[str, object] = {}
    errors: dict[str, BaseException] = {}

    def construct_a():
        try:
            results["a"] = settings_cls(config_files=files_a)
        except BaseException as exc:  # noqa: BLE001 - surfaced via errors dict
            errors["a"] = exc

    thread = threading.Thread(target=construct_a, name="construct-a")
    thread.start()
    try:
        assert paused.wait(timeout=5), "A never reached its pause point"
        during_result = during()
    finally:
        resume.set()
        thread.join(timeout=5)
    assert not thread.is_alive(), "construction thread A did not finish"
    assert not errors, errors
    return results["a"], during_result


@pytest.fixture(params=["local-yaml", "remote-env"])
def marker_source(request, tmp_path, memory_config_root):
    """Marker-file factory over a local YAML file and a memory-backed dotenv file."""
    suffix, root = ("yaml", tmp_path) if request.param == "local-yaml" else ("env", memory_config_root)

    def make(name: str, marker: str):
        return _write_marker(root / f"{name}.{suffix}", suffix, marker)

    make.provenance = _PROVENANCE_ATTR[suffix]
    return make


class TestConcurrentConstructionIsolation:
    """The historical vulnerability: B must never make A observe B's source."""

    @pytest.mark.parametrize("suffix", ["yaml", "toml", "json", "env"])
    def test_overlapping_same_class_construction_isolates_source_paths(self, tmp_path, suffix):
        path_a = _write_marker(tmp_path / f"a.{suffix}", suffix, "a")
        path_b = _write_marker(tmp_path / f"b.{suffix}", suffix, "b")
        paused, resume = threading.Event(), threading.Event()
        settings_cls = _pausing_settings_class(paused, resume)

        # B must fully construct, using its own path, while A is paused with
        # its own frame installed and no source objects built yet.
        settings_a, settings_b = _construct_a_paused_around(
            settings_cls, paused, resume, [path_a], lambda: settings_cls(config_files=[path_b]),
        )

        assert settings_a.marker == "a"
        assert settings_b.marker == "b"
        attr = _PROVENANCE_ATTR[suffix]
        assert [str(p) for p in getattr(settings_a, attr)] == [str(path_a)]
        assert [str(p) for p in getattr(settings_b, attr)] == [str(path_b)]

    @pytest.mark.parametrize("representation", ["string", "upath"])
    def test_overlapping_remote_dotenv_construction_keeps_ordered_frames_apart(
        self, tmp_path, memory_config_root, representation,
    ):
        local = tmp_path / "base.env"
        local.write_text("marker=local\nother=kept\n")
        remote_a = memory_config_root / "a.env"
        remote_a.write_text("marker=a\ncount=1\n")
        remote_b = memory_config_root / "b.env"
        remote_b.write_text("marker=b\ncount=2\n")
        select = (lambda path: str(path)) if representation == "string" else (lambda path: path)
        paused, resume = threading.Event(), threading.Event()
        settings_cls = _pausing_settings_class(paused, resume)

        settings_a, settings_b = _construct_a_paused_around(
            settings_cls, paused, resume, [str(local), select(remote_a)],
            lambda: settings_cls(config_files=[select(remote_b)]),
        )

        # A: the later remote file overrides the earlier local one, keys it lacks survive.
        assert (settings_a.marker, settings_a.other, settings_a.count) == ("a", "kept", 1)
        assert (settings_b.marker, settings_b.other, settings_b.count) == ("b", "unset", 2)
        assert [str(p) for p in settings_a.SETTINGS_SOURCE_ENV_FILES] == [str(local), str(remote_a)]
        assert [str(p) for p in settings_b.SETTINGS_SOURCE_ENV_FILES] == [str(remote_b)]

    def test_failed_overlapping_remote_dotenv_construction_does_not_disturb_the_paused_one(
        self, memory_config_root,
    ):
        remote_a = memory_config_root / "a_ok.env"
        remote_a.write_text("marker=a\ncount=1\n")
        remote_bad = memory_config_root / "b_bad.env"
        remote_bad.write_text("marker=bad\ncount=not-an-int\n")
        paused, resume = threading.Event(), threading.Event()
        settings_cls = _pausing_settings_class(paused, resume)

        def failing_then_unrelated():
            with pytest.raises(ValidationError):
                settings_cls(config_files=[remote_bad])
            return settings_cls()

        settings_a, later = _construct_a_paused_around(
            settings_cls, paused, resume, [remote_a], failing_then_unrelated,
        )

        assert (settings_a.marker, settings_a.count) == ("a", 1)
        assert [str(p) for p in settings_a.SETTINGS_SOURCE_ENV_FILES] == [str(remote_a)]
        assert (later.marker, later.count) == ("unset", 0)

    def test_local_dotenv_failure_in_an_overlapping_construction_does_not_disturb_the_paused_one(
        self, tmp_path, local_opens,
    ):
        path_a = _write_marker(tmp_path / "paused_a.env", "env", "a")
        path_bad = _write_marker(tmp_path / "paused_bad.env", "env", "bad")
        path_c = _write_marker(tmp_path / "paused_c.env", "env", "c")
        local_opens.fail(path_bad)
        paused, resume = threading.Event(), threading.Event()
        settings_cls = _pausing_settings_class(paused, resume)

        def failing_then_unrelated():
            with pytest.raises(PermissionError):
                settings_cls(config_files=[path_bad])
            return settings_cls(config_files=[path_c])

        settings_a, later = _construct_a_paused_around(
            settings_cls, paused, resume, [path_a], failing_then_unrelated,
        )

        assert (settings_a.marker, later.marker) == ("a", "c")
        assert [str(p) for p in settings_a.SETTINGS_SOURCE_ENV_FILES] == [str(path_a)]



class TestNestedConstruction:
    def test_outer_hook_constructing_a_different_class_restores_outer_frame(self, marker_source):
        outer_path = marker_source("outer", "outer")
        inner_path = marker_source("inner", "inner")

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
                assert [str(p) for p in getattr(inner, marker_source.provenance)] == [str(inner_path)]
                # Inner's frame has been installed and torn down by this
                # point; the outer frame must still resolve outer's own path.
                return super().settings_customise_sources(
                    settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
                )

        outer = _OuterSettings(config_files=[outer_path])
        assert outer.marker == "outer"
        assert [str(p) for p in getattr(outer, marker_source.provenance)] == [str(outer_path)]

    def test_outer_hook_recursively_constructing_same_class_restores_outer_frame(self, marker_source):
        outer_path = marker_source("outer_same", "outer_same")
        inner_path = marker_source("inner_same", "inner_same")

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

    def test_failed_nested_construction_leaks_no_frame_to_a_later_unrelated_call(self, marker_source):
        good_path = marker_source("good", "good")

        class _StrictInner(MountainAshBaseSettings):
            required_value: int

        class _OuterWithFailingNested(MountainAshBaseSettings):
            marker: str = "unset"

            @classmethod
            def settings_customise_sources(
                cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
            ):
                # Fails while its own file frame is active.
                with pytest.raises(ValidationError):
                    _StrictInner(config_files=[good_path])
                return super().settings_customise_sources(
                    settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
                )

        outer = _OuterWithFailingNested(config_files=[good_path])
        assert outer.marker == "good"

        class _LaterSettings(MountainAshBaseSettings):
            marker: str = "unset"

        assert _LaterSettings().marker == "unset"
        assert _LaterSettings(config_files=[good_path]).marker == "good"

    def test_nested_construction_hydrates_each_incoming_source_from_its_own_frame(self, tmp_path, local_opens):
        outer_path = _write_marker(tmp_path / "outer_hydrated.env", "env", "outer")
        inner_path = _write_marker(tmp_path / "inner_hydrated.env", "env", "inner")
        local_opens.watch(outer_path)
        local_opens.watch(inner_path)
        observed: dict[str, object] = {}

        class _NestingSettings(MountainAshBaseSettings):
            marker: str = "unset"

            @classmethod
            def settings_customise_sources(
                cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
            ):
                if not getattr(cls, "_nesting_guard", False):
                    observed["outer_before"] = dict(dotenv_settings.env_vars)
                    cls._nesting_guard = True
                    try:
                        observed["inner"] = _NestingSettings(config_files=[inner_path]).marker
                    finally:
                        cls._nesting_guard = False
                return super().settings_customise_sources(
                    settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
                )

        outer = _NestingSettings(config_files=[outer_path])

        assert observed == {"outer_before": {"marker": "outer"}, "inner": "inner"}
        assert outer.marker == "outer"
        assert (local_opens.count(outer_path), local_opens.count(inner_path)) == (1, 1)


class TestCacheMaterializationPrecedence:
    """A direct-construction frame active during nested cache materialization
    must never leak into the cache's own captured source paths."""

    def test_nested_cache_materialization_for_a_different_class_resolves_its_own_paths(
        self, marker_source, isolated_settings_manager,
    ):
        outer_path = marker_source("outer_direct", "outer_direct")
        cached_path = marker_source("cached_other", "cached_other")

        class _CachedSettings(MountainAshBaseSettings):
            marker: str = "unset"

        class _OuterSettings(MountainAshBaseSettings):
            marker: str = "unset"

            @classmethod
            def settings_customise_sources(
                cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
            ):
                cached = isolated_settings_manager.get_or_create_settings(
                    SettingsParameters.create(settings_class=_CachedSettings, config_files=[cached_path]),
                )
                assert cached.marker == "cached_other"
                return super().settings_customise_sources(
                    settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
                )

        outer = _OuterSettings(config_files=[outer_path])
        assert outer.marker == "outer_direct"

    def test_nested_cache_materialization_for_the_same_class_resolves_its_own_paths(
        self, marker_source, isolated_settings_manager,
    ):
        outer_path = marker_source("outer_self", "outer_self")
        cached_path = marker_source("cached_self", "cached_self")

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
                        cached = isolated_settings_manager.get_or_create_settings(
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

    def test_subclass_hook_calling_super_receives_remote_dotenv_paths(self, tmp_path, memory_config_root):
        local = tmp_path / "local.env"
        local.write_text("marker=local\nother=local-only\n")
        remote = memory_config_root / "super_call.env"
        remote.write_text("marker=remote\n")

        class _SuperCallingSettings(MountainAshBaseSettings):
            marker: str = "unset"
            other: str = "unset"

            @classmethod
            def settings_customise_sources(
                cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
            ):
                return super().settings_customise_sources(
                    settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
                )

        settings = _SuperCallingSettings(config_files=[str(local), remote])
        assert (settings.marker, settings.other) == ("remote", "local-only")

    def test_subclass_hook_replacing_sources_never_opens_a_remote_dotenv(self, memory_config_root, memory_reads):
        path = memory_config_root / "ignored.env"
        path.write_text("marker=should-be-ignored\n")

        class _ReplacingSettings(MountainAshBaseSettings):
            marker: str = "unset"

            @classmethod
            def settings_customise_sources(
                cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
            ):
                return (InitSettingsSource(settings_cls, init_kwargs={"marker": "overridden"}),)

        assert _ReplacingSettings(config_files=[path]).marker == "overridden"
        assert memory_reads(path) == 0

    @pytest.mark.parametrize("selection", ["local", "mixed"])
    def test_hook_receives_the_standard_primary_with_only_local_dotenv_paths(
        self, tmp_path, memory_config_root, selection,
    ):
        local = tmp_path / "primary.env"
        local.write_text("marker=local\n")
        remote = memory_config_root / "primary_remote.env"
        remote.write_text("marker=remote\n")
        files = [str(local)] if selection == "local" else [str(local), remote]
        seen: dict[str, object] = {}

        class _PrimaryUsingSettings(MountainAshBaseSettings):
            marker: str = "unset"

            @classmethod
            def settings_customise_sources(
                cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
            ):
                seen["files"] = tuple(str(p) for p in dotenv_settings.env_file)
                return (init_settings, dotenv_settings)

        settings = _PrimaryUsingSettings(config_files=files)
        assert seen["files"] == (str(local),)
        assert settings.marker == "local"

    @pytest.mark.parametrize("shape", _HOOK_SHAPES)
    def test_every_supported_hook_shape_loads_the_local_dotenv_with_one_parse(
        self, tmp_path, local_opens, shape,
    ):
        path = tmp_path / "shapes.env"
        path.write_text("marker=local\nother=kept\n")
        local_opens.watch(path)
        entered: list[str] = []

        settings = _hooked_settings(shape, entered)(config_files=[path])

        assert (settings.marker, settings.other) == ("local", "kept")
        assert local_opens.count(path) == 1
        assert entered == _EXPECTED_ENTRIES[shape]

    @pytest.mark.parametrize("shape", _HOOK_SHAPES)
    def test_local_dotenv_open_failure_is_safe_before_any_hook_sees_the_source(
        self, tmp_path, local_opens, shape,
    ):
        path = _write_marker(tmp_path / "unreadable.env", "env", "never-loaded")
        native = local_opens.fail(path)
        entered: list[str] = []

        with pytest.raises(PermissionError) as caught:
            _hooked_settings(shape, entered)(config_files=[path])

        # The access error is raised while preparing the incoming source, so not even
        # a no-super hook body ran, and the native error is unreachable from it.
        assert entered == []
        assert caught.value.errno == errno.EACCES
        assert str(path) in str(caught.value)
        _assert_native_unreachable(caught.value, native)

    def test_mixed_selection_local_failure_precedes_any_remote_open(
        self, tmp_path, memory_config_root, memory_reads, local_opens,
    ):
        local = _write_marker(tmp_path / "mixed_unreadable.env", "env", "local")
        remote = _write_marker(memory_config_root / "mixed_remote.env", "env", "remote")
        native = local_opens.fail(local)
        entered: list[str] = []

        with pytest.raises(PermissionError) as caught:
            _hooked_settings("super", entered)(config_files=[str(local), remote])

        assert entered == []
        assert memory_reads(remote) == 0
        _assert_native_unreachable(caught.value, native)

    def test_delayed_rethrow_keeps_a_clean_error_clean(self, tmp_path, local_opens):
        path = _write_marker(tmp_path / "ambient_unreadable.env", "env", "never-loaded")
        native = local_opens.fail(path)
        ambient = RuntimeError("ambient failure")

        try:
            raise ambient
        except RuntimeError:
            with pytest.raises(PermissionError) as caught:
                _hooked_settings("no-super", [])(config_files=[path])

        assert caught.value.__context__ is None
        _assert_native_unreachable(caught.value, native)

    def test_delayed_rethrow_keeps_an_existing_content_chain(self, tmp_path):
        path = _write_marker(tmp_path / "chained.env", "env", "value")

        class _ChainingSettings(MountainAshBaseSettings):
            marker: str = "unset"

            @classmethod
            def settings_customise_sources(
                cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
            ):
                try:
                    raise KeyError("content-detail")
                except KeyError as inner:
                    raise ValueError("bad source content") from inner

        ambient = RuntimeError("ambient failure")
        try:
            raise ambient
        except RuntimeError:
            with pytest.raises(ValueError, match="bad source content") as caught:
                _ChainingSettings(config_files=[path])

        # The content cause was raised under the same handler, so its own ambient
        # context is part of the existing chain and stays; the rethrow adds nothing.
        error = caught.value
        assert isinstance(error.__cause__, KeyError) and error.__cause__.args == ("content-detail",)
        assert error.__context__ is error.__cause__
        assert error.__cause__.__context__ is ambient

    def test_no_super_hook_receives_the_ordinary_source_hydrated_from_the_local_selection(
        self, tmp_path, local_opens,
    ):
        path = tmp_path / "ordinary.env"
        path.write_text("APP_marker=local\nAPP_other=kept\nunrelated=x\n")
        local_opens.watch(path)
        seen: dict[str, object] = {}

        class _NoSuperSettings(MountainAshBaseSettings):
            marker: str = "unset"
            other: str = "unset"

            @classmethod
            def settings_customise_sources(
                cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
            ):
                seen["source"] = dotenv_settings
                seen["init"] = init_settings
                return (init_settings, dotenv_settings)

        settings = _NoSuperSettings(config_files=[path], env_prefix="APP_")
        source = cast(DotEnvSettingsSource, seen["source"])

        assert (settings.marker, settings.other) == ("local", "kept")
        assert type(source) is DotEnvSettingsSource
        assert source.env_file == (str(path),)
        assert dict(source.env_vars) == {"APP_marker": "local", "APP_other": "kept", "unrelated": "x"}
        assert (source.env_prefix, source.env_file_encoding) == ("APP_", "utf-8")
        assert (source.case_sensitive, source.env_ignore_empty, source.env_parse_none_str) == (True, True, "None")
        assert source._init_state is cast(InitSettingsSource, seen["init"])._init_state
        assert local_opens.count(path) == 1

    def test_source_mutated_before_super_is_neither_reread_nor_replaced(self, tmp_path, local_opens):
        path = _write_marker(tmp_path / "mutated.env", "env", "from-file")
        local_opens.watch(path)
        seen: dict[str, object] = {}

        class _MutatingSettings(MountainAshBaseSettings):
            marker: str = "unset"

            @classmethod
            def settings_customise_sources(
                cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
            ):
                dotenv_settings.env_vars = {**dotenv_settings.env_vars, "marker": "mutated"}
                seen["incoming"] = dotenv_settings
                sources = super().settings_customise_sources(
                    settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
                )
                seen["sources"] = sources
                return sources

        settings = _MutatingSettings(config_files=[path])

        assert settings.marker == "mutated"
        assert any(source is seen["incoming"] for source in cast(tuple, seen["sources"]))
        assert local_opens.count(path) == 1



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
            state = {}
            for source in sources:
                source._set_current_state(state)
                state = deep_update(source(), state)
            assert state["marker"] == "static-value"
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

    def test_standalone_hook_call_leaves_the_ordinary_source_untouched(self, tmp_path, local_opens):
        path = _write_marker(tmp_path / "standalone_untouched.env", "env", "never-read")
        local_opens.watch(path)

        class _StandaloneSettings(MountainAshBaseSettings):
            marker: str = "unset"

        class _Declared(_StandaloneSettings):
            @classmethod
            def settings_customise_sources(
                cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
            ):
                return super().settings_customise_sources(
                    settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
                )

        for settings_class in (_StandaloneSettings, _Declared):
            source = DotEnvSettingsSource(settings_class)
            settings_class.settings_customise_sources(
                settings_class, InitSettingsSource(settings_class, {}), EnvSettingsSource(settings_class),
                source, SecretsSettingsSource(settings_class),
            )
            assert source.env_file is None
            assert dict(source.env_vars) == {}
        assert local_opens.count(path) == 0

    def test_hook_call_for_another_class_inside_a_direct_frame_is_not_hydrated(self, tmp_path, local_opens):
        path = _write_marker(tmp_path / "frame_owner.env", "env", "owner")
        local_opens.watch(path)
        probes: list[DotEnvSettingsSource] = []

        class _Other(MountainAshBaseSettings):
            marker: str = "unset"

        class _Owner(MountainAshBaseSettings):
            marker: str = "unset"

            @classmethod
            def settings_customise_sources(
                cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
            ):
                probe = DotEnvSettingsSource(_Other)
                _Other.settings_customise_sources(
                    _Other, InitSettingsSource(_Other, {}), EnvSettingsSource(_Other), probe,
                    SecretsSettingsSource(_Other),
                )
                probes.append(probe)
                return super().settings_customise_sources(
                    settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
                )

        assert _Owner(config_files=[path]).marker == "owner"
        assert (probes[0].env_file, dict(probes[0].env_vars)) == (None, {})
        assert local_opens.count(path) == 1



@pytest.mark.parametrize("representation", ["string", "upath"])
@pytest.mark.parametrize("route", ["direct", "cached", "standalone"])
def test_remote_toml_table_selection(memory_config_root, isolated_settings_manager, representation, route):
    path = memory_config_root / "table.toml"
    path.write_text("[app]\nVALUE=7\n")
    selected = str(path) if representation == "string" else path

    class TableSettings(MountainAshBaseSettings):
        model_config = {"toml_file": selected, "toml_table_header": ("app",)}
        VALUE: int = 0

    if route == "direct":
        assert TableSettings(config_files=selected).VALUE == 7
    elif route == "cached":
        parameters = SettingsParameters.create(settings_class=TableSettings, config_files=selected)
        assert isolated_settings_manager.get_or_create_settings(parameters).VALUE == 7
    else:
        sources = TableSettings.settings_customise_sources(
            TableSettings, InitSettingsSource(TableSettings, {}),
            EnvSettingsSource(TableSettings), DotEnvSettingsSource(TableSettings),
            SecretsSettingsSource(TableSettings),
        )
        state = {}
        for source in sources:
            source._set_current_state(state)
            state = deep_update(source(), state)
        assert state["VALUE"] == 7


def test_remote_toml_optional_file_and_missing_table(memory_config_root):
    path = memory_config_root / "optional.toml"

    class OptionalSettings(MountainAshBaseSettings):
        model_config = {"toml_file": str(path), "toml_table_header": ("app",)}
        VALUE: int = 0

    def sources():
        return OptionalSettings.settings_customise_sources(
            OptionalSettings, InitSettingsSource(OptionalSettings, {}),
            EnvSettingsSource(OptionalSettings), DotEnvSettingsSource(OptionalSettings),
            SecretsSettingsSource(OptionalSettings),
        )

    state = {}
    for source in sources():
        state = deep_update(source(), state)
    assert state.get("VALUE", 0) == 0
    path.write_text("[other]\nVALUE=9\n")
    with pytest.raises(KeyError):
        sources()


@pytest.mark.parametrize(
    "suffix, source_type, argument",
    [
        ("yaml", YamlConfigSettingsSource, "yaml_file"),
        ("toml", TomlConfigSettingsSource, "toml_file"),
        ("json", JsonConfigSettingsSource, "json_file"),
    ],
)
def test_capture_hook_can_select_standard_structured_source(
    tmp_path, isolated_settings_manager, suffix, source_type, argument,
):
    path = _write_marker(tmp_path / f"selected.{suffix}", suffix, "selected")

    class SelectedSettings(MountainAshBaseSettings):
        marker: str = "default"

        @classmethod
        def settings_capture_sources(cls, sources):
            return (source_type(cls, **{argument: path}),)

    parameters = SettingsParameters.create(settings_class=SelectedSettings)
    first = parameters.get_settings()
    path.unlink()
    assert first.marker == parameters.get_settings().marker == "selected"


@pytest.mark.parametrize("route, selection", [
    ("standalone", "string"), ("standalone", "tuple"),
    ("direct", "upath"), ("cached", "upath"),
])
def test_dotenv_views_share_one_remote_parse(
    memory_config_root, memory_reads, isolated_settings_manager, route, selection,
):
    class Settings(MountainAshBaseSettings):
        VALUE: str = "default"
        FALLBACK: str = "default"

    path = memory_config_root / ".env"
    path.write_text("VALUE=base\nAPP_VALUE=prefixed\nFALLBACK=fallback\n")
    env_file = str(path) if selection == "string" else ((str(path),) if selection == "tuple" else path)
    if route == "standalone":
        state = _standalone_state(
            Settings, DotEnvSettingsSource(Settings, env_file=env_file, env_prefix="APP_"),
        )
        values = (state["VALUE"], state["FALLBACK"])
    elif route == "direct":
        settings = Settings(config_files=path, env_prefix="APP_")
        values = (settings.VALUE, settings.FALLBACK)
    else:
        params = SettingsParameters.create(settings_class=Settings, config_files=path, env_prefix="APP_")
        settings = params.get_settings()
        path.unlink()
        again = params.get_settings()
        assert (again.VALUE, again.FALLBACK) == ("prefixed", "fallback")
        values = (settings.VALUE, settings.FALLBACK)
    assert values == ("prefixed", "fallback")
    # The primary and the unprefixed fallback view share one read of the remote file.
    assert memory_reads(path) == 1


@pytest.mark.parametrize("remote_first", [False, True])
def test_standalone_remote_dotenv_keeps_file_order_with_a_local_file(tmp_path, memory_config_root, remote_first):
    class Settings(MountainAshBaseSettings):
        VALUE: str = "default"
        FALLBACK: str = "default"

    local = tmp_path / "local.env"
    local.write_text("VALUE=local\nFALLBACK=local\n")
    remote = memory_config_root / "remote.env"
    remote.write_text("VALUE=remote\n")
    files = (str(remote), str(local)) if remote_first else (str(local), str(remote))
    state = _standalone_state(Settings, DotEnvSettingsSource(Settings, env_file=files))
    assert state["VALUE"] == ("local" if remote_first else "remote")
    assert state["FALLBACK"] == "local"


@pytest.mark.parametrize("route", ["standalone", "direct"])
def test_custom_dotenv_subclass_is_not_replaced(memory_config_root, route):
    class Settings(MountainAshBaseSettings):
        VALUE: str = "default"

    path = memory_config_root / "custom.env"
    path.write_text("VALUE=remote\n")

    class CustomDotenv(DotEnvSettingsSource):
        def __call__(self):
            return {"VALUE": "custom"}

    if route == "standalone":
        state = _standalone_state(Settings, CustomDotenv(Settings, env_file=str(path)))
        assert state["VALUE"] == "custom"
    else:
        class HookSettings(Settings):
            @classmethod
            def settings_customise_sources(
                cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
            ):
                custom = CustomDotenv(settings_cls, env_file=dotenv_settings.env_file)
                return super().settings_customise_sources(
                    settings_cls, init_settings, env_settings, custom, file_secret_settings,
                )

        assert HookSettings(config_files=path).VALUE == "custom"


_CLASS_SELECTED_FILES = [
    ("env_file", "VALUE=class\n"),
    ("yaml_file", "VALUE: class\n"),
    ("toml_file", 'VALUE = "class"\n'),
    ("json_file", '{"VALUE": "class"}'),
]


# Extensionless names: only the declared class setting selects the parser.
@pytest.mark.parametrize("argument, content", _CLASS_SELECTED_FILES)
@pytest.mark.parametrize("route", ["standalone", "direct", "cached"])
def test_class_selected_remote_file_follows_each_routes_absent_selection(
    memory_config_root, isolated_settings_manager, argument, content, route,
):
    path = memory_config_root / "selected"
    path.write_text(content)

    class ClassSelected(MountainAshBaseSettings):
        model_config = cast(SettingsConfigDict, {argument: str(path)})
        VALUE: str = "default"

    if route == "standalone":
        value = _standalone_state(ClassSelected).get("VALUE", "default")
    elif route == "direct":
        value = ClassSelected().VALUE
    else:
        value = isolated_settings_manager.get_or_create_settings(
            SettingsParameters.create(settings_class=ClassSelected),
        ).VALUE
    # Direct construction disables class file fallback; cached dotenv alone may
    # fall back to the class selection while cached structured sources do not.
    expected = "class" if route == "standalone" or (route, argument) == ("cached", "env_file") else "default"
    assert value == expected


@pytest.mark.parametrize("argument, content", _CLASS_SELECTED_FILES)
@pytest.mark.parametrize("route", ["standalone", "cached"])
def test_class_selected_missing_remote_file_is_optional(
    memory_config_root, isolated_settings_manager, argument, content, route,
):
    path = memory_config_root / "absent"

    class ClassSelected(MountainAshBaseSettings):
        model_config = cast(SettingsConfigDict, {argument: str(path)})
        VALUE: str = "default"

    def load():
        if route == "standalone":
            return _standalone_state(ClassSelected).get("VALUE", "default")
        return isolated_settings_manager.get_or_create_settings(
            SettingsParameters.create(settings_class=ClassSelected),
        ).VALUE

    assert load() == "default"
    if route == "standalone":
        path.write_text(content)
        assert load() == "class"


def test_capture_hook_can_select_standard_dotenv_source(tmp_path, isolated_settings_manager):
    path = _write_marker(tmp_path / "selected.env", "env", "selected")

    class SelectedSettings(MountainAshBaseSettings):
        marker: str = "default"

        @classmethod
        def settings_capture_sources(cls, sources):
            return (DotEnvSettingsSource(cls, env_file=path),)

    parameters = SettingsParameters.create(settings_class=SelectedSettings)
    first = parameters.get_settings()
    path.unlink()
    assert first.marker == parameters.get_settings().marker == "selected"


def test_capture_hook_rejects_a_custom_dotenv_subclass(tmp_path, isolated_settings_manager):
    path = _write_marker(tmp_path / "custom.env", "env", "custom")

    class CustomDotenv(DotEnvSettingsSource):
        pass

    class CustomSettings(MountainAshBaseSettings):
        marker: str = "default"

        @classmethod
        def settings_capture_sources(cls, sources):
            return (CustomDotenv(cls, env_file=path),)

    parameters = SettingsParameters.create(settings_class=CustomSettings)
    with pytest.raises(ValueError):
        parameters.get_settings()
    assert not isolated_settings_manager.is_initialised(parameters)


def test_cached_capture_participant_observes_remote_dotenv_state_without_recapture(
    memory_config_root, isolated_settings_manager,
):
    captures: list[None] = []

    class _Observer(CacheableSettingsSource):
        def get_field_value(self, field, field_name):
            return None, field_name, False

        def __call__(self):
            return self.project(self.capture(), self.current_state, self.settings_sources_data)

        def capture(self):
            captures.append(None)
            return {}

        @staticmethod
        def project(owned_resolved_snapshot, owned_current_state, owned_sources_data):
            return {"OBSERVED": owned_current_state.get("VALUE", "missing")}

    class ObservedSettings(MountainAshBaseSettings):
        VALUE: str = "default"
        OBSERVED: str = "default"

        @classmethod
        def settings_capture_sources(cls, sources):
            return sources[:-1] + (_Observer(cls),) + sources[-1:]

    path = memory_config_root / "observed.env"
    path.write_text("VALUE=remote\n")
    parameters = SettingsParameters.create(settings_class=ObservedSettings, config_files=path)
    first = isolated_settings_manager.get_or_create_settings(parameters)
    path.unlink()
    second = isolated_settings_manager.get_or_create_settings(parameters)
    assert (first.VALUE, first.OBSERVED) == (second.VALUE, second.OBSERVED) == ("remote", "remote")
    assert len(captures) == 1


def test_cached_class_dotenv_accepts_scalar_upath(memory_config_root, isolated_settings_manager):
    path = memory_config_root / "selected"
    path.write_text("VALUE=class-upath\n")

    class Settings(MountainAshBaseSettings):
        model_config = {"env_file": path}
        VALUE: str = "default"

    params = SettingsParameters.create(settings_class=Settings)
    assert params.get_settings().VALUE == "class-upath"
    path.unlink()
    assert params.get_settings().VALUE == "class-upath"


class TestHookWrappingKeepsCacheAdmission:
    def test_inheriting_subclass_shares_the_base_hook_and_stays_cache_admissible(
        self, tmp_path, isolated_settings_manager,
    ):
        path = _write_marker(tmp_path / "inherited.env", "env", "inherited")

        class _Parent(MountainAshBaseSettings):
            marker: str = "unset"

        class _Child(_Parent):
            pass

        # Only the base hook and hooks declared in a subclass body are wrapped; an
        # inheriting subclass resolves to the very same hook function.
        base_hook = MountainAshBaseSettings.settings_customise_sources.__func__
        assert _Parent.settings_customise_sources.__func__ is base_hook
        assert _Child.settings_customise_sources.__func__ is base_hook
        parameters = SettingsParameters.create(settings_class=_Child, config_files=[path])
        assert parameters.get_settings().marker == "inherited"

    def test_declared_hook_without_capture_hook_is_still_rejected_for_cache(self, isolated_settings_manager):
        class _Legacy(MountainAshBaseSettings):
            marker: str = "unset"

            @classmethod
            def settings_customise_sources(
                cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
            ):
                return super().settings_customise_sources(
                    settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
                )

        class _Inheriting(_Legacy):
            pass

        assert _Legacy.settings_customise_sources.__func__ is not (
            MountainAshBaseSettings.settings_customise_sources.__func__
        )
        for settings_class in (_Legacy, _Inheriting):
            parameters = SettingsParameters.create(settings_class=settings_class)
            with pytest.raises(ValueError):
                parameters.get_settings()
            assert not isolated_settings_manager.is_initialised(parameters)
        assert _Legacy(marker="direct").marker == "direct"
