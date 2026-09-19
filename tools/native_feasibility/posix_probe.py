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
    _ACL.acl_get_entry.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]
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
    acl = _ACL.acl_get_fd_np(fd, 0x100) if sys.platform == "darwin" else _ACL.acl_get_fd(fd)
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


def _clear_new_acl(fd: int) -> None:
    """Only exclusive, newly created leaves may have inherited ACLs removed."""
    acl = _ACL.acl_init(0) if sys.platform == "darwin" else _ACL.acl_from_text(b"u::rw-,g::---,o::---")
    if not acl:
        raise _acl_error()
    try:
        result = _ACL.acl_set_fd_np(fd, acl, 0x100) if sys.platform == "darwin" else _ACL.acl_set_fd(fd, acl)
        if result != 0:
            raise _acl_error()
    finally:
        _ACL.acl_free(acl)
    os.fchmod(fd, _MODE_PRIVATE)




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


def _entry_matches(parent_fd: int, name: str, fd: int) -> os.stat_result:
    """Prove the name still designates this validated file without following it."""
    named = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    opened = _private_regular(fd)
    if _identity(named) != _identity(opened):
        raise _Refused(f"{name!r} was replaced after opening")
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


def _read(fd: int) -> bytes:
    os.lseek(fd, 0, os.SEEK_SET)
    return os.read(fd, 4096)


def _assert_refused(action: Callable[[], object], label: str) -> str:
    try:
        action()
    except (OSError, RuntimeError, _Refused) as error:
        return type(error).__name__
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
    with _fixture(root, "root-pinning") as fixture:
        stable_parent = fixture / "stable-parent"
        first = stable_parent / "first"
        second = stable_parent / "second"
        stable_parent.mkdir(mode=0o700)
        first.mkdir(mode=0o700)
        second.mkdir(mode=0o700)
        (fixture / "ancestor").symlink_to(stable_parent, target_is_directory=True)
        (fixture / "alias").symlink_to(Path("ancestor") / "first", target_is_directory=True)

        # Startup aliases are intentionally followed once; the result is then a pinned handle.
        root_fd = os.open(fixture / "alias", os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0))
        initial = _identity(os.fstat(root_fd))
        os.unlink(fixture / "ancestor")
        (fixture / "ancestor").symlink_to(second, target_is_directory=True)
        os.unlink(fixture / "alias")
        (fixture / "alias").symlink_to(second, target_is_directory=True)
        try:
            fd = _create_regular(root_fd, "pinned.record")
            try:
                _write(fd, b"pinned-root")
            finally:
                os.close(fd)
        finally:
            os.close(root_fd)

        if (first / "pinned.record").read_bytes() != b"pinned-root":
            raise AssertionError("pinned root write did not remain in first target")
        if (second / "pinned.record").exists():
            raise AssertionError("retargeted aliases influenced pinned root handle")
        return {
            "mechanism": "trusted startup traversal followed by openat directory descriptor pinning",
            "pinned_identity": list(initial),
            "ancestor_alias_retargeted": True,
            "root_alias_retargeted": True,
        }


def _layout_worker(fixture_name: str) -> int:
    fixture = Path(fixture_name)
    store = fixture / "store"
    store.mkdir(mode=0o770)
    os.chmod(store, 0o2770)
    root_fd = os.open(store, os.O_RDONLY | os.O_DIRECTORY | _OPEN_BASE)
    observations: dict[str, dict[str, object]] = {}
    try:
        before = os.fstat(root_fd)
        with _temporary_umask(0o027):
            for key in ("one", "domain.stem", "domain.middle.leaf"):
                directory_fd, name, namespaces = _make_layout(root_fd, key)
                try:
                    record_fd = _create_regular(directory_fd, name)
                    try:
                        _write(record_fd, key.encode())
                        record_mode = stat.S_IMODE(os.fstat(record_fd).st_mode)
                    finally:
                        os.close(record_fd)
                    relative = Path(*namespaces, name) if namespaces else Path(name)
                    if not (store / relative).is_file():
                        raise AssertionError(f"native layout path was not created: {relative}")
                    namespace_stats = []
                    cursor = store
                    for segment in namespaces:
                        cursor = cursor / segment
                        namespace_stats.append(os.stat(cursor, follow_symlinks=False))
                    for info in namespace_stats:
                        if info.st_gid != before.st_gid or not info.st_mode & stat.S_ISGID:
                            raise AssertionError("namespace did not inherit setgid parent policy")
                    observations[key] = {
                        "relative_path": str(relative),
                        "record_mode": oct(record_mode),
                        "namespace_permission_modes": [
                            oct(info.st_mode & 0o777) for info in namespace_stats
                        ],
                        "namespace_setgid_bits": [bool(info.st_mode & stat.S_ISGID) for info in namespace_stats],
                    }
                finally:
                    os.close(directory_fd)
        after = os.fstat(root_fd)
    finally:
        os.close(root_fd)
    application_metadata_unchanged = (
        _identity(before) == _identity(after)
        and before.st_mode == after.st_mode
        and before.st_gid == after.st_gid
    )
    if not application_metadata_unchanged:
        raise AssertionError("namespace creation changed application directory metadata")
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
                "mechanism": "child-process umask + mkdirat/openat with setgid inheritance",
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


