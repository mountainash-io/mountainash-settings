"""Keep the runnable reporting example identical to the README and executable."""

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "reporting"


def test_reporting_files_match_readme_verbatim() -> None:
    """Catch edits to either copy that leave the other out of date."""
    assert EXAMPLE.is_dir(), "The README's runnable reporting example is missing"
    blocks = re.findall(
        r"^```([^\n]*)\n(.*?)^```\s*$",
        (ROOT / "README.md").read_text(encoding="utf-8"),
        re.MULTILINE | re.DOTALL,
    )
    python_blocks = [body for language, body in blocks if language == "python"]
    assert python_blocks, "The README must contain the reporting walkthrough"
    assert (EXAMPLE / "reporting.py").read_text(encoding="utf-8") == "\n".join(python_blocks)
    for language, relative in (
        ("yaml", "config/base.yaml"),
        ("toml", "config/production.toml"),
        ("dotenv", ".env"),
    ):
        bodies = [body for label, body in blocks if label == language]
        assert len(bodies) == 1, f"Expected one {language} configuration example"
        assert (EXAMPLE / relative).read_text(encoding="utf-8") == bodies[0]


def test_reporting_walkthrough_and_invariants_run(tmp_path: Path) -> None:
    """Catch broken imports, API drift and assertions in the actual example."""
    assert EXAMPLE.is_dir(), "The README's runnable reporting example is missing"
    work = tmp_path / "reporting"
    shutil.copytree(EXAMPLE, work)
    environment = {
        key: value for key, value in os.environ.items()
        if key.upper() not in {
            "APP_NAME", "ENV", "DEBUG", "DATABASE", "LOG_PATH", "LOG_PATH_TEMPLATE",
            "HOST", "PORT", "USERNAME", "PASSWORD", "PYTHONPATH", "PYTHONHOME",
            "PYTHONOPTIMIZE", "PYTEST_ADDOPTS", "PYTEST_PLUGINS",
        } and not key.upper().startswith("REPORT_")
    }
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    commands = [
        [sys.executable, "-I", "reporting.py"],
        [
            sys.executable, "-I", "-m", "pytest", "-q", "reporting.py",
            "--import-mode=importlib", f"--confcutdir={work}",
            "-c", "pytest.ini", "--junitxml=invariants.xml",
        ],
    ]
    (work / "pytest.ini").write_text(
        "[pytest]\nmarkers =\n    unit: generated profile invariant checks\n",
        encoding="utf-8",
    )
    for command in commands:
        result = subprocess.run(
            command, cwd=work, env=environment, capture_output=True, text=True,
            timeout=60, check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
    suites = list(ET.parse(work / "invariants.xml").getroot().iter("testsuite"))
    assert sum(int(suite.get("tests", "0")) for suite in suites) > 0
    for suite in suites:
        assert all(int(suite.get(key, "0")) == 0 for key in ("errors", "failures", "skipped"))
