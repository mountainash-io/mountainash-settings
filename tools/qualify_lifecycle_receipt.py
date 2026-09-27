"""Installed two-process credential-lifecycle qualification receipt."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ORIGINAL = "m9-original-secret"
_UPDATED = "m9-updated-secret"


def _load_common():
    path = Path(__file__).with_name("_qualification_common.py")
    spec = importlib.util.spec_from_file_location("_qualification_common", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_common = _load_common()
confine_to_temp = _common.confine_to_temp


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_environment() -> dict[str, str]:
    return {
        key: value
        for key, value in os.environ.items()
        if key not in {"PYTHONPATH", "PYTHONHOME"}
    }


def _resolve_in_child(root: Path) -> dict[str, Any]:
    from pydantic import Field

    from mountainash_settings import MountainAshBaseSettings  # type: ignore[import-untyped]
    from mountainash_settings.secrets import (  # type: ignore[import-untyped]
        FilesystemBackend,
    )

    class LifecycleSettings(MountainAshBaseSettings):
        token: str = Field(default="unset")

    with FilesystemBackend(root) as store:
        settings = LifecycleSettings(
            token="secret:lifecycle.token",
            secret_store=store,
        )
    return {
        "pid": os.getpid(),
        "resolved": settings.token,
        "root": str(root.resolve()),
        "timestamp": _timestamp(),
    }


def _run_child(root: Path, result: Path) -> dict[str, Any]:
    environment = _clean_environment()
    environment["M9_LIFECYCLE_ROOT"] = str(root)
    with result.open("w", encoding="utf-8") as result_stream:
        completed = subprocess.run(
            [
                sys.executable,
                "-I",
                str(Path(__file__).resolve()),
                "--child",
            ],
            text=True,
            stdout=result_stream,
            stderr=subprocess.PIPE,
            check=False,
            env=environment,
        )
    if completed.returncode:
        raise RuntimeError(f"Lifecycle child failed with exit {completed.returncode}")
    return json.loads(result.read_text(encoding="utf-8"))


def run_scenario() -> dict[str, Any]:
    """Resolve before and after rotation in two genuine child processes."""
    from mountainash_settings.secrets import (  # type: ignore[import-untyped]
        FilesystemBackend,
    )

    with tempfile.TemporaryDirectory(prefix="settings-m9-scenario-") as work_name:
        work = confine_to_temp(Path(work_name))
        root = work / "store"
        results = work / "results"
        root.mkdir()
        results.mkdir()
        with FilesystemBackend(root) as store:
            store.set("lifecycle", {"token": _ORIGINAL})
        result_a = results / "process-a.json"
        result_b = results / "process-b.json"
        process_a = _run_child(root, result_a)
        original_seen = process_a["resolved"] == _ORIGINAL

        with FilesystemBackend(root) as store:
            store.set("lifecycle", {"token": _UPDATED})
        preserved_a = json.loads(result_a.read_text(encoding="utf-8"))
        process_b = _run_child(root, result_b)
        updated_seen = process_b["resolved"] == _UPDATED

    same_root = (
        process_a["root"] == process_b["root"] == str(root.resolve())
    )
    if not original_seen or not updated_seen:
        raise RuntimeError("Lifecycle processes did not observe the expected generations")
    if preserved_a["resolved"] != _ORIGINAL:
        raise RuntimeError("Process A snapshot changed after rotation")
    if not same_root:
        raise RuntimeError("Lifecycle processes did not use the same store root")
    if process_a["pid"] == process_b["pid"] or os.getpid() in {
        process_a["pid"],
        process_b["pid"],
    }:
        raise RuntimeError("Lifecycle scenario did not use distinct processes")
    return {
        "orchestrator_pid": os.getpid(),
        "started_at": process_a["timestamp"],
        "completed_at": process_b["timestamp"],
        "original_seen_by_a": original_seen,
        "updated_seen_by_b": updated_seen,
        "a_snapshot_preserved": preserved_a["resolved"] == _ORIGINAL,
        "same_store_root": same_root,
        "process_a": {
            "pid": process_a["pid"],
            "timestamp": process_a["timestamp"],
            "result_marker": "original",
        },
        "process_b": {
            "pid": process_b["pid"],
            "timestamp": process_b["timestamp"],
            "result_marker": "updated",
        },
    }


def validate_candidate_receipt(
    receipt: dict[str, Any], revision: str, artifact_root: Path
) -> dict[str, Path]:
    """Bind lifecycle work to a passed, current, hash-verified candidate."""
    if receipt.get("status") != "passed":
        raise ValueError("Lifecycle qualification requires a passed full-suite receipt")
    if receipt.get("source_revision") != revision:
        raise ValueError("Full-suite receipt source revision does not match HEAD")
    artifacts = receipt.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ValueError("Full-suite receipt has no artifacts")
    validated: dict[str, Path] = {}
    artifact_root = artifact_root.resolve()
    for kind in ("wheel", "sdist-wheel"):
        record = artifacts.get(kind)
        if not isinstance(record, dict):
            raise ValueError(f"Full-suite receipt has no {kind} artifact")
        path = Path(str(record.get("path", ""))).resolve()
        if not path.is_relative_to((artifact_root / kind).resolve()):
            raise ValueError(
                f"Full-suite receipt {kind} artifact is outside the receipt artifact root"
            )
        if not path.is_file() or _common.sha256(path) != record.get("sha256"):
            raise ValueError(f"Full-suite receipt {kind} hash does not match")
        validated[kind] = path
    return validated


def _python_identity(python: Path) -> dict[str, Any]:
    source = (
        "import json,platform,sys;"
        "print(json.dumps({'version_info':list(sys.version_info[:2]),"
        "'version':sys.version,'implementation':platform.python_implementation(),"
        "'executable':sys.executable}))"
    )
    return json.loads(_common.run([str(python), "-I", "-c", source]))


def qualify(
    output: Path,
    candidate_receipt: Path,
    pythons: list[Path],
) -> int:
    """Run the lifecycle scenario for both artifacts and Python versions."""
    repository = Path(__file__).resolve().parents[1]
    output = confine_to_temp(output)
    candidate_receipt = confine_to_temp(candidate_receipt)
    output.parent.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "status": "failed",
        "candidate_receipt": str(candidate_receipt.resolve()),
        "scenarios": [],
        "runner_sha256": _common.sha256(Path(__file__)),
        "common_sha256": _common.sha256(Path(_common.__file__)),
    }
    try:
        revision = _common.run(["git", "rev-parse", "HEAD"], cwd=repository).strip()
        report["source_revision"] = revision
        if _common.run(
            ["git", "status", "--porcelain", "--untracked-files=normal"],
            cwd=repository,
        ):
            raise RuntimeError("Candidate proof requires committed, clean source inputs")
        candidate_data = json.loads(candidate_receipt.read_text(encoding="utf-8"))
        artifacts = validate_candidate_receipt(
            candidate_data, revision, candidate_receipt.parent / "artifacts"
        )
        report["artifacts"] = candidate_data["artifacts"]
        identities = [_python_identity(python) for python in pythons]
        versions: list[tuple[int, int]] = [
            tuple(identity["version_info"]) for identity in identities
        ]
        if sorted(versions) != [(3, 12), (3, 13)]:
            raise ValueError("Qualification requires Python 3.12 and 3.13 exactly once")
        ordered = sorted(
            zip(pythons, identities, strict=True),
            key=lambda item: tuple(item[1]["version_info"]),
        )
        report["python_interpreters"] = [identity for _, identity in ordered]
        with tempfile.TemporaryDirectory(prefix="settings-m9-lifecycle-") as work_name:
            work = Path(work_name)
            for base_python, identity in ordered:
                version_label = ".".join(
                    str(part) for part in identity["version_info"]
                )
                for kind, artifact in artifacts.items():
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
                        ]
                    )
                    _common.run(
                        [str(installed_python), "-I", "-m", "pip", "check"]
                    )
                    evidence = json.loads(
                        _common.run(
                            [
                                str(installed_python),
                                "-I",
                                str(Path(__file__).resolve()),
                                "--scenario",
                            ],
                            cwd=work,
                        )
                    )
                    distributions = json.loads(
                        _common.run(
                            [
                                str(installed_python),
                                "-I",
                                "-m",
                                "pip",
                                "list",
                                "--format=json",
                            ]
                        )
                    )
                    report["scenarios"].append(
                        {
                            "kind": kind,
                            "artifact_sha256": _common.sha256(artifact),
                            "requested_python": identity,
                            "evidence": evidence,
                            "resolved_distributions": distributions,
                        }
                    )
            final_revision = _common.run(
                ["git", "rev-parse", "HEAD"], cwd=repository
            ).strip()
            if final_revision != revision:
                raise RuntimeError("Candidate source revision changed during qualification")
            if _common.run(
                ["git", "status", "--porcelain", "--untracked-files=normal"],
                cwd=repository,
            ):
                raise RuntimeError("Candidate source changed during qualification")
            report["status"] = "passed"
    except Exception as error:
        report["failure"] = str(error)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if _ORIGINAL in rendered or _UPDATED in rendered:
        report = {
            "status": "failed",
            "source_revision": report.get("source_revision"),
            "failure": "Lifecycle receipt contained a forbidden value",
        }
        rendered = json.dumps(report, indent=2, sort_keys=True)
    output.write_text(rendered, encoding="utf-8")
    return 0 if report["status"] == "passed" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--output", type=Path)
    mode.add_argument("--child", action="store_true")
    mode.add_argument("--scenario", action="store_true")
    parser.add_argument("--candidate-receipt", type=Path)
    parser.add_argument("--python", type=Path, action="append", default=[])
    args = parser.parse_args()
    if args.child:
        raw_root = os.environ.get("M9_LIFECYCLE_ROOT")
        if raw_root is None:
            parser.error("M9_LIFECYCLE_ROOT is required with --child")
        root = confine_to_temp(Path(raw_root))
        print(json.dumps(_resolve_in_child(root), sort_keys=True))
        return 0
    if args.scenario:
        print(json.dumps(run_scenario(), sort_keys=True))
        return 0
    if args.candidate_receipt is None:
        parser.error("--candidate-receipt is required with --output")
    return qualify(args.output, args.candidate_receipt, args.python)


if __name__ == "__main__":
    raise SystemExit(main())
