"""Shared machinery for installed-candidate qualification tools."""

from __future__ import annotations

import ctypes
import hashlib
import importlib
import importlib.metadata
import importlib.util
import inspect
import json
import os
import platform
import plistlib
import re
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import venv
import xml.etree.ElementTree as ET
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AcceptedSkip:
    """One exact xfail that a qualification run may record as a limitation."""

    name: str
    reason_contains: str


@dataclass(frozen=True)
class CandidateArtifacts:
    """Candidate artifacts and the environment that built them."""

    wheel: Path
    sdist: Path
    rebuilt_wheel: Path
    build_python: Path
    build_distributions: list[dict[str, str]]


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
    """Run a qualification command without inherited Python path overrides."""
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
        env={
            key: value
            for key, value in os.environ.items()
            if key not in {"PYTHONPATH", "PYTHONHOME"}
        },
    )
    if result.returncode:
        raise RuntimeError(
            f"Command failed: {command!r}\n{result.stdout}\n{result.stderr}"
        )
    return result.stdout


def sha256(path: Path) -> str:
    """Return a file's SHA-256 digest."""
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def python_in(environment: Path) -> Path:
    """Return the Python executable inside a virtual environment."""
    return environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def confine_to_temp(path: Path) -> Path:
    """Resolve a qualification path beneath the operating-system temp root."""
    temp_root = Path(tempfile.gettempdir()).resolve()
    resolved = path.expanduser().resolve()
    if not resolved.is_relative_to(temp_root):
        raise ValueError("Qualification paths must stay in the OS temporary directory")
    return resolved


def create_environment(environment: Path, *, base_python: Path | None = None) -> Path:
    """Create a venv with either this interpreter or an explicit candidate Python."""
    if base_python is None:
        venv.create(environment, with_pip=True)
    else:
        run([str(base_python), "-I", "-m", "venv", str(environment)])
    return python_in(environment)


def build_candidate(
    repository: Path,
    work: Path,
    *,
    base_python: Path | None = None,
) -> CandidateArtifacts:
    """Build a wheel, sdist and wheel rebuilt from that sdist."""
    builder = work / "builder"
    build_python = create_environment(builder, base_python=base_python)
    build_requires = tomllib.loads(
        (repository / "pyproject.toml").read_text(encoding="utf-8")
    )["build-system"]["requires"]
    run(
        [
            str(build_python),
            "-I",
            "-m",
            "pip",
            "install",
            "build",
            *build_requires,
        ]
    )
    original = work / "original"
    run(
        [
            str(build_python),
            "-I",
            "-m",
            "build",
            "--no-isolation",
            "--wheel",
            "--sdist",
            "--outdir",
            str(original),
            str(repository),
        ]
    )
    wheels = list(original.glob("*.whl"))
    sdists = list(original.glob("*.tar.gz"))
    assert len(wheels) == len(sdists) == 1
    unpacked = work / "unpacked"
    unpacked.mkdir()
    with tarfile.open(sdists[0]) as archive:
        archive.extractall(unpacked, filter="data")
    source_dirs = [path for path in unpacked.iterdir() if path.is_dir()]
    assert len(source_dirs) == 1
    rebuilt = work / "rebuilt"
    run(
        [
            str(build_python),
            "-I",
            "-m",
            "build",
            "--no-isolation",
            "--wheel",
            "--outdir",
            str(rebuilt),
            str(source_dirs[0]),
        ]
    )
    rebuilt_wheels = list(rebuilt.glob("*.whl"))
    assert len(rebuilt_wheels) == 1
    return CandidateArtifacts(
        wheel=wheels[0],
        sdist=sdists[0],
        rebuilt_wheel=rebuilt_wheels[0],
        build_python=build_python,
        build_distributions=json.loads(
            run([str(build_python), "-I", "-m", "pip", "list", "--format=json"])
        ),
    )


