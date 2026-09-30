"""Execute the README's actual quick start with its documented input."""

from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_readme_quickstart_runs(tmp_path: Path, example_environment: dict[str, str]) -> None:
    blocks = re.findall(
        r"^```([^\n]*)\n(.*?)^```\s*$",
        (ROOT / "README.md").read_text(encoding="utf-8"),
        re.MULTILINE | re.DOTALL,
    )
    for language, filename in (("yaml", "report.yaml"), ("python", "quickstart.py")):
        bodies = [body for label, body in blocks if label == language]
        assert len(bodies) == 1, f"Expected one {language} quick-start block"
        (tmp_path / filename).write_text(bodies[0], encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-I", "quickstart.py"], cwd=tmp_path,
        env=example_environment, capture_output=True, text=True,
        timeout=60, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "reports: reports, debug=True"
