"""Check production code under common and native typeshed platforms."""
from pathlib import Path
import subprocess
import sys


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    package = "src/mountainash_settings"
    passes = [
        ["--exclude", r"(^|/)_native_(posix|windows)\.py$", package],
        ["--platform", "linux", "--follow-imports=silent", f"{package}/secrets/_native_posix.py"],
        ["--platform", "darwin", "--follow-imports=silent", f"{package}/secrets/_native_posix.py"],
        ["--platform", "win32", "--follow-imports=silent", f"{package}/secrets/_native_windows.py"],
    ]
    failed = False
    for args in passes:
        result = subprocess.run([sys.executable, "-m", "mypy", *args, *sys.argv[1:]], cwd=root, check=False)
        failed = result.returncode != 0 or failed
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
