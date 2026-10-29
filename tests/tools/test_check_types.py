"""Typing runners must retain their targets, flags and every failure."""
import importlib.util
from pathlib import Path
import re
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize("script", ["check_types.py", "check_test_types.py"])
@pytest.mark.parametrize("failed_pass", [None, 0, 1, 2, 3])
@pytest.mark.parametrize("extra_args", [[], ["--check-untyped-defs"]])
def test_all_passes_run_and_failures_propagate(
    monkeypatch: pytest.MonkeyPatch,
    script: str,
    failed_pass: int | None,
    extra_args: list[str],
) -> None:
    root = Path(__file__).resolve().parents[2]
    path = root / "tools" / script
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.sys, "argv", [str(path), *extra_args])
    calls: list[list[str]] = []

    def run(command: list[str], *, cwd: Path, check: bool) -> SimpleNamespace:
        assert cwd == root
        assert check is False
        index = len(calls)
        calls.append(command)
        return SimpleNamespace(returncode=int(index == failed_pass))
    monkeypatch.setattr(module.subprocess, "run", run)
    assert module.main() == int(failed_pass is not None)
    assert len(calls) == 4
    for command in calls:
        assert command[:3] == [module.sys.executable, "-m", "mypy"]
        assert command.count("--check-untyped-defs") == len(extra_args)
        assert "--strict" not in command and "--install-types" not in command
    targets = [c[:-len(extra_args)] if extra_args else c for c in calls]
    assert [c[c.index("--platform") + 1] for c in calls[1:]] == ["linux", "darwin", "win32"]
    if script == "check_types.py":
        assert targets[0][-1] == "src/mountainash_settings"
        assert "--exclude" in targets[0]
    else:
        assert targets[0][-1] == "tests"
        assert targets[0][targets[0].index("--platform") + 1] == "linux"
        native = "tests/secrets/native/"
        posix = [native + "test_posix.py", native + "posix_helpers.py"]
        windows = [native + "test_windows.py", native + "_windows_fixtures.py"]
        assert targets[1][-2:] == targets[2][-2:] == posix
        assert targets[3][-2:] == windows
        exclusion = targets[0][targets[0].index("--exclude") + 1]
        assert all(re.search(exclusion, name) for name in posix + windows)
        assert not re.search(exclusion, native + "test_filesystem.py")
        assert not re.search(exclusion, "tests/settings/test_base_settings.py")
