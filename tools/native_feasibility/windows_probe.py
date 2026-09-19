"""Windows-native, disposable feasibility probes for private file-store mechanics.

This module deliberately uses the NT directory-handle API for every store
namespace operation after the trusted startup directory has been acquired.
It is a probe, not a store implementation.
"""

from __future__ import annotations

import ctypes as c
import errno
import json
import re
import secrets
from contextlib import ExitStack, contextmanager
import os
from collections.abc import Callable
from pathlib import Path
import subprocess
import sys
import threading
import typing as t


HANDLE = c.c_void_p
PHANDLE = c.POINTER(HANDLE)
# Explicit widths preserve the Windows ABI even when this module is imported
# by a non-Windows discovery process.
ULONG = c.c_uint32
USHORT = c.c_uint16
DWORD = c.c_uint32
WORD = c.c_uint16
BYTE = c.c_uint8
BOOL = c.c_int32
LONG = c.c_int32
ULONG_PTR = c.c_size_t
PVOID = c.c_void_p
NTSTATUS = c.c_int32

INVALID_HANDLE_VALUE = c.c_void_p(-1).value

# Object-manager and I/O-manager constants from ntifs.h / winnt.h.
OBJ_CASE_INSENSITIVE = 0x00000040
OBJ_DONT_REPARSE = 0x00001000
FILE_SUPERSEDE = 0
FILE_OPEN = 1
FILE_CREATE = 2
FILE_OPEN_IF = 3
FILE_OVERWRITE = 4
FILE_OVERWRITE_IF = 5
FILE_DIRECTORY_FILE = 0x00000001
FILE_SYNCHRONOUS_IO_NONALERT = 0x00000020
FILE_OPEN_REPARSE_POINT = 0x00200000
FILE_ATTRIBUTE_NORMAL = 0x00000080
FILE_ATTRIBUTE_DIRECTORY = 0x00000010
FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
FILE_SHARE_DELETE = 0x00000004
OPEN_EXISTING = 3
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
GENERIC_ALL = 0x10000000
DELETE = 0x00010000
READ_CONTROL = 0x00020000
WRITE_DAC = 0x00040000
SYNCHRONIZE = 0x00100000
# Metadata/traverse only: data-access directory handles can conflict with the
# I/O manager's rename-target open (FILE_RENAME_INFORMATION.RootDirectory).
DIRECTORY_ACCESS = 0x20 | 0x80 | READ_CONTROL | SYNCHRONIZE
FILE_END = 2
FILE_TYPE_DISK = 0x0001
FILE_RENAME_INFORMATION = 10
FILE_LINK_INFORMATION = 11
FILE_DISPOSITION_INFORMATION_CLASS = 13
ERROR_INSUFFICIENT_BUFFER = 122
ERROR_LOCK_VIOLATION = 33
LOCKFILE_FAIL_IMMEDIATELY = 0x00000001
LOCKFILE_EXCLUSIVE_LOCK = 0x00000002
PROTECTED_DACL_SECURITY_INFORMATION = 0x80000000
TOKEN_QUERY = 0x0008
TOKEN_USER = 1
SE_FILE_OBJECT = 1
DACL_SECURITY_INFORMATION = 0x00000004
ACL_SIZE_INFORMATION = 2
ACCESS_ALLOWED_ACE_TYPE = 0x00
SE_DACL_PROTECTED = 0x1000
FILE_ALL_ACCESS = 0x001F01FF
STATUS_OBJECT_NAME_NOT_FOUND = 0xC0000034
STATUS_OBJECT_PATH_NOT_FOUND = 0xC000003A
STATUS_OBJECT_NAME_COLLISION = 0xC0000035
STATUS_ACCESS_DENIED = 0xC0000022
STATUS_REPARSE_POINT_ENCOUNTERED = 0xC000050B
STATUS_STOPPED_ON_SYMLINK = 0x8000002D


class UNICODE_STRING(c.Structure):
    _fields_ = [
        ("Length", USHORT),
        ("MaximumLength", USHORT),
        ("Buffer", c.POINTER(c.c_wchar)),
    ]


class OBJECT_ATTRIBUTES(c.Structure):
    _fields_ = [
        ("Length", ULONG),
        ("RootDirectory", HANDLE),
        ("ObjectName", c.POINTER(UNICODE_STRING)),
        ("Attributes", ULONG),
        ("SecurityDescriptor", PVOID),
        ("SecurityQualityOfService", PVOID),
    ]


class _IoStatusUnion(c.Union):
    _fields_ = [("Status", NTSTATUS), ("Pointer", PVOID)]


class IO_STATUS_BLOCK(c.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("u", _IoStatusUnion), ("Information", ULONG_PTR)]


class BY_HANDLE_FILE_INFORMATION(c.Structure):
    _fields_ = [
        ("FileAttributes", DWORD),
        ("CreationTimeLow", DWORD),
        ("CreationTimeHigh", DWORD),
        ("LastAccessTimeLow", DWORD),
        ("LastAccessTimeHigh", DWORD),
        ("LastWriteTimeLow", DWORD),
        ("LastWriteTimeHigh", DWORD),
        ("VolumeSerialNumber", DWORD),
        ("FileSizeHigh", DWORD),
        ("FileSizeLow", DWORD),
        ("NumberOfLinks", DWORD),
        ("FileIndexHigh", DWORD),
        ("FileIndexLow", DWORD),
    ]


class FILE_STANDARD_INFO(c.Structure):
    _fields_ = [
        ("AllocationSize", c.c_longlong),
        ("EndOfFile", c.c_longlong),
        ("NumberOfLinks", DWORD),
        ("DeletePending", BYTE),  # BOOLEAN, not Win32 BOOL
        ("Directory", BYTE),  # BOOLEAN, not Win32 BOOL
    ]


class FILE_ATTRIBUTE_TAG_INFO(c.Structure):
    _fields_ = [("FileAttributes", DWORD), ("ReparseTag", DWORD)]


class FILE_DISPOSITION_INFORMATION(c.Structure):
    _fields_ = [("DeleteFile", BYTE)]


class FILE_RENAME_INFORMATION_FIXED(c.Structure):
    _fields_ = [
        ("ReplaceIfExists", BYTE),
        ("RootDirectory", HANDLE),
        ("FileNameLength", ULONG),
        ("FileName", c.c_wchar * 1),
    ]


class OVERLAPPED(c.Structure):
    _fields_ = [
        ("Internal", ULONG_PTR),
        ("InternalHigh", ULONG_PTR),
        ("Offset", DWORD),
        ("OffsetHigh", DWORD),
        ("hEvent", HANDLE),
    ]


class TOKEN_USER_DATA(c.Structure):
    _fields_ = [("Sid", PVOID), ("Attributes", DWORD)]


class ACL_SIZE_INFORMATION_DATA(c.Structure):
    _fields_ = [("AceCount", DWORD), ("AclBytesInUse", DWORD), ("AclBytesFree", DWORD)]


class ACE_HEADER(c.Structure):
    _fields_ = [("AceType", BYTE), ("AceFlags", BYTE), ("AceSize", WORD)]


class _NtName:
    """Keep a UTF-16 buffer alive across an NtCreateFile invocation."""

    def __init__(self, value: str) -> None:
        if not value or "\x00" in value:
            raise ValueError("native relative names must be non-empty and NUL-free")
        self.buffer = c.create_unicode_buffer(value)
        length = len(value.encode("utf-16-le"))
        self.string = UNICODE_STRING(
            length,
            length + c.sizeof(c.c_wchar),
            c.cast(self.buffer, c.POINTER(c.c_wchar)),
        )


