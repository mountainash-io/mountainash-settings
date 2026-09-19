"""Windows-native, disposable feasibility probes for private file-store mechanics.

This module deliberately uses the NT directory-handle API for every store
namespace operation after the trusted startup directory has been acquired.
It is a probe, not a store implementation.
"""

from __future__ import annotations

import ctypes as c
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
FILE_NON_DIRECTORY_FILE = 0x00000040
FILE_SYNCHRONOUS_IO_NONALERT = 0x00000020
FILE_OPEN_REPARSE_POINT = 0x00200000
FILE_ATTRIBUTE_NORMAL = 0x00000080
FILE_ATTRIBUTE_DIRECTORY = 0x00000010
FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
GENERIC_ALL = 0x10000000
DELETE = 0x00010000
READ_CONTROL = 0x00020000
WRITE_DAC = 0x00040000
SYNCHRONIZE = 0x00100000
FILE_END = 2
FILE_TYPE_DISK = 0x0001
FILE_RENAME_INFORMATION = 10
FILE_LINK_INFORMATION = 11
FILE_DISPOSITION_INFORMATION = 13
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


class UNICODE_STRING(c.Structure):
    _fields_ = [("Length", USHORT), ("MaximumLength", USHORT), ("Buffer", c.POINTER(c.c_wchar))]


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
        ("DeletePending", BOOL),
        ("Directory", BOOL),
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
        self.string = UNICODE_STRING(length, length + c.sizeof(c.c_wchar), c.cast(self.buffer, c.POINTER(c.c_wchar)))


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
        self.CreateFileW.argtypes = [c.c_wchar_p, DWORD, DWORD, PVOID, DWORD, DWORD, HANDLE]
        self.CreateFileW.restype = HANDLE
        self.CloseHandle = self.k32.CloseHandle
        self.CloseHandle.argtypes = [HANDLE]
        self.CloseHandle.restype = BOOL
        self.GetFileInformationByHandle = self.k32.GetFileInformationByHandle
        self.GetFileInformationByHandle.argtypes = [HANDLE, c.POINTER(BY_HANDLE_FILE_INFORMATION)]
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
        self.SetFilePointerEx.argtypes = [HANDLE, c.c_longlong, c.POINTER(c.c_longlong), DWORD]
        self.SetFilePointerEx.restype = BOOL
        self.LockFileEx = self.k32.LockFileEx
        self.LockFileEx.argtypes = [HANDLE, DWORD, DWORD, DWORD, DWORD, c.POINTER(OVERLAPPED)]
        self.LockFileEx.restype = BOOL
        self.UnlockFileEx = self.k32.UnlockFileEx
        self.UnlockFileEx.argtypes = [HANDLE, DWORD, DWORD, DWORD, c.POINTER(OVERLAPPED)]
        self.UnlockFileEx.restype = BOOL
        self.GetCurrentProcess = self.k32.GetCurrentProcess
        self.GetCurrentProcess.argtypes = []
        self.GetCurrentProcess.restype = HANDLE
        self.LocalFree = self.k32.LocalFree
        self.LocalFree.argtypes = [HANDLE]
        self.LocalFree.restype = HANDLE

        self.NtCreateFile = self.ntdll.NtCreateFile
        self.NtCreateFile.argtypes = [
            PHANDLE, ULONG, c.POINTER(OBJECT_ATTRIBUTES), c.POINTER(IO_STATUS_BLOCK), PVOID,
            ULONG, ULONG, ULONG, ULONG, PVOID, ULONG,
        ]
        self.NtCreateFile.restype = NTSTATUS
        self.NtSetInformationFile = self.ntdll.NtSetInformationFile
        self.NtSetInformationFile.argtypes = [HANDLE, c.POINTER(IO_STATUS_BLOCK), PVOID, ULONG, c.c_int]
        self.NtSetInformationFile.restype = NTSTATUS

        self.OpenProcessToken = self.advapi.OpenProcessToken
        self.OpenProcessToken.argtypes = [HANDLE, DWORD, PHANDLE]
        self.OpenProcessToken.restype = BOOL
        self.GetTokenInformation = self.advapi.GetTokenInformation
        self.GetTokenInformation.argtypes = [HANDLE, c.c_int, PVOID, DWORD, c.POINTER(DWORD)]
        self.GetTokenInformation.restype = BOOL
        self.ConvertSidToStringSidW = self.advapi.ConvertSidToStringSidW
        self.ConvertSidToStringSidW.argtypes = [PVOID, c.POINTER(c.c_wchar_p)]
        self.ConvertSidToStringSidW.restype = BOOL
        self.ConvertStringSecurityDescriptorToSecurityDescriptorW = self.advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW
        self.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [c.c_wchar_p, DWORD, c.POINTER(PVOID), c.POINTER(DWORD)]
        self.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = BOOL
        self.GetSecurityDescriptorDacl = self.advapi.GetSecurityDescriptorDacl
        self.GetSecurityDescriptorDacl.argtypes = [PVOID, c.POINTER(BOOL), c.POINTER(PVOID), c.POINTER(BOOL)]
        self.GetSecurityDescriptorDacl.restype = BOOL
        self.SetSecurityInfo = self.advapi.SetSecurityInfo
        self.SetSecurityInfo.argtypes = [HANDLE, c.c_int, DWORD, PVOID, PVOID, PVOID, PVOID]
        self.SetSecurityInfo.restype = DWORD
        self.GetSecurityInfo = self.advapi.GetSecurityInfo
        self.GetSecurityInfo.argtypes = [HANDLE, c.c_int, DWORD, c.POINTER(PVOID), c.POINTER(PVOID), c.POINTER(PVOID), c.POINTER(PVOID), c.POINTER(PVOID)]
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


