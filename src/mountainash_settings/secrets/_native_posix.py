"""Private POSIX native operations; selected only by ``_native`` after platform choice."""
from __future__ import annotations
import ctypes
import errno
import fcntl
import os
import stat
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import NoReturn

from .errors import _Failure

_MODE_PRIVATE = 0o600
_OPEN_BASE = os.O_NOFOLLOW | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0)
_DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | _OPEN_BASE


class _Refused(PermissionError):
    pass


class _MissingNative(_Failure):
    def __init__(self) -> None:
        super().__init__("unsupported_filesystem")


_ACL: ctypes.CDLL | None = None


def _acl() -> ctypes.CDLL:
    global _ACL
    if _ACL is not None:
        return _ACL
    try:
        acl = ctypes.CDLL(
            "/usr/lib/libSystem.B.dylib" if sys.platform == "darwin" else "libacl.so.1",
            use_errno=True,
        )
    except OSError as exc:
        raise _MissingNative() from exc
    required = (
        ("acl_free", "acl_get_fd_np", "acl_set_fd_np", "acl_init", "acl_get_entry")
        if sys.platform == "darwin"
        else ("acl_free", "acl_get_fd", "acl_set_fd", "acl_from_text", "acl_equiv_mode")
    )
    if any(not hasattr(acl, name) for name in required):
        raise _MissingNative()
    acl.acl_free.argtypes = [ctypes.c_void_p]
    acl.acl_free.restype = ctypes.c_int
    if sys.platform == "darwin":
        acl.acl_get_fd_np.argtypes = [ctypes.c_int, ctypes.c_int]
        acl.acl_get_fd_np.restype = ctypes.c_void_p
        acl.acl_set_fd_np.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_int]
        acl.acl_set_fd_np.restype = ctypes.c_int
        acl.acl_init.argtypes = [ctypes.c_int]
        acl.acl_init.restype = ctypes.c_void_p
        acl.acl_get_entry.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]
        acl.acl_get_entry.restype = ctypes.c_int
    else:
        acl.acl_get_fd.argtypes = [ctypes.c_int]
        acl.acl_get_fd.restype = ctypes.c_void_p
        acl.acl_set_fd.argtypes = [ctypes.c_int, ctypes.c_void_p]
        acl.acl_set_fd.restype = ctypes.c_int
        acl.acl_from_text.argtypes = [ctypes.c_char_p]
        acl.acl_from_text.restype = ctypes.c_void_p
        acl.acl_equiv_mode.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)]
        acl.acl_equiv_mode.restype = ctypes.c_int
    _ACL = acl
    return acl


def _acl_error() -> OSError:
    return OSError(ctypes.get_errno(), "native descriptor ACL operation failed")


@contextmanager
def _opened_acl(fd: int) -> Iterator[int]:
    acl_api = _acl()
    ctypes.set_errno(0)
    acl = acl_api.acl_get_fd_np(fd, 0x100) if sys.platform == "darwin" else acl_api.acl_get_fd(fd)
    if not acl and sys.platform == "darwin" and ctypes.get_errno() == errno.ENOENT:
        # Missing FILESEC_ACL is an empty ACL only after proving this descriptor exists.
        os.fstat(fd)
        acl = acl_api.acl_init(0)
    if not acl:
        raise _acl_error()
    try:
        yield acl
    finally:
        acl_api.acl_free(acl)


def _has_extended_acl(fd: int) -> bool:
    with _opened_acl(fd) as acl:
        if sys.platform == "darwin":
            entry = ctypes.c_void_p()
            result = _acl().acl_get_entry(acl, 0, ctypes.byref(entry))
            if result == 0:
                return True
            if result == -1 and ctypes.get_errno() == errno.EINVAL:
                return False
            raise _acl_error()
        result = _acl().acl_equiv_mode(acl, None)
        if result < 0:
            raise _acl_error()
        return result != 0


def _clear_new_acl(fd: int, mode: int = _MODE_PRIVATE) -> None:
    acl_api = _acl()
    acl = (
        acl_api.acl_init(0)
        if sys.platform == "darwin"
        else acl_api.acl_from_text(b"u::rw-,g::---,o::---")
    )
    if not acl:
        raise _acl_error()
    try:
        result = (
            acl_api.acl_set_fd_np(fd, acl, 0x100)
            if sys.platform == "darwin"
            else acl_api.acl_set_fd(fd, acl)
        )
        if result != 0:
            raise _acl_error()
    finally:
        acl_api.acl_free(acl)
    os.fchmod(fd, mode)


def _identity(info: os.stat_result) -> tuple[int, int]:
    return info.st_dev, info.st_ino


def _private_regular(fd: int) -> os.stat_result:
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode):
        raise _Refused()
    if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != _MODE_PRIVATE:
        raise _Refused()
    if info.st_nlink != 1 or _has_extended_acl(fd):
        raise _Refused()
    return info