class _Api:
    """Lazily bound Windows DLL entry points; module import is non-Windows safe."""

    def __init__(self) -> None:
        if os.name != "nt":
            raise RuntimeError("windows native feasibility probes require Windows")
        self.k32 = c.WinDLL("kernel32", use_last_error=True)
        self.advapi = c.WinDLL("advapi32", use_last_error=True)
        self.ntdll = c.WinDLL("ntdll")
        self._bind()

    def _bind(self) -> None:
        self.CreateFileW = self.k32.CreateFileW
        self.CreateFileW.argtypes = [
            c.c_wchar_p,
            DWORD,
            DWORD,
            PVOID,
            DWORD,
            DWORD,
            HANDLE,
        ]
        self.CreateFileW.restype = HANDLE
        self.CloseHandle = self.k32.CloseHandle
        self.CloseHandle.argtypes = [HANDLE]
        self.CloseHandle.restype = BOOL
        self.GetFileInformationByHandle = self.k32.GetFileInformationByHandle
        self.GetFileInformationByHandle.argtypes = [
            HANDLE,
            c.POINTER(BY_HANDLE_FILE_INFORMATION),
        ]
        self.GetFileInformationByHandle.restype = BOOL
        self.GetFileInformationByHandleEx = self.k32.GetFileInformationByHandleEx
        self.GetFileInformationByHandleEx.argtypes = [HANDLE, c.c_int, PVOID, DWORD]
        self.GetFileInformationByHandleEx.restype = BOOL
        self.GetFileType = self.k32.GetFileType
        self.GetFileType.argtypes = [HANDLE]
        self.GetFileType.restype = DWORD
        self.WriteFile = self.k32.WriteFile
        self.WriteFile.argtypes = [HANDLE, PVOID, DWORD, c.POINTER(DWORD), PVOID]
        self.WriteFile.restype = BOOL
        self.ReadFile = self.k32.ReadFile
        self.ReadFile.argtypes = [HANDLE, PVOID, DWORD, c.POINTER(DWORD), PVOID]
        self.ReadFile.restype = BOOL
        self.SetFilePointerEx = self.k32.SetFilePointerEx
        self.SetFilePointerEx.argtypes = [
            HANDLE,
            c.c_longlong,
            c.POINTER(c.c_longlong),
            DWORD,
        ]
        self.SetFilePointerEx.restype = BOOL
        self.LockFileEx = self.k32.LockFileEx
        self.LockFileEx.argtypes = [
            HANDLE,
            DWORD,
            DWORD,
            DWORD,
            DWORD,
            c.POINTER(OVERLAPPED),
        ]
        self.LockFileEx.restype = BOOL
        self.UnlockFileEx = self.k32.UnlockFileEx
        self.UnlockFileEx.argtypes = [
            HANDLE,
            DWORD,
            DWORD,
            DWORD,
            c.POINTER(OVERLAPPED),
        ]
        self.UnlockFileEx.restype = BOOL
        self.GetCurrentProcess = self.k32.GetCurrentProcess
        self.GetCurrentProcess.argtypes = []
        self.GetCurrentProcess.restype = HANDLE
        self.LocalFree = self.k32.LocalFree
        self.LocalFree.argtypes = [HANDLE]
        self.LocalFree.restype = HANDLE

        self.NtCreateFile = self.ntdll.NtCreateFile
        self.NtCreateFile.argtypes = [
            PHANDLE,
            ULONG,
            c.POINTER(OBJECT_ATTRIBUTES),
            c.POINTER(IO_STATUS_BLOCK),
            PVOID,
            ULONG,
            ULONG,
            ULONG,
            ULONG,
            PVOID,
            ULONG,
        ]
        self.NtCreateFile.restype = NTSTATUS
        self.NtSetInformationFile = self.ntdll.NtSetInformationFile
        self.NtSetInformationFile.argtypes = [
            HANDLE,
            c.POINTER(IO_STATUS_BLOCK),
            PVOID,
            ULONG,
            c.c_int,
        ]
        self.NtSetInformationFile.restype = NTSTATUS

        self.OpenProcessToken = self.advapi.OpenProcessToken
        self.OpenProcessToken.argtypes = [HANDLE, DWORD, PHANDLE]
        self.OpenProcessToken.restype = BOOL
        self.GetTokenInformation = self.advapi.GetTokenInformation
        self.GetTokenInformation.argtypes = [
            HANDLE,
            c.c_int,
            PVOID,
            DWORD,
            c.POINTER(DWORD),
        ]
        self.GetTokenInformation.restype = BOOL
        self.ConvertSidToStringSidW = self.advapi.ConvertSidToStringSidW
        self.ConvertSidToStringSidW.argtypes = [PVOID, c.POINTER(c.c_wchar_p)]
        self.ConvertSidToStringSidW.restype = BOOL
        self.ConvertStringSecurityDescriptorToSecurityDescriptorW = (
            self.advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW
        )
        self.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
            c.c_wchar_p,
            DWORD,
            c.POINTER(PVOID),
            c.POINTER(DWORD),
        ]
        self.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = BOOL
        self.GetSecurityDescriptorDacl = self.advapi.GetSecurityDescriptorDacl
        self.GetSecurityDescriptorDacl.argtypes = [
            PVOID,
            c.POINTER(BOOL),
            c.POINTER(PVOID),
            c.POINTER(BOOL),
        ]
        self.GetSecurityDescriptorDacl.restype = BOOL
        self.GetSecurityDescriptorControl = self.advapi.GetSecurityDescriptorControl
        self.GetSecurityDescriptorControl.argtypes = [
            PVOID,
            c.POINTER(USHORT),
            c.POINTER(DWORD),
        ]
        self.GetSecurityDescriptorControl.restype = BOOL
        self.SetSecurityInfo = self.advapi.SetSecurityInfo
        self.SetSecurityInfo.argtypes = [
            HANDLE,
            c.c_int,
            DWORD,
            PVOID,
            PVOID,
            PVOID,
            PVOID,
        ]
        self.SetSecurityInfo.restype = DWORD
        self.GetSecurityInfo = self.advapi.GetSecurityInfo
        self.GetSecurityInfo.argtypes = [
            HANDLE,
            c.c_int,
            DWORD,
            c.POINTER(PVOID),
            c.POINTER(PVOID),
            c.POINTER(PVOID),
            c.POINTER(PVOID),
            c.POINTER(PVOID),
        ]
        self.GetSecurityInfo.restype = DWORD
        self.GetAclInformation = self.advapi.GetAclInformation
        self.GetAclInformation.argtypes = [PVOID, PVOID, DWORD, c.c_int]
        self.GetAclInformation.restype = BOOL
        self.GetAce = self.advapi.GetAce
        self.GetAce.argtypes = [PVOID, DWORD, c.POINTER(PVOID)]
        self.GetAce.restype = BOOL


_API: _Api | None = None


def _api() -> _Api:
    global _API
    if _API is None:
        _API = _Api()
    return _API


def _last_error(action: str) -> OSError:
    return OSError(c.get_last_error(), f"{action}: {c.WinError(c.get_last_error())}")


def _check_bool(ok: int, action: str) -> None:
    if not ok:
        raise _last_error(action)


def _status_hex(status: int) -> str:
    return f"0x{status & 0xFFFFFFFF:08X}"


class _NtError(OSError):
    def __init__(self, status: int, action: str) -> None:
        self.status = status & 0xFFFFFFFF
        super().__init__(f"{action} failed with NTSTATUS {_status_hex(status)}")


class _ReparseRefused(PermissionError):
    def __init__(self, tag: int) -> None:
        self.tag = tag
        super().__init__("internal reparse point refused without following")


def _check_status(status: int, action: str) -> None:
    if status != 0:
        raise _NtError(status, action)


def _close(handle: HANDLE) -> None:
    value, handle.value = handle.value, None
    if value not in (None, INVALID_HANDLE_VALUE):
        _check_bool(_api().CloseHandle(HANDLE(value)), "CloseHandle")


def _open_startup_directory(path: Path, access: int = DIRECTORY_ACCESS) -> HANDLE:
    """Acquire and validate the one trusted startup directory."""
    handle = HANDLE(
        _api().CreateFileW(
            str(path),
            access,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            None,
            OPEN_EXISTING,
            0x02000000,
            None,
        )
    )
    if handle.value == INVALID_HANDLE_VALUE:
        raise _last_error("CreateFileW startup directory")
    try:
        observed = _identity(handle)
        if (
            not observed["directory"]
            or not observed["disk_file"]
            or observed["reparse"]
        ):
            raise PermissionError("startup object is not a non-reparse disk directory")
        return handle
    except BaseException:
        _close(handle)
        raise


def _open_relative(
    parent: HANDLE,
    name: str,
    disposition: int,
    *,
    directory: bool = False,
    access: int = GENERIC_ALL | SYNCHRONIZE,
    security_descriptor: PVOID | None = None,
) -> HANDLE:
    """Open only beneath a retained directory handle, refusing reparse traversal."""
    native_name = _NtName(name)
    attributes = OBJECT_ATTRIBUTES(
        c.sizeof(OBJECT_ATTRIBUTES),
        parent,
        c.pointer(native_name.string),
        OBJ_CASE_INSENSITIVE | OBJ_DONT_REPARSE,
        security_descriptor,
        None,
    )
    iosb = IO_STATUS_BLOCK()
    result = HANDLE()
    options = FILE_SYNCHRONOUS_IO_NONALERT | FILE_OPEN_REPARSE_POINT
    if directory:
        options |= FILE_DIRECTORY_FILE
    status = _api().NtCreateFile(
        c.byref(result),
        access,
        c.byref(attributes),
        c.byref(iosb),
        None,
        FILE_ATTRIBUTE_DIRECTORY if directory else FILE_ATTRIBUTE_NORMAL,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        disposition,
        options,
        None,
        0,
    )
    _check_status(status, "NtCreateFile relative")
    try:
        observed = _identity(result)
        if observed["reparse"]:
            raise _ReparseRefused(t.cast(int, observed["reparse_tag"]))
        if not observed["disk_file"] or observed["directory"] != directory:
            raise PermissionError("relative object has an unexpected native type")
        return result
    except BaseException:
        _close(result)
        raise