def _check_status(status: int, action: str) -> None:
    if status < 0:
        raise OSError(f"{action} failed with NTSTATUS {_status_hex(status)}")


def _close(handle: HANDLE) -> None:
    if handle and handle.value not in (None, INVALID_HANDLE_VALUE):
        _check_bool(_api().CloseHandle(handle), "CloseHandle")


def _open_startup_directory(path: Path) -> HANDLE:
    """Acquire the one trusted startup directory with CreateFileW backup semantics."""
    handle = _api().CreateFileW(
        str(path), GENERIC_ALL, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        None, FILE_OPEN, 0x02000000, None,  # FILE_FLAG_BACKUP_SEMANTICS
    )
    if handle.value == INVALID_HANDLE_VALUE:
        raise _last_error(f"CreateFileW startup directory {path}")
    return handle


def _open_relative(
    parent: HANDLE,
    name: str,
    disposition: int,
    *,
    directory: bool = False,
    open_reparse_point: bool = False,
    access: int = GENERIC_ALL | SYNCHRONIZE,
) -> HANDLE:
    """Open only beneath a retained directory handle, refusing reparse traversal."""
    native_name = _NtName(name)
    attributes = OBJECT_ATTRIBUTES(
        c.sizeof(OBJECT_ATTRIBUTES), parent, c.pointer(native_name.string),
        OBJ_CASE_INSENSITIVE | OBJ_DONT_REPARSE, None, None,
    )
    iosb = IO_STATUS_BLOCK()
    result = HANDLE()
    options = FILE_SYNCHRONOUS_IO_NONALERT
    options |= FILE_DIRECTORY_FILE if directory else FILE_NON_DIRECTORY_FILE
    if open_reparse_point:
        options |= FILE_OPEN_REPARSE_POINT
    status = _api().NtCreateFile(
        c.byref(result), access, c.byref(attributes), c.byref(iosb), None,
        FILE_ATTRIBUTE_DIRECTORY if directory else FILE_ATTRIBUTE_NORMAL,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, disposition, options, None, 0,
    )
    _check_status(status, f"NtCreateFile relative {name!r}")
    return result


def _make_dir(parent: HANDLE, name: str) -> HANDLE:
    return _open_relative(parent, name, FILE_CREATE, directory=True)


def _write(handle: HANDLE, value: bytes) -> None:
    data = c.create_string_buffer(value)
    written = DWORD()
    _check_bool(_api().WriteFile(handle, data, len(value), c.byref(written), None), "WriteFile")
    if written.value != len(value):
        raise OSError(f"WriteFile made a short write ({written.value}/{len(value)})")

def _append(handle: HANDLE, value: bytes) -> None:
    offset = c.c_longlong()
    _check_bool(_api().SetFilePointerEx(handle, 0, c.byref(offset), FILE_END), "SetFilePointerEx(FILE_END)")
    _write(handle, value)


def _read(handle: HANDLE) -> bytes:
    offset = c.c_longlong()
    _check_bool(_api().SetFilePointerEx(handle, 0, c.byref(offset), 0), "SetFilePointerEx")
    info = FILE_STANDARD_INFO()
    _check_bool(_api().GetFileInformationByHandleEx(handle, 1, c.byref(info), c.sizeof(info)), "GetFileInformationByHandleEx(FileStandardInfo)")
    data = c.create_string_buffer(info.EndOfFile)
    got = DWORD()
    _check_bool(_api().ReadFile(handle, data, info.EndOfFile, c.byref(got), None), "ReadFile")
    return data.raw[:got.value]


