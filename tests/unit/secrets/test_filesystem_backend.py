"""Tests for FilesystemBackend."""
from __future__ import annotations

import os
import stat

import pytest

from mountainash_settings.secrets.backend import ClearableBackend, SecretsBackend
from mountainash_settings.secrets.filesystem import FilesystemBackend


@pytest.fixture
def backend(tmp_path):
    return FilesystemBackend(base_dir=tmp_path)


@pytest.mark.unit
class TestFilesystemBackendProtocol:
    def test_satisfies_secrets_backend(self, backend):
        assert isinstance(backend, SecretsBackend)

    def test_satisfies_clearable_backend(self, backend):
        assert isinstance(backend, ClearableBackend)


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
    def test_file_permissions_0600(self, backend, tmp_path):
        backend.set("wearables.strava.default", {"token": "x"})
        path = tmp_path / "wearables" / "strava-default.yaml"
        mode = stat.S_IMODE(path.stat().st_mode)
        assert mode == 0o600

    def test_directory_permissions_0700(self, backend, tmp_path):
        backend.set("wearables.strava.default", {"token": "x"})
        dir_path = tmp_path / "wearables"
        mode = stat.S_IMODE(dir_path.stat().st_mode)
        assert mode == 0o700

    def test_rejects_symlink_on_read(self, backend, tmp_path):
        real_file = tmp_path / "real.yaml"
        real_file.write_text("token: x\n")
        domain_dir = tmp_path / "wearables"
        domain_dir.mkdir()
        link = domain_dir / "strava-default.yaml"
        link.symlink_to(real_file)
        with pytest.raises(PermissionError):
            backend.get("wearables.strava.default")


@pytest.mark.unit
class TestFilesystemBackendTransaction:
    def test_transaction_context_manager(self, backend):
        backend.set("wearables.strava.default", {"token": "old"})
        with backend.transaction("wearables.strava.default"):
            data = backend.get("wearables.strava.default")
            data["token"] = "new"
            backend.set("wearables.strava.default", data)
        assert backend.get("wearables.strava.default") == {"token": "new"}


@pytest.mark.unit
class TestFilesystemBackendKeyMapping:
    def test_single_segment_key(self, backend, tmp_path):
        backend.set("simple", {"val": 1})
        assert (tmp_path / "simple.yaml").exists()

    def test_two_segment_key(self, backend, tmp_path):
        backend.set("domain.provider", {"val": 1})
        assert (tmp_path / "domain" / "provider.yaml").exists()

    def test_three_segment_key(self, backend, tmp_path):
        backend.set("wearables.strava.default", {"val": 1})
        assert (tmp_path / "wearables" / "strava-default.yaml").exists()
