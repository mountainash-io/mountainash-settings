from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from mountainash_settings.secrets import _native_posix as native

def close_all(*fds: int | None) -> None:
    for fd in fds:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass


def snapshot(parent: int, name: str) -> tuple[int, int, int, bytes]:
    fd = native.open_file(parent, name)
    try:
        info = os.fstat(fd)
        return info.st_dev, info.st_ino, info.st_mode, native.read_file(fd)
    finally:
        native.close(fd)
def read_linux_acl(parent: Path) -> str:
    return subprocess.run(
        ["getfacl", "-cp", str(parent)],
        check=True, capture_output=True, text=True, timeout=5,
    ).stdout


def linux_default_acl(parent: Path) -> str:
    if not shutil.which("setfacl") or not shutil.which("getfacl"):
        pytest.skip("setfacl/getfacl unavailable: Linux ACL privacy is not qualified")
    uid = os.geteuid() + 100_000
    try:
        subprocess.run(
            ["setfacl", "-m", f"d:u::rwx,d:u:{uid}:rwx,d:g::---,d:m::rwx,d:o::---", str(parent)],
            check=True, capture_output=True, text=True, timeout=5,
        )
        return read_linux_acl(parent)
    except subprocess.CalledProcessError:
        pytest.skip("host/filesystem rejects default ACL fixture: Linux ACL privacy is not qualified")


def darwin_inheritable_acl(parent: Path) -> None:
    try:
        subprocess.run(
            ["chmod", "+a", "everyone allow read,file_inherit,directory_inherit", str(parent)],
            check=True, capture_output=True, text=True, timeout=5,
        )
    except subprocess.CalledProcessError:
        pytest.skip("host/filesystem rejects inheritable ACL fixture: Darwin ACL privacy is not qualified")


def darwin_acl_fingerprint(path: Path) -> list[str]:
    return subprocess.run(
        ["ls", "-led", str(path)],
        check=True, capture_output=True, text=True, timeout=5,
    ).stdout.splitlines()[1:]
