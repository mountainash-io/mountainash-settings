"""W8 regressions at public configuration boundaries, not only rendering helpers."""
from __future__ import annotations

import traceback

import pytest

from mountainash_settings import MountainAshBaseSettings, get_settings


CREDENTIAL_LOCATION = "https://P8_USER:P8_PASSWORD@host/config.yaml?token=P8_QUERY#P8_FRAGMENT"
SENTINELS = ("P8_USER", "P8_PASSWORD", "P8_QUERY", "P8_FRAGMENT", "P8_AMBIENT")


class SafeErrorSettings(MountainAshBaseSettings):
    VALUE: int = 0


def assert_safe_error(error: BaseException) -> None:
    pending = [error]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        surfaces = [str(current), repr(current), repr(current.args), repr(vars(current)),
                    repr(getattr(current, "filename", None)),
                    repr(getattr(current, "filename2", None)),
                    "".join(traceback.format_exception(current))]
        for text in surfaces:
            for sentinel in SENTINELS:
                assert sentinel not in text
        for chained in (current.__cause__, current.__context__):
            if chained is not None:
                pending.append(chained)


def construct(path, cached):
    if cached:
        return get_settings(settings_class=SafeErrorSettings, config_files=path)
    return SafeErrorSettings(config_files=path)


@pytest.mark.parametrize("cached", [False, True])
def test_native_inspection_failure_has_safe_attributes(
    memory_config_root, isolated_settings_manager, monkeypatch, cached,
):
    path = memory_config_root / "config.yaml"
    path.write_text("VALUE: 5\n")
    native = PermissionError(13, "Permission denied", CREDENTIAL_LOCATION)
    native.add_note(CREDENTIAL_LOCATION)
    reached = []

    def fail_exists(self):
        reached.append(str(self))
        raise native

    monkeypatch.setattr(type(path), "exists", fail_exists)
    with pytest.raises(PermissionError) as caught:
        construct(path, cached)
    assert reached
    assert_safe_error(caught.value)
    assert caught.value.__cause__ is not native
    assert caught.value.__cause__.filename is None
    assert caught.value.__cause__.errno == 13


@pytest.mark.parametrize("cached", [False, True])
def test_missing_location_omits_url_tail_and_ambient_context(
    memory_config_root, isolated_settings_manager, cached,
):
    path = memory_config_root / "missing?P8_QUERY#P8_FRAGMENT.yaml"
    try:
        raise RuntimeError(SENTINELS[-1])
    except RuntimeError:
        with pytest.raises(FileNotFoundError) as caught:
            construct(path, cached)
    assert_safe_error(caught.value)
    assert "missing" in str(caught.value)
    assert caught.value.__context__ is None


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("operation", ["normalization", "classification", "identity"])
def test_native_path_preparation_failure_is_controlled(
    memory_config_root, tmp_path, isolated_settings_manager, monkeypatch, cached, operation,
):
    from upath import UPath

    path = UPath(tmp_path / "config.yaml") if operation == "normalization" else memory_config_root / "config.yaml"
    path.write_text("VALUE: 5\n")
    native = PermissionError(13, "Permission denied", CREDENTIAL_LOCATION)
    reached = []

    def fail(self):
        reached.append(type(self))
        raise native

    if operation == "normalization":
        monkeypatch.setattr(type(path), "expanduser", fail)
    else:
        attribute = "name" if operation == "classification" else "storage_options"
        monkeypatch.setattr(type(path), attribute, property(fail))
    with pytest.raises(ValueError) as caught:
        construct(path, cached)
    assert reached
    assert_safe_error(caught.value)
    assert caught.value.__cause__.errno == 13
    assert caught.value.__cause__.filename is None