def _close_after_failure(fd: int, error: BaseException) -> NoReturn:
    try:
        os.close(fd)
    except OSError:
        pass
    raise error


def _operation_error(exc: OSError) -> NoReturn:
    if exc.errno in (errno.EACCES, errno.EPERM, errno.ELOOP, errno.ENOTDIR):
        raise _Refused() from exc
    if exc.errno in {
        errno.ENOSYS,
        getattr(errno, "EOPNOTSUPP", errno.ENOSYS),
        getattr(errno, "ENOTSUP", errno.ENOSYS),
    }:
        raise _MissingNative() from exc
    raise _Failure("unavailable") from exc


def _open_directory(parent: int, name: str) -> int:
    try:
        fd = os.open(name, _DIRECTORY_FLAGS, dir_fd=parent)
    except FileNotFoundError:
        raise
    except OSError as exc:
        _operation_error(exc)
    try:
        if not stat.S_ISDIR(os.fstat(fd).st_mode):
            raise _Refused()
        return fd
    except BaseException as exc:
        _close_after_failure(fd, exc)


def open_root(path: Path) -> int:
    required = {os.open, os.stat, os.mkdir, os.unlink, os.rmdir, os.rename, os.link}
    if not required <= os.supports_dir_fd or os.stat not in os.supports_follow_symlinks:
        raise _MissingNative()
    _acl()  # Bind required primitives before touching even the provisioned root.
    try:
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0))
    except OSError as exc:
        raise _Failure("unavailable") from exc
    try:
        if not stat.S_ISDIR(os.fstat(fd).st_mode):
            raise _Failure("unavailable")
        _has_extended_acl(fd)  # Query capability; broad directory ACLs remain valid.
        return fd
    except BaseException as exc:
        _close_after_failure(fd, exc)


def open_namespace(parent: int, name: str, *, create: bool) -> int:
    if create:
        try:
            os.mkdir(name, 0o777, dir_fd=parent)
        except FileExistsError:
            pass
        except OSError as exc:
            _operation_error(exc)
    return _open_directory(parent, name)


def open_file(parent: int, name: str, *, writable: bool = False) -> int:
    try:
        fd = os.open(
            name,
            (os.O_RDWR if writable else os.O_RDONLY) | _OPEN_BASE,
            dir_fd=parent,
        )
    except FileNotFoundError:
        raise
    except OSError as exc:
        _operation_error(exc)
    try:
        _private_regular(fd)
        return fd
    except BaseException as exc:
        _close_after_failure(fd, exc)


def _new_entry_matches(parent: int, name: str, handle: int) -> None:
    """Compare a just-created entry without requiring final private-link state."""
    try:
        named = os.stat(name, dir_fd=parent, follow_symlinks=False)
    except OSError as exc:
        raise _Refused() from exc
    if _identity(named) != _identity(os.fstat(handle)):
        raise _Refused()


def _cleanup_new(parent: int, name: str, handle: int) -> None:
    _new_entry_matches(parent, name, handle)
    os.unlink(name, dir_fd=parent)


def _discard_new(parent: int, name: str, fd: int, primary: BaseException) -> NoReturn:
    cleanup_error: BaseException | None = None
    try:
        _cleanup_new(parent, name, fd)
    except BaseException as exc:
        cleanup_error = exc
    try:
        os.close(fd)
    except BaseException as exc:
        if cleanup_error is None:
            cleanup_error = exc
    if cleanup_error is not None:
        raise cleanup_error from primary
    raise primary


