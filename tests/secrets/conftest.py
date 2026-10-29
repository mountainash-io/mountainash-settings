"""Local-store setup shared by portable and native filesystem tests."""

import pytest

from mountainash_settings.secrets import FilesystemBackend


@pytest.fixture
def store(tmp_path):
    """Close native handles after each test using the store."""
    with FilesystemBackend(base_dir=tmp_path) as value:
        yield value