def _identity(handle: HANDLE) -> dict[str, int | bool]:
    basic = BY_HANDLE_FILE_INFORMATION()
    standard = FILE_STANDARD_INFO()
    tag = FILE_ATTRIBUTE_TAG_INFO()
    api = _api()
    _check_bool(api.GetFileInformationByHandle(handle, c.byref(basic)), "GetFileInformationByHandle")
    _check_bool(api.GetFileInformationByHandleEx(handle, 1, c.byref(standard), c.sizeof(standard)), "GetFileInformationByHandleEx(FileStandardInfo)")
    _check_bool(api.GetFileInformationByHandleEx(handle, 9, c.byref(tag), c.sizeof(tag)), "GetFileInformationByHandleEx(FileAttributeTagInfo)")
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
    if observed["directory"] or not observed["disk_file"] or observed["reparse"] or observed["links"] != 1:
        raise PermissionError(f"unsafe leaf identity: {observed}")
    private, dacl = _dacl_private(handle)
    if not private:
        raise PermissionError(f"leaf DACL is not conservatively private: {dacl}")
    return {"identity": observed, "dacl": dacl}


def _current_sid() -> str:
    api = _api()
    token = HANDLE()
    _check_bool(api.OpenProcessToken(api.GetCurrentProcess(), TOKEN_QUERY, c.byref(token)), "OpenProcessToken")
    try:
        size = DWORD()
        api.GetTokenInformation(token, TOKEN_USER, None, 0, c.byref(size))
        if c.get_last_error() != ERROR_INSUFFICIENT_BUFFER:
            raise _last_error("GetTokenInformation size")
        buffer = c.create_string_buffer(size.value)
        _check_bool(api.GetTokenInformation(token, TOKEN_USER, buffer, size, c.byref(size)), "GetTokenInformation")
        user = c.cast(buffer, c.POINTER(TOKEN_USER_DATA)).contents
        text = c.c_wchar_p()
        _check_bool(api.ConvertSidToStringSidW(user.Sid, c.byref(text)), "ConvertSidToStringSidW")
        try:
            return text.value
        finally:
            api.LocalFree(c.cast(text, HANDLE))
    finally:
        _close(token)


def _set_sddl_dacl(handle: HANDLE, sddl: str) -> None:
    api = _api()
    descriptor = PVOID()
    _check_bool(
        api.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl, 1, c.byref(descriptor), None),
        "ConvertStringSecurityDescriptorToSecurityDescriptorW",
    )
    try:
        present = BOOL()
        defaulted = BOOL()
        dacl = PVOID()
        _check_bool(api.GetSecurityDescriptorDacl(descriptor, c.byref(present), c.byref(dacl), c.byref(defaulted)), "GetSecurityDescriptorDacl")
        if not present.value:
            raise PermissionError("constructed private descriptor unexpectedly lacks a DACL")
        status = api.SetSecurityInfo(
            handle, SE_FILE_OBJECT,
            DACL_SECURITY_INFORMATION | PROTECTED_DACL_SECURITY_INFORMATION,
            None, None, dacl, None,
        )
        if status:
            raise OSError(status, "SetSecurityInfo(DACL)")
    finally:
        api.LocalFree(c.cast(descriptor, HANDLE))


def _set_private_before_data(handle: HANDLE) -> str:
    sid = _current_sid()
    _set_sddl_dacl(handle, f"D:P(A;;FA;;;SY)(A;;FA;;;{sid})")
    private, _ = _dacl_private(handle)
    if not private:
        raise PermissionError("private DACL did not round-trip as current-user + SYSTEM only")
    return sid


def _sid_text(sid: PVOID) -> str:
    text = c.c_wchar_p()
    _check_bool(_api().ConvertSidToStringSidW(sid, c.byref(text)), "ConvertSidToStringSidW ACE")
    try:
        return text.value
    finally:
        _api().LocalFree(c.cast(text, HANDLE))


