"""Check tests with common and native typeshed platform selections."""
from pathlib import Path
import subprocess
import sys


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    native = "tests/secrets/native"
    exclude = (
        r"^tests/secrets/native/"
        r"(test_posix|posix_helpers|test_windows|_windows_fixtures)\.py$"
    )
    passes = [
        ("common tests", ["--platform", "linux", "--exclude", exclude, "tests"]),
        ("Linux POSIX tests", ["--platform", "linux", "--follow-imports=silent",
                              f"{native}/test_posix.py", f"{native}/posix_helpers.py"]),
        ("macOS POSIX tests", ["--platform", "darwin", "--follow-imports=silent",
                              f"{native}/test_posix.py", f"{native}/posix_helpers.py"]),
        ("Windows tests", ["--platform", "win32", "--follow-imports=silent",
                           f"{native}/test_windows.py", f"{native}/_windows_fixtures.py"]),
    ]
    failed = False
    for label, args in passes:
        print(f"Checking {label}", flush=True)
        result = subprocess.run(
            [sys.executable, "-m", "mypy", *args, *sys.argv[1:]],
            cwd=root, check=False,
        )
        failed = result.returncode != 0 or failed
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
