"""Strict local-record values; no user hooks, coercion or recursive Python walk."""
from __future__ import annotations

import math
import typing as t

from .errors import _raise_clean

JSONValue: t.TypeAlias = t.Union[
    None, bool, int, float, str, list["JSONValue"], dict[str, "JSONValue"]
]
SecretRecord: t.TypeAlias = dict[str, JSONValue]

__all__ = ["JSONValue", "SecretRecord"]


def _own_record(value: object) -> SecretRecord:
    if type(value) is not dict:  # noqa: E721 -- exact-type, reject dict subclasses
        _raise_clean(ValueError("Invalid local record"))
    result: dict[str, t.Any] = {}
    memo: dict[int, t.Any] = {id(value): result}
    active = {id(value)}
    stack: list[tuple[t.Any, t.Any, t.Iterator[tuple[t.Any, t.Any]]]] = [
        (value, result, iter(t.cast(dict[str, t.Any], value).items()))
    ]
    while stack:
        source, destination, items = stack[-1]
        try:
            key, child = next(items)
        except StopIteration:
            active.remove(id(source))
            stack.pop()
            continue
        if type(source) is dict and type(key) is not str:  # noqa: E721 -- exact-type
            _raise_clean(ValueError("Invalid local record"))
        kind = type(child)
        if kind is dict or kind is list:
            identity = id(child)
            if identity in active:
                _raise_clean(ValueError("Invalid local record"))
            if identity in memo:
                owned = memo[identity]
            else:
                owned = {} if kind is dict else []
                memo[identity] = owned
                active.add(identity)
                child_items = (
                    iter(child.items()) if kind is dict else iter(enumerate(child))
                )
                stack.append((child, owned, child_items))
        elif child is None or kind is str or kind is int or kind is bool:
            owned = child
        elif kind is float and math.isfinite(child):
            owned = child
        else:
            _raise_clean(ValueError("Invalid local record"))
        if type(destination) is dict:  # noqa: E721 -- exact-type
            destination[key] = owned
        else:
            destination.append(owned)
    return t.cast(SecretRecord, result)