def _make_dir(parent: HANDLE, name: str) -> HANDLE:
    return _open_relative(
        parent, name, FILE_CREATE, directory=True, access=DIRECTORY_ACCESS
    )


def _write(handle: HANDLE, value: bytes) -> None:
    data = c.create_string_buffer(value)
    written = DWORD()
    _check_bool(
        _api().WriteFile(handle, data, len(value), c.byref(written), None), "WriteFile"
    )
    if written.value != len(value):
        raise OSError(f"WriteFile made a short write ({written.value}/{len(value)})")


def _append(handle: HANDLE, value: bytes) -> None:
    offset = c.c_longlong()
    _check_bool(
        _api().SetFilePointerEx(handle, 0, c.byref(offset), FILE_END),
        "SetFilePointerEx(FILE_END)",
    )
    _write(handle, value)


def _read(handle: HANDLE) -> bytes:
    offset = c.c_longlong()
    _check_bool(
        _api().SetFilePointerEx(handle, 0, c.byref(offset), 0), "SetFilePointerEx"
    )
    info = FILE_STANDARD_INFO()
    _check_bool(
        _api().GetFileInformationByHandleEx(handle, 1, c.byref(info), c.sizeof(info)),
        "GetFileInformationByHandleEx(FileStandardInfo)",
    )
    data = c.create_string_buffer(info.EndOfFile)
    got = DWORD()
    _check_bool(
        _api().ReadFile(handle, data, info.EndOfFile, c.byref(got), None), "ReadFile"
    )
    return data.raw[: got.value]


def _identity(handle: HANDLE) -> dict[str, int | bool]:
    basic = BY_HANDLE_FILE_INFORMATION()
    standard = FILE_STANDARD_INFO()
    tag = FILE_ATTRIBUTE_TAG_INFO()
    api = _api()
    _check_bool(
        api.GetFileInformationByHandle(handle, c.byref(basic)),
        "GetFileInformationByHandle",
    )
    _check_bool(
        api.GetFileInformationByHandleEx(
            handle, 1, c.byref(standard), c.sizeof(standard)
        ),
        "GetFileInformationByHandleEx(FileStandardInfo)",
    )
    _check_bool(
        api.GetFileInformationByHandleEx(handle, 9, c.byref(tag), c.sizeof(tag)),
        "GetFileInformationByHandleEx(FileAttributeTagInfo)",
    )
    disk = api.GetFileType(handle) == FILE_TYPE_DISK
    return {
        "volume": basic.VolumeSerialNumber,
        "file_index": (basic.FileIndexHigh << 32) | basic.FileIndexLow,
        "links": standard.NumberOfLinks,
        "directory": bool(standard.Directory),
        "disk_file": disk,
        "reparse": bool(tag.FileAttributes & FILE_ATTRIBUTE_REPARSE_POINT),
        "reparse_tag": tag.ReparseTag,
    }


def _assert_private_regular(handle: HANDLE) -> dict[str, object]:
    observed = _identity(handle)
    if (
        observed["directory"]
        or not observed["disk_file"]
        or observed["reparse"]
        or observed["links"] != 1
    ):
        raise PermissionError("leaf is not regular, single-link and non-reparse")
    private, dacl = _dacl_private(handle)
    if not private:
        raise PermissionError("leaf DACL is not conservatively private")
    return {"identity": observed, "dacl": dacl}


def _current_sid() -> str:
    api = _api()
    token = HANDLE()
    _check_bool(
        api.OpenProcessToken(api.GetCurrentProcess(), TOKEN_QUERY, c.byref(token)),
        "OpenProcessToken",
    )
    try:
        size = DWORD()
        api.GetTokenInformation(token, TOKEN_USER, None, 0, c.byref(size))
        if c.get_last_error() != ERROR_INSUFFICIENT_BUFFER:
            raise _last_error("GetTokenInformation size")
        buffer = c.create_string_buffer(size.value)
        _check_bool(
            api.GetTokenInformation(token, TOKEN_USER, buffer, size, c.byref(size)),
            "GetTokenInformation",
        )
        user = c.cast(buffer, c.POINTER(TOKEN_USER_DATA)).contents
        text = c.c_wchar_p()
        _check_bool(
            api.ConvertSidToStringSidW(user.Sid, c.byref(text)),
            "ConvertSidToStringSidW",
        )
        try:
            return text.value
        finally:
            api.LocalFree(c.cast(text, HANDLE))
    finally:
        _close(token)


def _set_sddl_dacl(handle: HANDLE, sddl: str, *, protected: bool = True) -> None:
    api = _api()
    descriptor = PVOID()
    _check_bool(
        api.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            sddl, 1, c.byref(descriptor), None
        ),
        "ConvertStringSecurityDescriptorToSecurityDescriptorW",
    )
    try:
        present = BOOL()
        defaulted = BOOL()
        dacl = PVOID()
        _check_bool(
            api.GetSecurityDescriptorDacl(
                descriptor, c.byref(present), c.byref(dacl), c.byref(defaulted)
            ),
            "GetSecurityDescriptorDacl",
        )
        if not present.value:
            raise PermissionError(
                "constructed private descriptor unexpectedly lacks a DACL"
            )
        information = DACL_SECURITY_INFORMATION
        if protected:
            information |= PROTECTED_DACL_SECURITY_INFORMATION
        status = api.SetSecurityInfo(
            handle, SE_FILE_OBJECT, information, None, None, dacl, None
        )
        if status:
            raise OSError(status, "SetSecurityInfo(DACL)")
    finally:
        api.LocalFree(c.cast(descriptor, HANDLE))


def _private_descriptor() -> tuple[PVOID, str]:
    sid = _current_sid()
    descriptor = PVOID()
    _check_bool(
        _api().ConvertStringSecurityDescriptorToSecurityDescriptorW(
            f"O:{sid}D:P(A;;FA;;;SY)(A;;FA;;;{sid})",
            1,
            c.byref(descriptor),
            None,
        ),
        "ConvertStringSecurityDescriptorToSecurityDescriptorW(private create)",
    )
    return descriptor, sid


def _sid_text(sid: PVOID) -> str:
    text = c.c_wchar_p()
    _check_bool(
        _api().ConvertSidToStringSidW(sid, c.byref(text)), "ConvertSidToStringSidW ACE"
    )
    try:
        return text.value
    finally:
        _api().LocalFree(c.cast(text, HANDLE))


