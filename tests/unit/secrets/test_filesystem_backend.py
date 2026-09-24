"""Tests for FilesystemBackend."""
from __future__ import annotations

import os
import stat

import pytest

from mountainash_settings.secrets.backend import SecretWriter, ClearableSecretStore
from mountainash_settings.secrets.filesystem import FilesystemBackend


@pytest.fixture
def backend(tmp_path):
    with FilesystemBackend(base_dir=tmp_path) as value:
        yield value


@pytest.mark.unit
class TestFilesystemBackendProtocol:
    def test_satisfies_secret_writer(self, backend):
        assert isinstance(backend, SecretWriter)

    def test_satisfies_clearable_secret_store(self, backend):
        assert isinstance(backend, ClearableSecretStore)


@pytest.mark.unit
class TestFilesystemBackendBasic:
    def test_set_and_get_round_trip(self, backend):
        data = {"access_token": "tok123", "refresh_token": "ref456"}
        backend.set("wearables.strava.default", data)
        result = backend.get("wearables.strava.default")
        assert result == data

    def test_get_missing_returns_none(self, backend):
        assert backend.get("wearables.strava.nobody") is None

    def test_delete_removes_value(self, backend):
        backend.set("wearables.strava.alice", {"token": "x"})
        backend.delete("wearables.strava.alice")
        assert backend.get("wearables.strava.alice") is None

    def test_is_cleared_after_delete(self, backend):
        backend.set("wearables.strava.alice", {"token": "x"})
        backend.delete("wearables.strava.alice")
        assert backend.is_cleared("wearables.strava.alice") is True

    def test_is_not_cleared_before_delete(self, backend):
        backend.set("wearables.strava.alice", {"token": "x"})
        assert backend.is_cleared("wearables.strava.alice") is False

    def test_is_not_cleared_when_never_set(self, backend):
        assert backend.is_cleared("wearables.strava.alice") is False

    def test_set_after_delete_removes_tombstone(self, backend):
        backend.set("wearables.strava.alice", {"token": "x"})
        backend.delete("wearables.strava.alice")
        assert backend.is_cleared("wearables.strava.alice") is True
        backend.set("wearables.strava.alice", {"token": "y"})
        assert backend.is_cleared("wearables.strava.alice") is False
        assert backend.get("wearables.strava.alice") == {"token": "y"}


@pytest.mark.unit
class TestFilesystemBackendSecurity:
    @pytest.mark.skipif(os.name == "nt", reason="POSIX mode contract; Windows DACL tested natively")
    def test_file_permissions_0600(self, backend, tmp_path):
        backend.set("wearables.strava.default", {"token": "x"})
        path = tmp_path / "wearables" / "strava-default.yaml"
        mode = stat.S_IMODE(path.stat().st_mode)
        assert mode == 0o600


@pytest.mark.unit
class TestFilesystemBackendTransaction:
    def test_transaction_context_manager(self, backend):
        backend.set("wearables.strava.default", {"token": "old"})
        with backend.transaction("wearables.strava.default"):
            data = backend.get("wearables.strava.default")
            data["token"] = "new"
            backend.set("wearables.strava.default", data)
        assert backend.get("wearables.strava.default") == {"token": "new"}


