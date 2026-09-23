from __future__ import annotations

import gc
import importlib
import os
import subprocess
import sys
import traceback
from contextlib import ExitStack
from pathlib import Path

import pytest

from mountainash_settings.secrets import (
    FilesystemBackend, NamespacedSecretStore, SecretStoreUnavailableError,
)


@pytest.fixture
def store(tmp_path):
    with FilesystemBackend(tmp_path) as value:
        yield value


def raw_file(store, root, name, payload):
    """Fixture-only invalid-record/marker writer using private native creation."""
    ops = store._ops
    with ExitStack() as resources:
        parent = ops.open_root(root)
        resources.callback(ops.close, parent)
        handle = ops.create_file(parent, name)
        resources.callback(ops.close, handle)
        ops.write_file(handle, payload)


def assert_safe(error, reason, sentinel="SECRET_CANARY"):
    assert isinstance(error, SecretStoreUnavailableError)
    assert error.reason == reason
    assert error.__cause__ is None
    assert error.__context__ is None
    assert sentinel not in "".join(traceback.format_exception(error))


@pytest.mark.parametrize("key,relative", [
    ("one", "one.yaml"),
    ("domain.leaf", "domain/leaf.yaml"),
    ("domain.provider.user", "domain/provider-user.yaml"),
])
def test_layout_complete_record_and_empty_mapping(store, tmp_path, key, relative):
    record = {"token": "x" * 200000, "unicode": "é", "nested": [True, None, 3.5]}
    store.set(key, record)
    assert store.get(key) == record
    assert (tmp_path / relative).is_file()
    store.set(key, {})
    assert store.get(key) == {}


def test_read_only_absence_and_bad_input_create_nothing(store, tmp_path):
    assert store.get("missing.user") is None
    assert not store.is_cleared("missing.user")
    with pytest.raises(ValueError):
        store.set("missing.user", {"token": float("nan")})
    with pytest.raises(ValueError):
        store.set("missing.user\n", {"token": "dummy"})
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("payload,reason", [
    (b"", "invalid_record_shape"),
    (b"null\n", "invalid_record_shape"),
    (b"[]\n", "invalid_record_shape"),
    (b"x: 2026-09-21\n", "invalid_record_shape"),
    (b"1: value\n", "invalid_record_shape"),
    (b"x: .nan\n", "invalid_record_shape"),
    (b"&a {x: *a}\n", "invalid_record_shape"),
    (b"x: [SECRET_CANARY\n", "malformed_yaml"),
    (b"x: 2026-99-99\n", "malformed_yaml"),
    (b"\xffSECRET_CANARY", "decode_error"),
])
def test_invalid_existing_record_is_not_missing_or_repaired(
    store, tmp_path, payload, reason,
):
    raw_file(store, tmp_path, "one.yaml", payload)
    with pytest.raises(SecretStoreUnavailableError) as caught:
        store.get("one")
    assert_safe(caught.value, reason)
    assert (tmp_path / "one.yaml").read_bytes() == payload


def test_bad_write_preserves_record_and_marker(store, tmp_path):
    store.set("one", {"token": "old"})
    raw_file(store, tmp_path, ".one.cleared", b"")
    cycle = {}
    cycle["loop"] = cycle
    with pytest.raises(ValueError):
        store.set("one", cycle)
    assert store.get("one") == {"token": "old"}
    assert store.is_cleared("one")


@pytest.mark.parametrize("failure", ["write_file", "replace_file"])
def test_precommit_fault_preserves_old_state_and_removes_only_own_temp(
    store, tmp_path, monkeypatch, failure,
):
    store.set("one", {"token": "old"})
    raw_file(store, tmp_path, ".one.cleared", b"")
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    real_write = store._ops.write_file

    def fail(*args):
        if failure == "write_file":
            real_write(args[0], b"unfinished SECRET_CANARY")
        raise OSError("SECRET_CANARY")

    with monkeypatch.context() as patch:
        patch.setattr(store._ops, failure, fail)
        with pytest.raises(SecretStoreUnavailableError) as caught:
            store.set("one", {"token": "new"})
    assert_safe(caught.value, "unavailable")
    assert store.get("one") == {"token": "old"}
    assert store.is_cleared("one")
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


