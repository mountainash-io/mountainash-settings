from __future__ import annotations

import errno
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

if not (sys.platform.startswith("linux") or sys.platform == "darwin"):
    pytest.skip(
        "POSIX native adapter is selected only on Linux and Darwin",
        allow_module_level=True,
    )

from mountainash_settings.secrets import _native_posix as native
from .posix_helpers import (
    close_all,
    darwin_acl_fingerprint,
    darwin_inheritable_acl,
    linux_default_acl,
    read_linux_acl,
    snapshot,
)


def test_root_is_retained_fd_not_retargeted_alias(tmp_path: Path):
    first, second, alias = tmp_path / "first", tmp_path / "second", tmp_path / "alias"
    first.mkdir(); second.mkdir(); alias.symlink_to(first, target_is_directory=True)
    root = native.open_root(alias)
    try:
        alias.unlink(); alias.symlink_to(second, target_is_directory=True)
        item = native.create_file(root, "record")
        try:
            native.write_file(item, b"first")
        finally:
            native.close(item)
        assert (first / "record").read_bytes() == b"first"
        assert not (second / "record").exists()
    finally:
        native.close(root)


def test_namespace_inherits_policy_but_private_leaf_is_private_before_write(tmp_path: Path):
    parent = tmp_path / "store"; parent.mkdir(mode=0o700)
    if sys.platform.startswith("linux"):
        root_policy = linux_default_acl(parent)
        policy = read_linux_acl
    else:
        darwin_inheritable_acl(parent)
        root_policy = darwin_acl_fingerprint(parent)
        policy = darwin_acl_fingerprint
    root = native.open_root(parent)
    namespace = native.open_namespace(root, "namespace", create=True)
    namespace_policy = policy(parent / "namespace")
    assert native._has_extended_acl(namespace)
    leaf = native.create_file(namespace, "record")
    try:
        info = os.fstat(leaf)
        assert info.st_uid == os.geteuid()
        assert stat.S_IMODE(info.st_mode) == 0o600
        assert info.st_nlink == 1
        native.check_entry(namespace, "record", leaf)
        assert native.read_file(leaf) == b""
        native.write_file(leaf, b"dummy")
    finally:
        close_all(leaf, namespace, root)
    assert policy(parent) == root_policy
    assert policy(parent / "namespace") == namespace_policy


_INHERITED_GID = next(
    (group for group in os.getgroups() if group != os.getgid()), os.getgid()
)


