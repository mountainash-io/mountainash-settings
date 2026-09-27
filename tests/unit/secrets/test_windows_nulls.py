"""Safe null-result simulation; real Windows ownership tests run natively."""
from types import SimpleNamespace

import pytest

from mountainash_settings.secrets import _native_windows as native
from mountainash_settings.secrets.errors import _Failure


def test_sid_conversion_null_success_fails_and_releases(monkeypatch):
    freed = []
    monkeypatch.setattr(native, "_api", lambda: SimpleNamespace(
        ConvertSidToStringSidW=lambda sid, output: 1,
        LocalFree=lambda pointer: freed.append(pointer),
    ))
    with pytest.raises(_Failure):
        native._sid_text(native.PVOID())
    assert len(freed) == 1


@pytest.mark.parametrize("operation", ["root", "relative"])
def test_open_null_success_fails_before_identity(monkeypatch, tmp_path, operation):
    inspected = []
    monkeypatch.setattr(native, "_api", lambda: SimpleNamespace(
        CreateFileW=lambda *args: None,
        NtCreateFile=lambda *args: 0,
    ))
    def identity(handle):
        inspected.append(handle)
        return {"reparse": False, "disk_file": True, "directory": True}
    monkeypatch.setattr(native, "_identity", identity)
    with pytest.raises(_Failure):
        if operation == "root":
            native.open_root(tmp_path)
        else:
            native._open_relative(1, "child", native.FILE_OPEN, directory=True, access=native.DIRECTORY_ACCESS)
    assert inspected == []


def test_null_ace_fails_before_dereference_and_frees_descriptor(monkeypatch):
    freed = []
    def security_info(handle, kind, flags, owner, group, dacl, sacl, descriptor):
        dacl._obj.value = 1
        descriptor._obj.value = 2
        return 0
    def acl_info(dacl, info, size, kind):
        info._obj.AceCount = 1
        return 1
    monkeypatch.setattr(native, "_current_sid", lambda: "user")
    monkeypatch.setattr(native, "_api", lambda: SimpleNamespace(
        GetSecurityInfo=security_info,
        GetSecurityDescriptorControl=lambda *args: 1,
        GetAclInformation=acl_info,
        GetAce=lambda *args: 1,
        LocalFree=lambda pointer: freed.append(pointer),
    ))
    with pytest.raises(_Failure):
        native._dacl_private(native.HANDLE(1))
    assert len(freed) == 1
