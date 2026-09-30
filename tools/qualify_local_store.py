"""Non-publishing installed local-store qualification; not release authority."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def _load_common():
    path = Path(__file__).with_name("_qualification_common.py")
    spec = importlib.util.spec_from_file_location("_qualification_common", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_common = _load_common()
build_candidate = _common.build_candidate
create_environment = _common.create_environment
filesystem_type = _common.filesystem_type
inspect_junit = _common.inspect_junit
native_dependencies = _common.native_dependencies
probe = _common.probe
run = _common.run
sha256 = _common.sha256


def qualify(output: Path) -> int:
    repository = Path(__file__).resolve().parents[1]
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    revision = run(["git", "rev-parse", "HEAD"], cwd=repository).strip()
    dirty = run(
        ["git", "status", "--porcelain", "--untracked-files=normal"], cwd=repository
    )
    if dirty:
        raise RuntimeError("Candidate proof requires committed, clean source inputs")
    report: dict[str, Any] = {
        "status": "failed", "source_revision": revision, "installed": [],
        "runner_sha256": sha256(Path(__file__)), "artifacts": {},
    }
    try:
        with tempfile.TemporaryDirectory(prefix="settings-m3-installed-") as work_name:
            work = Path(work_name)
            candidate = build_candidate(repository, work)
            copied_tests = work / "tests"
            shutil.copytree(repository / "tests/secrets/native", copied_tests)
            shutil.copy2(repository / "tests/secrets/conftest.py", copied_tests / "conftest.py")
            portable_names = ("records", "keys", "memory", "namespaced")
            for name in portable_names:
                shutil.copy2(
                    repository / f"tests/secrets/test_{name}.py",
                    copied_tests / f"test_{name}.py",
                )
            test_hashes = {
                str(path.relative_to(copied_tests)): sha256(path)
                for path in copied_tests.rglob("*.py")
            }
            report["test_inputs"] = test_hashes
            report["build_distributions"] = candidate.build_distributions
            for kind, artifact in (
                ("wheel", candidate.wheel),
                ("sdist-wheel", candidate.rebuilt_wheel),
            ):
                destination = output.parent / kind
                destination.mkdir(exist_ok=True)
                saved_artifact = destination / artifact.name
                shutil.copy2(artifact, saved_artifact)
                if kind == "wheel":
                    shutil.copy2(
                        candidate.sdist, destination / candidate.sdist.name
                    )
                    report["artifacts"]["sdist"] = {
                        "path": str(destination / candidate.sdist.name),
                        "sha256": sha256(candidate.sdist),
                    }
                report["artifacts"][kind] = {
                    "path": str(saved_artifact), "sha256": sha256(saved_artifact),
                }
                environment = work / f"installed-{kind}"
                installed_python = str(create_environment(environment))
                run([
                    installed_python, "-I", "-m", "pip", "install",
                    str(saved_artifact), "pytest",
                ])
                run([installed_python, "-I", "-m", "pip", "check"])
                native_test = (
                    "test_windows.py" if sys.platform == "win32" else "test_posix.py"
                )
                junit = destination / "junit.xml"
                selected = [native_test, "test_filesystem.py"] + [
                    f"test_{name}.py" for name in portable_names
                ]
                command = [
                    installed_python, "-I", "-m", "pytest",
                    "--import-mode=importlib", f"--confcutdir={copied_tests}",
                    f"--basetemp={work / ('pytest-' + kind)}",
                    f"--junitxml={junit}", "-q",
                    *[str(copied_tests / name) for name in selected],
                ]
                # Persist pytest output even on failure; do not lose diagnostic receipts.
                result = subprocess.run(
                    command, cwd=work, text=True, capture_output=True, check=False,
                    env={key: value for key, value in os.environ.items()
                         if key not in {"PYTHONPATH", "PYTHONHOME"}},
                )
                (destination / "pytest.txt").write_text(
                    result.stdout + result.stderr, encoding="utf-8"
                )
                tests = inspect_junit(junit)
                evidence = json.loads(run([
                    installed_python, "-I", str(Path(__file__).resolve()),
                    "--probe", str(work / f"probe-{kind}"),
                ], cwd=work))
                report["installed"].append({
                    "kind": kind, "artifact_sha256": sha256(saved_artifact),
                    "tests": tests, "probe": evidence,
                })
                assert result.returncode == 0
                assert not tests["failures"] and not tests["required_skips"]
            assert run(["git", "rev-parse", "HEAD"], cwd=repository).strip() == revision
            assert not run(
                ["git", "status", "--porcelain", "--untracked-files=normal"], cwd=repository
            ), "Candidate source changed during qualification"
            report["status"] = "passed"
    except Exception as exc:
        report["failure"] = str(exc)
    finally:
        output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return 0 if report["status"] == "passed" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--output", type=Path)
    mode.add_argument("--probe", type=Path)
    args = parser.parse_args()
    if args.probe is not None:
        print(json.dumps(probe(args.probe), sort_keys=True))
        return 0
    return qualify(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