def test_postcommit_marker_failure_reports_new_record_not_rollback(
    store, tmp_path, monkeypatch,
):
    store.set("one", {"token": "old"})
    raw_file(store, tmp_path, ".one.cleared", b"")
    real_cleanup = store._ops.cleanup_owned

    def fail_marker(parent, name, handle):
        if name == ".one.cleared":
            raise OSError("SECRET_CANARY")
        return real_cleanup(parent, name, handle)

    with monkeypatch.context() as patch:
        patch.setattr(store._ops, "cleanup_owned", fail_marker)
        with pytest.raises(SecretStoreUnavailableError) as caught:
            store.set("one", {"token": "new"})
    assert_safe(caught.value, "write_committed_cleanup_failed")
    assert store.get("one") == {"token": "new"}
    assert store.is_cleared("one")


def test_postcommit_marker_close_failure_reports_commit_without_retry(
    store, tmp_path, monkeypatch,
):
    store.set("one", {"token": "old"})
    raw_file(store, tmp_path, ".one.cleared", b"")
    real_open, real_close = store._ops.open_file, store._ops.close
    marker_handle = None
    marker_closes = 0

    def observe_open(parent, name, *, writable=False):
        nonlocal marker_handle
        handle = real_open(parent, name, writable=writable)
        if name == ".one.cleared":
            marker_handle = handle
        return handle

    def fail_after_release(handle):
        nonlocal marker_closes
        is_marker = handle == marker_handle
        if is_marker:
            marker_closes += 1
        real_close(handle)
        if is_marker:
            raise OSError("SECRET_CANARY")

    with monkeypatch.context() as patch:
        patch.setattr(store._ops, "open_file", observe_open)
        patch.setattr(store._ops, "close", fail_after_release)
        with pytest.raises(SecretStoreUnavailableError) as caught:
            store.set("one", {"token": "new"})
    assert_safe(caught.value, "write_committed_cleanup_failed")
    assert store.get("one") == {"token": "new"}
    assert not store.is_cleared("one")  # This injected error follows real release.
    assert marker_closes == 1


def test_delete_rolls_back_only_its_own_new_marker(store, tmp_path, monkeypatch):
    store.set("one", {"token": "old"})
    real_cleanup = store._ops.cleanup_owned

    def fail_record(parent, name, handle):
        if name == "one.yaml":
            raise OSError("SECRET_CANARY")
        return real_cleanup(parent, name, handle)

    with monkeypatch.context() as patch:
        patch.setattr(store._ops, "cleanup_owned", fail_record)
        with pytest.raises(SecretStoreUnavailableError) as caught:
            store.delete("one")
    assert_safe(caught.value, "unavailable")
    assert store.get("one") == {"token": "old"}
    assert not store.is_cleared("one")
    raw_file(store, tmp_path, ".one.cleared", b"")
    with monkeypatch.context() as patch:
        patch.setattr(store._ops, "cleanup_owned", fail_record)
        with pytest.raises(SecretStoreUnavailableError):
            store.delete("one")
    assert store.is_cleared("one")  # Pre-existing marker is not operation-owned.


def test_interruption_observation_and_normal_recreate(store, tmp_path, monkeypatch):
    store.set("one", {"token": "old"})
    real_cleanup = store._ops.cleanup_owned

    def interrupt(parent, name, handle):
        if name == "one.yaml":
            raise KeyboardInterrupt
        return real_cleanup(parent, name, handle)

    with monkeypatch.context() as patch:
        patch.setattr(store._ops, "cleanup_owned", interrupt)
        with pytest.raises(KeyboardInterrupt):
            store.delete("one")
    # Controlled interruption at the actual removal seam, not a crash-durability claim.
    assert store.get("one") == {"token": "old"}
    assert store.is_cleared("one")
    store.delete("one")
    assert store.get("one") is None
    assert store.is_cleared("one")
    store.set("one", {"token": "new"})
    assert store.get("one") == {"token": "new"}
    assert not store.is_cleared("one")


