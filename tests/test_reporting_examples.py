"""Execute the examples users run, independently of their working directory."""

from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPORTING = ROOT / "examples" / "reporting"
RECIPES = sorted(REPORTING.glob("*/example.py"))
assert RECIPES, "No runnable reporting recipes found"


@pytest.mark.parametrize("recipe", RECIPES, ids=lambda path: path.parent.name)
def test_reporting_recipe_runs(recipe: Path, tmp_path: Path, example_environment: dict[str, str]) -> None:
    work = tmp_path / "reporting examples"
    shutil.copytree(REPORTING, work)
    script = work / recipe.relative_to(REPORTING)
    result = subprocess.run(
        [sys.executable, "-I", str(script)], cwd=tmp_path,
        env=example_environment, capture_output=True, text=True,
        timeout=60, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip(), "The recipe must show its demonstrated result"


def test_reporting_invariants_run(tmp_path: Path, example_environment: dict[str, str]) -> None:
    work = tmp_path / "reporting examples"
    shutil.copytree(REPORTING, work)
    config = tmp_path / "pytest.ini"
    config.write_text("[pytest]\nmarkers =\n    unit: generated profile invariant checks\n", encoding="utf-8")
    receipt = tmp_path / "invariants.xml"
    result = subprocess.run(
        [
            sys.executable, "-I", "-m", "pytest", "-q",
            str(work / "invariant_checks" / "test_profiles.py"),
            "--import-mode=importlib", f"--confcutdir={work}",
            "-c", str(config), f"--junitxml={receipt}",
        ],
        cwd=tmp_path, env=example_environment, capture_output=True, text=True,
        timeout=60, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    suites = list(ET.parse(receipt).getroot().iter("testsuite"))
    assert sum(int(suite.get("tests", "0")) for suite in suites) > 0
    for suite in suites:
        assert all(int(suite.get(key, "0")) == 0 for key in ("errors", "failures", "skipped"))
