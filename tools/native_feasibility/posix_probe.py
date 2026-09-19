"""Disposable native POSIX filesystem-mechanism feasibility probes.

This module deliberately models only mechanisms that a future store could use.  It
never imports the product package and every fixture lives under the caller's
throwaway root.
"""

from __future__ import annotations

import ctypes
import errno
import fcntl
import json
import os
import re
import secrets
import select
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path


_MODE_PRIVATE = 0o600
_OPEN_BASE = os.O_NOFOLLOW | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0)


class _Refused(PermissionError):
    """An unsafe filesystem entry was observed and intentionally not repaired."""


_ACL = ctypes.CDLL(
    "/usr/lib/libSystem.B.dylib" if sys.platform == "darwin" else "libacl.so.1",
    use_errno=True,
)
_ACL.acl_free.argtypes = [ctypes.c_void_p]
_ACL.acl_free.restype = ctypes.c_int
_ACL.acl_to_text.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ssize_t)]
_ACL.acl_to_text.restype = ctypes.c_void_p
if sys.platform == "darwin":
    _ACL.acl_get_fd_np.argtypes = [ctypes.c_int, ctypes.c_int]
    _ACL.acl_get_fd_np.restype = ctypes.c_void_p
    _ACL.acl_set_fd_np.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_int]
    _ACL.acl_set_fd_np.restype = ctypes.c_int
    _ACL.acl_init.argtypes = [ctypes.c_int]
    _ACL.acl_init.restype = ctypes.c_void_p
    _ACL.acl_get_entry.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    _ACL.acl_get_entry.restype = ctypes.c_int
else:
    _ACL.acl_get_fd.argtypes = [ctypes.c_int]
    _ACL.acl_get_fd.restype = ctypes.c_void_p
    _ACL.acl_set_fd.argtypes = [ctypes.c_int, ctypes.c_void_p]
    _ACL.acl_set_fd.restype = ctypes.c_int
    _ACL.acl_from_text.argtypes = [ctypes.c_char_p]
    _ACL.acl_from_text.restype = ctypes.c_void_p
    _ACL.acl_equiv_mode.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)]
    _ACL.acl_equiv_mode.restype = ctypes.c_int


def _acl_error() -> OSError:
    code = ctypes.get_errno()
    return OSError(code, "native descriptor ACL operation failed")


@contextmanager
def _opened_acl(fd: int) -> Iterator[int]:
    ctypes.set_errno(0)
    acl = (
        _ACL.acl_get_fd_np(fd, 0x100)
        if sys.platform == "darwin"
        else _ACL.acl_get_fd(fd)
    )
    if not acl and sys.platform == "darwin" and ctypes.get_errno() == errno.ENOENT:
        # acl_get_fd_np reports a missing FILESEC_ACL property as ENOENT.
        # The descriptor must still designate a real object; this is not record absence.
        os.fstat(fd)
        acl = _ACL.acl_init(0)
    if not acl:
        raise _acl_error()
    try:
        yield acl
    finally:
        _ACL.acl_free(acl)


def _has_extended_acl(fd: int) -> bool:
    with _opened_acl(fd) as acl:
        if sys.platform == "darwin":
            entry = ctypes.c_void_p()
            # Darwin returns 0 for an entry, -1/EINVAL for an empty valid ACL.
            result = _ACL.acl_get_entry(acl, 0, ctypes.byref(entry))
            if result == 0:
                return True
            if ctypes.get_errno() == errno.EINVAL:
                return False
            raise _acl_error()
        result = _ACL.acl_equiv_mode(acl, None)
        if result < 0:
            raise _acl_error()
        return result != 0


def _acl_text(fd: int) -> str:
    with _opened_acl(fd) as acl:
        length = ctypes.c_ssize_t()
        text = _ACL.acl_to_text(acl, ctypes.byref(length))
        if not text:
            raise _acl_error()
        try:
            return ctypes.string_at(text, length.value).decode("utf-8")
        finally:
            _ACL.acl_free(text)


def _clear_new_acl(fd: int, mode: int = _MODE_PRIVATE) -> None:
    """Only exclusive new internal objects may have inherited ACLs removed."""
    acl = (
        _ACL.acl_init(0)
        if sys.platform == "darwin"
        else _ACL.acl_from_text(b"u::rw-,g::---,o::---")
    )
    if not acl:
        raise _acl_error()
    try:
        result = (
            _ACL.acl_set_fd_np(fd, acl, 0x100)
            if sys.platform == "darwin"
            else _ACL.acl_set_fd(fd, acl)
        )
        if result != 0:
            raise _acl_error()
    finally:
        _ACL.acl_free(acl)
    os.fchmod(fd, mode)


@contextmanager
def _fixture(root: Path, prefix: str) -> Iterator[Path]:
    path = Path(tempfile.mkdtemp(prefix=f"{prefix}-", dir=root))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@contextmanager
def _temporary_umask(value: int) -> Iterator[None]:
    old = os.umask(value)
    try:
        yield
    finally:
        os.umask(old)


def _identity(info: os.stat_result) -> tuple[int, int]:
    return (info.st_dev, info.st_ino)


def _private_regular(fd: int) -> os.stat_result:
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode):
        raise _Refused("entry is not a regular file")
    if info.st_nlink != 1:
        raise _Refused("regular file has more than one link")
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise _Refused("regular file is exposed through mode bits")
    if _has_extended_acl(fd):
        raise _Refused("entry has an unsupported extended ACL")
    return info


def _open_directory(parent_fd: int, name: str) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY | _OPEN_BASE
    fd = os.open(name, flags, dir_fd=parent_fd)
    try:
        if not stat.S_ISDIR(os.fstat(fd).st_mode):
            raise _Refused("opened namespace is not a directory")
        return fd
    except BaseException:
        os.close(fd)
        raise


def _open_regular(parent_fd: int, name: str, *, writable: bool = False) -> int:
    flags = (os.O_RDWR if writable else os.O_RDONLY) | _OPEN_BASE
    fd = os.open(name, flags, dir_fd=parent_fd)
    try:
        _private_regular(fd)
        return fd
    except BaseException:
        os.close(fd)
        raise