def _darwin_create_private(parent: int, name: str) -> int:
    """Publish a private inode from a private stage, before any payload write."""
    import secrets

    stage_name = f".private-{secrets.token_hex(16)}.stage"
    try:
        os.mkdir(stage_name, 0o700, dir_fd=parent)
    except FileExistsError:
        raise
    except OSError as exc:
        _operation_error(exc)
    try:
        created_identity = _identity(
            os.stat(stage_name, dir_fd=parent, follow_symlinks=False)
        )
    except OSError as exc:
        raise _Refused() from exc
    stage_fd: int | None = None
    payload_fd: int | None = None
    payload_exists = False
    published = False
    primary: BaseException | None = None
    cleanup_error: BaseException | None = None

    def remember(error: BaseException) -> None:
        nonlocal cleanup_error
        if cleanup_error is None:
            cleanup_error = error

    try:
        stage_fd = _open_directory(parent, stage_name)
        if _identity(os.fstat(stage_fd)) != created_identity:
            raise _Refused()
        _clear_new_acl(stage_fd, 0o700)
        if stat.S_IMODE(os.fstat(stage_fd).st_mode) != 0o700 or _has_extended_acl(stage_fd):
            raise _Refused()
        payload_fd = os.open(
            "payload",
            os.O_RDWR | os.O_CREAT | os.O_EXCL | _OPEN_BASE,
            _MODE_PRIVATE,
            dir_fd=stage_fd,
        )
        payload_exists = True
        _private_regular(payload_fd)
        os.link(
            "payload",
            name,
            src_dir_fd=stage_fd,
            dst_dir_fd=parent,
            follow_symlinks=False,
        )
        published = True
        _new_entry_matches(stage_fd, "payload", payload_fd)
        os.unlink("payload", dir_fd=stage_fd)
        payload_exists = False
        _private_regular(payload_fd)
    except BaseException as exc:
        primary = exc

    if primary is not None and published and payload_fd is not None:
        try:
            _cleanup_new(parent, name, payload_fd)
        except BaseException as exc:
            remember(exc)
    if payload_exists and payload_fd is not None and stage_fd is not None:
        try:
            _cleanup_new(stage_fd, "payload", payload_fd)
        except BaseException as exc:
            remember(exc)
    try:
        if stage_fd is not None and _identity(os.fstat(stage_fd)) != created_identity:
            raise _Refused()
        if _identity(os.stat(stage_name, dir_fd=parent, follow_symlinks=False)) != created_identity:
            raise _Refused()
        os.rmdir(stage_name, dir_fd=parent)
    except BaseException as exc:
        remember(exc)
    finally:
        if stage_fd is not None:
            try:
                os.close(stage_fd)
            except BaseException as exc:
                remember(exc)
    if cleanup_error is not None and published and payload_fd is not None and primary is None:
        try:
            _cleanup_new(parent, name, payload_fd)
        except BaseException as exc:
            remember(exc)
    if primary is not None or cleanup_error is not None:
        if payload_fd is not None:
            try:
                os.close(payload_fd)
            except BaseException as exc:
                remember(exc)
        if cleanup_error is not None:
            if primary is not None:
                raise cleanup_error from primary
            raise cleanup_error
        assert primary is not None
        raise primary
    assert payload_fd is not None
    return payload_fd


def create_file(parent: int, name: str) -> int:
    if sys.platform == "darwin":
        return _darwin_create_private(parent, name)
    try:
        fd = os.open(
            name,
            os.O_RDWR | os.O_CREAT | os.O_EXCL | _OPEN_BASE,
            _MODE_PRIVATE,
            dir_fd=parent,
        )
    except FileExistsError:
        raise
    except OSError as exc:
        _operation_error(exc)
    try:
        _clear_new_acl(fd)
        _private_regular(fd)
        return fd
    except BaseException as exc:
        _discard_new(parent, name, fd, exc)


def read_file(handle: int) -> bytes:
    os.lseek(handle, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    while chunk := os.read(handle, 64 * 1024):
        chunks.append(chunk)
    return b"".join(chunks)


def write_file(handle: int, payload: bytes) -> None:
    writer = os.dup(handle)
    pending: BaseException | None = None
    try:
        os.lseek(writer, 0, os.SEEK_SET)
        os.ftruncate(writer, 0)
        view = memoryview(payload)
        while view:
            written = os.write(writer, view)
            if written <= 0:
                raise OSError(errno.EIO, "native short write")
            view = view[written:]
    except BaseException as exc:
        pending = exc
    try:
        os.close(writer)
    except BaseException:
        if pending is None:
            raise
    if pending is not None:
        raise pending


def check_entry(parent: int, name: str, handle: int) -> None:
    try:
        named = os.stat(name, dir_fd=parent, follow_symlinks=False)
    except OSError as exc:
        raise _Refused() from exc
    opened = _private_regular(handle)
    if _identity(named) != _identity(opened):
        raise _Refused()


def replace_file(parent: int, temp_name: str, temp_handle: int, destination: str) -> None:
    check_entry(parent, temp_name, temp_handle)
    os.replace(temp_name, destination, src_dir_fd=parent, dst_dir_fd=parent)


def cleanup_owned(parent: int, name: str, handle: int) -> None:
    check_entry(parent, name, handle)
    os.unlink(name, dir_fd=parent)


def lock(handle: int, *, blocking: bool = True) -> bool:
    flags = fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB)
    try:
        fcntl.flock(handle, flags)
    except BlockingIOError:
        if not blocking:
            return False
        raise
    return True


def unlock(handle: int) -> None:
    fcntl.flock(handle, fcntl.LOCK_UN)


def close(handle: int) -> None:
    os.close(handle)


def reason(exc: Exception) -> str:
    if isinstance(exc, _Failure):
        return exc.reason
    if isinstance(exc, _Refused):
        return "unsafe_entry"
    if isinstance(exc, OSError) and exc.errno in {
        errno.ENOSYS,
        getattr(errno, "EOPNOTSUPP", errno.ENOSYS),
        getattr(errno, "ENOTSUP", errno.ENOSYS),
    }:
        return "unsupported_filesystem"
    return "unavailable"
