"""One storage key grammar and the existing deterministic identifier encoding."""
from __future__ import annotations

import base64
import hashlib
import re

from .errors import _raise_clean

_SEGMENT = re.compile(r"[a-z0-9_]+")
__all__ = ["to_key_segment"]


def _segments(key: str) -> list[str]:
    if type(key) is not str:
        _raise_clean(ValueError("Invalid local record key"))
    parts = key.split(".")
    if not all(_SEGMENT.fullmatch(part) for part in parts):
        _raise_clean(ValueError("Invalid local record key"))
    return parts


def _layout(key: str) -> tuple[str | None, str]:
    parts = _segments(key)
    if len(parts) == 1:
        return None, parts[0]
    return parts[0], "-".join(parts[1:])


def to_key_segment(raw: str) -> str:
    if type(raw) is not str:
        _raise_clean(ValueError("Invalid local record key"))
    if _SEGMENT.fullmatch(raw) and not raw.startswith("h_"):
        return raw
    try:
        payload = raw.encode("utf-8")
    except UnicodeError:
        _raise_clean(ValueError("Invalid local record key"))
    digest = hashlib.sha256(payload).digest()
    return "h_" + base64.b32encode(digest).decode("ascii").rstrip("=").lower()