def _dacl_private(handle: HANDLE) -> tuple[bool, dict[str, object]]:
    """Narrow effective policy: protected current-user/SYSTEM full-control DACL."""
    descriptor = PVOID()
    dacl = PVOID()
    owner, group = PVOID(), PVOID()
    status = _api().GetSecurityInfo(
        handle,
        SE_FILE_OBJECT,
        DACL_SECURITY_INFORMATION | 0x1 | 0x2,
        c.byref(owner),
        c.byref(group),
        c.byref(dacl),
        None,
        c.byref(descriptor),
    )
    if status:
        raise OSError(status, "GetSecurityInfo(DACL)")
    try:
        control = USHORT()
        revision = DWORD()
        _check_bool(
            _api().GetSecurityDescriptorControl(
                descriptor, c.byref(control), c.byref(revision)
            ),
            "GetSecurityDescriptorControl",
        )
        if not dacl:
            return False, {
                "scope": "protected-current-user-and-system-full-control",
                "reason": "null DACL",
            }
        info = ACL_SIZE_INFORMATION_DATA()
        _check_bool(
            _api().GetAclInformation(
                dacl, c.byref(info), c.sizeof(info), ACL_SIZE_INFORMATION
            ),
            "GetAclInformation",
        )
        current_sid = _current_sid()
        owner_sid = _sid_text(owner) if owner.value else None
        permitted = {current_sid, "S-1-5-18"}
        allow_sids: list[str] = []
        masks: list[int] = []
        ace_flags: list[int] = []
        rejected: list[str] = []
        for index in range(info.AceCount):
            ace = PVOID()
            _check_bool(_api().GetAce(dacl, index, c.byref(ace)), "GetAce")
            header = c.cast(ace, c.POINTER(ACE_HEADER)).contents
            ace_flags.append(header.AceFlags)
            if header.AceType != ACCESS_ALLOWED_ACE_TYPE:
                rejected.append(f"ace-type-{header.AceType}")
                continue
            mask = c.cast(
                PVOID(ace.value + c.sizeof(ACE_HEADER)), c.POINTER(DWORD)
            ).contents.value
            sid_pointer = PVOID(ace.value + c.sizeof(ACE_HEADER) + c.sizeof(DWORD))
            sid = _sid_text(sid_pointer)
            allow_sids.append(sid)
            masks.append(mask)
            if sid not in permitted or mask != FILE_ALL_ACCESS:
                rejected.append(f"{sid}:0x{mask:08X}")
        protected = bool(control.value & SE_DACL_PROTECTED)
        private = (
            owner_sid == current_sid
            and protected
            and not rejected
            and set(allow_sids) == permitted
            and len(allow_sids) == 2
        )
        return private, {
            "scope": "protected-current-user-and-system-full-control",
            "owner_sid": owner_sid,
            "group_sid": _sid_text(group) if group.value else None,
            "protected": protected,
            "allow_sids": allow_sids,
            "masks": masks,
            "ace_flags": ace_flags,
            "rejected": rejected,
        }
    finally:
        _api().LocalFree(c.cast(descriptor, HANDLE))


def _new_private_file(
    parent: HANDLE, name: str, payload: bytes
) -> tuple[HANDLE, dict[str, object]]:
    descriptor, sid = _private_descriptor()
    try:
        handle = _open_relative(
            parent, name, FILE_CREATE, security_descriptor=descriptor
        )
    finally:
        _api().LocalFree(c.cast(descriptor, HANDLE))
    try:
        facts = _assert_private_regular(handle)
        _write(handle, payload)
        facts["owner_sid"] = sid
        facts["acl_applied_in_create"] = True
        return handle, facts
    except BaseException:
        try:
            _delete_on_handle(handle)
        finally:
            _close(handle)
        raise


def _delete_on_handle(handle: HANDLE) -> None:
    info = FILE_DISPOSITION_INFORMATION(1)
    iosb = IO_STATUS_BLOCK()
    status = _api().NtSetInformationFile(
        handle,
        c.byref(iosb),
        c.byref(info),
        c.sizeof(info),
        FILE_DISPOSITION_INFORMATION_CLASS,
    )
    _check_status(status, "NtSetInformationFile(FileDispositionInformation)")


def _rename_on_handle(
    handle: HANDLE, destination_parent: HANDLE, destination_name: str, replace: bool
) -> None:
    encoded = destination_name.encode("utf-16-le")
    size = FILE_RENAME_INFORMATION_FIXED.FileName.offset + len(encoded)
    buffer = c.create_string_buffer(size)
    fixed = c.cast(buffer, c.POINTER(FILE_RENAME_INFORMATION_FIXED)).contents
    fixed.ReplaceIfExists = 1 if replace else 0
    fixed.RootDirectory = destination_parent
    fixed.FileNameLength = len(encoded)
    c.memmove(
        c.addressof(buffer) + FILE_RENAME_INFORMATION_FIXED.FileName.offset,
        encoded,
        len(encoded),
    )
    iosb = IO_STATUS_BLOCK()
    status = _api().NtSetInformationFile(
        handle, c.byref(iosb), buffer, size, FILE_RENAME_INFORMATION
    )
    _check_status(status, "NtSetInformationFile(FileRenameInformation)")


def _link_on_handle(
    handle: HANDLE, destination_parent: HANDLE, destination_name: str
) -> None:
    encoded = destination_name.encode("utf-16-le")
    size = FILE_RENAME_INFORMATION_FIXED.FileName.offset + len(encoded)
    buffer = c.create_string_buffer(size)
    fixed = c.cast(buffer, c.POINTER(FILE_RENAME_INFORMATION_FIXED)).contents
    fixed.ReplaceIfExists = 0
    fixed.RootDirectory = destination_parent
    fixed.FileNameLength = len(encoded)
    c.memmove(
        c.addressof(buffer) + FILE_RENAME_INFORMATION_FIXED.FileName.offset,
        encoded,
        len(encoded),
    )
    iosb = IO_STATUS_BLOCK()
    status = _api().NtSetInformationFile(
        handle, c.byref(iosb), buffer, size, FILE_LINK_INFORMATION
    )
    _check_status(status, "NtSetInformationFile(FileLinkInformation)")


def _exists_relative(parent: HANDLE, name: str, *, directory: bool = False) -> bool:
    try:
        handle = _open_relative(
            parent,
            name,
            FILE_OPEN,
            directory=directory,
            access=GENERIC_READ | SYNCHRONIZE,
        )
    except _NtError as error:
        if error.status in {STATUS_OBJECT_NAME_NOT_FOUND, STATUS_OBJECT_PATH_NOT_FOUND}:
            return False
        raise
    try:
        if not directory:
            _assert_private_regular(handle)
    except BaseException:
        _close(handle)
        raise
    _close(handle)
    return True


def _open_and_read(parent: HANDLE, name: str) -> bytes:
    handle = _open_private(parent, name, access=GENERIC_READ | SYNCHRONIZE)
    try:
        return _read(handle)
    finally:
        _close(handle)


def _junction(link: Path, target: Path) -> None:
    result = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    if result.returncode:
        raise OSError(f"mklink /J failed: {result.stdout} {result.stderr}")


def _open_private(
    parent: HANDLE, name: str, *, access: int = GENERIC_ALL | SYNCHRONIZE
) -> HANDLE:
    handle = _open_relative(parent, name, FILE_OPEN, access=access)
    try:
        _assert_private_regular(handle)
        return handle
    except BaseException:
        _close(handle)
        raise


def _file_id(handle: HANDLE) -> tuple[int, int]:
    facts = _identity(handle)
    return (t.cast(int, facts["volume"]), t.cast(int, facts["file_index"]))


def _snapshot(parent: HANDLE, name: str) -> dict[str, object]:
    handle = _open_private(parent, name, access=GENERIC_READ | SYNCHRONIZE)
    try:
        basic = BY_HANDLE_FILE_INFORMATION()
        _check_bool(
            _api().GetFileInformationByHandle(handle, c.byref(basic)),
            "snapshot metadata",
        )
        return {
            "facts": _assert_private_regular(handle),
            "content": _read(handle).hex(),
            "attributes": basic.FileAttributes,
            "created": (basic.CreationTimeHigh << 32) | basic.CreationTimeLow,
            "written": (basic.LastWriteTimeHigh << 32) | basic.LastWriteTimeLow,
        }
    finally:
        _close(handle)


def _directory_policy(handle: HANDLE) -> dict[str, object]:
    _, acl = _dacl_private(handle)
    return {"identity": _file_id(handle), "acl": acl}


def _refused(
    action: Callable[[], object],
    *,
    expected: type[Exception],
    codes: tuple[int, ...] = (),
) -> str:
    try:
        action()
    except expected as error:
        actual = (
            error.status
            if isinstance(error, _NtError)
            else getattr(error, "errno", None)
        )
        if codes and actual not in codes:
            raise AssertionError("unexpected native refusal code") from error
        return f"{type(error).__name__}:{actual}"
    raise AssertionError("unsafe operation was accepted")


def _cleanup_owned(parent: HANDLE, name: str, owned: HANDLE) -> None:
    named = _open_private(parent, name, access=GENERIC_READ | SYNCHRONIZE)
    try:
        _assert_private_regular(owned)
        if _file_id(named) != _file_id(owned):
            raise PermissionError("cleanup entry identity changed")
    finally:
        _close(named)
    _delete_on_handle(owned)


def _publish_file(
    parent: HANDLE, name: str, payload: bytes
) -> tuple[HANDLE, dict[str, object]]:
    temporary = f".record.{secrets.token_hex(16)}.tmp"
    handle, facts = _new_private_file(parent, temporary, payload)
    try:
        _rename_on_handle(handle, parent, name, replace=False)
        return handle, facts
    except BaseException:
        try:
            _cleanup_owned(parent, temporary, handle)
        finally:
            _close(handle)
        raise