def _create_regular(parent_fd: int, name: str) -> int:
    """Create an empty private fixture/temp, NOT a complete logical record write."""
    if sys.platform == "darwin":
        return _darwin_create_private(parent_fd, name)
    fd = os.open(
        name,
        os.O_RDWR | os.O_CREAT | os.O_EXCL | _OPEN_BASE,
        _MODE_PRIVATE,
        dir_fd=parent_fd,
    )
    try:
        _clear_new_acl(fd)
        _private_regular(fd)
        return fd
    except BaseException:
        os.close(fd)
        raise


def _darwin_create_private(parent_fd: int, name: str) -> int:
    """Secure an empty internal directory before any payload inode exists.

    Revoking an inherited file ACL after opening is insufficient: another reader
    could retain already-granted rights. Publish an already-private inode instead.
    Application namespaces are never tightened.
    """
    staging = f".private-{secrets.token_hex(16)}.stage"
    os.mkdir(staging, 0o700, dir_fd=parent_fd)
    identity = _identity(os.stat(staging, dir_fd=parent_fd, follow_symlinks=False))
    with ExitStack() as resources:
        try:
            stage_fd = _open_directory(parent_fd, staging)
        except BaseException:
            if (
                _identity(os.stat(staging, dir_fd=parent_fd, follow_symlinks=False))
                != identity
            ):
                raise _Refused("unopened staging directory identity changed")
            os.rmdir(staging, dir_fd=parent_fd)
            raise
        resources.callback(os.close, stage_fd)
        identity = _identity(os.fstat(stage_fd))
        fd: int | None = None
        payload_exists = published = False
        try:
            try:
                _clear_new_acl(stage_fd, 0o700)
                if (
                    _has_extended_acl(stage_fd)
                    or stat.S_IMODE(os.fstat(stage_fd).st_mode) != 0o700
                ):
                    raise _Refused("internal staging directory is not private")
                fd = os.open(
                    "payload",
                    os.O_RDWR | os.O_CREAT | os.O_EXCL | _OPEN_BASE,
                    _MODE_PRIVATE,
                    dir_fd=stage_fd,
                )
                payload_exists = True
                _private_regular(fd)
                os.link(
                    "payload",
                    name,
                    src_dir_fd=stage_fd,
                    dst_dir_fd=parent_fd,
                    follow_symlinks=False,
                )
                published = True
                os.unlink("payload", dir_fd=stage_fd)
                payload_exists = False
                _private_regular(fd)
            finally:
                if payload_exists:
                    os.unlink("payload", dir_fd=stage_fd)
                if (
                    _identity(os.stat(staging, dir_fd=parent_fd, follow_symlinks=False))
                    != identity
                ):
                    raise _Refused("internal staging directory identity changed")
                os.rmdir(staging, dir_fd=parent_fd)
            resources.close()
        except BaseException:
            if fd is not None:
                try:
                    if published:
                        _cleanup_owned(parent_fd, name, fd)
                finally:
                    os.close(fd)
            raise
        assert fd is not None
        return fd


def _entry_matches(parent_fd: int, name: str, fd: int) -> os.stat_result:
    """Prove the name still designates this validated file without following it."""
    named = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    opened = _private_regular(fd)
    if _identity(named) != _identity(opened):
        raise _Refused("entry was replaced after opening")
    return opened


def _cleanup_owned(parent_fd: int, name: str, fd: int) -> None:
    """Unlink only a still-owned entry during the protected cleanup interval."""
    _entry_matches(parent_fd, name, fd)
    os.unlink(name, dir_fd=parent_fd)


def _write(fd: int, payload: bytes) -> None:
    os.lseek(fd, 0, os.SEEK_SET)
    os.ftruncate(fd, 0)
    written = os.write(fd, payload)
    if written != len(payload):
        raise AssertionError("short dummy-fixture write")
    os.fsync(fd)


def _publish_record(parent: int, name: str, payload: bytes) -> int:
    """Publish complete bytes via a private temp under exclusive writer ownership."""
    old: int | None = None
    fd: int | None = None
    committed = False
    temporary = f".record.{secrets.token_hex(16)}.tmp"
    try:
        try:
            old = _open_regular(parent, name)
        except FileNotFoundError:
            pass
        fd = _create_regular(parent, temporary)
        _write(fd, payload)
        _entry_matches(parent, temporary, fd)
        if old is not None:
            _entry_matches(parent, name, old)
        os.replace(temporary, name, src_dir_fd=parent, dst_dir_fd=parent)
        committed = True
        if old is not None:
            detached, old = old, None
            os.close(detached)
        result, fd = fd, None
        return result
    finally:
        try:
            if fd is not None and not committed:
                _cleanup_owned(parent, temporary, fd)
        finally:
            try:
                if fd is not None:
                    os.close(fd)
            finally:
                if old is not None:
                    os.close(old)


def _read(fd: int) -> bytes:
    os.lseek(fd, 0, os.SEEK_SET)
    return os.read(fd, 4096)


def _assert_refused(
    action: Callable[[], object],
    label: str,
    *,
    expected: type[Exception] = _Refused,
    codes: tuple[int, ...] = (),
) -> str:
    try:
        action()
    except expected as error:
        if codes and getattr(error, "errno", None) not in codes:
            raise AssertionError(f"{label}: unexpected native refusal code") from error
        return f"{type(error).__name__}:{getattr(error, 'errno', None)}"
    raise AssertionError(f"{label} was accepted")


def _key_layout(key: str) -> tuple[tuple[str, ...], str]:
    parts = key.split(".")
    if not parts or any(not re.fullmatch(r"[a-z0-9_]+", part) for part in parts):
        raise ValueError("probe key segments must match [a-z0-9_]+")
    if len(parts) == 1:
        return (), f"{parts[0]}.yaml"
    if len(parts) == 2:
        return (parts[0],), f"{parts[1]}.yaml"
    return (parts[0],), f"{'-'.join(parts[1:])}.yaml"


def _make_layout(root_fd: int, key: str) -> tuple[int, str, tuple[str, ...]]:
    namespaces, leaf = _key_layout(key)
    current = os.dup(root_fd)
    try:
        for namespace in namespaces:
            try:
                os.mkdir(namespace, 0o777, dir_fd=current)
            except FileExistsError:
                pass
            next_fd = _open_directory(current, namespace)
            os.close(current)
            current = next_fd
        return current, leaf, namespaces
    except BaseException:
        os.close(current)
        raise


