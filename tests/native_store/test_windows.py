from __future__ import annotations

import os
from contextlib import ExitStack
from pathlib import Path

import pytest

if os.name != "nt":
    pytest.skip("Windows-native primitives", allow_module_level=True)

from mountainash_settings.secrets import _native_windows as native  # noqa: E402
from mountainash_settings.secrets.errors import _Failure  # noqa: E402
from ._windows_fixtures import (  # noqa: E402
    close_quietly,
    file_id,
    make_junction,
    make_symbolic_link,
    open_descendant_without_component_guard,
    open_for_dacl,
    open_without_delete_share,
    set_dacl,
    snapshot_private,
)


def _private(parent: int, name: str, payload: bytes = b"") -> int:
    handle = native.create_file(parent, name)
    native.write_file(handle, payload)
    return handle


def test_retained_root_refuses_junctions_and_remains_pinned(tmp_path: Path):
    original, replacement, outside = tmp_path / "original", tmp_path / "replacement", tmp_path / "outside"
    original.mkdir(); replacement.mkdir(); outside.mkdir()
    alias = tmp_path / "alias"
    make_junction(alias, original)
    root = native.open_root(alias)
    sentinel_parent = native.open_root(outside)
    sentinel = _private(sentinel_parent, "sentinel", b"outside")
    native.close(sentinel)
    os.rmdir(alias)
    make_junction(alias, replacement)
    try:
        written = _private(root, "inside", b"inside")
        native.close(written)
        assert (original / "inside").read_bytes() == b"inside"
        assert not (replacement / "inside").exists()
        for surface in ("namespace", "credential", "temp", "marker", "lock"):
            redirect = original / f"{surface}.entry"
            make_junction(redirect, outside)
            try:
                with pytest.raises(_Failure) as caught:
                    if surface == "namespace":
                        native.open_namespace(root, redirect.name, create=False)
                    else:
                        native.open_file(root, redirect.name, writable=False)
                assert native.reason(caught.value) == "unsafe_entry"
                assert (outside / "sentinel").read_bytes() == b"outside"
            finally:
                os.rmdir(redirect)
    finally:
        close_quietly(sentinel_parent)
        close_quietly(root)


@pytest.mark.parametrize("kind", ["file-symbolic", "directory-symbolic", "symbolic-ancestor"])
def test_symbolic_links_refuse_without_touching_outside(tmp_path: Path, kind):
    store, outside = tmp_path / "store", tmp_path / "outside"
    store.mkdir()
    outside.mkdir()
    with ExitStack() as resources:
        parent = native.open_root(store)
        resources.callback(native.close, parent)
        outside_parent = native.open_root(outside)
        resources.callback(native.close, outside_parent)
        # A valid private target prevents an unrelated DACL refusal masking a
        # regression that follows the link instead of rejecting its reparse tag.
        sentinel = _private(outside_parent, "sentinel", b"outside-unchanged")
        native.close(sentinel)
        before = snapshot_private(outside_parent, "sentinel")
        link = store / kind
        directory = kind != "file-symbolic"
        make_symbolic_link(
            link, outside if directory else outside / "sentinel",
            directory=directory,
        )
        resources.callback(os.rmdir if directory else os.unlink, link)
        opened = None
        try:
            if kind == "symbolic-ancestor":
                with pytest.raises(native._NtError) as caught:
                    opened = open_descendant_without_component_guard(
                        parent, r"symbolic-ancestor\sentinel",
                    )
                assert caught.value.status in (
                    native.STATUS_REPARSE_POINT_ENCOUNTERED,
                    native.STATUS_STOPPED_ON_SYMLINK,
                )
            else:
                with pytest.raises(_Failure) as caught:
                    opened = (
                        native.open_namespace(parent, kind, create=False)
                        if directory else native.open_file(parent, kind)
                    )
                assert native.reason(caught.value) == "unsafe_entry"
        finally:
            if opened is not None:
                native.close(opened)
        assert snapshot_private(outside_parent, "sentinel") == before
        assert list(outside.iterdir()) == [outside / "sentinel"]


def test_directory_inherits_but_new_leaves_are_private_and_existing_acl_is_refused(tmp_path: Path):
    parent = native.open_root(tmp_path)
    try:
        sid = native._current_sid()
        security = open_for_dacl(tmp_path, directory=True)
        try:
            set_dacl(security, f"D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;{sid})(A;OICI;GR;;;WD)")
        finally:
            native.close(security)
        namespace = native.open_namespace(parent, "domain", create=True)
        try:
            policy_before = native._dacl_private(native.HANDLE(namespace))[1]
            assert any(flags & 0x10 for flags in policy_before["ace_flags"])
            leaf = _private(namespace, "private.yaml", b"payload")
            try:
                assert native._dacl_private(native.HANDLE(leaf))[0]
                assert native._identity(native.HANDLE(leaf))["links"] == 1
            finally:
                native.close(leaf)
            exposed = _private(namespace, "exposed.yaml")
            native.close(exposed)
            exposed = open_for_dacl(tmp_path / "domain" / "exposed.yaml")
            try:
                set_dacl(exposed, "D:P(A;;FA;;;WD)")
            finally:
                native.close(exposed)
            with pytest.raises(_Failure) as caught:
                native.open_file(namespace, "exposed.yaml")
            assert native.reason(caught.value) == "unsafe_entry"
            assert native._dacl_private(native.HANDLE(namespace))[1] == policy_before
        finally:
            native.close(namespace)
    finally:
        native.close(parent)


