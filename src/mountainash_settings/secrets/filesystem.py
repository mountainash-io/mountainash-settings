"""Handle-bound local YAML records under application-owned directory policy."""
from __future__ import annotations

import secrets
import threading
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from types import TracebackType
from typing import Any, TypeVar

import yaml

from ._native import NativeOps, select_ops
from .errors import SecretStoreUnavailableError, _Failure, _raise_clean
from .keys import _layout
from .records import SecretRecord, _own_record

T = TypeVar("T")
__all__ = ["FilesystemBackend"]


def _encode(data: object) -> bytes:
    owned = _own_record(data)
    try:
        return yaml.safe_dump(owned, sort_keys=False).encode("utf-8")
    except (yaml.YAMLError, UnicodeError, ValueError, RecursionError):
        _raise_clean(ValueError("Invalid local record"))


def _decode(payload: bytes) -> SecretRecord:
    try:
        text = payload.decode("utf-8")
    except UnicodeError:
        raise _Failure("decode_error") from None
    try:
        value = yaml.safe_load(text)
    except (yaml.YAMLError, ValueError, TypeError, OverflowError, RecursionError):
        raise _Failure("malformed_yaml") from None
    try:
        return _own_record(value)
    except ValueError:
        raise _Failure("invalid_record_shape") from None