def test_context_exit_preserves_caller_error_and_clean_unlock_failure(
    store, monkeypatch,
):
    caller_error = RuntimeError("caller-owned")
    with pytest.raises(RuntimeError) as caught:
        with store.transaction("one"):
            raise caller_error
    assert caught.value is caller_error
    real_unlock = store._ops.unlock

    def failed_unlock(handle):
        real_unlock(handle)
        raise OSError("SECRET_CANARY")

    with monkeypatch.context() as patch:
        patch.setattr(store._ops, "unlock", failed_unlock)
        with pytest.raises(SecretStoreUnavailableError) as caught:
            with store.transaction("one"):
                raise RuntimeError("SECRET_CANARY")
    assert_safe(caught.value, "unavailable")


def test_terminal_close_deferred_entry_and_borrowed_view(store):
    view = NamespacedSecretStore(store, "view")
    deferred = store.transaction("one")
    view.set("one", {"value": 1})
    store.close()
    for operation in (
        lambda: store.get("one"), lambda: store.set("one", {}),
        lambda: store.delete("one"), lambda: store.is_cleared("one"),
        lambda: deferred.__enter__(), lambda: view.get("one"),
    ):
        with pytest.raises(SecretStoreUnavailableError) as caught:
            operation()
        assert_safe(caught.value, "store_closed")
    store.close()


def test_owner_exits_transaction_before_close(store):
    with store.transaction("one"):
        store.set("one", {"value": 1})
    store.close()
    with pytest.raises(SecretStoreUnavailableError) as caught:
        store.get("one")
    assert_safe(caught.value, "store_closed")


def test_repeated_close_and_finalization_leave_reused_handle_usable(tmp_path):
    store = FilesystemBackend(tmp_path)
    old = store._root
    ops = store._ops
    store.close()
    held = []
    reused = None
    try:
        # Keep nonmatching handles open: do not cycle over the same free slot.
        for _ in range(4096):
            handle = ops.open_root(tmp_path)
            held.append(handle)
            if handle == old:
                reused = handle
                break
        assert reused is not None, "Required native handle-reuse evidence unavailable"
        store.close()
        del store
        gc.collect()
        child = ops.open_namespace(reused, "unrelated", create=True)
        ops.close(child)
        assert (tmp_path / "unrelated").is_dir()
    finally:
        for handle in reversed(held):
            ops.close(handle)


def test_unrepresentable_native_name_never_aliases_a_shorter_namespace(store):
    store.set("victim.one", {"token": "unchanged"})
    oversized = "victim" + "a" * 32768 + ".one"
    for operation in (
        lambda: store.get(oversized), lambda: store.set(oversized, {}),
        lambda: store.delete(oversized), lambda: store.is_cleared(oversized),
        lambda: store.transaction(oversized).__enter__(),
    ):
        with pytest.raises(SecretStoreUnavailableError) as caught:
            operation()
        assert_safe(caught.value, "unavailable")
        assert store.get("victim.one") == {"token": "unchanged"}
        assert not store.is_cleared("victim.one")


def test_missing_native_capability_refuses_before_storage_mutation(tmp_path, monkeypatch):
    from mountainash_settings.secrets._native import select_ops
    ops = select_ops()
    if sys.platform == "win32":
        api = ops._api()
        def no_persistent_acl(handle, volume, size, serial, maximum, flags, name, name_size):
            ops.c.cast(flags, ops.c.POINTER(ops.DWORD)).contents.value = 0
            return 1
        monkeypatch.setattr(api, "GetVolumeInformationByHandleW", no_persistent_acl)
    else:
        def missing_library():
            raise ops._MissingNative()
        monkeypatch.setattr(ops, "_acl", missing_library)
        # Required primitives are checked before even a missing root is accessed.
        with pytest.raises(SecretStoreUnavailableError) as caught:
            FilesystemBackend(tmp_path / "missing")
        assert_safe(caught.value, "unsupported_filesystem")
    with pytest.raises(SecretStoreUnavailableError) as caught:
        with FilesystemBackend(tmp_path) as candidate:
            candidate.set("new.one", {"token": "dummy"})
    assert_safe(caught.value, "unsupported_filesystem")
    assert not list(tmp_path.iterdir())