def installed_api_evidence() -> dict[str, bool]:
    """Prove retired secrets APIs are absent from the importable candidate."""
    import mountainash_settings  # type: ignore[import-untyped]
    import mountainash_settings.secrets as secrets  # type: ignore[import-untyped]
    from mountainash_settings import (  # type: ignore[import-untyped]
        MountainAshBaseSettings,
        SettingsParameters,
    )

    registry_name = "mountainash_settings.secrets.registry"
    registry_module_absent = importlib.util.find_spec(registry_name) is None
    try:
        importlib.import_module(registry_name)
    except ModuleNotFoundError as error:
        registry_module_absent = registry_module_absent and error.name == registry_name
    else:
        registry_module_absent = False

    removed = (
        "register_secrets_backend",
        "get_secrets_backend",
        "replace_secrets_backend",
        "clear_secrets_registry",
        "SecretsBackend",
        "ClearableBackend",
    )
    surfaces = (mountainash_settings, secrets)
    removed_exports_absent = all(
        getattr(surface, name, _MISSING) is _MISSING
        for surface in surfaces
        for name in removed
    )
    parameter_names = {field.name for field in fields(SettingsParameters)}
    secrets_provider_absent = (
        "secrets_provider" not in parameter_names
        and "secrets_provider" not in inspect.signature(SettingsParameters).parameters
        and "secrets_provider" not in inspect.signature(SettingsParameters.create).parameters
        and all(
            getattr(surface, "secrets_provider", _MISSING) is _MISSING
            for surface in surfaces
        )
    )
    settings_source_secrets_provider_absent = getattr(
        MountainAshBaseSettings, "SETTINGS_SOURCE_SECRETS_PROVIDER", _MISSING
    ) is _MISSING
    evidence = {
        "registry_module_absent": registry_module_absent,
        "removed_exports_absent": removed_exports_absent,
        "secrets_provider_absent": secrets_provider_absent,
        "settings_source_secrets_provider_absent": (
            settings_source_secrets_provider_absent
        ),
    }
    assert all(evidence.values())
    return evidence


def probe(root: Path, *, check_api: bool = False) -> dict[str, Any]:
    """Exercise an installed local store and bind its runtime environment."""
    import mountainash_settings  # type: ignore[import-untyped]
    from mountainash_settings.secrets import (  # type: ignore[import-untyped]
        FilesystemBackend,
    )

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
        name: str(Path(str(module.__file__)).resolve())
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
    evidence: dict[str, Any] = {
        "python": sys.version,
        "implementation": platform.python_implementation(),
        "python_floor_exercised": sys.version_info[:2] == (3, 12),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "filesystem": filesystem_type(root),
        "native_dependencies": native_dependencies(),
        "environment": str(prefix),
        "imports": origins,
        "import_inside_environment": inside,
        "retired_package_absent": retired_absent,
        "resolved_distributions": distributions,
    }
    if check_api:
        evidence["retired_api"] = installed_api_evidence()
    return evidence


def _skip_reason(skipped: ET.Element) -> str:
    message = skipped.get("message", "")
    if message.startswith("optional-native:"):
        return message
    body = skipped.text or ""
    match = re.search(r"optional-native:[^'\"\r\n<]*", body)
    return match.group(0).strip() if match else message


def inspect_junit(
    path: Path,
    *,
    accepted_skips: tuple[AcceptedSkip, ...] = (),
) -> dict[str, object]:
    """Classify candidate failures, required skips and accepted limitations."""
    root = ET.parse(path).getroot()
    cases, failures, required_skips, limitations = [], [], [], []
    for case in root.iter("testcase"):
        identity = f"{case.get('classname')}::{case.get('name')}"
        cases.append(identity)
        for tag in ("failure", "error"):
            if case.find(tag) is not None:
                failures.append(identity)
        skipped = case.find("skipped")
        if skipped is None:
            continue
        reason = _skip_reason(skipped)
        accepted = any(
            skipped.get("type") == "pytest.xfail"
            and case.get("name") == allowed.name
            and allowed.reason_contains in reason
            for allowed in accepted_skips
        )
        entry = {"case": identity, "reason": reason}
        if reason.startswith("optional-native:") or accepted:
            limitations.append(entry)
        else:
            required_skips.append(entry)
    assert cases, "No candidate tests ran"
    return {
        "cases": cases,
        "failures": failures,
        "required_skips": required_skips,
        "limitations": limitations,
    }


_MISSING = object()