@pytest.mark.parametrize(
    "inherited_group", [_INHERITED_GID],
    ids=[f"{'primary' if _INHERITED_GID == os.getgid() else 'nonprimary'}-gid-{_INHERITED_GID}"],
)
def test_namespace_creation_matches_native_mkdir_policy_without_umask_mutation(
    tmp_path: Path, inherited_group: int,
):
    parent = tmp_path / "non-primary-group-parent"
    parent.mkdir()
    os.chown(parent, -1, inherited_group)
    os.chmod(parent, 0o2770)
    before = os.stat(parent, follow_symlinks=False)
    script = """
import os
import stat
import sys
from pathlib import Path
from mountainash_settings.secrets import _native_posix as native

parent = Path(sys.argv[1])
expected_group = int(sys.argv[2])
previous = os.umask(0o027)
try:
    root = native.open_root(parent)
    try:
        before = os.fstat(root)
        assert before.st_gid == expected_group
        os.mkdir("native-control", 0o777, dir_fd=root)
        reference = os.stat(
            "native-control", dir_fd=root, follow_symlinks=False,
        )
        namespace = native.open_namespace(root, "namespace", create=True)
        try:
            created = os.fstat(namespace)
            assert created.st_gid == reference.st_gid == before.st_gid
            assert stat.S_IMODE(created.st_mode) == stat.S_IMODE(reference.st_mode)
        finally:
            native.close(namespace)
        after = os.fstat(root)
        assert (
            (after.st_dev, after.st_ino, after.st_mode, after.st_uid, after.st_gid)
            == (before.st_dev, before.st_ino, before.st_mode, before.st_uid, before.st_gid)
        )
    finally:
        native.close(root)
    # This observes the old mask and restores it immediately; adapter code did not
    # change process-global umask while creating the namespace.
    assert os.umask(previous) == 0o027
finally:
    os.umask(previous)
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(parent), str(inherited_group)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    after = os.stat(parent, follow_symlinks=False)
    assert (
        (after.st_dev, after.st_ino, after.st_mode, after.st_uid, after.st_gid)
        == (before.st_dev, before.st_ino, before.st_mode, before.st_uid, before.st_gid)
    )


def test_existing_inherited_acl_is_refused_without_mutating_it(tmp_path: Path):
    parent = tmp_path / "store"; parent.mkdir(mode=0o700)
    if sys.platform.startswith("linux"):
        linux_default_acl(parent)
    else:
        darwin_inheritable_acl(parent)
    root = native.open_root(parent)
    try:
        raw = os.open("exposed", os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=root)
        try:
            before = os.fstat(raw)
            with pytest.raises(Exception) as caught:
                native.check_entry(root, "exposed", raw)
            assert native.reason(caught.value) == "unsafe_entry"
            assert os.fstat(raw).st_size == before.st_size == 0
        finally:
            os.close(raw)
    finally:
        native.close(root)


def test_redirects_hardlinks_and_fifo_refuse_without_outside_access(tmp_path: Path):
    store, outside = tmp_path / "store", tmp_path / "outside"
    store.mkdir(mode=0o700); outside.mkdir(mode=0o700)
    target = outside / "sentinel"; target.write_bytes(b"outside"); target.chmod(0o600)
    root = native.open_root(store)
    try:
        store.joinpath("namespace").symlink_to(outside, target_is_directory=True)
        with pytest.raises(Exception) as caught:
            native.open_namespace(root, "namespace", create=False)
        assert native.reason(caught.value) == "unsafe_entry"
        for name in ("record", ".record.tmp", ".record.cleared", ".record.lock"):
            store.joinpath(name).symlink_to(target)
            with pytest.raises(Exception) as caught:
                native.open_file(root, name, writable=name.endswith("lock"))
            assert native.reason(caught.value) == "unsafe_entry"
        private = native.create_file(root, "private")
        try:
            os.link(store / "private", store / "alias")
        finally:
            native.close(private)
        with pytest.raises(Exception) as caught:
            native.open_file(root, "alias")
        assert native.reason(caught.value) == "unsafe_entry"
        os.mkfifo(store / "fifo", 0o600)
        with pytest.raises(Exception) as caught:
            native.open_file(root, "fifo")
        assert native.reason(caught.value) == "unsafe_entry"
        assert target.read_bytes() == b"outside"
    finally:
        native.close(root)


def test_complete_io_loops_over_forced_short_reads_and_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root = native.open_root(tmp_path)
    temp = native.create_file(root, ".record.tmp")
    real_read, real_write = native.os.read, native.os.write

    def short_write(fd: int, data: bytes | memoryview) -> int:
        return real_write(fd, memoryview(data)[:7])

    def short_read(fd: int, size: int) -> bytes:
        return real_read(fd, min(size, 5))

    monkeypatch.setattr(native.os, "write", short_write)
    try:
        payload = b"x" * (256 * 1024 + 17)
        native.write_file(temp, payload)
        monkeypatch.setattr(native.os, "read", short_read)
        assert native.read_file(temp) == payload
        native.replace_file(root, ".record.tmp", temp, "record")
        native.check_entry(root, "record", temp)
    finally:
        monkeypatch.setattr(native.os, "read", real_read)
        monkeypatch.setattr(native.os, "write", real_write)
        native.close(temp)
        native.close(root)
def test_precommit_writer_close_error_preserves_old_entry_and_cleans_owned_temp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root = native.open_root(tmp_path)
    old = native.create_file(root, "record")
    native.write_file(old, b"old"); native.close(old)
    temp = native.create_file(root, ".record.tmp")
    real_close = native.os.close
    duplicate = os.dup(temp); real_close(duplicate)  # obtain the next deterministic reusable fd number
    calls: list[int] = []
    def close_after_real_release(fd: int) -> None:
        real_close(fd)
        calls.append(fd)
        if len(calls) == 1:
            raise OSError(errno.EIO, "injected after native close")
    monkeypatch.setattr(native.os, "close", close_after_real_release)
    try:
        with pytest.raises(OSError):
            native.write_file(temp, b"new")
        native.cleanup_owned(root, ".record.tmp", temp)
        assert snapshot(root, "record")[-1] == b"old"
        with pytest.raises(FileNotFoundError):
            native.open_file(root, ".record.tmp")
    finally:
        monkeypatch.setattr(native.os, "close", real_close)
        close_all(temp, root)


@pytest.mark.parametrize(
    "code",
    sorted(
        {
            errno.ENOSYS,
            getattr(errno, "EOPNOTSUPP", errno.ENOSYS),
            getattr(errno, "ENOTSUP", errno.ENOSYS),
        }
    ),
)
def test_missing_native_capability_has_fixed_reason(code: int):
    assert native.reason(OSError(code, "fixture")) == "unsupported_filesystem"


def test_cleanup_substitution_refuses_and_preserves_reused_name(tmp_path: Path):
    root = native.open_root(tmp_path)
    owned = native.create_file(root, ".owned.tmp")
    os.unlink(".owned.tmp", dir_fd=root)
    replacement = native.create_file(root, ".owned.tmp")
    try:
        native.write_file(replacement, b"intruder")
        before = snapshot(root, ".owned.tmp")
        with pytest.raises(Exception) as caught:
            native.cleanup_owned(root, ".owned.tmp", owned)
        assert native.reason(caught.value) == "unsafe_entry"
        assert snapshot(root, ".owned.tmp") == before
    finally:
        close_all(replacement, owned, root)


if sys.platform == "darwin":
    def test_initial_stage_substitution_preserves_the_unexpected_directory(tmp_path, monkeypatch):
        root = native.open_root(tmp_path)
        original_open = native._open_directory
        observed = None

        def substitute(parent, name):
            nonlocal observed
            if name.startswith(".private-"):
                os.rename(name, "original.stage", src_dir_fd=parent, dst_dir_fd=parent)
                os.mkdir(name, 0o700, dir_fd=parent)
                facts = os.stat(name, dir_fd=parent, follow_symlinks=False)
                observed = (name, (facts.st_dev, facts.st_ino))
            return original_open(parent, name)

        try:
            monkeypatch.setattr(native, "_open_directory", substitute)
            with pytest.raises(Exception) as caught:
                native.create_file(root, "record")
            assert native.reason(caught.value) == "unsafe_entry"
            assert observed is not None
            name, identity = observed
            facts = os.stat(name, dir_fd=root, follow_symlinks=False)
            assert (facts.st_dev, facts.st_ino) == identity
            assert not (tmp_path / "record").exists()
        finally:
            native.close(root)


def test_nonblocking_flock_reports_only_contention(tmp_path: Path):
    root = native.open_root(tmp_path)
    first = native.create_file(root, ".record.lock")
    second = native.open_file(root, ".record.lock", writable=True)
    try:
        assert native.lock(first)
        assert native.lock(second, blocking=False) is False
        native.unlock(first)
        assert native.lock(second, blocking=False) is True
        native.unlock(second)
    finally:
        close_all(second, first, root)
