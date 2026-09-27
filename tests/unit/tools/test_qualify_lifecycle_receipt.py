from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


def _lifecycle_module():
    name = "qualify_lifecycle_receipt_under_test"
    path = Path(__file__).resolve().parents[3] / "tools" / "qualify_lifecycle_receipt.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_lifecycle_scenario_uses_two_processes_and_emits_value_free_evidence(
    tmp_path: Path,
):
    lifecycle = _lifecycle_module()

    evidence = lifecycle.run_scenario()

    assert evidence["original_seen_by_a"] is True
    assert evidence["updated_seen_by_b"] is True
    assert evidence["a_snapshot_preserved"] is True
    assert evidence["same_store_root"] is True
    assert evidence["process_a"]["pid"] != evidence["process_b"]["pid"]
    assert evidence["process_a"]["pid"] != evidence["orchestrator_pid"]
    assert evidence["process_b"]["pid"] != evidence["orchestrator_pid"]
    rendered = json.dumps(evidence, sort_keys=True)
    assert "m9-original-secret" not in rendered
    assert "m9-updated-secret" not in rendered


def test_candidate_receipt_must_be_passed_current_and_hash_bound(tmp_path: Path):
    lifecycle = _lifecycle_module()
    artifact_root = tmp_path / "artifacts"
    wheel = artifact_root / "wheel" / "candidate.whl"
    rebuilt = artifact_root / "sdist-wheel" / "rebuilt.whl"
    wheel.parent.mkdir(parents=True)
    rebuilt.parent.mkdir(parents=True)
    wheel.write_bytes(b"wheel")
    rebuilt.write_bytes(b"rebuilt")
    receipt = {
        "status": "passed",
        "source_revision": "abc123",
        "artifacts": {
            "wheel": {
                "path": str(wheel),
                "sha256": "ba59926159d2aa256eb8739b8da7e2b574b960e1202c6d624cbe981cef996c91",
            },
            "sdist-wheel": {
                "path": str(rebuilt),
                "sha256": "9ae832844d70dd5a06b8c70f3f4f68bbe1c907b116d378c9654b217d4a7b6b4c",
            },
        },
    }

    assert lifecycle.validate_candidate_receipt(
        receipt, "abc123", artifact_root
    ) == {
        "wheel": wheel,
        "sdist-wheel": rebuilt,
    }

    receipt["status"] = "failed"
    with pytest.raises(ValueError, match="passed full-suite receipt"):
        lifecycle.validate_candidate_receipt(receipt, "abc123", artifact_root)


def test_candidate_receipt_rejects_artifact_outside_receipt_artifact_root(
    tmp_path: Path,
):
    lifecycle = _lifecycle_module()
    outside = tmp_path / "outside.whl"
    outside.write_bytes(b"wheel")
    receipt = {
        "status": "passed",
        "source_revision": "abc123",
        "artifacts": {
            "wheel": {
                "path": str(outside),
                "sha256": "ba59926159d2aa256eb8739b8da7e2b574b960e1202c6d624cbe981cef996c91",
            },
            "sdist-wheel": {
                "path": str(outside),
                "sha256": "ba59926159d2aa256eb8739b8da7e2b574b960e1202c6d624cbe981cef996c91",
            },
        },
    }

    with pytest.raises(ValueError, match="outside the receipt artifact root"):
        lifecycle.validate_candidate_receipt(
            receipt, "abc123", tmp_path / "artifacts"
        )


def test_receipt_paths_are_confined_to_os_temporary_directory(tmp_path: Path):
    lifecycle = _lifecycle_module()

    assert lifecycle.confine_to_temp(tmp_path / "receipt.json") == (
        tmp_path / "receipt.json"
    ).resolve()
    with pytest.raises(ValueError, match="OS temporary directory"):
        lifecycle.confine_to_temp(Path.home() / "m9-outside-temp-receipt.json")


def test_lifecycle_qualify_writes_failed_receipt_for_preflight_failure(
    tmp_path: Path,
):
    lifecycle = _lifecycle_module()
    output = tmp_path / "lifecycle.json"

    assert lifecycle.qualify(output, tmp_path / "missing.json", []) == 1

    receipt = json.loads(output.read_text(encoding="utf-8"))
    assert receipt["status"] == "failed"
    assert receipt["failure"]
