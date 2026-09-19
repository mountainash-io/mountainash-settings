"""Disposable native-mechanism experiment; not a settings backend or certification."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib.util
import json
import os
import platform
import plistlib
import subprocess
import sys
import tempfile
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

CASES = {
    "root_pinning": (
        "direct",
        "linked_final",
        "linked_ancestor",
        "retarget_existing",
        "retarget_new",
        "missing",
        "non_directory",
    ),
    "namespace_inheritance_and_layouts": (
        "layouts",
        "invalid_keys",
        "set_first_use",
        "delete_first_use",
        "transaction_first_use",
        "existing_policy",
        "inherited_policy",
    ),
    "redirect_refusal": (
        "namespace",
        "credential",
        "temp",
        "marker",
        "lock",
        "substitution",
        "outside_unchanged",
    ),
    "object_privacy": (
        "nonregular",
        "hardlink",
        "exposed",
        "private_before_payload",
        "namespace_acl_unchanged",
    ),
    "temp_replace_cleanup": (
        "exclusive_random",
        "collision_preserved",
        "serialization_fault",
        "write_fault",
        "close_fault",
        "replace_fault",
        "precommit_preserved",
        "postcommit_failure",
        "mismatch_preserved",
    ),
    "marker_interruption": (
        "normal_delete",
        "recreate",
        "handled_failure",
        "interruption",
        "no_repair",
    ),
    "cooperative_locking": (
        "independent_process",
        "same_process",
        "stable_lock",
        "invalid_lock",
        "protected_cleanup",
    ),
    "owner_quiescent_lifecycle": (
        "construction_failure",
        "context_exit",
        "finalization",
        "quiescent_close",
        "postclose_read",
        "postclose_write",
        "postclose_delete",
        "postclose_marker",
        "deferred_entry",
        "transaction_exit_open",
        "native_reuse",
        "idempotent_close",
    ),
}


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


def revision() -> str:
    if value := os.environ.get("GITHUB_SHA"):
        return value
    return subprocess.run(
        ["git", "-C", str(Path(__file__).resolve().parents[2]), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    ).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    here = Path(__file__).resolve().parent
    rows: list[dict[str, object]] = []
    report: dict[str, object] = {
        "schema": 2,
        "purpose": "disposable native mechanism feasibility, not product qualification",
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": revision(),
        "probe_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(here.glob("*.py"))
        },
        "environment": {
            "platform": sys.platform,
            "os": platform.platform(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "python_executable": sys.executable,
            "runner_os": os.environ.get("RUNNER_OS"),
            "run_id": os.environ.get("GITHUB_RUN_ID"),
            "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        },
        "scope_limits": [
            "No product package was installed, built or certified.",
            "Results cover only the recorded OS, interpreter, filesystem and mechanisms.",
            "All live writers must coordinate; external modifications require quiescence.",
            "No identity-atomic cleanup guarantee against authorized protocol bypass.",
            "Caller integration and complete M3/M4 candidate acceptance remain separate.",
        ],
        "cases": rows,
        "status": "running",
    }

    def save() -> None:
        output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    def record(name: str, operation: Callable[[], dict[str, object]]) -> None:
        if any(row["name"] == name for row in rows):
            raise ValueError(f"Duplicate probe case: {name}")
        row: dict[str, object] = {"name": name, "status": "running"}
        rows.append(row)
        save()
        print(f"START {name}", flush=True)
        started = time.monotonic()
        try:
            observations = operation()
            if not isinstance(observations, dict):
                raise TypeError("Probe must return an observation dictionary")
            status = observations.pop("status", "passed")
            if status not in ("passed", "failed", "blocked"):
                raise ValueError("Unknown probe status")
            json.dumps(observations)
            if status == "passed" and name in CASES:
                checks = observations.get("checks", {})
                missing = [
                    key
                    for key in CASES[name]
                    if not isinstance(checks, dict) or checks.get(key) is not True
                ]
                if missing:
                    status = "blocked"
                    observations["missing_required_checks"] = missing
            row.update(status=status, observations=observations)
        except Exception as error:
            row.update(
                status="failed",
                error_type=type(error).__name__,
                error=str(error),
                traceback="".join(traceback.format_exception(error)),
            )
        row["duration_seconds"] = round(time.monotonic() - started, 6)
        save()
        print(f"{str(row['status']).upper()} {name}", flush=True)

    save()
    try:
        with tempfile.TemporaryDirectory(prefix="mas-native-feasibility-") as temporary:
            root = Path(temporary).resolve()
            report["environment"]["filesystem"] = filesystem_type(root)
            module_name = "windows_probe" if sys.platform == "win32" else "posix_probe"
            if sys.platform not in ("linux", "darwin", "win32"):
                raise RuntimeError("This experiment requires Linux, macOS or Windows")
            spec = importlib.util.spec_from_file_location(
                module_name, here / f"{module_name}.py"
            )
            if spec is None or spec.loader is None:
                raise RuntimeError("Native probe module unavailable")
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            record(
                "prototype_dispatch",
                lambda: {
                    "module": module_name,
                    "boundary": "prototype dispatch only; not product portable-import proof",
                },
            )
            module.run(root, record)
            report["environment"]["native_dependencies"] = native_dependencies()
            observed_names = {row["name"] for row in rows}
            for missing in sorted(set(CASES) - observed_names):
                rows.append(
                    {
                        "name": missing,
                        "status": "blocked",
                        "reason": "scenario_not_executed",
                    }
                )
    except Exception as error:
        rows.append(
            {
                "name": "experiment_infrastructure",
                "status": "failed",
                "error_type": type(error).__name__,
                "error": str(error),
                "traceback": "".join(traceback.format_exception(error)),
            }
        )
    report["finished_utc"] = datetime.now(timezone.utc).isoformat()
    report["status"] = (
        "passed"
        if rows
        and all(row["status"] == "passed" for row in rows)
        and set(CASES).issubset({row["name"] for row in rows})
        else "failed_or_blocked"
    )
    save()
    print(
        json.dumps({"status": report["status"], "report": str(output)}, sort_keys=True)
    )
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