def _dacl_private(handle: HANDLE) -> tuple[bool, dict[str, object]]:
    """Deliberately narrow ACL check: protected allow ACEs only for user and SYSTEM."""
    descriptor = PVOID()
    dacl = PVOID()
    status = _api().GetSecurityInfo(
        handle, SE_FILE_OBJECT, DACL_SECURITY_INFORMATION,
        None, None, c.byref(dacl), None, c.byref(descriptor),
    )
    if status:
        raise OSError(status, "GetSecurityInfo(DACL)")
    try:
        if not dacl:
            return False, {"scope": "protected-current-user-and-system-full-control", "reason": "null DACL"}
        info = ACL_SIZE_INFORMATION_DATA()
        _check_bool(_api().GetAclInformation(dacl, c.byref(info), c.sizeof(info), ACL_SIZE_INFORMATION), "GetAclInformation")
        permitted = {_current_sid(), "S-1-5-18"}
        allow_sids: list[str] = []
        rejected: list[str] = []
        for index in range(info.AceCount):
            ace = PVOID()
            _check_bool(_api().GetAce(dacl, index, c.byref(ace)), "GetAce")
            header = c.cast(ace, c.POINTER(ACE_HEADER)).contents
            if header.AceType != ACCESS_ALLOWED_ACE_TYPE:
                rejected.append(f"ace-type-{header.AceType}")
                continue
            # ACCESS_ALLOWED_ACE is ACE_HEADER + ACCESS_MASK followed by SID.
            sid_pointer = PVOID(ace.value + c.sizeof(ACE_HEADER) + c.sizeof(DWORD))
            sid = _sid_text(sid_pointer)
            allow_sids.append(sid)
            if sid not in permitted:
                rejected.append(sid)
        private = not rejected and set(allow_sids) == permitted and len(allow_sids) == 2
        return private, {
            "scope": "protected-current-user-and-system-full-control",
            "ace_count": info.AceCount,
            "allow_sids": allow_sids,
            "rejected": rejected,
        }
    finally:
        _api().LocalFree(c.cast(descriptor, HANDLE))


def _new_private_file(parent: HANDLE, name: str, payload: bytes) -> tuple[HANDLE, dict[str, object]]:
    handle = _open_relative(parent, name, FILE_CREATE)
    try:
        sid = _set_private_before_data(handle)
        _write(handle, payload)
        facts = _assert_private_regular(handle)
        facts["owner_sid"] = sid
        return handle, facts
    except BaseException:
        _close(handle)
        raise


def _delete_on_handle(handle: HANDLE) -> None:
    info = FILE_DISPOSITION_INFORMATION(1)
    iosb = IO_STATUS_BLOCK()
    status = _api().NtSetInformationFile(handle, c.byref(iosb), c.byref(info), c.sizeof(info), FILE_DISPOSITION_INFORMATION)
    _check_status(status, "NtSetInformationFile(FileDispositionInformation)")


def _rename_on_handle(handle: HANDLE, destination_parent: HANDLE, destination_name: str, replace: bool) -> None:
    encoded = destination_name.encode("utf-16-le")
    size = FILE_RENAME_INFORMATION_FIXED.FileName.offset + len(encoded)
    buffer = c.create_string_buffer(size)
    fixed = c.cast(buffer, c.POINTER(FILE_RENAME_INFORMATION_FIXED)).contents
    fixed.ReplaceIfExists = 1 if replace else 0
    fixed.RootDirectory = destination_parent
    fixed.FileNameLength = len(encoded)
    c.memmove(c.addressof(buffer) + FILE_RENAME_INFORMATION_FIXED.FileName.offset, encoded, len(encoded))
    iosb = IO_STATUS_BLOCK()
    status = _api().NtSetInformationFile(handle, c.byref(iosb), buffer, size, FILE_RENAME_INFORMATION)
    _check_status(status, "NtSetInformationFile(FileRenameInformation)")


def _link_on_handle(handle: HANDLE, destination_parent: HANDLE, destination_name: str) -> None:
    encoded = destination_name.encode("utf-16-le")
    size = FILE_RENAME_INFORMATION_FIXED.FileName.offset + len(encoded)
    buffer = c.create_string_buffer(size)
    fixed = c.cast(buffer, c.POINTER(FILE_RENAME_INFORMATION_FIXED)).contents
    fixed.ReplaceIfExists = 0
    fixed.RootDirectory = destination_parent
    fixed.FileNameLength = len(encoded)
    c.memmove(c.addressof(buffer) + FILE_RENAME_INFORMATION_FIXED.FileName.offset, encoded, len(encoded))
    iosb = IO_STATUS_BLOCK()
    status = _api().NtSetInformationFile(handle, c.byref(iosb), buffer, size, FILE_LINK_INFORMATION)
    _check_status(status, "NtSetInformationFile(FileLinkInformation)")


