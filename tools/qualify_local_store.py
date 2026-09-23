"""Non-publishing installed local-store qualification; not release authority."""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import plistlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import venv
import xml.etree.ElementTree as ET
from pathlib import Path


def filesystem_type(root: Path) -> str:
    """Identify the filesystem actually hosting the disposable fixtures."""
    if sys.platform == "win32":
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetVolumePathNameW.argtypes = (
            wintypes.LPCWSTR,
            wintypes.LPWSTR,
            wintypes.DWORD,
        )
        kernel.GetVolumePathNameW.restype = wintypes.BOOL
        kernel.GetVolumeInformationW.argtypes = (
            wintypes.LPCWSTR,
            wintypes.LPWSTR,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPWSTR,
            wintypes.DWORD,
        )
        kernel.GetVolumeInformationW.restype = wintypes.BOOL
        volume = ctypes.create_unicode_buffer(32768)
        kind = ctypes.create_unicode_buffer(256)
        if not kernel.GetVolumePathNameW(str(root), volume, len(volume)):
            raise ctypes.WinError(ctypes.get_last_error())
        if not kernel.GetVolumeInformationW(
            volume.value, None, 0, None, None, None, kind, len(kind)
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return kind.value
    if sys.platform == "darwin":
        result = subprocess.run(
            ["df", "-P", str(root)],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        device = result.stdout.splitlines()[-1].split()[0]
        info = subprocess.run(
            ["diskutil", "info", "-plist", device],
            check=True,
            capture_output=True,
            timeout=15,
        )
        return str(plistlib.loads(info.stdout)["FilesystemType"])
    return subprocess.run(
        ["findmnt", "-n", "-o", "FSTYPE", "-T", str(root)],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    ).stdout.strip()


def native_dependencies() -> dict[str, object]:
    """Bind native implementation inputs, not merely Python probe hashes."""

    def binary_hash(path: Path) -> str:
        with path.open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()

    if sys.platform == "linux":
        packages = subprocess.run(
            ["dpkg-query", "-W", "-f=${binary:Package} ${Version}\n", "acl", "libacl1"],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout.splitlines()
        libraries = sorted(
            {
                line.split(maxsplit=5)[-1]
                for line in Path("/proc/self/maps").read_text().splitlines()
                if "/libacl.so" in line
            }
        )
        if not libraries:
            raise RuntimeError("loaded libacl identity was not observed")
        return {
            "packages": packages,
            "loaded_libraries": {path: binary_hash(Path(path)) for path in libraries},
        }
    if sys.platform == "darwin":
        build = subprocess.run(
            ["sw_vers", "-buildVersion"],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout.strip()
        return {
            "libSystem_load_name": "/usr/lib/libSystem.B.dylib",
            "os_build": build,
            "kernel_build": platform.uname().version,
        }
    system = Path(os.environ["SystemRoot"]) / "System32"
    return {
        "system_dll_sha256": {
            str(system / name): binary_hash(system / name)
            for name in ("ntdll.dll", "kernel32.dll", "advapi32.dll")
        }
    }


def run(command: list[str], *, cwd: Path | None = None) -> str:
    result = subprocess.run(
        command, cwd=cwd, text=True, capture_output=True, check=False,
        env={key: value for key, value in os.environ.items()
             if key not in {"PYTHONPATH", "PYTHONHOME"}},
    )
    if result.returncode:
        raise RuntimeError(
            f"Command failed: {command!r}\n{result.stdout}\n{result.stderr}"
        )
    return result.stdout


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def python_in(environment: Path) -> Path:
    return environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def probe(root: Path) -> dict[str, object]:
    import mountainash_settings
    from mountainash_settings.secrets import FilesystemBackend

    root.mkdir()
    with FilesystemBackend(root) as store:
        with store.transaction("receipt"):
            store.set("receipt", {"dummy": "installed", "empty": {}})
        assert store.get("receipt") == {"dummy": "installed", "empty": {}}
        store.delete("receipt")
        assert store.get("receipt") is None
        assert store.is_cleared("receipt")
    prefix = Path(sys.prefix).resolve()
    origins = {
        name: str(Path(module.__file__).resolve())
        for name, module in tuple(sys.modules.items())
        if name.startswith("mountainash_settings")
        and getattr(module, "__file__", None)
    }
    inside = all(Path(path).is_relative_to(prefix) for path in origins.values())
    assert inside and origins
    distributions = {
        distribution.metadata["Name"]: distribution.version
        for distribution in importlib.metadata.distributions()
    }
    retired_absent = (
        importlib.util.find_spec("mountainash_secrets") is None
        and not any(
            name.lower().replace("_", "-") == "mountainash-secrets"
            for name in distributions
        )
    )
    assert retired_absent
    return {
        "python": sys.version, "implementation": platform.python_implementation(),
        "python_floor_exercised": sys.version_info[:2] == (3, 12),
        "platform": platform.platform(), "machine": platform.machine(),
        "filesystem": filesystem_type(root), "native_dependencies": native_dependencies(),
        "environment": str(prefix), "imports": origins,
        "import_inside_environment": inside,
        "retired_package_absent": retired_absent,
        "resolved_distributions": distributions,
    }


def inspect_junit(path: Path) -> dict[str, object]:
    root = ET.parse(path).getroot()
    cases, failures, required_skips, limitations = [], [], [], []
    for case in root.iter("testcase"):
        identity = f"{case.get('classname')}::{case.get('name')}"
        cases.append(identity)
        for tag in ("failure", "error"):
            if case.find(tag) is not None:
                failures.append(identity)
        skipped = case.find("skipped")
        if skipped is not None:
            message = skipped.get("message", "")
            if message.startswith("optional-native:"):
                limitations.append({"case": identity, "reason": message})
            else:
                required_skips.append({"case": identity, "reason": message})
    assert cases, "No candidate tests ran"
    return {
        "cases": cases, "failures": failures,
        "required_skips": required_skips, "limitations": limitations,
    }


def qualify(output: Path) -> int:
    repository = Path(__file__).resolve().parents[1]
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    revision = run(["git", "rev-parse", "HEAD"], cwd=repository).strip()
    dirty = run(
        ["git", "status", "--porcelain", "--untracked-files=normal"], cwd=repository
    )
    if dirty:
        raise RuntimeError("Candidate proof requires committed, clean source inputs")
    report: dict[str, object] = {
        "status": "failed", "source_revision": revision, "installed": [],
        "runner_sha256": sha256(Path(__file__)), "artifacts": {},
    }
    try:
        with tempfile.TemporaryDirectory(prefix="settings-m3-installed-") as work_name:
            work = Path(work_name)
            builder = work / "builder"
            venv.create(builder, with_pip=True)
            build_python = str(python_in(builder))
            build_requires = tomllib.loads(
                (repository / "pyproject.toml").read_text(encoding="utf-8")
            )["build-system"]["requires"]
            run([build_python, "-I", "-m", "pip", "install", "build", *build_requires])
            original = work / "original"
            run([
                build_python, "-I", "-m", "build", "--no-isolation", "--wheel", "--sdist",
                "--outdir", str(original), str(repository),
            ])
            wheels = list(original.glob("*.whl"))
            sdists = list(original.glob("*.tar.gz"))
            assert len(wheels) == len(sdists) == 1
            unpacked = work / "unpacked"
            unpacked.mkdir()
            with tarfile.open(sdists[0]) as archive:
                archive.extractall(unpacked, filter="data")
            source_dirs = [p for p in unpacked.iterdir() if p.is_dir()]
            assert len(source_dirs) == 1
            rebuilt = work / "rebuilt"
            run([
                build_python, "-I", "-m", "build", "--no-isolation", "--wheel",
                "--outdir", str(rebuilt), str(source_dirs[0]),
            ])
            rebuilt_wheels = list(rebuilt.glob("*.whl"))
            assert len(rebuilt_wheels) == 1
            copied_tests = work / "tests"
            shutil.copytree(repository / "tests/native_store", copied_tests)
            portable_names = ("records", "keys", "memory", "namespaced")
            for name in portable_names:
                shutil.copy2(
                    repository / f"tests/unit/secrets/test_{name}.py",
                    copied_tests / f"test_{name}.py",
                )
            test_hashes = {
                str(path.relative_to(copied_tests)): sha256(path)
                for path in copied_tests.rglob("*.py")
            }
            report["test_inputs"] = test_hashes
            report["build_distributions"] = json.loads(run(
                [build_python, "-I", "-m", "pip", "list", "--format=json"]
            ))
            for kind, artifact in (
                ("wheel", wheels[0]), ("sdist-wheel", rebuilt_wheels[0]),
            ):
                destination = output.parent / kind
                destination.mkdir(exist_ok=True)
                saved_artifact = destination / artifact.name
                shutil.copy2(artifact, saved_artifact)
                if kind == "wheel":
                    shutil.copy2(sdists[0], destination / sdists[0].name)
                    report["artifacts"]["sdist"] = {
                        "path": str(destination / sdists[0].name),
                        "sha256": sha256(sdists[0]),
                    }
                report["artifacts"][kind] = {
                    "path": str(saved_artifact), "sha256": sha256(saved_artifact),
                }
                environment = work / f"installed-{kind}"
                venv.create(environment, with_pip=True)
                installed_python = str(python_in(environment))
                run([
                    installed_python, "-I", "-m", "pip", "install",
                    str(saved_artifact), "pytest",
                ])
                run([installed_python, "-I", "-m", "pip", "check"])
                native_test = (
                    "test_windows.py" if sys.platform == "win32" else "test_posix.py"
                )
                junit = destination / "junit.xml"
                selected = [native_test, "test_filesystem.py"] + [
                    f"test_{name}.py" for name in portable_names
                ]
                command = [
                    installed_python, "-I", "-m", "pytest",
                    "--import-mode=importlib", f"--confcutdir={copied_tests}",
                    f"--basetemp={work / ('pytest-' + kind)}",
                    f"--junitxml={junit}", "-q",
                    *[str(copied_tests / name) for name in selected],
                ]
                # Persist pytest output even on failure; do not lose diagnostic receipts.
                result = subprocess.run(
                    command, cwd=work, text=True, capture_output=True, check=False,
                    env={key: value for key, value in os.environ.items()
                         if key not in {"PYTHONPATH", "PYTHONHOME"}},
                )
                (destination / "pytest.txt").write_text(
                    result.stdout + result.stderr, encoding="utf-8"
                )
                tests = inspect_junit(junit)
                evidence = json.loads(run([
                    installed_python, "-I", str(Path(__file__).resolve()),
                    "--probe", str(work / f"probe-{kind}"),
                ], cwd=work))
                report["installed"].append({
                    "kind": kind, "artifact_sha256": sha256(saved_artifact),
                    "tests": tests, "probe": evidence,
                })
                assert result.returncode == 0
                assert not tests["failures"] and not tests["required_skips"]
            assert run(["git", "rev-parse", "HEAD"], cwd=repository).strip() == revision
            assert not run(
                ["git", "status", "--porcelain", "--untracked-files=normal"], cwd=repository
            ), "Candidate source changed during qualification"
            report["status"] = "passed"
    except Exception as exc:
        report["failure"] = str(exc)
    finally:
        output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return 0 if report["status"] == "passed" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--output", type=Path)
    mode.add_argument("--probe", type=Path)
    args = parser.parse_args()
    if args.probe is not None:
        print(json.dumps(probe(args.probe), sort_keys=True))
        return 0
    return qualify(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