@pytest.mark.parametrize("cached", [False, True])
def test_unsupported_format_does_not_retain_ambient_exception(
    memory_config_root, isolated_settings_manager, cached,
):
    path = memory_config_root / "config.unsupported"
    path.write_text("VALUE: 5\n")
    try:
        raise RuntimeError(SENTINELS[-1])
    except RuntimeError:
        with pytest.raises(ValueError) as caught:
            construct(path, cached)
    assert_safe_error(caught.value)
    assert caught.value.__context__ is None


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("suffix, content", [
    ("yaml", "VALUE: 5\n"), ("yml", "VALUE: 5\n"),
    ("json", '{"VALUE": 5}'), ("toml", "VALUE = 5\n"), ("env", "VALUE=5\n"),
])
@pytest.mark.parametrize("operation", ["open", "read", "close"])
def test_native_source_io_does_not_escape_with_credentials(
    memory_config_root, isolated_settings_manager, monkeypatch, cached, suffix, content, operation,
):
    path = memory_config_root / f"config.{suffix}"
    path.write_text(content)
    original_open = type(path).open
    native = PermissionError(13, "Permission denied", CREDENTIAL_LOCATION)
    reached = []

    class FailingStream:
        def __init__(self, stream):
            self.stream = stream

        @property
        def name(self):
            return self.stream.name

        def __enter__(self):
            self.stream.__enter__()
            return self

        def read(self, *args, **kwargs):
            if operation == "read":
                reached.append(operation)
                raise native
            return self.stream.read(*args, **kwargs)

        def __exit__(self, *args):
            result = self.stream.__exit__(*args)
            if operation == "close":
                reached.append(operation)
                raise native
            return result

    def fail_open(self, *args, **kwargs):
        if operation == "open":
            reached.append(operation)
            raise native
        return FailingStream(original_open(self, *args, **kwargs))

    monkeypatch.setattr(type(path), "open", fail_open)
    try:
        raise RuntimeError(SENTINELS[-1])
    except RuntimeError:
        with pytest.raises(PermissionError) as caught:
            construct(path, cached)
    assert reached
    assert_safe_error(caught.value)
    assert caught.value.__cause__.errno == 13
    assert caught.value.__cause__.filename is None


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("native_type, expected", [
    (FileNotFoundError, FileNotFoundError), (RuntimeError, OSError),
])
def test_errno_less_open_failure_preserves_missing_category_without_native_text(
    memory_config_root, isolated_settings_manager, monkeypatch, cached, native_type, expected,
):
    path = memory_config_root / "config.yaml"
    path.write_text("VALUE: 5\n")
    native = native_type(CREDENTIAL_LOCATION)
    reached = []

    def fail_open(self, *args, **kwargs):
        reached.append(str(self))
        raise native

    monkeypatch.setattr(type(path), "open", fail_open)
    with pytest.raises(expected) as caught:
        construct(path, cached)
    assert reached
    assert_safe_error(caught.value)
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


@pytest.mark.parametrize("cached", [False, True])
def test_native_option_ownership_failure_is_controlled(
    memory_config_root, isolated_settings_manager, cached,
):
    from upath import UPath

    class CapabilityKey:
        fail = False

        def __hash__(self):
            if self.fail:
                raise PermissionError(13, "Permission denied", CREDENTIAL_LOCATION)
            return 1

    key = CapabilityKey()
    path = UPath(str(memory_config_root / "config.yaml"), custom_options={key: "value"})
    path.write_text("VALUE: 5\n")
    key.fail = True
    with pytest.raises(ValueError) as caught:
        construct(path, cached)
    assert_safe_error(caught.value)
    assert caught.value.__cause__.errno == 13


@pytest.mark.parametrize("cached", [False, True])
def test_cyclic_options_refusal_cannot_retain_ambient_context(
    memory_config_root, isolated_settings_manager, cached,
):
    from upath import UPath

    cycle = {}
    cycle["self"] = cycle
    path = UPath(str(memory_config_root / "config.yaml"), custom_options=cycle)
    try:
        raise RuntimeError(SENTINELS[-1])
    except RuntimeError:
        with pytest.raises(TypeError) as caught:
            construct(path, cached)
    assert_safe_error(caught.value)
    assert caught.value.__context__ is None


def test_cached_ownership_refusal_drops_native_and_ambient_chains(
    memory_config_root, isolated_settings_manager, monkeypatch,
):
    path = memory_config_root / "config.yaml"

    def fail_reconstruction(self, *args, **kwargs):
        raise ValueError(CREDENTIAL_LOCATION)

    monkeypatch.setattr(type(path), "__init__", fail_reconstruction)
    try:
        raise RuntimeError(SENTINELS[-1])
    except RuntimeError:
        with pytest.raises(ValueError) as caught:
            construct(path, True)
    assert_safe_error(caught.value)
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