def _key_layout(key: str) -> tuple[str | None, str]:
    parts = key.split(".")
    if any(re.fullmatch(r"[a-z0-9_]+", part) is None for part in parts):
        raise ValueError("invalid key segments")
    return (
        (None, f"{parts[0]}.yaml")
        if len(parts) == 1
        else (parts[0], "-".join(parts[1:]) + ".yaml")
    )


@contextmanager
def _layout_parent(root: HANDLE, key: str) -> t.Iterator[tuple[HANDLE, str]]:
    namespace, leaf = _key_layout(key)
    if namespace is None:
        yield root, leaf
        return
    try:
        directory = _make_dir(root, namespace)
    except _NtError as error:
        if error.status != STATUS_OBJECT_NAME_COLLISION:
            raise
        directory = _open_relative(
            root, namespace, FILE_OPEN, directory=True, access=DIRECTORY_ACCESS
        )
    try:
        yield directory, leaf
    finally:
        _close(directory)


def _scenario_root_pinning(root: Path) -> dict[str, object]:
    fixture = root / "root-pinning"
    fixture.mkdir()
    physical, alternate = fixture / "physical", fixture / "alternate"
    physical.mkdir()
    alternate.mkdir()
    first, second = physical / "store", alternate / "store"
    first.mkdir()
    second.mkdir()
    with ExitStack() as resources:
        setup = _open_startup_directory(fixture)
        resources.callback(_close, setup)
        ordinary, _ = _new_private_file(setup, "ordinary", b"not-a-directory")
        _close(ordinary)
        before = _snapshot(setup, "ordinary")
        missing = _refused(
            lambda: _open_startup_directory(fixture / "missing"),
            expected=OSError,
            codes=(2, 3),
        )
        invalid = _refused(
            lambda: _open_startup_directory(fixture / "ordinary"),
            expected=PermissionError,
        )
        if _exists_relative(setup, "missing") or _snapshot(setup, "ordinary") != before:
            raise AssertionError(
                "invalid startup selection created or repaired its target"
            )
        a, b = _open_startup_directory(first), _open_startup_directory(second)
        resources.callback(_close, a)
        resources.callback(_close, b)
        sentinel, _ = _new_private_file(b, "sentinel", b"outside-retained-root")
        _close(sentinel)
        outside_before = _snapshot(b, "sentinel")
        ancestor, alias = fixture / "ancestor", fixture / "alias"
        _junction(ancestor, physical)
        _junction(alias, ancestor / "store")
        pinned = _open_startup_directory(alias)
        resources.callback(_close, pinned)
        if _file_id(pinned) != _file_id(a):
            raise AssertionError("linked root did not select the direct directory")
        os.rmdir(alias)
        _junction(alias, second)
        final, _ = _publish_file(pinned, "final.bin", b"final-pinned")
        _close(final)
        os.rmdir(alias)
        _junction(alias, ancestor / "store")
        os.rmdir(ancestor)
        _junction(ancestor, alternate)
        linked, _ = _publish_file(pinned, "ancestor.bin", b"ancestor-pinned")
        _close(linked)
        newer = _open_startup_directory(alias)
        resources.callback(_close, newer)
        if _file_id(newer) != _file_id(b):
            raise AssertionError("new instance did not select retargeted root")
        if (
            _open_and_read(a, "final.bin") != b"final-pinned"
            or _open_and_read(a, "ancestor.bin") != b"ancestor-pinned"
            or _exists_relative(b, "final.bin")
            or _exists_relative(b, "ancestor.bin")
            or _snapshot(b, "sentinel") != outside_before
        ):
            raise AssertionError("retargeting redirected retained-root operations")
        return {
            "mechanism": "trusted final/ancestor junction selection then retained RootDirectory",
            "missing_refusal": missing,
            "non_directory_refusal": invalid,
            "checks": {
                name: True
                for name in (
                    "direct",
                    "linked_final",
                    "linked_ancestor",
                    "retarget_existing",
                    "retarget_new",
                    "missing",
                    "non_directory",
                )
            },
        }


def _scenario_namespace_inheritance_and_layouts(root: Path) -> dict[str, object]:
    fixture = root / "namespace-layout"
    fixture.mkdir()
    with ExitStack() as resources:
        parent = _open_startup_directory(fixture, access=GENERIC_ALL)
        resources.callback(_close, parent)
        sid = _current_sid()
        _set_sddl_dacl(
            parent, f"D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;{sid})(A;OICI;GR;;;WD)"
        )
        _close(parent)
        parent = _open_startup_directory(fixture)
        resources.callback(_close, parent)
        policy = _directory_policy(parent)
        layouts = {}
        for key, expected_path in (
            ("one", "one.yaml"),
            ("domain.stem", "domain/stem.yaml"),
            ("domain.middle.leaf", "domain/middle-leaf.yaml"),
        ):
            with _layout_parent(parent, key) as (directory, leaf):
                handle, _ = _publish_file(directory, leaf, key.encode())
                _close(handle)
                if _open_and_read(directory, leaf) != key.encode():
                    raise AssertionError("native key layout selected wrong payload")
                namespace, mapped = _key_layout(key)
                actual = mapped if namespace is None else f"{namespace}/{mapped}"
                if actual != expected_path:
                    raise AssertionError("native key layout differs from M1")
                layouts[key] = actual
        entries = sorted(path.name for path in fixture.iterdir())
        for invalid in ("", "UPPER", "a/b", "a..b", "a-b"):
            _refused(lambda invalid=invalid: _key_layout(invalid), expected=ValueError)
        if sorted(path.name for path in fixture.iterdir()) != entries:
            raise AssertionError("invalid key created native entries")
        routes = {}
        for route in ("set", "delete", "transaction"):
            key = f"{route}_first.item"
            with _layout_parent(parent, key) as (directory, leaf):
                before = _directory_policy(directory)
                if not any(flag & 0x10 for flag in before["acl"]["ace_flags"]):
                    raise AssertionError("namespace did not inherit application ACEs")
                with _layout_parent(parent, f"{route}_first.existing"):
                    pass
                if route == "set":
                    handle, _ = _publish_file(directory, leaf, b"record")
                else:
                    handle, _ = _new_private_file(directory, f".{leaf}.{route}", b"")
                try:
                    if route == "transaction":
                        if not _lock(handle, fail_immediately=True):
                            raise AssertionError("new first-use lock was already held")
                        _unlock(handle)
                    elif route == "delete" and _exists_relative(directory, leaf):
                        raise AssertionError("first-use delete created a credential")
                finally:
                    _close(handle)
                if _directory_policy(directory) != before:
                    raise AssertionError("existing namespace policy was repaired")
                routes[route] = before
        if _directory_policy(parent) != policy:
            raise AssertionError(
                "native child operations modified application root policy"
            )
        return {
            "layouts": layouts,
            "first_use_routes": routes,
            "checks": {
                name: True
                for name in (
                    "layouts",
                    "invalid_keys",
                    "set_first_use",
                    "delete_first_use",
                    "transaction_first_use",
                    "existing_policy",
                    "inherited_policy",
                )
            },
        }


def _expect_reparse(operation: Callable[[], object], tag: int) -> dict[str, object]:
    try:
        result = operation()
    except _ReparseRefused as error:
        if error.tag != tag:
            raise AssertionError("opened reparse tag differs from planted fixture")
        return {
            "mechanism": "FILE_OPEN_REPARSE_POINT then handle-tag refusal",
            "tag": tag,
        }
    except _NtError as error:
        if error.status not in (
            STATUS_REPARSE_POINT_ENCOUNTERED,
            STATUS_STOPPED_ON_SYMLINK,
        ):
            raise
        return {
            "mechanism": "OBJ_DONT_REPARSE traversal refusal",
            "status": _status_hex(error.status),
            "fixture_tag": tag,
        }
    if isinstance(result, HANDLE):
        _close(result)
    raise AssertionError("internal reparse entry was accepted")


