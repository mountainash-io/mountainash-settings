"""Build and check typed distributions from isolated installed consumers."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="New directory for artifacts and logs")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve() if args.output else Path(tempfile.mkdtemp(prefix="settings-typing-"))
    if args.output:
        output.mkdir(parents=True, exist_ok=False)
    print(f"Typing qualification evidence: {output}", flush=True)
    env = os.environ.copy()
    for key in ("PYTHONPATH", "PYTHONHOME", "MYPYPATH"):
        env.pop(key, None)

    def run(command: list[str], cwd: Path, log: str) -> None:
        result = subprocess.run(command, cwd=cwd, env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (output / log).write_text(result.stdout)
        print(result.stdout, end="", flush=True)
        result.check_returncode()

    run(["git", "rev-parse", "HEAD"], root, "source-revision.log")
    run(["git", "status", "--short"], root, "source-status.log")
    run([sys.executable, "-m", "build", "--wheel", "--sdist", "--outdir",
         str(output / "direct"), str(root)], output, "build.log")
    sdist, = (output / "direct").glob("*.tar.gz")
    with tarfile.open(sdist) as archive:
        if not any(name.endswith("/src/mountainash_settings/py.typed") for name in archive.getnames()):
            raise RuntimeError("sdist lacks py.typed")
        archive.extractall(output / "source", filter="data")
    source, = (output / "source").iterdir()
    run([sys.executable, "-m", "build", "--wheel", "--outdir",
         str(output / "rebuilt"), str(source)], output, "rebuild.log")

    artifacts = [sdist]
    for kind in ("direct", "rebuilt"):
        wheel, = (output / kind).glob("*.whl")
        artifacts.append(wheel)
        with zipfile.ZipFile(wheel) as archive:
            if "mountainash_settings/py.typed" not in archive.namelist():
                raise RuntimeError(f"{kind} wheel lacks py.typed")
        consumer = output / f"consumer-{kind}"
        consumer.mkdir()
        shutil.copy(root / "tests/typing/consumer.py", consumer / "consumer.py")
        (consumer / "mypy.ini").write_text("[mypy]\n")
        environment = output / f"env-{kind}"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = str(environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))
        run([python, "-m", "pip", "install", str(wheel), "mypy==1.10.1",
             "types-PyYAML==6.0.12.20260906", "pytest==8.3.5"], consumer, f"{kind}-install.log")
        run([python, "-m", "pip", "freeze"], consumer, f"{kind}-dependencies.log")
        # Obtain the real public export list from the installed distribution.
        run([python, "-c", "import mountainash_settings as m; from pathlib import Path; "
             "print(m.__file__); "
             "Path('exports.py').write_text('from mountainash_settings import ' + ', '.join(m.__all__) + '\\n')"],
            consumer, f"{kind}-imports.log")
        run([python, "-m", "mypy", "--config-file", "mypy.ini", "--no-incremental", "--no-implicit-reexport",
             "--warn-unused-ignores", "consumer.py", "exports.py"], consumer, f"{kind}-mypy.log")
        run([python, "consumer.py"], consumer, f"{kind}-runtime.log")

    receipt = {
        "python": sys.version,
        "consumer_sha256": hashlib.sha256((root / "tests/typing/consumer.py").read_bytes()).hexdigest(),
        "artifacts": {str(path.relative_to(output)): hashlib.sha256(path.read_bytes()).hexdigest()
                      for path in artifacts},
    }
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()