def _namespace_inheritance_and_layouts(root: Path) -> dict[str, object]:
    with _fixture(root, "layout") as fixture:
        result = subprocess.run(
            [sys.executable, __file__, "--worker-layout", str(fixture)],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    return json.loads(result.stdout)


def _redirect_refusal(root: Path) -> dict[str, object]:
    with _fixture(root, "redirect") as fixture, ExitStack() as resources:
        root_fd = os.open(fixture, os.O_RDONLY | os.O_DIRECTORY | _OPEN_BASE)
        resources.callback(os.close, root_fd)
        outside = fixture / "outside"
        outside.mkdir(mode=0o700)
        (outside / "target").write_bytes(b"outside")
        os.chmod(outside / "target", _MODE_PRIVATE)
        names = ("credential.record", ".credential.tmp", ".credential.marker", ".credential.lock")
        refusals: dict[str, str] = {}
        (fixture / "namespace").symlink_to(outside, target_is_directory=True)
        refusals["namespace"] = _assert_refused(lambda: _open_directory(root_fd, "namespace"), "namespace link")
        for name in names:
            (fixture / name).symlink_to(outside / "target")
            refusals[name] = _assert_refused(lambda name=name: _open_regular(root_fd, name), name)

        original = _create_regular(root_fd, "mutable.record")
        resources.callback(os.close, original)
        _write(original, b"original")
        os.unlink("mutable.record", dir_fd=root_fd)
        replacement = _create_regular(root_fd, "mutable.record")
        resources.callback(os.close, replacement)
        _write(replacement, b"replacement")
        refusals["prevalidation_substitution"] = _assert_refused(
            lambda: _entry_matches(root_fd, "mutable.record", original), "post-open substitution"
        )
        if _read(replacement) != b"replacement":
            raise AssertionError("substitution fixture was unexpectedly repaired")
        return {
            "mechanism": "O_NOFOLLOW/O_NONBLOCK/openat and fstat-vs-lstat identity",
            "refusals": refusals,
            "reparse_note": "POSIX symlink refusal exercised; Windows reparse points are outside this probe.",
        }


def _linux_acl_privacy(fixture: Path) -> dict[str, object]:
    if not shutil.which("setfacl") or not shutil.which("getfacl"):
        return {"status": "blocked", "reason": "Linux ACL fixture utilities unavailable"}
    parent = fixture / "linux-acl-parent"
    parent.mkdir(mode=0o700)
    uid = os.getuid() + 100_000
    subprocess.run(
        ["setfacl", "-m", f"d:u::rwx,d:u:{uid}:rwx,d:g::---,d:m::rwx,d:o::---", str(parent)],
        check=True, capture_output=True, text=True, timeout=5,
    )
    def parent_policy() -> str:
        return subprocess.run(
            ["getfacl", "-cp", str(parent)], check=True, capture_output=True, text=True, timeout=5,
        ).stdout
    before = parent_policy()
    with ExitStack() as resources:
        parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | _OPEN_BASE)
        resources.callback(os.close, parent_fd)
        os.mkdir("namespace", 0o777, dir_fd=parent_fd)
        namespace_fd = _open_directory(parent_fd, "namespace")
        resources.callback(os.close, namespace_fd)
        if not _has_extended_acl(namespace_fd):
            raise AssertionError("namespace did not inherit application ACL policy")
        fd = os.open("private.record", os.O_RDWR | os.O_CREAT | os.O_EXCL | _OPEN_BASE,
                     _MODE_PRIVATE, dir_fd=parent_fd)
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
            "privacy_policy": "reject extended ACLs; clear only exclusive newly created files",
        }