def _root_pinning(root: Path) -> dict[str, object]:
    with _fixture(root, "root-pinning") as fixture, ExitStack() as resources:
        stable_parent = fixture / "stable-parent"
        first, second = stable_parent / "first", stable_parent / "second"
        stable_parent.mkdir(mode=0o700)
        first.mkdir(mode=0o700)
        second.mkdir(mode=0o700)
        (second / "sentinel").write_bytes(b"outside-retained-root")
        flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0)
        direct = os.open(first, flags)
        resources.callback(os.close, direct)
        (fixture / "ancestor").symlink_to(stable_parent, target_is_directory=True)
        (fixture / "alias").symlink_to(
            Path("ancestor") / "first", target_is_directory=True
        )
        pinned = os.open(fixture / "alias", flags)
        resources.callback(os.close, pinned)
        if _identity(os.fstat(pinned)) != _identity(os.fstat(direct)):
            raise AssertionError("startup alias did not resolve to the direct root")
        os.unlink(fixture / "ancestor")
        (fixture / "ancestor").symlink_to(second, target_is_directory=True)
        fd = _publish_record(pinned, "ancestor.record", b"ancestor-pinned")
        resources.callback(os.close, fd)
        os.unlink(fixture / "alias")
        (fixture / "alias").symlink_to(second, target_is_directory=True)
        fd = _publish_record(pinned, "final.record", b"final-pinned")
        resources.callback(os.close, fd)
        newer = os.open(fixture / "alias", flags)
        resources.callback(os.close, newer)
        if _identity(os.fstat(newer)) != _identity(os.stat(second)):
            raise AssertionError("new root selection did not see retargeted alias")
        if (first / "ancestor.record").read_bytes() != b"ancestor-pinned":
            raise AssertionError("ancestor retarget escaped pinned root")
        if (first / "final.record").read_bytes() != b"final-pinned":
            raise AssertionError("final retarget escaped pinned root")
        if sorted(p.name for p in second.iterdir()) != ["sentinel"]:
            raise AssertionError("pinned operations touched the second root")
        if (second / "sentinel").read_bytes() != b"outside-retained-root":
            raise AssertionError("second root sentinel changed")
        missing = _assert_refused(
            lambda: os.open(fixture / "missing", flags),
            "missing root",
            expected=FileNotFoundError,
            codes=(errno.ENOENT,),
        )
        ordinary = fixture / "ordinary"
        ordinary.write_bytes(b"not-a-directory")
        before = ordinary.stat()
        non_directory = _assert_refused(
            lambda: os.open(ordinary, flags),
            "non-directory root",
            expected=NotADirectoryError,
            codes=(errno.ENOTDIR,),
        )
        if (fixture / "missing").exists() or ordinary.stat() != before:
            raise AssertionError("failed startup created or repaired its target")
        return {
            "mechanism": "trusted startup traversal then retained directory descriptor",
            "pinned_identity": list(_identity(os.fstat(pinned))),
            "missing_refusal": missing,
            "non_directory_refusal": non_directory,
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


def _layout_worker(fixture_name: str) -> int:
    fixture = Path(fixture_name)
    store = fixture / "store"
    store.mkdir(mode=0o770)
    selected_gid = next(
        (gid for gid in os.getgroups() if gid != os.getgid()), os.getgid()
    )
    os.chown(store, -1, selected_gid)
    os.chmod(store, 0o2770)
    root_fd = os.open(store, os.O_RDONLY | os.O_DIRECTORY | _OPEN_BASE)
    observations: dict[str, dict[str, object]] = {}
    try:
        before = os.fstat(root_fd)
        with _temporary_umask(0o027):
            os.mkdir("native-control", 0o777, dir_fd=root_fd)
            reference = os.stat("native-control", dir_fd=root_fd, follow_symlinks=False)
            if reference.st_gid != before.st_gid:
                raise AssertionError(
                    "native mkdir did not inherit the application group"
                )
            for key in ("one", "domain.stem", "domain.middle.leaf"):
                directory_fd, name, namespaces = _make_layout(root_fd, key)
                try:
                    record_fd = _publish_record(directory_fd, name, key.encode())
                    try:
                        record_mode = stat.S_IMODE(os.fstat(record_fd).st_mode)
                    finally:
                        os.close(record_fd)
                    relative = Path(*namespaces, name) if namespaces else Path(name)
                    if not (store / relative).is_file():
                        raise AssertionError(
                            f"native layout path was not created: {relative}"
                        )
                    namespace_stats = []
                    cursor = store
                    for segment in namespaces:
                        cursor = cursor / segment
                        namespace_stats.append(os.stat(cursor, follow_symlinks=False))
                    for info in namespace_stats:
                        if info.st_gid != reference.st_gid or stat.S_IMODE(
                            info.st_mode
                        ) != stat.S_IMODE(reference.st_mode):
                            raise AssertionError(
                                "namespace diverged from native mkdir inheritance policy"
                            )
                    observations[key] = {
                        "relative_path": str(relative),
                        "record_mode": oct(record_mode),
                        "namespace_permission_modes": [
                            oct(info.st_mode & 0o777) for info in namespace_stats
                        ],
                        "namespace_setgid_bits": [
                            bool(info.st_mode & stat.S_ISGID)
                            for info in namespace_stats
                        ],
                    }
                finally:
                    os.close(directory_fd)
        entries_before_fault = set(os.listdir(root_fd))
        with _temporary_umask(0o777):
            _assert_refused(
                lambda: _darwin_create_private(root_fd, ".unopened.tmp"),
                "staging directory open fault",
                expected=PermissionError,
                codes=(errno.EACCES, errno.EPERM),
            )
        if set(os.listdir(root_fd)) != entries_before_fault:
            raise AssertionError("failed staging open left an internal directory")
        after = os.fstat(root_fd)
    finally:
        os.close(root_fd)
    application_metadata_unchanged = (
        _identity(before) == _identity(after)
        and before.st_mode == after.st_mode
        and before.st_gid == after.st_gid
        and before.st_uid == after.st_uid
    )
    if not application_metadata_unchanged:
        raise AssertionError(
            "namespace creation changed application directory metadata"
        )
    if observations["one"]["relative_path"] != "one.yaml":
        raise AssertionError("one-part key layout does not match M1")
    if observations["domain.stem"]["relative_path"] != "domain/stem.yaml":
        raise AssertionError("two-part key layout does not match M1")
    if observations["domain.middle.leaf"]["relative_path"] != "domain/middle-leaf.yaml":
        raise AssertionError("three-part key layout does not match M1")
    if observations["domain.stem"]["namespace_permission_modes"] != ["0o750"]:
        raise AssertionError("namespace mode was not umask-derived")
    if observations["domain.middle.leaf"]["namespace_permission_modes"] != ["0o750"]:
        raise AssertionError("namespace mode was not inherited without repair")
    if any(item["record_mode"] != "0o600" for item in observations.values()):
        raise AssertionError("private record was not created before payload use")
    print(
        json.dumps(
            {
                "mechanism": "child-process umask and native mkdir permission/group inheritance",
                "native_reference_namespace": {
                    "mode": oct(stat.S_IMODE(reference.st_mode)),
                    "gid": reference.st_gid,
                },
                "layouts": observations,
                "application_directory_metadata_unchanged": application_metadata_unchanged,
                "application_directory_before": {
                    "mode": oct(stat.S_IMODE(before.st_mode)),
                    "gid": before.st_gid,
                },
                "application_directory_after": {
                    "mode": oct(stat.S_IMODE(after.st_mode)),
                    "gid": after.st_gid,
                },
                "private_internal_mode": "0o600",
            }
        )
    )
    return 0


def _directory_policy(fd: int) -> dict[str, object]:
    info = os.fstat(fd)
    return {
        "identity": list(_identity(info)),
        "uid": info.st_uid,
        "gid": info.st_gid,
        "mode": oct(stat.S_IMODE(info.st_mode)),
        "acl": _acl_text(fd),
    }


def _namespace_routes(parent_fd: int) -> dict[str, object]:
    routes: dict[str, object] = {}
    for route in ("set", "delete", "transaction"):
        directory, leaf, _ = _make_layout(parent_fd, f"{route}_first.item")
        try:
            if not _has_extended_acl(directory):
                raise AssertionError("first-use namespace lost inherited ACL policy")
            before = _directory_policy(directory)
            # Reusing an application-provisioned namespace must not repair its policy.
            again, _, _ = _make_layout(parent_fd, f"{route}_first.other")
            os.close(again)
            if _directory_policy(directory) != before:
                raise AssertionError("existing application namespace was modified")
            name = leaf if route == "set" else f".{leaf}.{route}"
            fd = (
                _publish_record(directory, name, b"record")
                if route == "set"
                else _create_regular(directory, name)
            )
            try:
                if route == "transaction":
                    fcntl.flock(fd, fcntl.LOCK_EX)
                    fcntl.flock(fd, fcntl.LOCK_UN)
                elif route == "delete":
                    _write(fd, b"cleared")
                _entry_matches(directory, name, fd)
            finally:
                os.close(fd)
            if _directory_policy(directory) != before:
                raise AssertionError("private leaf creation changed namespace policy")
            routes[route] = before
        finally:
            os.close(directory)
    return routes


def _namespace_inheritance_and_layouts(root: Path) -> dict[str, object]:
    with _fixture(root, "layout") as fixture:
        result = subprocess.run(
            [sys.executable, "-I", __file__, "--worker-layout", str(fixture)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode:
            raise RuntimeError(f"layout worker failed: {result.stderr}")
        observations = json.loads(result.stdout)
        with ExitStack() as resources:
            fd = os.open(fixture / "store", os.O_RDONLY | os.O_DIRECTORY | _OPEN_BASE)
            resources.callback(os.close, fd)
            before = sorted(os.listdir(fd))
            invalid = ("", "UPPER", "a/b", "a..b", "a-b")
            for key in invalid:
                _assert_refused(
                    lambda key=key: _make_layout(fd, key),
                    "invalid key",
                    expected=ValueError,
                )
            if sorted(os.listdir(fd)) != before:
                raise AssertionError("invalid keys changed store entries")
        acl = (
            _darwin_acl_privacy(fixture)
            if sys.platform == "darwin"
            else _linux_acl_privacy(fixture)
        )
        if acl.get("status") == "blocked":
            return acl
        observations["acl_routes"] = acl["first_use_routes"]
        observations["checks"] = {
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
        }
        return observations


def _redirect_refusal(root: Path) -> dict[str, object]:
    with _fixture(root, "redirect") as fixture, ExitStack() as resources:
        store, outside = fixture / "store", fixture / "outside"
        store.mkdir(mode=0o700)
        outside.mkdir(mode=0o700)
        root_fd = os.open(store, os.O_RDONLY | os.O_DIRECTORY | _OPEN_BASE)
        resources.callback(os.close, root_fd)
        target = outside / "target"
        target.write_bytes(b"outside")
        os.chmod(target, _MODE_PRIVATE)
        sentinel = os.open(target, os.O_RDWR | _OPEN_BASE)
        resources.callback(os.close, sentinel)
        _read(sentinel)
        before = os.fstat(sentinel)
        names = {
            "credential": "credential.record",
            "temp": ".credential.tmp",
            "marker": ".credential.marker",
            "lock": ".credential.lock",
        }
        refusals: dict[str, str] = {}
        (store / "namespace").symlink_to(outside, target_is_directory=True)
        refusals["namespace"] = _assert_refused(
            lambda: _open_directory(root_fd, "namespace"),
            "namespace link",
            expected=OSError,
            codes=(errno.ENOTDIR, errno.ELOOP),
        )
        for surface, name in names.items():
            (store / name).symlink_to(target)
            refusals[surface] = _assert_refused(
                lambda name=name: _open_regular(root_fd, name),
                surface,
                expected=OSError,
                codes=(errno.ELOOP,),
            )
            if os.fstat(sentinel) != before:
                raise AssertionError("redirect refusal touched outside metadata")
        fcntl.flock(sentinel, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(sentinel, fcntl.LOCK_UN)
        if _read(sentinel) != b"outside":
            raise AssertionError("redirect refusal changed outside content")
        original = _create_regular(root_fd, "mutable.record")
        resources.callback(os.close, original)
        os.unlink("mutable.record", dir_fd=root_fd)
        replacement = _create_regular(root_fd, "mutable.record")
        resources.callback(os.close, replacement)
        _write(replacement, b"replacement")
        refusals["substitution"] = _assert_refused(
            lambda: _cleanup_owned(root_fd, "mutable.record", original), "substitution"
        )
        _entry_matches(root_fd, "mutable.record", replacement)
        if _read(replacement) != b"replacement":
            raise AssertionError("substitution refusal changed the replacement")
        return {
            "mechanism": "O_NOFOLLOW/O_NONBLOCK/openat and named identity validation",
            "refusals": refusals,
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


def _linux_acl_privacy(fixture: Path) -> dict[str, object]:
    if not shutil.which("setfacl") or not shutil.which("getfacl"):
        return {
            "status": "blocked",
            "reason": "Linux ACL fixture utilities unavailable",
        }
    parent = fixture / "linux-acl-parent"
    parent.mkdir(mode=0o700)
    uid = os.getuid() + 100_000
    subprocess.run(
        [
            "setfacl",
            "-m",
            f"d:u::rwx,d:u:{uid}:rwx,d:g::---,d:m::rwx,d:o::---",
            str(parent),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    )

    def parent_policy() -> str:
        return subprocess.run(
            ["getfacl", "-cp", str(parent)],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout

    before = parent_policy()
    with ExitStack() as resources:
        parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | _OPEN_BASE)
        resources.callback(os.close, parent_fd)
        routes = _namespace_routes(parent_fd)
        os.mkdir("namespace", 0o777, dir_fd=parent_fd)
        namespace_fd = _open_directory(parent_fd, "namespace")
        resources.callback(os.close, namespace_fd)
        if not _has_extended_acl(namespace_fd):
            raise AssertionError("namespace did not inherit application ACL policy")
        fd = os.open(
            "private.record",
            os.O_RDWR | os.O_CREAT | os.O_EXCL | _OPEN_BASE,
            _MODE_PRIVATE,
            dir_fd=parent_fd,
        )
        resources.callback(os.close, fd)
        inherited = _acl_text(fd)
        if not _has_extended_acl(fd):
            raise AssertionError("fixture did not inherit a named ACL")
        refusal = _assert_refused(lambda: _private_regular(fd), "existing extended ACL")
        if _acl_text(fd) != inherited or os.fstat(fd).st_size != 0:
            raise AssertionError("refusal repaired or wrote the inherited-ACL fixture")
        _clear_new_acl(fd)
        _private_regular(fd)
        if parent_policy() != before:
            raise AssertionError("private-file ACL creation changed application policy")
        _write(fd, b"acl-cleared-before-payload")
        return {
            "mechanism": "libacl acl_get_fd/acl_set_fd; fixture-only setfacl/getfacl",
            "existing_extended_acl_refusal": refusal,
            "inherited_named_acl_removed_before_write": True,
            "namespace_acl_inherited": True,
            "parent_default_acl_preserved": True,
            "first_use_routes": routes,
            "privacy_policy": "reject extended ACLs; clear only exclusive newly created files",
        }


def _darwin_acl_privacy(fixture: Path) -> dict[str, object]:
    parent = fixture / "darwin-acl-parent"
    parent.mkdir(mode=0o700)
    subprocess.run(
        [
            "chmod",
            "+a",
            "everyone allow read,file_inherit,directory_inherit",
            str(parent),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    )
    with ExitStack() as resources:
        parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | _OPEN_BASE)
        resources.callback(os.close, parent_fd)
        before = _acl_text(parent_fd)
        routes = _namespace_routes(parent_fd)
        os.mkdir("namespace", 0o777, dir_fd=parent_fd)
        namespace_fd = _open_directory(parent_fd, "namespace")
        resources.callback(os.close, namespace_fd)
        if not _has_extended_acl(namespace_fd):
            raise AssertionError("namespace did not inherit application ACL policy")
        fd = os.open(
            "exposed.record",
            os.O_RDWR | os.O_CREAT | os.O_EXCL | _OPEN_BASE,
            _MODE_PRIVATE,
            dir_fd=parent_fd,
        )
        resources.callback(os.close, fd)
        if not _has_extended_acl(fd):
            raise AssertionError("fixture did not inherit an extended ACL")
        inherited = _acl_text(fd)
        refusal = _assert_refused(lambda: _private_regular(fd), "existing allow ACL")
        if _acl_text(fd) != inherited or os.fstat(fd).st_size != 0:
            raise AssertionError("refusal repaired or wrote the exposed-ACL fixture")
        private = _create_regular(parent_fd, ".private-fixture.tmp")
        resources.callback(os.close, private)
        _private_regular(private)
        if _acl_text(parent_fd) != before:
            raise AssertionError("private-file ACL creation changed application policy")
        _write(private, b"private-before-publication")
        return {
            "mechanism": "private empty staging directory; private inode; exclusive linkat publication",
            "existing_allow_acl_refusal": refusal,
            "private_inode_created_before_publication": True,
            "namespace_acl_inherited": True,
            "parent_acl_preserved": True,
            "first_use_routes": routes,
            "mode_bits_not_used_as_acl_proof": True,
            "privacy_policy": "existing extended ACLs rejected; no exposed payload inode tightening",
        }


def _object_privacy(root: Path) -> dict[str, object]:
    with _fixture(root, "privacy") as fixture, ExitStack() as resources:
        root_fd = os.open(fixture, os.O_RDONLY | os.O_DIRECTORY | _OPEN_BASE)
        resources.callback(os.close, root_fd)
        hard = _create_regular(root_fd, "hard.record")
        resources.callback(os.close, hard)
        os.link(
            "hard.record",
            "hard-alias.record",
            src_dir_fd=root_fd,
            dst_dir_fd=root_fd,
            follow_symlinks=False,
        )
        hardlink_refusal = _assert_refused(
            lambda: _open_regular(root_fd, "hard-alias.record"), "hard link"
        )

        exposed = _create_regular(root_fd, "exposed.record")
        resources.callback(os.close, exposed)
        os.chmod(fixture / "exposed.record", 0o644)
        exposed_refusal = _assert_refused(
            lambda: _open_regular(root_fd, "exposed.record"), "exposed regular file"
        )

        fifo = fixture / "blocking.fifo"
        os.mkfifo(fifo, 0o600)
        fifo_refusal = _assert_refused(
            lambda: _open_regular(root_fd, "blocking.fifo"), "FIFO"
        )

        if sys.platform.startswith("linux"):
            acl = _linux_acl_privacy(fixture)
        elif sys.platform == "darwin":
            acl = _darwin_acl_privacy(fixture)
        else:
            acl = {
                "status": "blocked",
                "reason": f"unsupported POSIX platform {sys.platform}",
            }
        if acl.get("status") == "blocked":
            return {
                "status": "blocked",
                "reason": str(acl["reason"]),
                "hardlink_refusal": hardlink_refusal,
                "exposed_refusal": exposed_refusal,
                "fifo_refusal": fifo_refusal,
            }
        return {
            "mechanism": "O_NONBLOCK open then fstat regular/single-link/private validation",
            "hardlink_refusal": hardlink_refusal,
            "exposed_refusal": exposed_refusal,
            "fifo_refusal": fifo_refusal,
            "fifo_never_read": True,
            "acl": acl,
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


def _snapshot_entry(parent: int, name: str) -> tuple[object, ...]:
    fd = _open_regular(parent, name)
    try:
        info = os.fstat(fd)
        # Exclude atime, which our own evidence reads may update.
        return (
            _identity(info),
            info.st_mode,
            info.st_uid,
            info.st_gid,
            info.st_nlink,
            info.st_size,
            info.st_mtime_ns,
            info.st_ctime_ns,
            _read(fd),
        )
    finally:
        os.close(fd)


def _precommit_fault(parent: int, phase: str) -> None:
    payload = json.dumps(
        {"value": object() if phase == "serialization" else "candidate"}
    ).encode()
    name = f".record.{secrets.token_hex(16)}.tmp"
    fd: int | None = _create_regular(parent, name)
    identity = _identity(os.fstat(fd))
    try:
        if phase == "write":
            readonly = _open_regular(parent, name)
            try:
                os.write(readonly, payload)  # Real EBADF at the write syscall itself.
            finally:
                os.close(readonly)
        _write(fd, payload)
        if phase == "close":
            # Deterministic close-boundary injection AFTER actual native release.
            # Model a reported close error without ever retrying the released fd.
            detached, fd = fd, None
            os.close(detached)
            raise OSError(
                errno.EIO, "injected close-boundary error after native release"
            )
        if phase == "replace":
            previous_mode = stat.S_IMODE(os.fstat(parent).st_mode)
            os.fchmod(parent, 0o500)
            try:
                os.replace(name, "record", src_dir_fd=parent, dst_dir_fd=parent)
            finally:
                os.fchmod(parent, previous_mode)
        raise AssertionError("requested precommit fault was not observed")
    finally:
        try:
            if fd is None:
                fd = _open_regular(parent, name)
                if _identity(os.fstat(fd)) != identity:
                    raise _Refused("cleanup candidate identity changed")
            _cleanup_owned(parent, name, fd)
        finally:
            if fd is not None:
                os.close(fd)


def _temp_replace_cleanup(root: Path) -> dict[str, object]:
    with _fixture(root, "replace") as fixture, ExitStack() as resources:
        parent = os.open(fixture, os.O_RDONLY | os.O_DIRECTORY | _OPEN_BASE)
        resources.callback(os.close, parent)
        for name, payload in (
            ("record", b"old-record"),
            (".record.marker", b"old-marker"),
            (".known.tmp", b"stale-collision"),
        ):
            fd = _create_regular(parent, name)
            resources.callback(os.close, fd)
            _write(fd, payload)
        snapshots = {
            name: _snapshot_entry(parent, name)
            for name in ("record", ".record.marker", ".known.tmp")
        }
        collision = _assert_refused(
            lambda: _create_regular(parent, ".known.tmp"),
            "exclusive collision",
            expected=FileExistsError,
            codes=(errno.EEXIST,),
        )
        faults = {}
        for phase, expected, codes in (
            ("serialization", TypeError, ()),
            ("write", OSError, (errno.EBADF,)),
            ("close", OSError, (errno.EIO,)),
            ("replace", PermissionError, (errno.EACCES, errno.EPERM)),
        ):
            faults[phase] = _assert_refused(
                lambda phase=phase: _precommit_fault(parent, phase),
                phase,
                expected=expected,
                codes=codes,
            )
            for name, before in snapshots.items():
                if _snapshot_entry(parent, name) != before:
                    raise AssertionError(
                        "precommit fault changed prior record, marker or collision"
                    )
            if set(os.listdir(parent)) != set(snapshots):
                raise AssertionError(
                    "precommit cleanup left an operation-owned temporary"
                )
        candidate_name = f".record.{secrets.token_hex(16)}.tmp"
        candidate = _create_regular(parent, candidate_name)
        resources.callback(os.close, candidate)
        _write(candidate, b"after-commit")
        marker = _open_regular(parent, ".record.marker")
        resources.callback(os.close, marker)
        _entry_matches(parent, candidate_name, candidate)
        os.replace(candidate_name, "record", src_dir_fd=parent, dst_dir_fd=parent)
        os.fchmod(parent, 0o500)
        try:
            postcommit = _assert_refused(
                lambda: _cleanup_owned(parent, ".record.marker", marker),
                "postcommit marker removal",
                expected=PermissionError,
                codes=(errno.EACCES, errno.EPERM),
            )
        finally:
            os.fchmod(parent, 0o700)
        if _snapshot_entry(parent, "record")[-1] != b"after-commit":
            raise AssertionError("postcommit failure hid the committed record")
        if _snapshot_entry(parent, ".record.marker") != snapshots[".record.marker"]:
            raise AssertionError("failed marker cleanup changed the retained marker")
        owned = _create_regular(parent, ".owned.tmp")
        resources.callback(os.close, owned)
        os.unlink(".owned.tmp", dir_fd=parent)
        intruder = _create_regular(parent, ".owned.tmp")
        resources.callback(os.close, intruder)
        _write(intruder, b"intruder")
        before = _snapshot_entry(parent, ".owned.tmp")
        mismatch = _assert_refused(
            lambda: _cleanup_owned(parent, ".owned.tmp", owned),
            "cleanup ownership mismatch",
        )
        _entry_matches(parent, ".owned.tmp", intruder)
        if _snapshot_entry(parent, ".owned.tmp") != before:
            raise AssertionError(
                "mismatched cleanup removed or changed the named replacement"
            )
        return {
            "mechanism": "exclusive random private temp; native replace; identity-checked cleanup",
            "collision": collision,
            "precommit_faults": faults,
            "close_fault_kind": "injected EIO after actual native close; not a naturally occurring OS error",
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


def _marker_interruption(root: Path) -> dict[str, object]:
    with _fixture(root, "marker") as fixture, ExitStack() as resources:
        parent = os.open(fixture, os.O_RDONLY | os.O_DIRECTORY | _OPEN_BASE)
        resources.callback(os.close, parent)
        states = {}
        for phase in ("interruption", "handled", "normal"):
            name, marker_name = f"{phase}.record", f".{phase}.cleared"
            record = _create_regular(parent, name)
            marker = _create_regular(parent, marker_name)
            resources.callback(os.close, record)
            resources.callback(os.close, marker)
            _write(record, b"raw-record")
            _write(marker, b"cleared")
            before_record = _snapshot_entry(parent, name)
            before_marker = _snapshot_entry(parent, marker_name)
            if phase == "handled":
                os.fchmod(parent, 0o500)
                try:
                    _assert_refused(
                        lambda: _cleanup_owned(parent, name, record),
                        "credential removal failure",
                        expected=PermissionError,
                        codes=(errno.EACCES, errno.EPERM),
                    )
                finally:
                    os.fchmod(parent, 0o700)
            if phase != "normal":
                if (
                    _snapshot_entry(parent, name) != before_record
                    or _snapshot_entry(parent, marker_name) != before_marker
                ):
                    raise AssertionError(
                        "interruption/failure performed unrequested repair"
                    )
                states[phase] = {"get": "raw-record", "is_cleared": True}
                continue
            _cleanup_owned(parent, name, record)
            _assert_refused(
                lambda: _open_regular(parent, name),
                "deleted credential",
                expected=FileNotFoundError,
                codes=(errno.ENOENT,),
            )
            if _snapshot_entry(parent, marker_name) != before_marker:
                raise AssertionError("normal deletion changed the authoritative marker")
            states["normal_delete"] = {"get": None, "is_cleared": True}
            recreated = _create_regular(parent, name)
            resources.callback(os.close, recreated)
            _write(recreated, b"recreated")
            _cleanup_owned(parent, marker_name, marker)
            _assert_refused(
                lambda: _open_regular(parent, marker_name),
                "recreated marker",
                expected=FileNotFoundError,
                codes=(errno.ENOENT,),
            )
            if _snapshot_entry(parent, name)[-1] != b"recreated":
                raise AssertionError("recreate did not publish the new record")
            states["recreate"] = {"get": "recreated", "is_cleared": False}
        return {
            "mechanism": "marker first; independent raw-record and marker observations",
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


def _worker_lock_wait(directory: str) -> int:
    parent = int(directory)
    fd = _open_regular(parent, ".record.lock", writable=True)
    try:
        _entry_matches(parent, ".record.lock", fd)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            print(json.dumps({"phase": "contended", "errno": error.errno}), flush=True)
            if error.errno not in (errno.EAGAIN, errno.EWOULDBLOCK):
                raise
        else:
            fcntl.flock(fd, fcntl.LOCK_UN)
            print(json.dumps({"phase": "unexpected-acquisition"}), flush=True)
            return 1
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            print(json.dumps({"phase": "acquired-after-release"}), flush=True)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
        return 0
    finally:
        os.close(fd)


def _read_worker_line(process: subprocess.Popen[str]) -> dict[str, object]:
    assert process.stdout is not None
    readable, _, _ = select.select([process.stdout], [], [], 5)
    if not readable:
        raise TimeoutError("lock contender did not report its nonblocking contention")
    line = process.stdout.readline()
    if not line:
        raise RuntimeError("lock contender exited before reporting contention")
    return json.loads(line)


def _cooperative_locking(root: Path) -> dict[str, object]:
    with _fixture(root, "locking") as fixture, ExitStack() as resources:
        root_fd = os.open(fixture, os.O_RDONLY | os.O_DIRECTORY | _OPEN_BASE)
        resources.callback(os.close, root_fd)
        lock = _create_regular(root_fd, ".record.lock")
        protected_temp = _create_regular(root_fd, ".record.cleanup.tmp")
        resources.callback(os.close, lock)
        resources.callback(os.close, protected_temp)
        _write(lock, b"cooperative-lock")
        same_process = _open_regular(root_fd, ".record.lock", writable=True)
        resources.callback(os.close, same_process)
        os.symlink(".record.lock", ".invalid.lock", dir_fd=root_fd)
        _assert_refused(
            lambda: _open_regular(root_fd, ".invalid.lock", writable=True),
            "invalid lock",
            expected=OSError,
            codes=(errno.ELOOP,),
        )
        _write(protected_temp, b"cleanup-under-lock")
        worker: subprocess.Popen[str] | None = None
        try:
            fcntl.flock(lock, fcntl.LOCK_EX)
            _assert_refused(
                lambda: fcntl.flock(same_process, fcntl.LOCK_EX | fcntl.LOCK_NB),
                "same-process contention",
                expected=BlockingIOError,
                codes=(errno.EAGAIN, errno.EWOULDBLOCK),
            )
            try:
                worker = subprocess.Popen(
                    [
                        sys.executable,
                        "-I",
                        __file__,
                        "--worker-lock-wait",
                        str(root_fd),
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    pass_fds=(root_fd,),
                )
                contended = _read_worker_line(worker)
                if contended.get("phase") != "contended":
                    raise AssertionError(
                        "separate process did not observe nonblocking lock contention"
                    )
                _cleanup_owned(root_fd, ".record.cleanup.tmp", protected_temp)
                if (fixture / ".record.cleanup.tmp").exists():
                    raise AssertionError(
                        "protected cleanup did not run while lock was held"
                    )
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
            assert worker is not None
            try:
                stdout, stderr = worker.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                worker.kill()
                worker.communicate()
                raise
            if worker.returncode:
                raise RuntimeError(f"lock contender failed: {stderr}")
            acquired = json.loads(stdout)
            if acquired.get("phase") != "acquired-after-release":
                raise AssertionError(
                    "same blocking contender did not acquire after lock release"
                )
            fcntl.flock(same_process, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(same_process, fcntl.LOCK_UN)
        except BaseException:
            if worker is not None and worker.poll() is None:
                worker.terminate()
                try:
                    worker.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    worker.kill()
                    worker.communicate()
            raise
        return {
            "mechanism": "one fcntl.flock contender: LOCK_NB observation then blocking LOCK_EX",
            "contender_nonblocking_contention_observed": True,
            "same_contender_acquired_after_release": True,
            "cleanup_ran_inside_lock_interval": True,
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


class _QuiescentOwner:
    """Native directory ownership only; not a product store implementation."""

    def __init__(self, source: int) -> None:
        self._lock = threading.Lock()
        self._fd: int | None = None
        fd = os.dup(source)
        try:
            if not stat.S_ISDIR(os.fstat(fd).st_mode):
                raise _Refused("owner root is not a directory")
        except BaseException:
            os.close(fd)
            raise
        self._fd = fd

    def directory(self) -> int:
        with self._lock:
            if self._fd is None:
                raise RuntimeError("owner is closed")
            return self._fd

    def close(self) -> None:
        with self._lock:
            fd, self._fd = self._fd, None
        if fd is not None:
            os.close(fd)

    def __enter__(self) -> _QuiescentOwner:
        self.directory()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except (AttributeError, OSError):
            pass  # Finalization is best effort; explicit close reports native errors.

    @contextmanager
    def deferred_entry(self) -> Iterator[_QuiescentOwner]:
        lock = _open_regular(self.directory(), ".lifecycle.lock", writable=True)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield self
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
        finally:
            os.close(lock)


def _owner_quiescent_lifecycle(root: Path) -> dict[str, object]:
    with _fixture(root, "lifecycle") as fixture, ExitStack() as resources:
        parent = os.open(fixture, os.O_RDONLY | os.O_DIRECTORY | _OPEN_BASE)
        resources.callback(os.close, parent)
        for name in (
            "owned.record",
            "unrelated.record",
            ".lifecycle.lock",
            ".owned.marker",
        ):
            fd = _create_regular(parent, name)
            try:
                _write(fd, name.encode())
            finally:
                os.close(fd)
        regular = _open_regular(parent, "owned.record")
        resources.callback(os.close, regular)
        reused_numbers = []

        def prove_reuse(number: int, closed: _QuiescentOwner | None = None) -> None:
            fd = _open_regular(parent, "unrelated.record")
            try:
                if fd != number:
                    raise AssertionError("released native descriptor was not reused")
                if closed is not None:
                    closed.close()
                    closed.close()
                    closed.__del__()
                if _read(fd) != b"unrelated.record":
                    raise AssertionError(
                        "stale owner released unrelated reused descriptor"
                    )
                reused_numbers.append(fd)
            finally:
                os.close(fd)

        expected = os.dup(parent)
        os.close(expected)
        _assert_refused(lambda: _QuiescentOwner(regular), "partial construction")
        prove_reuse(expected)
        with _QuiescentOwner(parent) as contextual:
            context_number = contextual.directory()
            if _snapshot_entry(context_number, "owned.record")[-1] != b"owned.record":
                raise AssertionError(
                    "context owner selected the wrong native directory"
                )
        prove_reuse(context_number, contextual)
        finalized = _QuiescentOwner(parent)
        final_number = finalized.directory()
        del finalized
        prove_reuse(final_number)

        owner = _QuiescentOwner(parent)
        resources.callback(owner.close)
        owned_number = owner.directory()
        with owner.deferred_entry():
            if (
                _snapshot_entry(owner.directory(), "owned.record")[-1]
                != b"owned.record"
            ):
                raise AssertionError("transaction admission lost the retained root")
        if _snapshot_entry(owner.directory(), "owned.record")[-1] != b"owned.record":
            raise AssertionError("transaction exit closed the store")
        entered, release = threading.Event(), threading.Event()
        failures: list[BaseException] = []

        def active_user() -> None:
            try:
                admitted = owner.directory()
                os.fstat(admitted)
                entered.set()
                if not release.wait(5):
                    raise TimeoutError("application did not release its active user")
                if _snapshot_entry(admitted, "owned.record")[-1] != b"owned.record":
                    raise AssertionError("active user lost the native root")
            except BaseException as error:
                failures.append(error)
                entered.set()

        worker = threading.Thread(target=active_user, daemon=True)
        worker.start()
        try:
            if not entered.wait(5):
                raise TimeoutError("active native user did not start")
            deferred = owner.deferred_entry()
        finally:
            release.set()
            worker.join(5)
        if worker.is_alive():
            raise AssertionError("application did not quiesce before native close")
        if failures:
            raise failures[0]
        owner.close()
        operations = {
            "postclose_read": lambda: _open_regular(owner.directory(), "owned.record"),
            "postclose_write": lambda: _create_regular(
                owner.directory(), "forbidden.record"
            ),
            "postclose_delete": lambda: os.unlink(
                "owned.record", dir_fd=owner.directory()
            ),
            "postclose_marker": lambda: os.stat(
                ".owned.marker", dir_fd=owner.directory(), follow_symlinks=False
            ),
            "deferred_entry": lambda: deferred.__enter__(),
        }
        refusals = {
            name: _assert_refused(operation, name, expected=RuntimeError)
            for name, operation in operations.items()
        }
        prove_reuse(owned_number, owner)
        if _snapshot_entry(parent, "owned.record")[-1] != b"owned.record":
            raise AssertionError("rejected post-close operation changed the record")
        if "forbidden.record" in os.listdir(parent):
            raise AssertionError("rejected post-close write created an entry")
        return {
            "mechanism": "native directory admission, caller quiescence, detached terminal close",
            "postclose_refusals": refusals,
            "native_reused_descriptors": reused_numbers,
            "boundary": "native ownership equivalents, not product API qualification",
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


def run(
    root: Path, record: Callable[[str, Callable[[], dict[str, object]]], None]
) -> None:
    """Register every disposable POSIX-native scenario with the shared reporter."""
    scenarios: tuple[tuple[str, Callable[[Path], dict[str, object]]], ...] = (
        ("root_pinning", _root_pinning),
        ("namespace_inheritance_and_layouts", _namespace_inheritance_and_layouts),
        ("redirect_refusal", _redirect_refusal),
        ("object_privacy", _object_privacy),
        ("temp_replace_cleanup", _temp_replace_cleanup),
        ("marker_interruption", _marker_interruption),
        ("cooperative_locking", _cooperative_locking),
        ("owner_quiescent_lifecycle", _owner_quiescent_lifecycle),
    )
    for name, scenario in scenarios:
        record(name, lambda scenario=scenario: scenario(root))


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--worker-layout":
        raise SystemExit(_layout_worker(sys.argv[2]))
    if len(sys.argv) == 3 and sys.argv[1] == "--worker-lock-wait":
        raise SystemExit(_worker_lock_wait(sys.argv[2]))
    raise SystemExit("private helper: --worker-layout PATH | --worker-lock-wait PATH")
