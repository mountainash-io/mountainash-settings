"""Unit tests for the secrets resolver registry."""

import pytest

from mountainash_settings.secrets.registry import (
    SecretsResolver,
    register_secrets_resolver,
    get_secrets_resolver,
    replace_secrets_resolver,
    clear_secrets_registry,
)


@pytest.fixture(autouse=True)
def clean_registry():
    """Ensure every test starts and ends with an empty registry."""
    clear_secrets_registry()
    yield
    clear_secrets_registry()


def _dummy_resolver(path: str) -> str:
    return f"resolved_{path}"


def _other_resolver(path: str) -> str:
    return f"other_{path}"


@pytest.mark.unit
class TestSecretsRegistry:
    def test_register_and_retrieve(self):
        register_secrets_resolver("local", _dummy_resolver)
        assert get_secrets_resolver("local") is _dummy_resolver

    def test_get_unregistered_raises_keyerror(self):
        with pytest.raises(KeyError):
            get_secrets_resolver("nonexistent")

    def test_duplicate_registration_raises_valueerror(self):
        register_secrets_resolver("local", _dummy_resolver)
        with pytest.raises(ValueError):
            register_secrets_resolver("local", _other_resolver)

    def test_replace_overwrites_existing(self):
        register_secrets_resolver("local", _dummy_resolver)
        replace_secrets_resolver("local", _other_resolver)
        assert get_secrets_resolver("local") is _other_resolver

    def test_replace_unregistered_registers(self):
        replace_secrets_resolver("new_provider", _dummy_resolver)
        assert get_secrets_resolver("new_provider") is _dummy_resolver

    def test_clear_removes_all(self):
        register_secrets_resolver("a", _dummy_resolver)
        register_secrets_resolver("b", _other_resolver)
        clear_secrets_registry()
        with pytest.raises(KeyError):
            get_secrets_resolver("a")
        with pytest.raises(KeyError):
            get_secrets_resolver("b")