def test_hardlink_cleanup_substitution_and_create_collision_preserve_intruder(tmp_path: Path):
    parent = native.open_root(tmp_path)
    try:
        owned = _private(parent, "owned.tmp", b"owned")
        native._rename_on_handle(native.HANDLE(owned), native.HANDLE(parent), "detached.tmp", False)
        intruder = _private(parent, "owned.tmp", b"intruder")
        native.close(intruder)
        with pytest.raises(_Failure) as caught:
            native.cleanup_owned(parent, "owned.tmp", owned)
        assert native.reason(caught.value) == "unsafe_entry"
        current = native.open_file(parent, "owned.tmp")
        try:
            assert native.read_file(current) == b"intruder"
            assert file_id(current) != file_id(owned)
        finally:
            native.close(current)
        linked = _private(parent, "linked.yaml", b"private")
        try:
            native._link_on_handle(
                native.HANDLE(linked), native.HANDLE(parent), "linked-alias.yaml"
            )
        finally:
            native.close(linked)
        with pytest.raises(_Failure) as caught:
            native.open_file(parent, "linked-alias.yaml")
        assert native.reason(caught.value) == "unsafe_entry"
        collision = _private(parent, "collision.tmp")
        native.close(collision)
        with pytest.raises(FileExistsError):
            native.create_file(parent, "collision.tmp")
    finally:
        close_quietly(owned)
        native.close(parent)


def test_full_io_duplicate_writer_real_lock_and_share_denial(tmp_path: Path):
    parent = native.open_root(tmp_path)
    try:
        record = _private(parent, "record.yaml", b"old")
        temp = _private(parent, "temp.tmp")
        payload = b"x" * (3 * 1024 * 1024 + 17)
        native.write_file(temp, payload)
        assert native.read_file(temp) == payload
        lock_a = _private(parent, ".record.lock")
        lock_b = native.open_file(parent, ".record.lock", writable=True)
        try:
            assert native.lock(lock_a, blocking=False)
            assert native.lock(lock_b, blocking=False) is False
            native.unlock(lock_a)
            assert native.lock(lock_b, blocking=False)
            native.unlock(lock_b)
        finally:
            native.close(lock_b); native.close(lock_a)
        native.close(record)
        deny_delete = open_without_delete_share(tmp_path / "record.yaml")
        try:
            with pytest.raises(_Failure) as caught:
                native.replace_file(parent, "temp.tmp", temp, "record.yaml")
            assert native.reason(caught.value) == "unavailable"
        finally:
            native.close(deny_delete)
        assert (tmp_path / "record.yaml").read_bytes() == b"old"
        native.replace_file(parent, "temp.tmp", temp, "record.yaml")
        replacement = native.open_file(parent, "record.yaml")
        try:
            assert native.read_file(replacement) == payload
        finally:
            native.close(replacement)
            native.close(temp)
    finally:
        native.close(parent)


def test_short_io_and_duplicate_close_failure_preserve_precommit_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    parent = native.open_root(tmp_path)
    try:
        looped = _private(parent, "looped.tmp")
        payload = b"x" * (1024 * 1024 + 17)
        api = native._api()
        read, write = api.ReadFile, api.WriteFile

        def short_read(handle, buffer, size, received, overlapped):
            return read(handle, buffer, max(1, size.value // 2), received, overlapped)

        def short_write(handle, buffer, size, written, overlapped):
            return write(handle, buffer, max(1, size.value // 2), written, overlapped)

        monkeypatch.setattr(api, "ReadFile", short_read)
        monkeypatch.setattr(api, "WriteFile", short_write)
        native.write_file(looped, payload)
        assert native.read_file(looped) == payload
        monkeypatch.setattr(api, "ReadFile", read)
        monkeypatch.setattr(api, "WriteFile", write)
        native.close(looped)

        old = _private(parent, "record.yaml", b"old")
        native.close(old)
        temporary = _private(parent, "broken.tmp")
        raw_close = native._close_raw

        def close_writer_then_fail(handle):
            value = handle.value
            raw_close(handle)
            if value != temporary:
                raise OSError("injected duplicate writer close failure")

        monkeypatch.setattr(native, "_close_raw", close_writer_then_fail)
        with pytest.raises(_Failure) as caught:
            native.write_file(temporary, b"candidate")
        assert native.reason(caught.value) == "unavailable"
        monkeypatch.setattr(native, "_close_raw", raw_close)
        assert (tmp_path / "record.yaml").read_bytes() == b"old"
        native.cleanup_owned(parent, "broken.tmp", temporary)
        native.close(temporary)
        with pytest.raises(FileNotFoundError):
            native.open_file(parent, "broken.tmp")
    finally:
        native.close(parent)
