from __future__ import annotations

import ctypes as c
import os
import subprocess
from pathlib import Path

import pytest

from mountainash_settings.secrets import _native_windows as native


def make_junction(link: Path, target: Path) -> None:
    completed = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode:
        raise RuntimeError("mklink /J fixture creation failed")


def make_symbolic_link(link: Path, target: Path, *, directory: bool) -> None:
    try:
        os.symlink(target, link, target_is_directory=directory)
    except OSError as error:
        if error.winerror in (50, 1314):
            pytest.skip(
                f"required-native: Windows symbolic-link fixture unavailable (Win32 {error.winerror})"
            )
        raise
    facts = os.lstat(link)
    assert facts.st_reparse_tag == 0xA000000C


def open_descendant_without_component_guard(parent: int, relative: str) -> int:
    """Fixture-only raw descendant open proving OBJ_DONT_REPARSE at an ancestor.

    The product adapter accepts one derived component at a time. This deliberately
    bypasses that public component guard only to reproduce the probe's native
    symbolic-ancestor observation with the proposed adapter's own FFI bindings.
    """
    name = native._NtName(relative)
    attributes = native.OBJECT_ATTRIBUTES(
        c.sizeof(native.OBJECT_ATTRIBUTES),
        native.HANDLE(parent),
        c.pointer(name.string),
        native.OBJ_CASE_INSENSITIVE | native.OBJ_DONT_REPARSE,
        None,
        None,
    )
    iosb, opened = native.IO_STATUS_BLOCK(), native.HANDLE()
    try:
        native._check_status(
            native._api().NtCreateFile(
                c.byref(opened),
                native.GENERIC_READ | native.SYNCHRONIZE,
                c.byref(attributes),
                c.byref(iosb),
                None,
                native.FILE_ATTRIBUTE_NORMAL,
                native.FILE_SHARE_READ
                | native.FILE_SHARE_WRITE
                | native.FILE_SHARE_DELETE,
                native.FILE_OPEN,
                native.FILE_SYNCHRONOUS_IO_NONALERT
                | native.FILE_OPEN_REPARSE_POINT,
                None,
                0,
            ),
            "fixture NtCreateFile descendant",
        )
        return int(opened.value)
    except BaseException:
        if opened.value not in (None, native.INVALID_HANDLE_VALUE):
            try:
                native._close_raw(opened)
            except Exception:
                pass
        raise


def snapshot_private(parent: int, name: str) -> dict[str, object]:
    """Transfer the probe's outside-object/content/security snapshot."""
    handle = native.open_file(parent, name)
    try:
        raw = native.HANDLE(handle)
        basic = native.BY_HANDLE_FILE_INFORMATION()
        native._check_bool(
            native._api().GetFileInformationByHandle(raw, c.byref(basic)),
            "fixture snapshot metadata",
        )
        return {
            "identity": native._identity(raw),
            "access": native._dacl_private(raw),
            "content": native.read_file(handle),
            "attributes": basic.FileAttributes,
            "created": (basic.CreationTimeHigh << 32) | basic.CreationTimeLow,
            "written": (basic.LastWriteTimeHigh << 32) | basic.LastWriteTimeLow,
        }
    finally:
        native.close(handle)


def set_dacl(handle: int, sddl: str) -> None:
    """Exact test-only extraction of prototype lines 626-658."""
    api = native._api()
    descriptor = native.PVOID()
    native._check_bool(
        api.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            sddl, 1, c.byref(descriptor), None
        ),
        "fixture ConvertStringSecurityDescriptorToSecurityDescriptorW",
    )
    try:
        present, defaulted, dacl = native.BOOL(), native.BOOL(), native.PVOID()
        native._check_bool(
            api.GetSecurityDescriptorDacl(
                descriptor, c.byref(present), c.byref(dacl), c.byref(defaulted)
            ),
            "fixture GetSecurityDescriptorDacl",
        )
        if not present.value:
            raise AssertionError("fixture SDDL unexpectedly has no DACL")
        status = api.SetSecurityInfo(
            native.HANDLE(handle), native.SE_FILE_OBJECT,
            native.DACL_SECURITY_INFORMATION | native.PROTECTED_DACL_SECURITY_INFORMATION,
            None, None, dacl, None,
        )
        if status:
            raise OSError(status, "fixture SetSecurityInfo")
    finally:
        api.LocalFree(c.cast(descriptor, native.HANDLE))


def open_for_dacl(path: Path, *, directory: bool = False) -> int:
    api = native._api()
    handle = native.HANDLE(api.CreateFileW(
        str(path), native.READ_CONTROL | 0x00040000,  # WRITE_DAC: fixture only.
        native.FILE_SHARE_READ | native.FILE_SHARE_WRITE | native.FILE_SHARE_DELETE,
        None, native.OPEN_EXISTING, 0x02000000 if directory else 0, None,
    ))
    if handle.value == native.INVALID_HANDLE_VALUE:
        raise OSError(c.get_last_error(), "fixture CreateFileW security handle")
    return int(handle.value)


def open_without_delete_share(path: Path) -> int:
    api = native._api()
    handle = native.HANDLE(api.CreateFileW(
        str(path), native.GENERIC_READ, native.FILE_SHARE_READ | native.FILE_SHARE_WRITE,
        None, native.OPEN_EXISTING, 0, None,
    ))
    if handle.value == native.INVALID_HANDLE_VALUE:
        raise OSError(c.get_last_error(), "fixture CreateFileW")
    return int(handle.value)


def file_id(handle: int) -> tuple[int, int]:
    facts = native._identity(native.HANDLE(handle))
    return int(facts["volume"]), int(facts["file_index"])


def close_quietly(handle: int | None) -> None:
    if handle is not None:
        try:
            native.close(handle)
        except Exception:
            pass