def _darwin_acl_privacy(fixture: Path) -> dict[str, object]:
    parent = fixture / "darwin-acl-parent"
    parent.mkdir(mode=0o700)
    subprocess.run(
        ["chmod", "+a", "everyone allow read,file_inherit,directory_inherit", str(parent)],
        check=True, capture_output=True, text=True, timeout=5,
    )
    with ExitStack() as resources:
        parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | _OPEN_BASE)
        resources.callback(os.close, parent_fd)
        before = _acl_text(parent_fd)
        os.mkdir("namespace", 0o777, dir_fd=parent_fd)
        namespace_fd = _open_directory(parent_fd, "namespace")
        resources.callback(os.close, namespace_fd)
        if not _has_extended_acl(namespace_fd):
            raise AssertionError("namespace did not inherit application ACL policy")
        fd = os.open("private.record", os.O_RDWR | os.O_CREAT | os.O_EXCL | _OPEN_BASE,
                     _MODE_PRIVATE, dir_fd=parent_fd)
        resources.callback(os.close, fd)
        if not _has_extended_acl(fd):
            raise AssertionError("fixture did not inherit an extended ACL")
        inherited = _acl_text(fd)
        refusal = _assert_refused(lambda: _private_regular(fd), "existing allow ACL")
        if _acl_text(fd) != inherited or os.fstat(fd).st_size != 0:
            raise AssertionError("refusal repaired or wrote the exposed-ACL fixture")
        _clear_new_acl(fd)
        _private_regular(fd)
        if _acl_text(parent_fd) != before:
            raise AssertionError("private-file ACL creation changed application policy")
        _write(fd, b"darwin-acl-cleared-before-payload")
        return {
            "mechanism": "Darwin acl_get_fd_np/acl_set_fd_np with ACL_TYPE_EXTENDED",
            "existing_allow_acl_refusal": refusal,
            "inherited_access_acl_removed_before_write": True,
            "namespace_acl_inherited": True,
            "parent_acl_preserved": True,
            "mode_bits_not_used_as_acl_proof": True,
            "privacy_policy": "reject extended ACLs; clear only exclusive newly created files",
        }


def _object_privacy(root: Path) -> dict[str, object]:
    with _fixture(root, "privacy") as fixture, ExitStack() as resources:
        root_fd = os.open(fixture, os.O_RDONLY | os.O_DIRECTORY | _OPEN_BASE)
        resources.callback(os.close, root_fd)
        hard = _create_regular(root_fd, "hard.record")
        resources.callback(os.close, hard)
        os.link("hard.record", "hard-alias.record", src_dir_fd=root_fd, dst_dir_fd=root_fd, follow_symlinks=False)
        hardlink_refusal = _assert_refused(lambda: _open_regular(root_fd, "hard-alias.record"), "hard link")

        exposed = _create_regular(root_fd, "exposed.record")
        resources.callback(os.close, exposed)
        os.chmod(fixture / "exposed.record", 0o644)
        exposed_refusal = _assert_refused(lambda: _open_regular(root_fd, "exposed.record"), "exposed regular file")

        fifo = fixture / "blocking.fifo"
        os.mkfifo(fifo, 0o600)
        fifo_refusal = _assert_refused(lambda: _open_regular(root_fd, "blocking.fifo"), "FIFO")

        if sys.platform.startswith("linux"):
            acl = _linux_acl_privacy(fixture)
        elif sys.platform == "darwin":
            acl = _darwin_acl_privacy(fixture)
        else:
            acl = {"status": "blocked", "reason": f"unsupported POSIX platform {sys.platform}"}
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
        }