def _scenario_redirect_refusal(root: Path) -> dict[str, object]:
    fixture = root / "redirect-refusal"
    fixture.mkdir()
    store, outside = fixture / "store", fixture / "outside"
    store.mkdir()
    outside.mkdir()
    with ExitStack() as resources:
        parent = _open_startup_directory(store)
        target = _open_startup_directory(outside)
        resources.callback(_close, parent)
        resources.callback(_close, target)
        sentinel, _ = _new_private_file(target, "sentinel", b"outside-unchanged")
        _close(sentinel)
        before = _snapshot(target, "sentinel")
        observations = {}
        for surface in ("namespace", "credential", "temp", "marker", "lock"):
            name = f"{surface}.entry"
            link = store / name
            _junction(link, outside)
            try:
                tag = os.lstat(link).st_reparse_tag
                if tag != 0xA0000003:
                    raise AssertionError(
                        "junction fixture has an unexpected native tag"
                    )
                relative = name + "\\sentinel" if surface == "namespace" else name
                observations[surface] = _expect_reparse(
                    lambda relative=relative: _open_private(parent, relative), tag
                )
                if _snapshot(target, "sentinel") != before:
                    raise AssertionError("reparse refusal changed outside sentinel")
            finally:
                os.rmdir(link)
        for name, target_path, directory in (
            ("file-symbolic", outside / "sentinel", False),
            ("directory-symbolic", outside, True),
        ):
            link = store / name
            try:
                os.symlink(target_path, link, target_is_directory=directory)
            except OSError as error:
                if error.winerror not in (50, 1314):
                    raise
                return {
                    "status": "blocked",
                    "reason": "native symbolic-link fixture unavailable",
                    "winerror": error.winerror,
                    "observed_refusals": observations,
                }
            tag = os.lstat(link).st_reparse_tag
            if tag != 0xA000000C:
                raise AssertionError(
                    "symbolic-link fixture has an unexpected native tag"
                )
            observations[name] = _expect_reparse(
                lambda name=name, directory=directory: _open_relative(
                    parent, name, FILE_OPEN, directory=directory
                ),
                tag,
            )
            if directory:
                observations["symbolic-ancestor"] = _expect_reparse(
                    lambda: _open_private(parent, name + "\\sentinel"), tag
                )
            if _snapshot(target, "sentinel") != before:
                raise AssertionError("symbolic-link refusal changed outside sentinel")
        owned, _ = _new_private_file(parent, "substitution.bin", b"owned")
        resources.callback(_close, owned)
        _rename_on_handle(owned, parent, "detached-owned.bin", replace=False)
        substituted = store / "substitution.bin"
        _junction(substituted, outside)
        observations["substitution"] = _expect_reparse(
            lambda: _cleanup_owned(parent, "substitution.bin", owned),
            os.lstat(substituted).st_reparse_tag,
        )
        if _snapshot(target, "sentinel") != before:
            raise AssertionError("substitution refusal changed outside sentinel")
        outside_lock = _open_private(target, "sentinel")
        try:
            if not _lock(outside_lock, fail_immediately=True):
                raise AssertionError("internal refusal retained an outside lock")
            _unlock(outside_lock)
        finally:
            _close(outside_lock)
        return {
            "reparse_kinds": [
                "mount-point junction",
                "file symbolic link",
                "directory symbolic link",
            ],
            "observations": observations,
            "checks": {
                name: True
                for name in (
                    "namespace",
                    "credential",
                    "temp",
                    "marker",
                    "lock",
                    "substitution",
                    "outside_unchanged",
                )
            },
        }


def _scenario_object_privacy(root: Path) -> dict[str, object]:
    fixture = root / "object-privacy"
    fixture.mkdir()
    with ExitStack() as resources:
        parent = _open_startup_directory(fixture)
        resources.callback(_close, parent)
        policy = _directory_policy(parent)
        leaf, facts = _new_private_file(parent, "private.bin", b"private")
        resources.callback(_close, leaf)
        exposed, _ = _new_private_file(parent, "exposed.bin", b"")
        resources.callback(_close, exposed)
        _set_sddl_dacl(exposed, "D:P(A;;FA;;;WD)")
        exposed_refusal = _refused(
            lambda: _assert_private_regular(exposed), expected=PermissionError
        )
        _link_on_handle(leaf, parent, "private-link.bin")
        hardlink_refusal = _refused(
            lambda: _open_private(parent, "private-link.bin"), expected=PermissionError
        )
        directory = _make_dir(parent, "nonregular")
        resources.callback(_close, directory)
        nonregular_refusal = _refused(
            lambda: _assert_private_regular(directory), expected=PermissionError
        )
        if _directory_policy(parent) != policy:
            raise AssertionError(
                "private leaf operations changed application namespace policy"
            )
        return {
            "private": facts,
            "exposed_refusal": exposed_refusal,
            "hardlink_refusal": hardlink_refusal,
            "nonregular_refusal": nonregular_refusal,
            "special_fixture_scope": "NTFS directory leaf; POSIX FIFO is not an NTFS leaf type",
            "checks": {
                name: True
                for name in (
                    "nonregular",
                    "hardlink",
                    "exposed",
                    "private_before_payload",
                    "namespace_acl_unchanged",
                )
            },
        }


def _precommit_fault(parent: HANDLE, phase: str) -> None:
    payload = json.dumps(
        {"value": object() if phase == "serialization" else "candidate"}
    ).encode()
    name = f".record.{secrets.token_hex(16)}.tmp"
    temporary, _ = _new_private_file(parent, name, b"")
    expected_identity = _file_id(temporary)
    try:
        if phase == "write":
            readonly = _open_private(parent, name, access=GENERIC_READ | SYNCHRONIZE)
            try:
                _write(readonly, payload)
            finally:
                _close(readonly)
        _write(temporary, payload)
        if phase == "close":
            _close(temporary)
            raise OSError(
                errno.EIO, "injected close-boundary error after native release"
            )
        if phase == "replace":
            readonly = _open_private(parent, name, access=GENERIC_READ | SYNCHRONIZE)
            try:
                _rename_on_handle(readonly, parent, "record.bin", replace=True)
            finally:
                _close(readonly)
        raise AssertionError("requested precommit fault was not observed")
    finally:
        if temporary.value is None:
            temporary = _open_private(parent, name)
        try:
            if _file_id(temporary) != expected_identity:
                raise PermissionError("temporary identity changed before cleanup")
            _cleanup_owned(parent, name, temporary)
        finally:
            _close(temporary)


def _scenario_temp_replace_cleanup(root: Path) -> dict[str, object]:
    fixture = root / "temp-replace"
    fixture.mkdir()
    with ExitStack() as resources:
        parent = _open_startup_directory(fixture)
        resources.callback(_close, parent)
        for name, value in (
            ("record.bin", b"old"),
            ("record.marker", b"marker"),
            (".collision.tmp", b"stale"),
        ):
            handle, _ = _new_private_file(parent, name, value)
            _close(handle)
        before = {
            name: _snapshot(parent, name)
            for name in ("record.bin", "record.marker", ".collision.tmp")
        }
        collision = _refused(
            lambda: _new_private_file(parent, ".collision.tmp", b"wrong"),
            expected=_NtError,
            codes=(STATUS_OBJECT_NAME_COLLISION,),
        )
        faults = {}
        for phase, expected, codes in (
            ("serialization", TypeError, ()),
            ("write", OSError, (5,)),
            ("close", OSError, (errno.EIO,)),
            ("replace", _NtError, (STATUS_ACCESS_DENIED,)),
        ):
            faults[phase] = _refused(
                lambda phase=phase: _precommit_fault(parent, phase),
                expected=expected,
                codes=codes,
            )
            if {name: _snapshot(parent, name) for name in before} != before:
                raise AssertionError(
                    "precommit fault changed record, marker or collision"
                )
            if {path.name for path in fixture.iterdir()} != set(before):
                raise AssertionError("precommit fault left an owned temporary")
        name = f".record.{secrets.token_hex(16)}.tmp"
        replacement, _ = _new_private_file(parent, name, b"committed")
        _rename_on_handle(replacement, parent, "record.bin", replace=True)
        _close(replacement)
        marker = _open_private(
            parent, "record.marker", access=GENERIC_READ | SYNCHRONIZE
        )
        try:
            postcommit = _refused(
                lambda: _cleanup_owned(parent, "record.marker", marker),
                expected=_NtError,
                codes=(STATUS_ACCESS_DENIED,),
            )
        finally:
            _close(marker)
        if (
            _open_and_read(parent, "record.bin") != b"committed"
            or _snapshot(parent, "record.marker") != before["record.marker"]
        ):
            raise AssertionError(
                "postcommit cleanup failure misreported committed state"
            )
        owned, _ = _new_private_file(parent, "owned.tmp", b"owned")
        resources.callback(_close, owned)
        _rename_on_handle(owned, parent, "detached-owned.tmp", replace=False)
        intruder, _ = _new_private_file(parent, "owned.tmp", b"intruder")
        _close(intruder)
        substituted = _snapshot(parent, "owned.tmp")
        mismatch = _refused(
            lambda: _cleanup_owned(parent, "owned.tmp", owned), expected=PermissionError
        )
        if _snapshot(parent, "owned.tmp") != substituted:
            raise AssertionError("mismatch cleanup changed the substituted named entry")
        return {
            "collision_refusal": collision,
            "precommit_faults": faults,
            "close_fault_kind": "injected EIO after actual native CloseHandle",
            "postcommit_marker_error": postcommit,
            "mismatch_refusal": mismatch,
            "checks": {
                name: True
                for name in (
                    "exclusive_random",
                    "collision_preserved",
                    "serialization_fault",
                    "write_fault",
                    "close_fault",
                    "replace_fault",
                    "precommit_preserved",
                    "postcommit_failure",
                    "mismatch_preserved",
                )
            },
        }