class FilesystemBackend:
    """Application-owned local store; callers quiesce before terminal close."""

    def __init__(self, base_dir: str | Path) -> None:
        self._gate = threading.Lock()
        self._active = 0
        self._root: int | None = None
        self._ops: NativeOps | None = None
        self._invoke(self._anchor, base_dir)

    def _anchor(self, base_dir: str | Path) -> None:
        self._ops = select_ops()
        try:
            path = Path(base_dir)
            self._root = self._ops.open_root(path)
        except (TypeError, ValueError):
            raise _Failure("unavailable") from None

    def _invoke(self, function: Callable[..., T], *args: Any) -> T:
        try:
            return function(*args)
        except ValueError:
            error: Exception = ValueError("Invalid local record input")
        except Exception as exc:
            reason = (
                exc.reason if isinstance(exc, _Failure)
                else self._ops.reason(exc) if self._ops is not None
                else "unavailable"
            )
            error = SecretStoreUnavailableError(
                "Local storage operation failed", reason=reason,
            )
        _raise_clean(error)

    @contextmanager
    def _admit(self) -> Iterator[tuple[int, NativeOps]]:
        with self._gate:
            if self._root is None or self._ops is None:
                raise _Failure("store_closed")
            root, ops = self._root, self._ops
            self._active += 1
        try:
            yield root, ops
        finally:
            with self._gate:
                self._active -= 1

    @contextmanager
    def _directory(
        self, root: int, ops: NativeOps,
        layout: tuple[str | None, str], create: bool,
    ) -> Iterator[tuple[int | None, str]]:
        namespace, stem = layout
        if namespace is None:
            yield root, stem
            return
        directory: int | None = None
        try:
            directory = ops.open_namespace(root, namespace, create=create)
        except FileNotFoundError:
            if create:
                raise
        try:
            yield directory, stem
        finally:
            if directory is not None:
                ops.close(directory)

    @staticmethod
    def _entry(
        resources: ExitStack, ops: NativeOps, parent: int, name: str,
        *, writable: bool = False, create: bool = False,
    ) -> tuple[int | None, bool]:
        created = False
        try:
            handle = ops.open_file(parent, name, writable=writable)
        except FileNotFoundError:
            if not create:
                return None, False
            try:
                handle = ops.create_file(parent, name)
                created = True
            except FileExistsError:
                # Only a fixed marker/lock may have a concurrently created winner.
                handle = ops.open_file(parent, name, writable=writable)
        resources.callback(ops.close, handle)
        return handle, created

    def get(self, key: str) -> SecretRecord | None:
        return self._invoke(self._get, key)

    def _get(self, key: str) -> SecretRecord | None:
        with self._admit() as (root, ops):
            with self._directory(root, ops, _layout(key), False) as (parent, stem):
                if parent is None:
                    return None
                with ExitStack() as resources:
                    handle, _ = self._entry(resources, ops, parent, f"{stem}.yaml")
                    return None if handle is None else _decode(ops.read_file(handle))

    def set(self, key: str, data: SecretRecord) -> None:
        self._invoke(self._set, key, data)

    def _set(self, key: str, data: SecretRecord) -> None:
        with self._admit() as (root, ops):
            layout = _layout(key)
            payload = _encode(data)  # No namespace/temp/storage mutation yet.
            with self._directory(root, ops, layout, True) as (parent, stem):
                assert parent is not None
                with (
                    ExitStack() as resources,
                    ExitStack() as old_resources,
                    ExitStack() as marker_resources,
                ):
                    target, marker = f"{stem}.yaml", f".{stem}.cleared"
                    old, _ = self._entry(old_resources, ops, parent, target, writable=True)
                    cleared, _ = self._entry(
                        marker_resources, ops, parent, marker, writable=True,
                    )
                    temporary = f".{stem}.{secrets.token_hex(16)}.tmp"
                    try:
                        handle = ops.create_file(parent, temporary)
                    except FileExistsError:
                        # Inspect only through the same no-follow private-entry open.
                        # Refuse unsafe occupants; never read, reuse, remove or retry one.
                        with ExitStack() as collision_resources:
                            self._entry(collision_resources, ops, parent, temporary)
                        raise _Failure("unavailable") from None
                    resources.callback(ops.close, handle)
                    committed = False
                    try:
                        ops.write_file(handle, payload)
                        if old is not None:
                            ops.check_entry(parent, target, old)
                        if cleared is not None:
                            ops.check_entry(parent, marker, cleared)
                        # Legacy Windows rename cannot replace an open destination.
                        # Pop ownership before close; the writer interval protects the name.
                        old_resources.close()
                        ops.replace_file(parent, temporary, handle, target)
                        committed = True
                        if cleared is not None:
                            try:
                                try:
                                    ops.cleanup_owned(parent, marker, cleared)
                                finally:
                                    # Windows deletion completes on handle release.
                                    # ExitStack detaches before calling close: no retry.
                                    marker_resources.close()
                            except Exception:
                                raise _Failure("write_committed_cleanup_failed") from None
                    finally:
                        if not committed:
                            ops.cleanup_owned(parent, temporary, handle)

    def delete(self, key: str) -> None:
        self._invoke(self._delete, key)

    def _delete(self, key: str) -> None:
        with self._admit() as (root, ops):
            with self._directory(root, ops, _layout(key), True) as (parent, stem):
                assert parent is not None
                with ExitStack() as resources:
                    target, marker = f"{stem}.yaml", f".{stem}.cleared"
                    old, _ = self._entry(resources, ops, parent, target, writable=True)
                    cleared, created = self._entry(
                        resources, ops, parent, marker, writable=True, create=True,
                    )
                    assert cleared is not None
                    try:
                        if old is not None:
                            ops.cleanup_owned(parent, target, old)
                    except Exception:
                        if created:
                            ops.cleanup_owned(parent, marker, cleared)
                        raise

    def is_cleared(self, key: str) -> bool:
        return self._invoke(self._is_cleared, key)

    def _is_cleared(self, key: str) -> bool:
        with self._admit() as (root, ops):
            with self._directory(root, ops, _layout(key), False) as (parent, stem):
                if parent is None:
                    return False
                with ExitStack() as resources:
                    handle, _ = self._entry(resources, ops, parent, f".{stem}.cleared")
                    return handle is not None

    def _begin_transaction(self, key: str, resources: ExitStack) -> None:
        try:
            root, ops = resources.enter_context(self._admit())
            parent, stem = resources.enter_context(
                self._directory(root, ops, _layout(key), True)
            )
            assert parent is not None
            handle, _ = self._entry(
                resources, ops, parent, f".{stem}.lock", writable=True, create=True,
            )
            assert handle is not None
            ops.check_entry(parent, f".{stem}.lock", handle)
            if not ops.lock(handle):
                raise _Failure("unavailable")
            resources.callback(ops.unlock, handle)
        except BaseException:
            resources.close()
            raise

    @contextmanager
    def transaction(self, key: str) -> Iterator[None]:
        # This generator captures only self/key until __enter__ advances it.
        resources = ExitStack()
        self._invoke(self._begin_transaction, key, resources)
        try:
            yield
        finally:
            self._invoke(resources.close)

    def close(self) -> None:
        self._invoke(self._close)

    def _close(self) -> None:
        with self._gate:
            if self._root is None:
                return
            if self._active:
                # Misuse refusal, not a drain/cancel service or alternate close policy.
                raise _Failure("unavailable")
            root, self._root = self._root, None
            ops = self._ops
        assert ops is not None
        ops.close(root)  # Detached before release; never retry a failed close.

    def __enter__(self) -> FilesystemBackend:
        self._invoke(self._check_open)
        return self

    def _check_open(self) -> None:
        with self._gate:
            if self._root is None:
                raise _Failure("store_closed")

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass  # Explicit close reports errors; finalization is best effort.