def _temp_replace_cleanup(root: Path) -> dict[str, object]:
    with _fixture(root, "replace") as fixture, ExitStack() as resources:
        root_fd = os.open(fixture, os.O_RDONLY | os.O_DIRECTORY | _OPEN_BASE)
        resources.callback(os.close, root_fd)
        collision = _create_regular(root_fd, ".known.tmp")
        resources.callback(os.close, collision)
        collision_refusal = _assert_refused(lambda: _create_regular(root_fd, ".known.tmp"), "exclusive create collision")
        names = (f".record.{secrets.token_hex(16)}.tmp", f".record.{secrets.token_hex(16)}.tmp")
        if names[0] == names[1] or len(names[0].split(".")[-2]) != 32:
            raise AssertionError("temporary names were not independent 128-bit tokens")

        credential = _create_regular(root_fd, "record")
        marker = _create_regular(root_fd, ".record.marker")
        resources.callback(os.close, credential)
        resources.callback(os.close, marker)
        _write(credential, b"old-record")
        _write(marker, b"old-marker")
        candidate = _create_regular(root_fd, names[0])
        resources.callback(os.close, candidate)
        _private_regular(candidate)  # Privacy is established before the dummy payload.
        _write(candidate, b"candidate")
        _entry_matches(root_fd, names[0], candidate)
        _entry_matches(root_fd, "record", credential)
        _entry_matches(root_fd, ".record.marker", marker)
        os.unlink(".record.marker", dir_fd=root_fd)
        (fixture / ".record.marker").symlink_to(fixture / "outside-marker")
        precommit_refusal = _assert_refused(
            lambda: _entry_matches(root_fd, ".record.marker", marker), "precommit marker substitution"
        )
        if _read(credential) != b"old-record":
            raise AssertionError("precommit refusal did not preserve old credential content")
        _cleanup_owned(root_fd, names[0], candidate)
        if (fixture / names[0]).exists():
            raise AssertionError("owned precommit temporary was not removed")

        post_marker = _create_regular(root_fd, ".post.marker")
        post_old = _create_regular(root_fd, "post.record")
        post_candidate = _create_regular(root_fd, names[1])
        resources.callback(os.close, post_marker)
        resources.callback(os.close, post_old)
        resources.callback(os.close, post_candidate)
        _write(post_old, b"before-commit")
        _private_regular(post_candidate)
        _write(post_candidate, b"after-commit")
        _entry_matches(root_fd, names[1], post_candidate)
        _entry_matches(root_fd, "post.record", post_old)
        _entry_matches(root_fd, ".post.marker", post_marker)
        os.replace(names[1], "post.record", src_dir_fd=root_fd, dst_dir_fd=root_fd)
        os.unlink(".post.marker", dir_fd=root_fd)
        os.mkdir(".post.marker", 0o700, dir_fd=root_fd)
        postcommit_fault = _assert_refused(
            lambda: _cleanup_owned(root_fd, ".post.marker", post_marker), "postcommit marker cleanup substitution"
        )
        committed = _open_regular(root_fd, "post.record")
        try:
            if _read(committed) != b"after-commit":
                raise AssertionError("replace did not commit candidate content")
        finally:
            os.close(committed)
        if not (fixture / ".post.marker").is_dir():
            raise AssertionError("substituted postcommit marker was unexpectedly repaired")

        owned = _create_regular(root_fd, ".owned-cleanup.tmp")
        resources.callback(os.close, owned)
        os.unlink(".owned-cleanup.tmp", dir_fd=root_fd)
        intruder = _create_regular(root_fd, ".owned-cleanup.tmp")
        resources.callback(os.close, intruder)
        _write(intruder, b"intruder")
        cleanup_refusal = _assert_refused(
            lambda: _cleanup_owned(root_fd, ".owned-cleanup.tmp", owned), "cleanup ownership mismatch"
        )
        if _read(intruder) != b"intruder":
            raise AssertionError("ownership-mismatched cleanup removed substituted entry")
        return {
            "mechanism": "O_CREAT|O_EXCL temporary, openat identity checks, replaceat, protected unlink",
            "exclusive_collision": collision_refusal,
            "temporary_token_hex_chars": 32,
            "precommit_refusal": precommit_refusal,
            "precommit_old_content_preserved": True,
            "postcommit_marker_cleanup_fault": postcommit_fault,
            "postcommit_record_committed": True,
            "ownership_mismatch_cleanup_refusal": cleanup_refusal,
            "substituted_entry_untouched": True,
        }


def _marker_interruption(root: Path) -> dict[str, object]:
    with _fixture(root, "marker") as fixture, ExitStack() as resources:
        root_fd = os.open(fixture, os.O_RDONLY | os.O_DIRECTORY | _OPEN_BASE)
        resources.callback(os.close, root_fd)
        record = _create_regular(root_fd, "record")
        marker = _create_regular(root_fd, ".record.cleared")
        resources.callback(os.close, record)
        resources.callback(os.close, marker)
        _write(record, b"raw-record-survives-interruption")
        _write(marker, b"marker-written-first")
        raw_fd = _open_regular(root_fd, "record")
        marker_fd = _open_regular(root_fd, ".record.cleared")
        try:
            raw = _read(raw_fd)
            observed_marker = _read(marker_fd)
        finally:
            os.close(raw_fd)
            os.close(marker_fd)
        if raw != b"raw-record-survives-interruption" or observed_marker != b"marker-written-first":
            raise AssertionError("marker-first fixture did not retain independent observations")
        if not (fixture / "record").exists() or not (fixture / ".record.cleared").exists():
            raise AssertionError("marker interruption fixture unexpectedly repaired itself")
        return {
            "mechanism": "independent no-follow record and marker reads",
            "marker_created_before_record_unlink": True,
            "raw_get_observed": raw.decode(),
            "marker_observed": True,
            "record_and_marker_coexist": True,
            "repair_performed": False,
        }