def _scenario_marker_interruption(root: Path) -> dict[str, object]:
    fixture = root / "marker-interruption"
    fixture.mkdir()
    with ExitStack() as resources:
        parent = _open_startup_directory(fixture)
        resources.callback(_close, parent)
        states = {}
        for phase in ("interruption", "handled", "normal"):
            name, marker_name = f"{phase}.record", f"{phase}.marker"
            record, _ = _new_private_file(parent, name, b"raw-record")
            marker, _ = _new_private_file(parent, marker_name, b"cleared")
            resources.callback(_close, record)
            resources.callback(_close, marker)
            before_record, before_marker = (
                _snapshot(parent, name),
                _snapshot(parent, marker_name),
            )
            if phase == "handled":
                readonly = _open_private(
                    parent, name, access=GENERIC_READ | SYNCHRONIZE
                )
                try:
                    _refused(
                        lambda: _cleanup_owned(parent, name, readonly),
                        expected=_NtError,
                        codes=(STATUS_ACCESS_DENIED,),
                    )
                finally:
                    _close(readonly)
            if phase != "normal":
                if (
                    _snapshot(parent, name) != before_record
                    or _snapshot(parent, marker_name) != before_marker
                ):
                    raise AssertionError(
                        "failed/interrupted delete repaired stored state"
                    )
                states[phase] = {"get": "raw-record", "is_cleared": True}
                continue
            _cleanup_owned(parent, name, record)
            _close(record)
            if (
                _exists_relative(parent, name)
                or _snapshot(parent, marker_name) != before_marker
            ):
                raise AssertionError("normal delete did not retain only the marker")
            states["normal_delete"] = {"get": None, "is_cleared": True}
            recreated, _ = _publish_file(parent, name, b"recreated")
            _close(recreated)
            _cleanup_owned(parent, marker_name, marker)
            _close(marker)
            if (
                _exists_relative(parent, marker_name)
                or _open_and_read(parent, name) != b"recreated"
            ):
                raise AssertionError(
                    "recreate did not clear the marker after publication"
                )
            states["recreate"] = {"get": "recreated", "is_cleared": False}
        return {
            "states": states,
            "checks": {
                name: True
                for name in (
                    "normal_delete",
                    "recreate",
                    "handled_failure",
                    "interruption",
                    "no_repair",
                )
            },
        }


def _lock(handle: HANDLE, fail_immediately: bool) -> bool:
    flags = LOCKFILE_EXCLUSIVE_LOCK | (
        LOCKFILE_FAIL_IMMEDIATELY if fail_immediately else 0
    )
    overlapped = OVERLAPPED()
    ok = _api().LockFileEx(handle, flags, 0, 1, 0, c.byref(overlapped))
    if not ok and c.get_last_error() == ERROR_LOCK_VIOLATION:
        return False
    _check_bool(ok, "LockFileEx")
    return True


def _unlock(handle: HANDLE) -> None:
    overlapped = OVERLAPPED()
    _check_bool(
        _api().UnlockFileEx(handle, 0, 1, 0, c.byref(overlapped)), "UnlockFileEx"
    )


def _bounded_line(
    stream: t.TextIO, timeout: float, process: subprocess.Popen[str]
) -> str:
    result: list[str] = []
    done = threading.Event()

    def read_one() -> None:
        try:
            result.append(stream.readline())
        finally:
            done.set()

    threading.Thread(target=read_one, daemon=True).start()
    if not done.wait(timeout):
        process.kill()
        process.wait(timeout=5)
        raise TimeoutError("lock worker did not reach its deterministic IPC boundary")
    if not result or not result[0]:
        raise RuntimeError("lock worker closed its IPC stream unexpectedly")
    return result[0].strip()


def _scenario_cooperative_locking(root: Path) -> dict[str, object]:
    fixture = root / "cooperative-locking"
    fixture.mkdir()
    with ExitStack() as resources:
        parent = _open_startup_directory(fixture)
        resources.callback(_close, parent)
        record, _ = _new_private_file(parent, "record.bin", b"old")
        _close(record)
        locked, facts = _new_private_file(parent, ".record.lock", b"")
        resources.callback(_close, locked)
        same = _open_private(parent, ".record.lock")
        resources.callback(_close, same)
        invalid, _ = _new_private_file(parent, "invalid.lock", b"")
        resources.callback(_close, invalid)
        _set_sddl_dacl(invalid, "D:P(A;;FA;;;WD)")
        _refused(
            lambda: _open_private(parent, "invalid.lock"), expected=PermissionError
        )
        process = None
        held = False
        try:
            if not _lock(locked, fail_immediately=True):
                raise AssertionError("initial lock acquisition failed")
            held = True
            if _lock(same, fail_immediately=True):
                _unlock(same)
                raise AssertionError(
                    "same-process independent handle bypassed exclusive lock"
                )
            inherited_before = os.get_handle_inheritable(parent.value)
            os.set_handle_inheritable(parent.value, True)
            try:
                startup = subprocess.STARTUPINFO(
                    lpAttributeList={"handle_list": [parent.value]}
                )
                process = subprocess.Popen(
                    [
                        sys.executable,
                        "-I",
                        __file__,
                        "--lock-worker",
                        str(parent.value),
                        ".record.lock",
                    ],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    close_fds=True,
                    startupinfo=startup,
                )
            finally:
                os.set_handle_inheritable(parent.value, inherited_before)
            assert process.stdout is not None and process.stdin is not None
            if _bounded_line(process.stdout, 15, process) != "BLOCKED":
                raise AssertionError("independent process did not observe contention")
            process.stdin.write("ACQUIRE\n")
            process.stdin.flush()
            if _bounded_line(process.stdout, 15, process) != "WAITING":
                raise AssertionError(
                    "same contender did not enter blocking acquisition"
                )
            cleanup, _ = _new_private_file(parent, ".cleanup.tmp", b"cleanup")
            try:
                _cleanup_owned(parent, ".cleanup.tmp", cleanup)
            finally:
                _close(cleanup)
            if _exists_relative(parent, ".cleanup.tmp"):
                raise AssertionError("protected cleanup left the named temporary")
            replacement, _ = _new_private_file(
                parent, f".{secrets.token_hex(16)}.tmp", b"committed"
            )
            try:
                _rename_on_handle(replacement, parent, "record.bin", replace=True)
            finally:
                _close(replacement)
            if _identity(locked) != facts["identity"]:
                raise AssertionError(
                    "credential replacement changed the stable lock object"
                )
            _unlock(locked)
            held = False
            if _bounded_line(process.stdout, 15, process) != "ACQUIRED":
                raise AssertionError(
                    "same contender failed to acquire after owner release"
                )
            process.stdin.write("RELEASE\n")
            process.stdin.flush()
            _, stderr = process.communicate(timeout=15)
            if process.returncode:
                raise RuntimeError(f"native lock worker failed: {stderr}")
            if not _lock(same, fail_immediately=True):
                raise AssertionError(
                    "same-process handle could not acquire after release"
                )
            _unlock(same)
            return {
                "mechanism": "independent LockFileEx handles and inherited pinned directory",
                "checks": {
                    name: True
                    for name in (
                        "independent_process",
                        "same_process",
                        "stable_lock",
                        "invalid_lock",
                        "protected_cleanup",
                    )
                },
            }
        finally:
            try:
                if held:
                    _unlock(locked)
            finally:
                if process is not None:
                    if process.poll() is None:
                        process.kill()
                        process.wait(timeout=5)
                    for stream in (process.stdin, process.stdout, process.stderr):
                        if stream is not None:
                            stream.close()


