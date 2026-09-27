from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _common() -> ModuleType:
    name = "_qualification_common_under_test"
    if name in sys.modules:
        return sys.modules[name]
    path = Path(__file__).resolve().parents[3] / "tools" / "_qualification_common.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _write_junit(path: Path, testcase: str) -> None:
    path.write_text(
        f'<testsuites><testsuite tests="1">{testcase}</testsuite></testsuites>',
        encoding="utf-8",
    )


def test_inspect_junit_accepts_optional_native_reason_from_collection_body(
    tmp_path: Path,
):
    common = _common()
    junit = tmp_path / "junit.xml"
    _write_junit(
        junit,
        """
        <testcase classname="" name="native_store.test_windows">
          <skipped message="collection skipped">
            ('test_windows.py', 10, 'Skipped: optional-native: Windows-only')
          </skipped>
        </testcase>
        """,
    )

    evidence = common.inspect_junit(junit)

    assert evidence["required_skips"] == []
    assert evidence["limitations"] == [
        {
            "case": "::native_store.test_windows",
            "reason": "optional-native: Windows-only",
        }
    ]


def test_inspect_junit_rejects_xfail(tmp_path: Path):
    common = _common()
    junit = tmp_path / "junit.xml"
    _write_junit(
        junit,
        """
        <testcase classname="tests.native_store.test_filesystem"
                  name="test_marker_close">
          <skipped type="pytest.xfail"
                   message="Tracked: windows-marker-close-reason-classification.md" />
        </testcase>
        """,
    )
    evidence = common.inspect_junit(junit)

    assert evidence["limitations"] == []
    assert evidence["required_skips"] == [
        {
            "case": "tests.native_store.test_filesystem::test_marker_close",
            "reason": "Tracked: windows-marker-close-reason-classification.md",
        }
    ]


def test_installed_api_evidence_proves_clean_break():
    common = _common()

    evidence = common.installed_api_evidence()

    assert evidence == {
        "registry_module_absent": True,
        "removed_exports_absent": True,
        "secrets_provider_absent": True,
        "settings_source_secrets_provider_absent": True,
    }
