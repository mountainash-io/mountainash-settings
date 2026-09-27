from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


def _qualifier_module():
    name = "qualify_release_candidate_under_test"
    path = Path(__file__).resolve().parents[3] / "tools" / "qualify_release_candidate.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_validate_python_identities_requires_312_and_313_once_each():
    qualifier = _qualifier_module()

    qualifier.validate_python_identities(
        [
            {"version_info": [3, 12], "executable": "/python312"},
            {"version_info": [3, 13], "executable": "/python313"},
        ]
    )

    with pytest.raises(ValueError, match="Python 3.12 and 3.13"):
        qualifier.validate_python_identities(
            [
                {"version_info": [3, 12], "executable": "/python312-a"},
                {"version_info": [3, 12], "executable": "/python312-b"},
            ]
        )


def test_installed_probe_rejects_stale_version(monkeypatch):
    import mountainash_settings as version_module
    qualifier = _qualifier_module()
    monkeypatch.setattr(version_module, "__version__", "26.5.0")
    with pytest.raises(AssertionError):
        qualifier._common.installed_api_evidence()


def test_installed_probe_rejects_profile_shim(monkeypatch):
    import mountainash_settings.profiles as profiles
    qualifier = _qualifier_module()
    monkeypatch.setattr(profiles, "DescriptorProfile", profiles.Profile, raising=False)
    with pytest.raises(AssertionError):
        qualifier._common.installed_api_evidence()


def test_validate_python_identities_rejects_additional_versions():
    qualifier = _qualifier_module()

    with pytest.raises(ValueError, match="Python 3.12 and 3.13"):
        qualifier.validate_python_identities(
            [
                {"version_info": [3, 12], "executable": "/python312"},
                {"version_info": [3, 13], "executable": "/python313"},
                {"version_info": [3, 14], "executable": "/python314"},
            ]
        )


def test_qualify_writes_failed_receipt_for_preflight_failure(tmp_path: Path):
    qualifier = _qualifier_module()
    output = tmp_path / "full-suite.json"

    assert qualifier.qualify(output, []) == 1

    receipt = json.loads(output.read_text(encoding="utf-8"))
    assert receipt["status"] == "failed"
    assert receipt["failure"]


def test_candidate_inspection_rejects_the_retired_windows_xfail(tmp_path: Path):
    qualifier = _qualifier_module()
    junit = tmp_path / "junit.xml"
    junit.write_text(
        """
        <testsuites><testsuite tests="1">
          <testcase classname="tests.native_store.test_filesystem"
                    name="test_postcommit_marker_close_failure_reports_commit_without_retry">
            <skipped type="pytest.xfail"
                     message="windows-marker-close-reason-classification.md" />
          </testcase>
        </testsuite></testsuites>
        """,
        encoding="utf-8",
    )

    evidence = qualifier.inspect_candidate_junit(junit)

    assert evidence["limitations"] == []
    assert evidence["required_skips"] == [
        {
            "case": (
                "tests.native_store.test_filesystem::"
                "test_postcommit_marker_close_failure_reports_commit_without_retry"
            ),
            "reason": "windows-marker-close-reason-classification.md",
        }
    ]
