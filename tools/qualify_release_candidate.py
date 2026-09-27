"""Non-publishing full installed release-candidate qualification."""

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


def _load_common():
    path = Path(__file__).with_name("_qualification_common.py")
    spec = importlib.util.spec_from_file_location("_qualification_common", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_common = _load_common()

_WINDOWS_MARKER_CLOSE = _common.AcceptedSkip(
    name="test_postcommit_marker_close_failure_reports_commit_without_retry",
    reason_contains="windows-marker-close-reason-classification.md",
)
_TEST_REQUIREMENTS = ("pytest==8.3.5", "pytest-check==2.5.3")


def validate_python_identities(identities: list[dict[str, object]]) -> None:
    """Require exactly one Python 3.12 and one Python 3.13 interpreter."""
    versions = [tuple(identity["version_info"]) for identity in identities]
    if sorted(versions) != [(3, 12), (3, 13)]:
        raise ValueError("Qualification requires Python 3.12 and 3.13 exactly once")


def _python_identity(python: Path) -> dict[str, object]:
    source = (
        "import json,platform,sys;"
        "print(json.dumps({'version_info':list(sys.version_info[:2]),"
        "'version':sys.version,'implementation':platform.python_implementation(),"
        "'executable':sys.executable}))"
    )
    return json.loads(_common.run([str(python), "-I", "-c", source]))


def _clean_environment() -> dict[str, str]:
    return {
        key: value
        for key, value in os.environ.items()
        if key not in {"PYTHONPATH", "PYTHONHOME"}
    }


def _save_artifacts(candidate, output: Path) -> dict[str, dict[str, str]]:
    saved: dict[str, dict[str, str]] = {}
    for kind, source in (
        ("wheel", candidate.wheel),
        ("sdist", candidate.sdist),
        ("sdist-wheel", candidate.rebuilt_wheel),
    ):
        destination = output.parent / "artifacts" / kind
        destination.mkdir(parents=True, exist_ok=True)
        path = destination / source.name
        shutil.copy2(source, path)
        saved[kind] = {"path": str(path), "sha256": _common.sha256(path)}
    return saved


def _run_installed_suite(
    *,
    repository: Path,
    work: Path,
    output: Path,
    copied_tests: Path,
    base_python: Path,
    python_identity: dict[str, object],
    kind: str,
    artifact: Path,
) -> dict[str, object]:
    version_label = ".".join(str(part) for part in python_identity["version_info"])
    environment = work / f"installed-{version_label}-{kind}"
    installed_python = _common.create_environment(
        environment, base_python=base_python
    )
    _common.run(
        [
            str(installed_python),
            "-I",
            "-m",
            "pip",
            "install",
            str(artifact),
            *_TEST_REQUIREMENTS,
        ]
    )
    _common.run([str(installed_python), "-I", "-m", "pip", "check"])
    destination = output.parent / "results" / f"python-{version_label}" / kind
    destination.mkdir(parents=True, exist_ok=True)
    junit = destination / "junit.xml"
    command = [
        str(installed_python),
        "-I",
        "-m",
        "pytest",
        "--import-mode=importlib",
        f"--confcutdir={copied_tests}",
        f"--basetemp={work / ('pytest-' + version_label + '-' + kind)}",
        f"--junitxml={junit}",
        "-q",
        str(copied_tests),
    ]
    completed = subprocess.run(
        command,
        cwd=work,
        text=True,
        capture_output=True,
        check=False,
        env=_clean_environment(),
    )
    (destination / "pytest.txt").write_text(
        completed.stdout + completed.stderr, encoding="utf-8"
    )
    accepted = (_WINDOWS_MARKER_CLOSE,) if sys.platform == "win32" else ()
    tests = _common.inspect_junit(junit, accepted_skips=accepted)
    probe = json.loads(
        _common.run(
            [
                str(installed_python),
                "-I",
                str(Path(__file__).resolve()),
                "--probe",
                str(work / f"probe-{version_label}-{kind}"),
            ],
            cwd=work,
        )
    )
    distributions = json.loads(
        _common.run(
            [str(installed_python), "-I", "-m", "pip", "list", "--format=json"]
        )
    )
    assert completed.returncode == 0
    assert not tests["failures"] and not tests["required_skips"]
    return {
        "kind": kind,
        "artifact_sha256": _common.sha256(artifact),
        "requested_python": python_identity,
        "tests": tests,
        "probe": probe,
        "resolved_distributions": distributions,
    }


def qualify(output: Path, pythons: list[Path]) -> int:
    """Build once and test both artifact forms with both required Pythons."""
    repository = Path(__file__).resolve().parents[1]
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    revision = _common.run(["git", "rev-parse", "HEAD"], cwd=repository).strip()
    dirty = _common.run(
        ["git", "status", "--porcelain", "--untracked-files=normal"],
        cwd=repository,
    )
    if dirty:
        raise RuntimeError("Candidate proof requires committed, clean source inputs")
    identities = [_python_identity(python) for python in pythons]
    validate_python_identities(identities)
    ordered = sorted(
        zip(pythons, identities, strict=True),
        key=lambda item: tuple(item[1]["version_info"]),
    )
    report: dict[str, object] = {
        "status": "failed",
        "source_revision": revision,
        "python_interpreters": [identity for _, identity in ordered],
        "installed": [],
        "runner_sha256": _common.sha256(Path(__file__)),
        "common_sha256": _common.sha256(Path(_common.__file__)),
        "artifacts": {},
    }
    try:
        with tempfile.TemporaryDirectory(prefix="settings-m9-installed-") as work_name:
            work = Path(work_name)
            candidate = _common.build_candidate(
                repository, work, base_python=ordered[0][0]
            )
            report["build_distributions"] = candidate.build_distributions
            report["artifacts"] = _save_artifacts(candidate, output)
            copied_tests = work / "tests"
            shutil.copytree(repository / "tests", copied_tests)
            shutil.copytree(repository / "tools", work / "tools")
            report["test_inputs"] = {
                str(path.relative_to(copied_tests)): _common.sha256(path)
                for path in copied_tests.rglob("*.py")
            }
            artifacts = (
                ("wheel", candidate.wheel),
                ("sdist-wheel", candidate.rebuilt_wheel),
            )
            for base_python, identity in ordered:
                for kind, artifact in artifacts:
                    report["installed"].append(
                        _run_installed_suite(
                            repository=repository,
                            work=work,
                            output=output,
                            copied_tests=copied_tests,
                            base_python=base_python,
                            python_identity=identity,
                            kind=kind,
                            artifact=artifact,
                        )
                    )
            assert (
                _common.run(["git", "rev-parse", "HEAD"], cwd=repository).strip()
                == revision
            )
            assert not _common.run(
                ["git", "status", "--porcelain", "--untracked-files=normal"],
                cwd=repository,
            ), "Candidate source changed during qualification"
            report["status"] = "passed"
    except Exception as error:
        report["failure"] = str(error)
    finally:
        output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return 0 if report["status"] == "passed" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--output", type=Path)
    mode.add_argument("--probe", type=Path)
    parser.add_argument("--python", type=Path, action="append", default=[])
    args = parser.parse_args()
    if args.probe is not None:
        print(json.dumps(_common.probe(args.probe, check_api=True), sort_keys=True))
        return 0
    return qualify(args.output, args.python)


if __name__ == "__main__":
    raise SystemExit(main())