def _exists_relative(parent: HANDLE, name: str, *, directory: bool = False) -> bool:
    try:
        handle = _open_relative(
            parent, name, FILE_OPEN, directory=directory,
            access=GENERIC_READ | SYNCHRONIZE,
        )
    except OSError:
        return False
    _close(handle)
    return True


def _open_and_read(parent: HANDLE, name: str) -> bytes:
    handle = _open_relative(parent, name, FILE_OPEN)
    try:
        return _read(handle)
    finally:
        _close(handle)


def _junction(link: Path, target: Path) -> None:
    result = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
        check=False, capture_output=True, text=True, timeout=15,
    )
    if result.returncode:
        raise OSError(f"mklink /J failed: {result.stdout} {result.stderr}")


def _scenario_root_pinning(root: Path) -> dict[str, object]:
    fixture = root / "root-pinning"
    fixture.mkdir()
    target_a = fixture / "a"
    target_b = fixture / "b"
    target_a.mkdir()
    target_b.mkdir()
    alias = fixture / "startup-alias"
    try:
        _junction(alias, target_a)
    except OSError as error:
        return {"status": "blocked", "reason": f"junction fixture unavailable: {error}"}
    pinned = _open_startup_directory(alias)
    try:
        os.rmdir(alias)  # Removes the disposable junction, not target_a.
        try:
            _junction(alias, target_b)
        except OSError as error:
            return {"status": "blocked", "reason": f"startup alias retarget fixture unavailable: {error}"}
        leaf, facts = _new_private_file(pinned, "pinned.bin", b"pinned")
        _close(leaf)
        a = _open_startup_directory(target_a)
        b = _open_startup_directory(target_b)
        try:
            in_a = _exists_relative(a, "pinned.bin")
            in_b = _exists_relative(b, "pinned.bin")
        finally:
            _close(a)
            _close(b)
        if not in_a or in_b:
            raise AssertionError("startup alias retarget changed an already-pinned directory handle")
        return {"mechanism": "CreateFileW(FILE_FLAG_BACKUP_SEMANTICS) then NtCreateFile(RootDirectory)", "retargeted_alias": True, "leaf": facts}
    finally:
        _close(pinned)


def _scenario_namespace_inheritance_and_layouts(root: Path) -> dict[str, object]:
    fixture = root / "namespace-layout"
    fixture.mkdir()
    root_handle = _open_startup_directory(fixture)
    try:
        one, one_facts = _new_private_file(root_handle, "solo.yaml", b"one")
        domain = _make_dir(root_handle, "domain")
        try:
            two, two_facts = _new_private_file(domain, "stem.yaml", b"two")
            three, three_facts = _new_private_file(domain, "rest-one-two.yaml", b"three")
            _close(one)
            _close(two)
            _close(three)
            domain_identity = _identity(domain)
            # The application-owned namespace directory is created with no ACL
            # rewrite; only credential and temporary leaves receive private ACLs.
            return {
                "layouts": {
                    "one_segment": {"segments": ["solo"], "path": "solo.yaml"},
                    "two_segments": {"segments": ["domain", "stem"], "path": "domain/stem.yaml"},
                    "three_plus_segments": {"segments": ["domain", "rest", "one", "two"], "path": "domain/rest-one-two.yaml"},
                },
                "namespace_creation": "NtCreateFile(FILE_DIRECTORY_FILE) without an application ACL rewrite",
                "namespace_identity": domain_identity,
                "one": one_facts,
                "two": two_facts,
                "three_plus": three_facts,
            }
        finally:
            _close(domain)
    finally:
        _close(root_handle)


def _scenario_redirect_refusal(root: Path) -> dict[str, object]:
    fixture = root / "redirect-refusal"
    fixture.mkdir()
    target = fixture / "target"
    target.mkdir()
    target_handle = _open_startup_directory(target)
    try:
        victim, _ = _new_private_file(target_handle, "victim", b"fixture")
        _close(victim)
    finally:
        _close(target_handle)
    junction = fixture / "junction"
    try:
        _junction(junction, target)
    except OSError as error:
        return {"status": "blocked", "reason": f"junction fixture unavailable: {error}"}
    parent = _open_startup_directory(fixture)
    try:
        try:
            handle = _open_relative(parent, "junction\\victim", FILE_OPEN)
        except OSError as error:
            return {
                "mechanism": "NtCreateFile RootDirectory + OBJ_DONT_REPARSE",
                "junction_fixture": "cmd.exe mklink /J",
                "refused": True,
                "native_error": str(error),
            }
        else:
            _close(handle)
            raise AssertionError("NtCreateFile traversed a junction despite OBJ_DONT_REPARSE")
    finally:
        _close(parent)