def _worker_lock_wait(path: str) -> int:
    fd = os.open(path, os.O_RDWR | _OPEN_BASE)
    try:
        _private_regular(fd)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            print(json.dumps({"phase": "contended", "errno": error.errno}), flush=True)
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
        _write(protected_temp, b"cleanup-under-lock")
        worker: subprocess.Popen[str] | None = None
        try:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                worker = subprocess.Popen(
                    [sys.executable, __file__, "--worker-lock-wait", str(fixture / ".record.lock")],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                )
                contended = _read_worker_line(worker)
                if contended.get("phase") != "contended":
                    raise AssertionError("separate process did not observe nonblocking lock contention")
                _cleanup_owned(root_fd, ".record.cleanup.tmp", protected_temp)
                if (fixture / ".record.cleanup.tmp").exists():
                    raise AssertionError("protected cleanup did not run while lock was held")
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
                raise AssertionError("same blocking contender did not acquire after lock release")
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
        }


class _QuiescentOwner:
    """Minimal terminal native-handle owner; callers must quiesce users before close."""

    def __init__(self, fd: int) -> None:
        self._fd: int | None = fd
        self._lock = threading.Lock()

    def close(self) -> None:
        with self._lock:
            fd = self._fd
            self._fd = None  # Detach before native release; repeats cannot close a reused fd.
        if fd is not None:
            os.close(fd)

    def __enter__(self) -> _QuiescentOwner:
        with self._lock:
            if self._fd is None:
                raise RuntimeError("owner is closed")
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @contextmanager
    def deferred_entry(self) -> Iterator[_QuiescentOwner]:
        self.__enter__()
        try:
            yield self
        finally:
            self.__exit__(None, None, None)


def _owner_quiescent_lifecycle(root: Path) -> dict[str, object]:
    with _fixture(root, "lifecycle") as fixture, ExitStack() as resources:
        root_fd = os.open(fixture, os.O_RDONLY | os.O_DIRECTORY | _OPEN_BASE)
        resources.callback(os.close, root_fd)
        target_fd = _create_regular(root_fd, "owned.record")
        _write(target_fd, b"owned")
        os.close(target_fd)
        owner = _QuiescentOwner(_open_regular(root_fd, "owned.record"))
        resources.callback(owner.close)
        owned_fd = owner._fd
        assert owned_fd is not None
        entered = threading.Event()
        release = threading.Event()
        failure: list[BaseException] = []

        def use_handle() -> None:
            try:
                _private_regular(owned_fd)
                entered.set()
                if not release.wait(5):
                    raise TimeoutError("application did not quiesce its active handle user")
                if _read(owned_fd) != b"owned":
                    raise AssertionError("active handle changed before application quiescence")
            except BaseException as error:
                failure.append(error)
                entered.set()

        user = threading.Thread(target=use_handle, daemon=True)
        user.start()
        if not entered.wait(5):
            release.set()
            raise AssertionError("active handle user did not begin")
        deferred = owner.deferred_entry()
        release.set()
        user.join(5)
        if user.is_alive():
            raise AssertionError("application did not join its active handle user before close")
        if failure:
            raise failure[0]
        owner.close()
        context_refusal = _assert_refused(lambda: deferred.__enter__(), "deferred entry after close")
        reused_fd = _create_regular(root_fd, "unrelated.record")
        try:
            _write(reused_fd, b"unrelated")
            if reused_fd != owned_fd:
                raise AssertionError("kernel did not deterministically reuse released descriptor")
            owner.close()
            owner.close()
            if _read(reused_fd) != b"unrelated":
                raise AssertionError("idempotent close released a reused unrelated descriptor")
        finally:
            os.close(reused_fd)
        return {
            "mechanism": "application quiescence followed by detach-before-os.close ownership",
            "application_joined_active_user_before_close": True,
            "deferred_context_refusal": context_refusal,
            "descriptor_reused": True,
            "repeated_close_preserved_reused_descriptor": True,
        }

def run(root: Path, record: Callable[[str, Callable[[], dict[str, object]]], None]) -> None:
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
