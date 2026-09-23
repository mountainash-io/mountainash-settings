"""Private Windows HANDLE primitives; loaded only after platform selection."""
from __future__ import annotations

import ctypes as c
import os
import threading
import typing as t
from pathlib import Path

from .errors import _Failure

DUPLICATE_SAME_ACCESS = 0x00000002
_FILE_STANDARD_INFO = 1
_FILE_ATTRIBUTE_TAG_INFO = 9
STATUS_INVALID_DEVICE_REQUEST = 0xC0000010
STATUS_NOT_SUPPORTED = 0xC00000BB
STATUS_NOT_A_DIRECTORY = 0xC0000103
ERROR_INVALID_FUNCTION = 1
ERROR_NOT_SUPPORTED = 50
_API_LOCK = threading.Lock()
_API: _Api | None = None

class _NtError(OSError):
    def __init__(self, status: int) -> None:
        self.status = status & 0xFFFFFFFF
        super().__init__(self.status, "native status")

class _ReparseRefused(PermissionError):
    pass

def _api() -> _Api:
    global _API
    with _API_LOCK:
        if _API is None:
            if os.name != "nt":
                raise _Failure("unsupported_filesystem")
            try:
                _API = _Api()
            except (AttributeError, OSError) as exc:
                raise _Failure("unsupported_filesystem") from exc
        return _API

def _check_bool(ok: int, action: str) -> None:
    if not ok:
        raise OSError(c.get_last_error(), action)

def _check_status(status: int, action: str) -> None:
    if status:
        raise _NtError(status)

def _as_handle(value: int) -> HANDLE:
    if type(value) is not int or value <= 0:  # noqa: E721 -- exact-type, reject bool
        raise _Failure("unsafe_entry")
    return HANDLE(value)

def _close_raw(handle: HANDLE) -> None:
    value, handle.value = handle.value, None
    if value not in (None, INVALID_HANDLE_VALUE):
        _check_bool(_api().CloseHandle(HANDLE(value)), "CloseHandle")

def _close(handle: HANDLE) -> None:
    _close_raw(handle)

class _NtName:
    """Retain UTF-16 bytes without narrowing overflow into another name."""
    def __init__(self, value: str) -> None:
        if not value or "\x00" in value:
            raise _Failure("unsafe_entry")
        length = len(value.encode("utf-16-le"))
        maximum = length + c.sizeof(c.c_wchar)
        if maximum > 0xFFFF:
            raise _Failure("unavailable")
        self.buffer = c.create_unicode_buffer(value)
        self.string = UNICODE_STRING(
            length, maximum, c.cast(self.buffer, c.POINTER(c.c_wchar)),
        )

def _component(name: str) -> str:
    # This validates only one NT-relative component. It intentionally does not
    # impose DOS device/reserved-name policy; facade-derived names are its input.
    if (type(name) is not str or not name or name in (".", "..") or "\x00" in name  # noqa: E721
            or "/" in name or "\\" in name):
        raise _Failure("unsafe_entry")
    return name

def _normalise(exc: Exception, *, opening: bool = False, creating: bool = False) -> Exception:
    if isinstance(exc, _Failure | FileNotFoundError | FileExistsError):
        return exc
    if isinstance(exc, _NtError):
        if opening and exc.status in (STATUS_OBJECT_NAME_NOT_FOUND, STATUS_OBJECT_PATH_NOT_FOUND):
            return FileNotFoundError()
        if creating and exc.status == STATUS_OBJECT_NAME_COLLISION:
            return FileExistsError()
        if exc.status in (STATUS_NOT_SUPPORTED, STATUS_INVALID_DEVICE_REQUEST):
            return _Failure("unsupported_filesystem")
        if exc.status in (
            STATUS_REPARSE_POINT_ENCOUNTERED, STATUS_STOPPED_ON_SYMLINK,
            STATUS_NOT_A_DIRECTORY,
        ):
            return _Failure("unsafe_entry")
        # STATUS_ACCESS_DENIED from FileRenameInformation is the legacy rename
        # API's sharing-violation signal (destination open without
        # FILE_SHARE_DELETE), not a redirect/security refusal -- that case is
        # PermissionError from check_entry's own identity check, independent
        # of this NTSTATUS. Falls through to the generic "unavailable" below.
    if isinstance(exc, (_ReparseRefused, PermissionError)):
        return _Failure("unsafe_entry")
    if isinstance(exc, OSError):
        code = exc.winerror if exc.winerror is not None else exc.errno
        if code in (ERROR_NOT_SUPPORTED, ERROR_INVALID_FUNCTION):
            return _Failure("unsupported_filesystem")
    return _Failure("unavailable")

def _raise(
    exc: Exception, *, opening: bool = False, creating: bool = False
) -> t.NoReturn:
    # This is a native classification boundary, not the public sanitization
    # boundary. Task 7 cleans context/cause only after owned cleanup is complete.
    raise _normalise(exc, opening=opening, creating=creating)
HANDLE = c.c_void_p

PHANDLE = c.POINTER(HANDLE)

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

OBJ_CASE_INSENSITIVE = 0x00000040

