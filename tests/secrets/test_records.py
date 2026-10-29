from __future__ import annotations

import subprocess
import sys

import pytest

from mountainash_settings.secrets.records import _own_record


def test_record_ownership_accepts_shared_graph_but_rejects_cycles():
    shared = [{"token": "dummy"}]
    original = {"a": shared, "b": shared}
    owned = _own_record(original)
    shared[0]["token"] = "changed"
    assert owned == {"a": [{"token": "dummy"}], "b": [{"token": "dummy"}]}
    cycle = {}
    cycle["self"] = cycle
    with pytest.raises(ValueError) as caught:
        _own_record(cycle)
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


@pytest.mark.parametrize("value", [
    [], {"n": float("nan")}, {"n": float("inf")},
    {1: "x"}, {"x": (1, 2)}, {"x": b"dummy"},
])
def test_rejects_distinct_non_json_categories(value):
    with pytest.raises(ValueError):
        _own_record(value)


def test_rejects_rich_values_without_running_their_hooks():
    class HostileType(type):
        def __eq__(cls, other):
            raise AssertionError("type equality must not run")

    class Hostile(metaclass=HostileType):
        def __repr__(self):
            raise AssertionError("repr must not run")

        def __deepcopy__(self, memo):
            raise AssertionError("deepcopy must not run")

    with pytest.raises(ValueError):
        _own_record({"token": Hostile()})


def test_empty_mapping_and_deep_builtin_graph_are_records():
    assert _own_record({}) == {}
    graph = {"leaf": True}
    for _ in range(1500):
        graph = {"next": graph}
    result = _own_record(graph)
    for _ in range(1500):
        result = result["next"]
    assert result == {"leaf": True}


def test_generic_import_does_not_require_fcntl():
    script = """
import importlib.abc
import sys
class DenyPosix(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "fcntl":
            raise ModuleNotFoundError("POSIX native dependency unavailable")
sys.meta_path.insert(0, DenyPosix())
from mountainash_settings import MountainAshBaseSettings
from mountainash_settings.secrets import SecretReader, SecretRecord
class Settings(MountainAshBaseSettings):
    value: int = 7
assert Settings().value == 7
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
