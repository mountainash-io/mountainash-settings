"""W8 safe-display helper: shared rendering table and safe list."""
from __future__ import annotations

from pathlib import PurePosixPath
import traceback

import pytest

from mountainash_settings._safe_errors import raise_safe, safe_cause, safe_detail, safe_location

# Shared across packages (W8 spec section 5.1): keep identical to the sibling copies.
RENDERING = [
    ("https://SENTU:SENTP@h:8443/a/x.csv?sig=SENTQ#SENTF", "https://h:8443/a/x.csv"),
    ("https://SENTU:pa@SENTP@host/x.csv", "https://host/x.csv"),
    ("https://SENTU:SENTP@[::1]:8443/d/x.csv", "https://[::1]:8443/d/x.csv"),
    ("https://host/a@b/x.csv", "https://host/a@b/x.csv"),
    ("https://host/x.csv#access_token=SENTF", "https://host/x.csv"),
    ("https://host/x.csv?SENTQ", "https://host/x.csv"),
    ("https://host/x.csv#f?tok=SENTQ", "https://host/x.csv"),
    ("https://h#SENTF@x/y", "https://h"),
    ("https://h?SENTQ@x/y", "https://h"),
    ("https://host", "https://host"),
    ("s3://bucket/x.csv", "s3://bucket/x.csv"),
    ("file:///tmp/x.csv", "file:///tmp/x.csv"),
    ("memory:///dir/x.yaml", "memory:///dir/x.yaml"),
    ("HTTPS://SENTU:SENTP@host/x.csv", "HTTPS://host/x.csv"),
    ("postgresql+psycopg://SENTU:SENTP@db/name", "postgresql+psycopg://db/name"),
    ("//SENTU:SENTP@host/x.csv", "//host/x.csv"),
    (" \thttps://SENTU:SENTP@host/x.csv", "https://host/x.csv"),
    ("https://SENTU:SENTP@ho\nst/x.csv", "https://host/x.csv"),
    ("https://SENTU:SENTP@ho\rst/x.csv", "https://host/x.csv"),
    ("ht\ttps://SENTU:SENTP@host/x.csv", "https://host/x.csv"),
    ("\x00https://SENTU:SENTP@host/x.csv", "https://host/x.csv"),
    ("\x1fhttps://SENTU:SENTP@host/x.csv", "https://host/x.csv"),
    ("https:/SENTU:SENTP@host/x.csv", "***"),
    ("s3:SENTU:SENTP@bucket/x.csv", "***"),
    ("SENTU:SENTP@host/x.csv", "***"),
    ("a:SENTP@host/x.csv", "***"),
    ("/data/x.csv", "/data/x.csv"),
    ("data/x.csv", "data/x.csv"),
    ("/srv/team@corp/x.csv", "/srv/team@corp/x.csv"),
    ("relative/a:b@c/x.csv", "relative/a:b@c/x.csv"),
    ("C:/d/x.csv", "C:/d/x.csv"),
    ("C:\\d\\x.csv", "C:\\d\\x.csv"),
]


def surfaces(error: BaseException) -> str:
    seen: set[int] = set()
    pending = [error]
    parts: list[str] = []
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        parts += [str(current), repr(current), repr(current.args), repr(vars(current)),
                  repr(getattr(current, "filename", None)), repr(getattr(current, "filename2", None)),
                  repr(getattr(current, "__notes__", None)),
                  "".join(traceback.format_exception(current))]
        pending += [e for e in (current.__cause__, current.__context__) if e is not None]
    return "\n".join(parts)


@pytest.mark.parametrize(("location", "shown"), RENDERING)
def test_safe_location_rendering(location, shown):
    assert safe_location(location) == shown
    assert "SENT" not in safe_location(location)


def test_safe_location_accepts_pathlike():
    assert safe_location(PurePosixPath("/data/x.csv")) == "/data/x.csv"


def test_safe_detail_keeps_errno_and_drops_filename():
    native = FileNotFoundError(2, "No such file or directory", "/secret/SENTINEL.key")
    assert safe_detail(native) == "[Errno 2] No such file or directory"


@pytest.mark.parametrize(
    "native", [ValueError("SENTINEL"), KeyError("SENTINEL"), OSError("SENTINEL no errno"),
               FileNotFoundError("SENTINEL"), RuntimeError("SENTINEL")],
)
def test_errno_less_native_shows_class_only_and_drops_cause(native):
    assert safe_detail(native) == type(native).__name__
    assert safe_cause(native) is None
    assert safe_cause(None) is None


def test_raise_safe_keeps_only_fresh_errno_cause_and_clears_context():
    native = ConnectionRefusedError(111, "Connection refused", "SENTINEL-file", None, "SENTINEL-file2")
    native.add_note("SENTINEL-note")
    native.attribute = "SENTINEL-attr"
    with pytest.raises(RuntimeError) as info:
        try:
            raise ValueError("SENTINEL-ambient")
        except ValueError:
            raise_safe(RuntimeError("x: failed"), native)
    error = info.value
    assert error.__context__ is None
    assert isinstance(error.__cause__, ConnectionRefusedError)
    assert error.__cause__ is not native
    assert error.__cause__.filename is None and error.__cause__.filename2 is None
    assert "SENTINEL" not in surfaces(error)


def test_raise_safe_without_native_has_no_cause_or_ambient_context():
    with pytest.raises(ValueError) as info:
        try:
            raise KeyError("SENTINEL-ambient")
        except KeyError:
            raise_safe(ValueError("fixed"))
    assert info.value.__cause__ is None
    assert info.value.__context__ is None
    assert "SENTINEL" not in surfaces(info.value)


class _StrictOSError(OSError):
    def __init__(self, only_one):
        super().__init__(only_one)


def test_cause_reconstruction_falls_back_to_plain_oserror():
    native = _StrictOSError.__new__(_StrictOSError)
    OSError.__init__(native, 5, "Input/output error", "SENTINEL-file")
    cause = safe_cause(native)
    assert type(cause) is OSError
    assert (cause.errno, cause.strerror, cause.filename) == (5, "Input/output error", None)


@pytest.mark.parametrize(
    "replacement", ["SENTINEL-invalid", None, ValueError("SENTINEL-invalid"), OSError],
    ids=["non-exception", "none", "non-os-exception", "exception-class"],
)
def test_raise_safe_falls_back_when_constructor_returns_non_os_instance(replacement):
    class UnusualOSError(OSError):
        def __new__(cls, *args):
            if len(args) == 2:
                return replacement
            return super().__new__(cls, *args)

    native = UnusualOSError(5, "Input/output error", "SENTINEL-file")
    outer = RuntimeError("controlled failure")
    try:
        raise native
    except OSError:
        with pytest.raises(RuntimeError) as info:
            raise_safe(outer, native)

    assert info.value is outer
    cause = outer.__cause__
    assert type(cause) is OSError
    assert (cause.errno, cause.strerror, cause.filename) == (5, "Input/output error", None)
    assert outer.__context__ is None
    assert "SENTINEL" not in surfaces(outer)