OBJ_DONT_REPARSE = 0x00001000

FILE_OPEN = 1

FILE_CREATE = 2

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

DELETE = 0x00010000

READ_CONTROL = 0x00020000

SYNCHRONIZE = 0x00100000

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

        self.DuplicateHandle = self.k32.DuplicateHandle
        self.DuplicateHandle.argtypes = [HANDLE, HANDLE, HANDLE, PHANDLE, DWORD, BOOL, DWORD]
        self.DuplicateHandle.restype = BOOL
        self.GetVolumeInformationByHandleW = self.k32.GetVolumeInformationByHandleW
        self.GetVolumeInformationByHandleW.argtypes = [
            HANDLE, c.c_wchar_p, DWORD, c.POINTER(DWORD), c.POINTER(DWORD),
            c.POINTER(DWORD), c.c_wchar_p, DWORD,
        ]
        self.GetVolumeInformationByHandleW.restype = BOOL
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

def _last_error(action: str) -> OSError:
    return OSError(c.get_last_error(), f"{action}: {c.WinError(c.get_last_error())}")

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

# The source helpers above deliberately resolve these late definitions at call time.
def _open_relative(parent: int, name: str, disposition: int, *, directory: bool, access: int, security_descriptor: PVOID | None = None) -> int:
    native_name = _NtName(_component(name))
    attributes = OBJECT_ATTRIBUTES(c.sizeof(OBJECT_ATTRIBUTES), _as_handle(parent), c.pointer(native_name.string), OBJ_CASE_INSENSITIVE | OBJ_DONT_REPARSE, security_descriptor, None)
    iosb, result = IO_STATUS_BLOCK(), HANDLE()
    options = FILE_SYNCHRONOUS_IO_NONALERT | FILE_OPEN_REPARSE_POINT
    if directory:
        options |= FILE_DIRECTORY_FILE
    try:
        _check_status(_api().NtCreateFile(c.byref(result), access, c.byref(attributes), c.byref(iosb), None, FILE_ATTRIBUTE_DIRECTORY if directory else FILE_ATTRIBUTE_NORMAL, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, disposition, options, None, 0), "NtCreateFile")
        facts = _identity(result)
        if facts["reparse"]:
            raise _ReparseRefused()
        if not facts["disk_file"] or bool(facts["directory"]) is not directory:
            raise PermissionError("unexpected object")
        return int(result.value)
    except Exception as exc:
        if result.value not in (None, INVALID_HANDLE_VALUE):
            try:
                _close_raw(result)
            except Exception:
                pass
        _raise(exc, opening=disposition == FILE_OPEN, creating=disposition == FILE_CREATE)

def open_root(path: Path) -> int:
    try:
        raw = HANDLE(_api().CreateFileW(str(path), DIRECTORY_ACCESS, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, None, OPEN_EXISTING, 0x02000000, None))
        if raw.value == INVALID_HANDLE_VALUE:
            raise OSError(c.get_last_error(), "CreateFileW")
        facts = _identity(raw)
        if not facts["directory"] or not facts["disk_file"] or facts["reparse"]:
            raise PermissionError("unsafe root")
        flags = DWORD()
        _check_bool(_api().GetVolumeInformationByHandleW(
            raw, None, 0, None, None, c.byref(flags), None, 0,
        ), "GetVolumeInformationByHandleW")
        if not flags.value & 0x00000008:  # FILE_PERSISTENT_ACLS
            raise _Failure("unsupported_filesystem")
        _dacl_private(raw)  # Inspect capability, not private-directory policy.
        return int(raw.value)
    except Exception as exc:
        if "raw" in locals() and raw.value not in (None, INVALID_HANDLE_VALUE):
            try:
                _close_raw(raw)
            except Exception:
                pass
        _raise(exc, opening=True)

def open_namespace(parent: int, name: str, *, create: bool) -> int:
    if not create:
        return _open_relative(parent, name, FILE_OPEN, directory=True, access=DIRECTORY_ACCESS)
    try:
        return _open_relative(parent, name, FILE_CREATE, directory=True, access=DIRECTORY_ACCESS)
    except FileExistsError:
        return _open_relative(parent, name, FILE_OPEN, directory=True, access=DIRECTORY_ACCESS)

def _private_leaf(handle: HANDLE) -> None:
    facts = _identity(handle)
    if facts["directory"] or not facts["disk_file"] or facts["reparse"] or facts["links"] != 1:
        raise PermissionError("unsafe leaf")
    private, details = _dacl_private(handle)
    if not private or any(details["ace_flags"]):
        raise PermissionError("unsafe DACL")

def open_file(parent: int, name: str, *, writable: bool = False) -> int:
    access = (GENERIC_READ | GENERIC_WRITE | DELETE | SYNCHRONIZE) if writable else (GENERIC_READ | SYNCHRONIZE)
    handle = _open_relative(parent, name, FILE_OPEN, directory=False, access=access)
    try:
        _private_leaf(_as_handle(handle))
        return handle
    except Exception as exc:
        try:
            close(handle)
        except Exception:
            pass
        _raise(exc)