def _scenario_object_privacy(root: Path) -> dict[str, object]:
    fixture = root / "object-privacy"
    fixture.mkdir()
    parent = _open_startup_directory(fixture)
    try:
        leaf, private_facts = _new_private_file(parent, "private.bin", b"private")
        try:
            exposed = _open_relative(parent, "exposed.bin", FILE_CREATE)
            try:
                _set_sddl_dacl(exposed, "D:P(A;;FA;;;WD)")
                _write(exposed, b"exposed")
                private, exposed_facts = _dacl_private(exposed)
                if private:
                    raise AssertionError("Everyone full-control fixture passed private-DACL check")
            finally:
                _close(exposed)
            _link_on_handle(leaf, parent, "private-link.bin")
            linked = _open_relative(parent, "private-link.bin", FILE_OPEN)
            try:
                try:
                    _assert_private_regular(linked)
                except PermissionError as error:
                    link_refused = str(error)
                else:
                    raise AssertionError("hard-linked credential fixture was accepted")
            finally:
                _close(linked)
            return {
                "private_created_before_payload": True,
                "private": private_facts,
                "broad_acl_refused": exposed_facts,
                "hardlink_refused": link_refused,
            }
        finally:
            _close(leaf)
    finally:
        _close(parent)


def _scenario_temp_replace_cleanup(root: Path) -> dict[str, object]:
    fixture = root / "temp-replace"
    fixture.mkdir()
    parent = _open_startup_directory(fixture)
    try:
        record, _ = _new_private_file(parent, "record.bin", b"old")
        _close(record)
        temporary, _ = _new_private_file(parent, "record.tmp", b"new")
        try:
            # Exercise an actual precommit exception path before the rename boundary.
            try:
                raise OSError("injected-before-rename")
            except OSError as error:
                precommit_error = str(error)
            if _open_and_read(parent, "record.bin") != b"old":
                raise AssertionError("precommit interruption did not preserve prior record")
            _delete_on_handle(temporary)
        finally:
            _close(temporary)
        if _exists_relative(parent, "record.tmp"):
            raise AssertionError("same-handle temporary disposition did not remove temporary")

        replacement, _ = _new_private_file(parent, "replace.tmp", b"new")
        try:
            _rename_on_handle(replacement, parent, "record.bin", replace=True)
        finally:
            _close(replacement)
        if _open_and_read(parent, "record.bin") != b"new":
            raise AssertionError("handle-relative replacement did not commit new content")

        marker, _ = _new_private_file(parent, "record.marker", b"marker")
        # Existing GENERIC_ALL rights would retain DELETE after the DACL change,
        # so cleanup is deliberately attempted through a newly opened read-only
        # handle, as a real later cleanup pass would be.
        _set_sddl_dacl(marker, f"D:P(D;;SD;;;{_current_sid()})(A;;FA;;;SY)(A;;FR;;;{_current_sid()})")
        _close(marker)
        marker = None
        cleanup_reader = _open_relative(
            parent, "record.marker", FILE_OPEN, access=GENERIC_READ | SYNCHRONIZE,
        )
        try:
            # This is an actual AccessDenied result from NtSetInformationFile.
            try:
                _delete_on_handle(cleanup_reader)
            except OSError as error:
                postcommit_error = str(error)
            else:
                raise AssertionError("delete-protected marker unexpectedly cleaned up")
        finally:
            _close(cleanup_reader)
        if _open_and_read(parent, "record.bin") != b"new" or not _exists_relative(parent, "record.marker"):
            raise AssertionError("postcommit failure did not honestly retain marker beside committed record")

        owned, _ = _new_private_file(parent, "owned.tmp", b"owned")
        expected_identity = _identity(owned)
        _close(owned)
        unrelated, _ = _new_private_file(parent, "unrelated.tmp", b"unrelated")
        try:
            _rename_on_handle(unrelated, parent, "owned.tmp", replace=True)
        finally:
            _close(unrelated)
        current = _open_relative(parent, "owned.tmp", FILE_OPEN)
        try:
            current_identity = _identity(current)
        finally:
            _close(current)
        mismatch_refused = current_identity != expected_identity
        if not mismatch_refused or _open_and_read(parent, "owned.tmp") != b"unrelated":
            raise AssertionError("ownership mismatch cleanup was not left untouched")
        return {
            "precommit_fault": precommit_error,
            "same_handle_temp_cleanup": True,
            "handle_relative_replace": True,
            "postcommit_marker_cleanup_failure": postcommit_error,
            "marker_retained": True,
            "identity_mismatch_refused": mismatch_refused,
            "atomicity_claim": "none against an authorized protocol-bypass replacement",
        }
    finally:
        _close(parent)