def test_constructor_failure_releases_the_actual_partially_opened_handle(tmp_path, monkeypatch):
    from mountainash_settings.secrets._native import select_ops
    ops = select_ops()
    observed = []
    if sys.platform == "win32":
        original = ops._identity
        def fail_identity(handle):
            observed.append(handle.value)
            raise OSError("SECRET_CANARY")
        target, symbol, replacement = ops, "_identity", fail_identity
    else:
        original = os.fstat
        def fail_stat(handle):
            observed.append(handle)
            raise OSError("SECRET_CANARY")
        target, symbol, replacement = os, "fstat", fail_stat
    with monkeypatch.context() as patch:
        patch.setattr(target, symbol, replacement)
        with pytest.raises(SecretStoreUnavailableError) as caught:
            FilesystemBackend(tmp_path)
    assert_safe(caught.value, "unavailable")
    assert len(observed) == 1
    with pytest.raises(OSError) as closed:
        original(ops.HANDLE(observed[0]) if sys.platform == "win32" else observed[0])
    assert closed.value.errno == (6 if sys.platform == "win32" else 9)


def test_real_independent_client_lock_survives_record_replacement(store, tmp_path):
    worker = r"""
import sys
from pathlib import Path
from mountainash_settings.secrets import FilesystemBackend
with FilesystemBackend(Path(sys.argv[1])) as store:
    ops = store._ops
    parent = ops.open_root(Path(sys.argv[1]))
    handle = ops.open_file(parent, ".one.lock", writable=True)
    try:
        assert not ops.lock(handle, blocking=False)
        print("BLOCKED", flush=True)
    finally:
        ops.close(handle)
        ops.close(parent)
    with store.transaction("one"):
        assert store.get("one") == {"value": 2}
        print("ACQUIRED", flush=True)
"""
    with store.transaction("one"):
        store.set("one", {"value": 1})
        child = subprocess.Popen(
            [sys.executable, "-c", worker, str(tmp_path)],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True,
        )
        try:
            # A reader future bounds the handshake on Windows as well as POSIX.
            from concurrent.futures import ThreadPoolExecutor
            pool = ThreadPoolExecutor(max_workers=1)
            try:
                line = pool.submit(child.stdout.readline).result(timeout=10)
                assert line.strip() == "BLOCKED"
                store.set("one", {"value": 2})
            except BaseException:
                child.kill()
                child.communicate()
                raise
            finally:
                pool.shutdown(wait=True)
        except BaseException:
            if child.poll() is None:
                child.kill()
                child.communicate()
            raise
    try:
        stdout, stderr = child.communicate(timeout=10)
        assert child.returncode == 0, stderr
        assert stdout.strip() == "ACQUIRED"
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate()


def make_redirect(link, target):
    if sys.platform == "win32":
        subprocess.run(
            ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
            check=True, capture_output=True, text=True,
        )
    else:
        link.symlink_to(target, target_is_directory=True)


def test_startup_ancestor_link_pins_old_store_and_new_store_selects_new_root(tmp_path):
    first, second, alias = tmp_path / "first", tmp_path / "second", tmp_path / "alias"
    (first / "root").mkdir(parents=True)
    (second / "root").mkdir(parents=True)
    make_redirect(alias, first)
    with FilesystemBackend(alias / "root") as original:
        if sys.platform == "win32":
            os.rmdir(alias)
        else:
            alias.unlink()
        make_redirect(alias, second)
        with original.transaction("one"):
            original.set("one", {"where": "first"})
        with FilesystemBackend(alias / "root") as replacement:
            assert replacement.get("one") is None
            replacement.set("one", {"where": "second"})
            assert original.get("one") == {"where": "first"}
            assert replacement.get("one") == {"where": "second"}
            original.delete("one")
            assert original.get("one") is None
            assert original.is_cleared("one")
            assert replacement.get("one") == {"where": "second"}
            assert not replacement.is_cleared("one")
    assert (first / "root" / ".one.cleared").is_file()
    assert (second / "root" / "one.yaml").is_file()


