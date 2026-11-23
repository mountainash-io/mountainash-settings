"""What a configuration error may show of a location or a native failure (W8 safe display).

Errors show only parts known to be safe, built up from the input rather than
masked down from it. Stdlib only; there is no trust list for package errors.
"""
from __future__ import annotations

import logging
import os
import re
import typing as t

REDACTED = "***"

# An RFC 3986 scheme at the start of the string; anchored, so matching is linear.
_SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.\-]*:")
_C0_OR_SPACE = "".join(chr(code) for code in range(0x21))


def _first(text: str, characters: str, start: int, end: int) -> int:
    """Index of the first of *characters* in text[start:end], or *end*."""
    found = end
    for character in characters:
        index = text.find(character, start, found)
        if index != -1:
            found = index
    return found


def safe_location(location: str | os.PathLike[str]) -> str:
    """Return the part of *location* an error may show.

    ``scheme://...`` and ``//...``: scheme, host, port and path; userinfo (to the
    last ``@`` of the authority), query and fragment are left out. Any other
    string that starts with a scheme: ``***``. Anything else is a local path
    (including ``C:/`` and ``C:\\`` drives) and is returned unchanged.
    """
    text = os.fspath(location).lstrip(_C0_OR_SPACE)
    for character in "\t\r\n":
        text = text.replace(character, "")
    scheme = _SCHEME.match(text)
    if text.startswith("//"):
        authority_start = 2
    elif scheme is None:
        return text
    elif text.startswith("//", scheme.end()):
        authority_start = scheme.end() + 2
    elif scheme.end() == 2 and text[2:3] in ("/", "\\"):
        return text  # Windows drive letter
    else:
        return REDACTED
    authority_end = _first(text, "/?#", authority_start, len(text))
    at = text.rfind("@", authority_start, authority_end)
    host_start = authority_start if at == -1 else at + 1
    path_end = _first(text, "?#", authority_end, len(text))
    return text[:authority_start] + text[host_start:authority_end] + text[authority_end:path_end]


def safe_detail(native: BaseException) -> str:
    """Native exception text an error may show.

    ``OSError`` with an errno: ``[Errno N] strerror``, never a filename.
    Anything else: the class name.
    """
    if isinstance(native, OSError) and native.errno is not None:
        return f"[Errno {native.errno}] {native.strerror}"
    return type(native).__name__


def safe_cause(native: BaseException | None) -> OSError | None:
    """The exception an error may chain as ``__cause__`` in place of *native*.

    ``OSError`` with an errno: a fresh exception carrying only ``errno`` and
    ``strerror``. Preserve its type if construction returns an ``OSError``;
    otherwise fall back to plain ``OSError``. Other native failures: ``None``.
    """
    if not isinstance(native, OSError) or native.errno is None:
        return None
    try:
        cause = type(native)(native.errno, native.strerror)
        if isinstance(cause, OSError):
            return cause
    except Exception:  # A subclass constructor may reject (errno, strerror).
        pass
    return OSError(native.errno, native.strerror)


def raise_safe(error: BaseException, native: BaseException | None = None) -> t.NoReturn:
    """Raise *error* with only :func:`safe_cause` of *native* reachable.

    ``__context__`` is always cleared: ``raise ... from`` alone keeps the
    active exception there.
    """
    try:
        raise error from safe_cause(native)
    finally:
        error.__context__ = None


_LOG_EMITTERS = ("fsspec", "fsspec.http", "fsspec.caching", "fsspec.asyn")


class _ConfigLogFilter(logging.Filter):
    """Replace raw diagnostic payloads of the filesystem emitters with a controlled category.

    The record is kept (level, handlers and other attributes untouched); its message,
    arguments, exception and stack payloads are never evaluated.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = f"Filesystem diagnostic ({record.name}:{record.funcName})"
        record.message = record.msg
        record.args = ()
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        return True


_CONFIG_LOG_FILTER = _ConfigLogFilter()


def install_config_log_filters() -> None:
    """Attach the package-owned filter to the four authorized fsspec emitters (idempotent)."""
    for name in _LOG_EMITTERS:
        logging.getLogger(name).addFilter(_CONFIG_LOG_FILTER)  # no-op if already attached