class _OwnedDirectory:
    """Native ownership model; the application must quiesce users before close."""

    def __init__(self, handle: HANDLE) -> None:
        self._guard = threading.Lock()
        self._handle: HANDLE | None = None
        try:
            facts = _identity(handle)
            if not facts["directory"] or not facts["disk_file"] or facts["reparse"]:
                raise PermissionError("owner root is not a non-reparse disk directory")
        except BaseException:
            _close(handle)
            raise
        self._handle = handle

    def take_for_entry(self) -> HANDLE:
        with self._guard:
            if self._handle is None:
                raise ValueError("owner is closed")
            return self._handle

    def close(self) -> None:
        with self._guard:
            detached, self._handle = self._handle, None
        if detached is not None:
            _close(detached)

    def __enter__(self) -> _OwnedDirectory:
        self.take_for_entry()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass  # Best effort only; explicit close exposes native errors.


class _DeferredDirectoryEntry:
    """Late admission and per-key lock ownership, not ownership of the store."""

    def __init__(self, owner: _OwnedDirectory) -> None:
        self._owner = owner
        self._lock: HANDLE | None = None

    def __enter__(self) -> HANDLE:
        parent = self._owner.take_for_entry()
        handle = _open_private(parent, ".lifecycle.lock")
        try:
            if not _lock(handle, fail_immediately=False):
                raise AssertionError("deferred native lock was not acquired")
        except BaseException:
            _close(handle)
            raise
        self._lock = handle
        return parent

    def __exit__(self, *_: object) -> None:
        handle, self._lock = self._lock, None
        if handle is not None:
            try:
                _unlock(handle)
            finally:
                _close(handle)


def _scenario_owner_quiescent_lifecycle(root: Path) -> dict[str, object]:
    fixture = root / "owner-lifecycle"
    fixture.mkdir()
    with ExitStack() as resources:
        auxiliary = _open_startup_directory(fixture)
        resources.callback(_close, auxiliary)
        for name, value in (
            ("owned.bin", b"owned"),
            ("unrelated.bin", b"unrelated"),
            (".lifecycle.lock", b""),
            (".owned.marker", b"marker"),
        ):
            handle, _ = _new_private_file(auxiliary, name, value)
            _close(handle)
        reused_values = []

        def prove_reuse(value: int, stale: _OwnedDirectory | None = None) -> bool:
            with ExitStack() as candidates:
                for _ in range(4096):
                    candidate = _open_private(auxiliary, "unrelated.bin")
                    candidates.callback(_close, candidate)
                    if candidate.value != value:
                        continue
                    if stale is not None:
                        stale.close()
                        stale.close()
                        stale.__del__()
                    if _read(candidate) != b"unrelated":
                        raise AssertionError(
                            "stale owner affected the reused unrelated handle"
                        )
                    reused_values.append(value)
                    return True
            return False

        blocked = {
            "status": "blocked",
            "reason": "native HANDLE reuse not observed in 4096 bounded live allocations",
        }
        bad = _open_private(auxiliary, "owned.bin")
        bad_value = bad.value
        _refused(lambda: _OwnedDirectory(bad), expected=PermissionError)
        if not prove_reuse(bad_value):
            return blocked
        with _OwnedDirectory(_open_startup_directory(fixture)) as contextual:
            context_value = contextual.take_for_entry().value
            if _open_and_read(contextual.take_for_entry(), "owned.bin") != b"owned":
                raise AssertionError("owner context selected the wrong directory")
        if not prove_reuse(context_value, contextual):
            return blocked
        finalizing = _OwnedDirectory(_open_startup_directory(fixture))
        final_value = finalizing.take_for_entry().value
        del finalizing
        if not prove_reuse(final_value):
            return blocked
        owner = _OwnedDirectory(_open_startup_directory(fixture))
        resources.callback(owner.close)
        with _DeferredDirectoryEntry(owner) as admitted:
            if _open_and_read(admitted, "owned.bin") != b"owned":
                raise AssertionError("transaction admission selected the wrong root")
        if _open_and_read(owner.take_for_entry(), "owned.bin") != b"owned":
            raise AssertionError("transaction exit closed the store")
        entered, release = threading.Event(), threading.Event()
        failures: list[BaseException] = []

        def active_user() -> None:
            try:
                admitted = owner.take_for_entry()
                _identity(admitted)
                entered.set()
                if not release.wait(5):
                    raise TimeoutError("application did not release its active user")
                if _open_and_read(admitted, "owned.bin") != b"owned":
                    raise AssertionError(
                        "active native user lost the retained directory"
                    )
            except BaseException as error:
                failures.append(error)
                entered.set()

        worker = threading.Thread(target=active_user, daemon=True)
        worker.start()
        try:
            if not entered.wait(5):
                raise TimeoutError("native user did not reach admission barrier")
            deferred = _DeferredDirectoryEntry(owner)
        finally:
            release.set()
            worker.join(5)
        if worker.is_alive():
            raise AssertionError("application failed to quiesce before close")
        if failures:
            raise failures[0]
        value = owner.take_for_entry().value
        owner.close()

        def delete_closed() -> None:
            parent = owner.take_for_entry()
            handle = _open_private(parent, "owned.bin")
            try:
                _cleanup_owned(parent, "owned.bin", handle)
            finally:
                _close(handle)

        operations = {
            "postclose_read": lambda: _open_and_read(
                owner.take_for_entry(), "owned.bin"
            ),
            "postclose_write": lambda: _new_private_file(
                owner.take_for_entry(), "forbidden.bin", b"no"
            ),
            "postclose_delete": delete_closed,
            "postclose_marker": lambda: _exists_relative(
                owner.take_for_entry(), ".owned.marker"
            ),
            "deferred_entry": lambda: deferred.__enter__(),
        }
        refusals = {
            name: _refused(operation, expected=ValueError)
            for name, operation in operations.items()
        }
        if not prove_reuse(value, owner):
            return blocked
        if _open_and_read(auxiliary, "owned.bin") != b"owned" or _exists_relative(
            auxiliary, "forbidden.bin"
        ):
            raise AssertionError("post-close operation changed stored state")
        return {
            "native_reused_handles": reused_values,
            "postclose_refusals": refusals,
            "scope": "native operation equivalents, not product API qualification",
            "checks": {
                name: True
                for name in (
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
                )
            },
        }


def _lock_worker(directory: int, name: str) -> int:
    """Independent client using an inherited pinned directory, never a path fallback."""
    parent = HANDLE(directory)
    with ExitStack() as resources:
        resources.callback(_close, parent)
        facts = _identity(parent)
        if not facts["directory"] or facts["reparse"]:
            raise PermissionError("inherited root is not a safe directory")
        handle = _open_private(parent, name)
        resources.callback(_close, handle)
        if _lock(handle, fail_immediately=True):
            _unlock(handle)
            raise AssertionError("contender acquired while parent held the lock")
        print("BLOCKED", flush=True)
        if sys.stdin.readline().strip() != "ACQUIRE":
            return 3
        print("WAITING", flush=True)
        if not _lock(handle, fail_immediately=False):
            return 4
        try:
            if _open_and_read(parent, "record.bin") != b"committed":
                raise AssertionError(
                    "participating client missed protected replacement"
                )
            print("ACQUIRED", flush=True)
            if sys.stdin.readline().strip() != "RELEASE":
                return 5
        finally:
            _unlock(handle)
        return 0


def run(
    root: Path, record: Callable[[str, Callable[[], dict[str, object]]], None]
) -> None:
    """Register exactly the Windows native feasibility scenarios expected by the parent runner."""
    if os.name != "nt":
        raise RuntimeError("windows_probe.run must only be dispatched on Windows")
    _api()  # Bind FFI before callbacks are registered, but do not perform filesystem work yet.
    record("root_pinning", lambda: _scenario_root_pinning(root))
    record(
        "namespace_inheritance_and_layouts",
        lambda: _scenario_namespace_inheritance_and_layouts(root),
    )
    record("redirect_refusal", lambda: _scenario_redirect_refusal(root))
    record("object_privacy", lambda: _scenario_object_privacy(root))
    record("temp_replace_cleanup", lambda: _scenario_temp_replace_cleanup(root))
    record("marker_interruption", lambda: _scenario_marker_interruption(root))
    record("cooperative_locking", lambda: _scenario_cooperative_locking(root))
    record(
        "owner_quiescent_lifecycle", lambda: _scenario_owner_quiescent_lifecycle(root)
    )


if __name__ == "__main__":
    if os.name != "nt" or len(sys.argv) != 4 or sys.argv[1] != "--lock-worker":
        raise SystemExit("windows_probe.py --lock-worker DIRECTORY NAME (Windows only)")
    raise SystemExit(_lock_worker(int(sys.argv[2]), sys.argv[3]))
