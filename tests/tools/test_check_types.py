"""Typing gate must check every platform and propagate any failure."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize("failed_pass", [None, 0, 1, 2, 3])
def test_all_passes_run_and_failures_propagate(monkeypatch, failed_pass):
    path = Path(__file__).resolve().parents[2] / "tools" / "check_types.py"
    spec = importlib.util.spec_from_file_location("check_types", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    calls = []
    def run(command, **kwargs):
        index = len(calls)
        calls.append(command)
        return SimpleNamespace(returncode=int(index == failed_pass))
    monkeypatch.setattr(module.subprocess, "run", run)
    assert module.main() == int(failed_pass is not None)
    assert len(calls) == 4
    assert [c[c.index("--platform") + 1] for c in calls[1:]] == ["linux", "darwin", "win32"]
    assert calls[0][-1] == "src/mountainash_settings"
    assert "--exclude" in calls[0]
    assert all("--strict" not in c and "--install-types" not in c for c in calls)