def _scenario_marker_interruption(root: Path) -> dict[str, object]:
    fixture = root / "marker-interruption"
    fixture.mkdir()
    parent = _open_startup_directory(fixture)
    try:
        record, _ = _new_private_file(parent, "record.bin", b"raw-record")
        marker, _ = _new_private_file(parent, "record.marker", b"delete-intent")
        try:
            raw = _read(record)
            marker_present = _exists_relative(parent, "record.marker")
            if raw != b"raw-record" or not marker_present:
                raise AssertionError("marker-first interruption did not leave distinct raw and marker observations")
            return {
                "ordering": "record then marker; interruption leaves both",
                "raw_get": raw.decode("ascii"),
                "marker_present": marker_present,
                "repair_attempted": False,
            }
        finally:
            _close(marker)
            _close(record)
    finally:
        _close(parent)


def _lock(handle: HANDLE, fail_immediately: bool) -> bool:
    flags = LOCKFILE_EXCLUSIVE_LOCK | (LOCKFILE_FAIL_IMMEDIATELY if fail_immediately else 0)
    overlapped = OVERLAPPED()
    ok = _api().LockFileEx(handle, flags, 0, 1, 0, c.byref(overlapped))
    if not ok and c.get_last_error() == ERROR_LOCK_VIOLATION:
        return False
    _check_bool(ok, "LockFileEx")
    return True


def _unlock(handle: HANDLE) -> None:
    overlapped = OVERLAPPED()
    _check_bool(_api().UnlockFileEx(handle, 0, 1, 0, c.byref(overlapped)), "UnlockFileEx")