@pytest.mark.parametrize("first_operation", ["set", "delete", "transaction"])
def test_each_mutating_first_use_creates_only_its_own_namespace(store, tmp_path, first_operation):
    if first_operation == "set":
        store.set("domain.one", {"value": 1})
        assert store.get("domain.one") == {"value": 1}
    elif first_operation == "delete":
        store.delete("domain.one")
        assert store.get("domain.one") is None
        assert store.is_cleared("domain.one")
    else:
        with store.transaction("domain.one"):
            store.set("domain.one", {"value": 2})
        assert store.get("domain.one") == {"value": 2}
    assert {path.name for path in tmp_path.iterdir()} == {"domain"}


@pytest.mark.parametrize("surface", ["namespace", "credential", "marker", "lock", "temp"])
def test_internal_redirect_never_touches_outside(
    store, tmp_path, monkeypatch, surface,
):
    outside = tmp_path.parent / f"outside-{surface}"
    outside.mkdir()
    sentinel = outside / "sentinel"
    sentinel.write_bytes(b"outside")
    original = sentinel.stat()
    if surface == "namespace":
        link, operation = tmp_path / "domain", lambda: store.set("domain.one", {})
    elif surface == "credential":
        link, operation = tmp_path / "one.yaml", lambda: store.get("one")
    elif surface == "marker":
        link, operation = tmp_path / ".one.cleared", lambda: store.is_cleared("one")
    elif surface == "lock":
        link, operation = tmp_path / ".one.lock", lambda: store.transaction("one").__enter__()
    else:
        import mountainash_settings.secrets.filesystem as implementation
        monkeypatch.setattr(implementation.secrets, "token_hex", lambda count: "fixed")
        link = tmp_path / ".one.fixed.tmp"
        operation = lambda: store.set("one", {})
    make_redirect(link, outside)
    with pytest.raises(SecretStoreUnavailableError) as caught:
        operation()
    assert_safe(caught.value, "unsafe_entry")
    assert sentinel.read_bytes() == b"outside"
    after = sentinel.stat()
    assert (after.st_ino, after.st_mode, after.st_size) == (
        original.st_ino, original.st_mode, original.st_size,
    )
    assert list(outside.iterdir()) == [sentinel]
    # Junctions are actual Windows reparse fixtures, not symlink-permission skips.


def test_random_temp_collision_is_not_reused(store, tmp_path, monkeypatch):
    import mountainash_settings.secrets.filesystem as implementation
    raw_file(store, tmp_path, ".one.fixed.tmp", b"collision")
    monkeypatch.setattr(implementation.secrets, "token_hex", lambda count: "fixed")
    with pytest.raises(SecretStoreUnavailableError) as caught:
        store.set("one", {"token": "new"})
    assert_safe(caught.value, "unavailable")
    assert (tmp_path / ".one.fixed.tmp").read_bytes() == b"collision"
    assert store.get("one") is None


def test_clean_error_does_not_retain_ambient_caller_exception(store, tmp_path):
    raw_file(store, tmp_path, "one.yaml", b"x: [SECRET_CANARY\n")
    try:
        raise RuntimeError("SECRET_CANARY")
    except RuntimeError:
        with pytest.raises(SecretStoreUnavailableError) as caught:
            store.get("one")
    assert_safe(caught.value, "malformed_yaml")


def test_missing_or_non_directory_root_is_not_created_or_repaired(tmp_path):
    missing = tmp_path / "missing"
    with pytest.raises(SecretStoreUnavailableError) as caught:
        FilesystemBackend(missing)
    assert_safe(caught.value, "unavailable")
    assert not missing.exists()
    ordinary = tmp_path / "ordinary"
    ordinary.write_bytes(b"sentinel")
    with pytest.raises(SecretStoreUnavailableError):
        FilesystemBackend(ordinary)
    assert ordinary.read_bytes() == b"sentinel"