def create_file(parent: int, name: str) -> int:
    descriptor = PVOID()
    handle: int | None = None
    try:
        descriptor, _ = _private_descriptor()
        handle = _open_relative(
            parent, name, FILE_CREATE, directory=False,
            access=GENERIC_READ | GENERIC_WRITE | DELETE | SYNCHRONIZE,
            security_descriptor=descriptor,
        )
        _private_leaf(_as_handle(handle))
        return handle
    except Exception as exc:
        if handle is not None:
            try:
                _delete_on_handle(_as_handle(handle))
            except Exception:
                pass
            try:
                close(handle)
            except Exception:
                pass
        _raise(exc)
    finally:
        if descriptor:
            _api().LocalFree(c.cast(descriptor, HANDLE))

def _seek_start(handle: HANDLE) -> None:
    ignored = c.c_longlong()
    _check_bool(_api().SetFilePointerEx(handle, 0, c.byref(ignored), 0), "SetFilePointerEx")

def read_file(handle: int) -> bytes:
    raw = _as_handle(handle)
    try:
        _private_leaf(raw)
        _seek_start(raw)
        chunks: list[bytes] = []
        while True:
            buffer = c.create_string_buffer(1024 * 1024)
            got = DWORD()
            _check_bool(_api().ReadFile(raw, buffer, DWORD(len(buffer)), c.byref(got), None), "ReadFile")
            if got.value:
                chunks.append(buffer.raw[:got.value])
                continue
            return b"".join(chunks)
    except Exception as exc:
        _raise(exc)

def write_file(handle: int, payload: bytes) -> None:
    if type(payload) is not bytes:  # noqa: E721 -- exact-type record contract
        raise _Failure("unavailable")
    source, duplicate = _as_handle(handle), HANDLE()
    failure: Exception | None = None
    try:
        _private_leaf(source)
        _check_bool(
            _api().DuplicateHandle(
                _api().GetCurrentProcess(), source, _api().GetCurrentProcess(),
                c.byref(duplicate), 0, False, DUPLICATE_SAME_ACCESS,
            ),
            "DuplicateHandle",
        )
        _seek_start(duplicate)
        offset = 0
        while offset < len(payload):
            part = payload[offset:offset + 1024 * 1024]
            buffer, wrote = c.create_string_buffer(part), DWORD()
            _check_bool(
                _api().WriteFile(
                    duplicate, buffer, DWORD(len(part)), c.byref(wrote), None
                ),
                "WriteFile",
            )
            if not wrote.value:
                raise OSError("zero WriteFile")
            offset += wrote.value
    except Exception as exc:
        failure = exc
    finally:
        if duplicate.value not in (None, INVALID_HANDLE_VALUE):
            try:
                _close_raw(duplicate)
            except Exception as exc:
                if failure is None:
                    failure = exc
    if failure is not None:
        _raise(failure)

def check_entry(parent: int, name: str, handle: int) -> None:
    named = open_file(parent, name)
    try:
        _private_leaf(_as_handle(handle))
        if (int(_identity(_as_handle(named))["volume"]), int(_identity(_as_handle(named))["file_index"])) != (int(_identity(_as_handle(handle))["volume"]), int(_identity(_as_handle(handle))["file_index"])):
            raise PermissionError("entry identity changed")
    except Exception as exc:
        _raise(exc)
    finally:
        close(named)

def replace_file(parent: int, temp_name: str, temp_handle: int, destination: str) -> None:
    try:
        check_entry(parent, temp_name, temp_handle)
        _rename_on_handle(_as_handle(temp_handle), _as_handle(parent), _component(destination), True)
    except Exception as exc:
        _raise(exc)

def cleanup_owned(parent: int, name: str, handle: int) -> None:
    try:
        check_entry(parent, name, handle)
        _delete_on_handle(_as_handle(handle))
    except Exception as exc:
        _raise(exc)

def lock(handle: int, *, blocking: bool = True) -> bool:
    try:
        raw = _as_handle(handle)
        _private_leaf(raw)
        flags = LOCKFILE_EXCLUSIVE_LOCK | (0 if blocking else LOCKFILE_FAIL_IMMEDIATELY)
        overlapped = OVERLAPPED()
        ok = _api().LockFileEx(raw, flags, 0, 1, 0, c.byref(overlapped))
        if not ok and c.get_last_error() == ERROR_LOCK_VIOLATION:
            return False
        _check_bool(ok, "LockFileEx")
        return True
    except Exception as exc:
        _raise(exc)

def unlock(handle: int) -> None:
    try:
        overlapped = OVERLAPPED()
        _check_bool(_api().UnlockFileEx(_as_handle(handle), 0, 1, 0, c.byref(overlapped)), "UnlockFileEx")
    except Exception as exc:
        _raise(exc)

def close(handle: int) -> None:
    try:
        _close_raw(_as_handle(handle))
    except Exception as exc:
        _raise(exc)

def reason(exc: Exception) -> str:
    if isinstance(exc, _Failure):
        return exc.reason
    if isinstance(exc, (_ReparseRefused, PermissionError)):
        return "unsafe_entry"
    if os.name != "nt":
        return "unsupported_filesystem"
    return "unavailable"