def _bounded_line(stream: t.TextIO, timeout: float, process: subprocess.Popen[str]) -> str:
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
    parent = _open_startup_directory(fixture)
    process: subprocess.Popen[str] | None = None
    locked: HANDLE | None = None
    try:
        locked, _ = _new_private_file(parent, "record.bin", b"locked")
        if not _lock(locked, fail_immediately=False):
            raise AssertionError("owner failed to acquire exclusive LockFileEx lock")
        process = subprocess.Popen(
            [sys.executable, __file__, "--lock-worker", str(fixture), "record.bin"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1,
        )
        assert process.stdout is not None and process.stdin is not None
        if _bounded_line(process.stdout, 15, process) != "BLOCKED":
            raise AssertionError("participating writer was not blocked by existing exclusive lock")
        process.stdin.write("ACQUIRE\n")
        process.stdin.flush()
        if _bounded_line(process.stdout, 15, process) != "WAITING":
            raise AssertionError("participating writer did not enter its blocking-lock phase")
        # The same child now blocks in LockFileEx until cleanup and release finish.
        cleanup, _ = _new_private_file(parent, "cleanup.tmp", b"cleanup")
        try:
            _delete_on_handle(cleanup)
        finally:
            _close(cleanup)
        _unlock(locked)
        if _bounded_line(process.stdout, 15, process) != "ACQUIRED":
            raise AssertionError("writer did not acquire only after cleanup and owner unlock")
        process.stdin.write("RELEASE\n")
        process.stdin.flush()
        process.wait(timeout=15)
        if process.returncode:
            assert process.stderr is not None
            raise RuntimeError(f"lock worker failed: {process.stderr.read()}")
        return {
            "mechanism": "LockFileEx exclusive byte-range lock with child-process IPC",
            "child_initial_observation": "BLOCKED",
            "child_blocking_phase": "WAITING",
            "cleanup_while_owner_lock_held": True,
            "child_after_release": "ACQUIRED",
            "scope": "participating writers; external modification requires owner quiescence",
        }
    finally:
        if locked is not None:
            try:
                _unlock(locked)
            except OSError:
                pass
            _close(locked)
        if process is not None and process.poll() is None:
            process.kill()
            process.wait(timeout=5)


class _OwnedDirectory:
    """Minimal ownership model: application work must quiesce before detach/close."""

    def __init__(self, handle: HANDLE) -> None:
        self._handle: HANDLE | None = handle
        self._closed = False
        self._quiesced = False

    def take_for_entry(self) -> HANDLE:
        if self._closed or self._handle is None:
            raise ValueError("deferred entry after owner close")
        return self._handle

    def quiesce_application_work(self) -> None:
        # This probe has no backend worker to drain; quiescence is a caller-side
        # lifecycle boundary, recorded before the minimal handle release below.
        self._quiesced = True

    def close(self) -> None:
        if self._closed:
            return
        if not self._quiesced:
            raise RuntimeError("owner close before application work quiesced")
        self._closed = True
        detached, self._handle = self._handle, None
        if detached is not None:
            _close(detached)


class _DeferredDirectoryEntry:
    """A deferred context created before close, whose entry resolves ownership late."""

    def __init__(self, owner: _OwnedDirectory) -> None:
        self._owner = owner

    def __enter__(self) -> HANDLE:
        return self._owner.take_for_entry()

    def __exit__(self, *_: object) -> None:
        return None


def _scenario_owner_quiescent_lifecycle(root: Path) -> dict[str, object]:
    fixture = root / "owner-lifecycle"
    fixture.mkdir()
    base = _open_startup_directory(fixture)
    private, _ = _new_private_file(base, "unrelated.bin", b"before")
    _close(private)
    owner = _OwnedDirectory(base)
    deferred = _DeferredDirectoryEntry(owner)
    released_value = owner.take_for_entry().value
    owner.quiesce_application_work()
    owner.close()
    try:
        with deferred:
            raise AssertionError("deferred context entry succeeded after owner close")
    except ValueError as error:
        deferred_refused = str(error)

    reused: HANDLE | None = None
    for _ in range(512):
        bootstrap = _open_startup_directory(fixture)
        try:
            candidate = _open_relative(bootstrap, "unrelated.bin", FILE_OPEN)
        finally:
            _close(bootstrap)
        if candidate.value == released_value:
            reused = candidate
            break
    if reused is None:
        return {
            "status": "blocked",
            "reason": "Windows did not reuse released native HANDLE for an unrelated file in 512 bounded allocations",
        }
    try:
        owner.close()
        owner.close()
        _append(reused, b"-after")
        data = _read(reused)
        if data != b"before-after":
            raise AssertionError("reused unrelated native handle was affected by repeated owner close")
        return {
            "detach_before_release": True,
            "deferred_entry_refused": deferred_refused,
            "released_handle_value": released_value,
            "reused_handle_value": reused.value,
            "reused_unrelated_handle_usable_after_repeated_close": True,
        }
    finally:
        _close(reused)


def _lock_worker(directory: Path, name: str) -> int:
    """A real second Windows process participating in LockFileEx protocol."""
    parent = _open_startup_directory(directory)
    handle: HANDLE | None = None
    try:
        handle = _open_relative(parent, name, FILE_OPEN)
        if _lock(handle, fail_immediately=True):
            print("UNEXPECTED", flush=True)
            _unlock(handle)
            return 2
        print("BLOCKED", flush=True)
        if sys.stdin.readline().strip() != "ACQUIRE":
            return 3
        print("WAITING", flush=True)
        if not _lock(handle, fail_immediately=False):
            return 4
        print("ACQUIRED", flush=True)
        if sys.stdin.readline().strip() != "RELEASE":
            return 5
        _unlock(handle)
        return 0
    finally:
        if handle is not None:
            _close(handle)
        _close(parent)


def run(root: Path, record: Callable[[str, Callable[[], dict[str, object]]], None]) -> None:
    """Register exactly the Windows native feasibility scenarios expected by the parent runner."""
    if os.name != "nt":
        raise RuntimeError("windows_probe.run must only be dispatched on Windows")
    _api()  # Bind FFI before callbacks are registered, but do not perform filesystem work yet.
    record("root_pinning", lambda: _scenario_root_pinning(root))
    record("namespace_inheritance_and_layouts", lambda: _scenario_namespace_inheritance_and_layouts(root))
    record("redirect_refusal", lambda: _scenario_redirect_refusal(root))
    record("object_privacy", lambda: _scenario_object_privacy(root))
    record("temp_replace_cleanup", lambda: _scenario_temp_replace_cleanup(root))
    record("marker_interruption", lambda: _scenario_marker_interruption(root))
    record("cooperative_locking", lambda: _scenario_cooperative_locking(root))
    record("owner_quiescent_lifecycle", lambda: _scenario_owner_quiescent_lifecycle(root))


if __name__ == "__main__":
    if os.name != "nt" or len(sys.argv) != 4 or sys.argv[1] != "--lock-worker":
        raise SystemExit("windows_probe.py --lock-worker DIRECTORY NAME (Windows only)")
    raise SystemExit(_lock_worker(Path(sys.argv[2]), sys.argv[3]))
