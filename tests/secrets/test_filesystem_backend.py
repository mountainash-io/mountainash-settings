"""Tests for FilesystemBackend."""
from __future__ import annotations

import os
import stat

import pytest

from mountainash_settings.secrets.backend import SecretWriter, ClearableSecretStore


@pytest.mark.unit
class TestFilesystemBackendProtocol:
    def test_satisfies_secret_writer(self, store):
        assert isinstance(store, SecretWriter)

    def test_satisfies_clearable_secret_store(self, store):
        assert isinstance(store, ClearableSecretStore)


@pytest.mark.unit
class TestFilesystemBackendBasic:
    def test_set_and_get_round_trip(self, store):
        data = {"access_token": "tok123", "refresh_token": "ref456"}
        store.set("wearables.strava.default", data)
        result = store.get("wearables.strava.default")
        assert result == data

    def test_get_missing_returns_none(self, store):
        assert store.get("wearables.strava.nobody") is None

    def test_delete_removes_value(self, store):
        store.set("wearables.strava.alice", {"token": "x"})
        store.delete("wearables.strava.alice")
        assert store.get("wearables.strava.alice") is None

    def test_is_cleared_after_delete(self, store):
        store.set("wearables.strava.alice", {"token": "x"})
        store.delete("wearables.strava.alice")
        assert store.is_cleared("wearables.strava.alice") is True

    def test_is_not_cleared_before_delete(self, store):
        store.set("wearables.strava.alice", {"token": "x"})
        assert store.is_cleared("wearables.strava.alice") is False

    def test_is_not_cleared_when_never_set(self, store):
        assert store.is_cleared("wearables.strava.alice") is False

    def test_set_after_delete_removes_tombstone(self, store):
        store.set("wearables.strava.alice", {"token": "x"})
        store.delete("wearables.strava.alice")
        assert store.is_cleared("wearables.strava.alice") is True
        store.set("wearables.strava.alice", {"token": "y"})
        assert store.is_cleared("wearables.strava.alice") is False
        assert store.get("wearables.strava.alice") == {"token": "y"}


@pytest.mark.unit
class TestFilesystemBackendSecurity:
    @pytest.mark.skipif(
        os.name == "nt",
        reason="optional-native: POSIX mode contract; Windows DACL tested natively",
    )
    def test_file_permissions_0600(self, store, tmp_path):
        store.set("wearables.strava.default", {"token": "x"})
        path = tmp_path / "wearables" / "strava-default.yaml"
        mode = stat.S_IMODE(path.stat().st_mode)
        assert mode == 0o600


@pytest.mark.unit
class TestFilesystemBackendTransaction:
    def test_transaction_context_manager(self, store):
        store.set("wearables.strava.default", {"token": "old"})
        with store.transaction("wearables.strava.default"):
            data = store.get("wearables.strava.default")
            data["token"] = "new"
            store.set("wearables.strava.default", data)
        assert store.get("wearables.strava.default") == {"token": "new"}
