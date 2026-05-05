"""Unit tests for secret resolution helpers."""

import pytest
from pydantic import Field, SecretStr

from mountainash_settings.secrets.resolve import (
    resolve_secrets_in_dict,
    resolve_secrets_on_instance,
)
from mountainash_settings.settings.base_settings import MountainAshBaseSettings


def _test_resolver(path: str) -> str:
    return f"resolved_{path}"


@pytest.mark.unit
class TestResolveSecretsInDict:
    def test_flat_dict_resolves_prefixed_value(self):
        data = {"PASSWORD": "secret:db/password"}
        result = resolve_secrets_in_dict(data, _test_resolver)
        assert result == {"PASSWORD": "resolved_db/password"}

    def test_nested_dict_resolved_recursively(self):
        data = {"outer": {"inner": "secret:nested/key"}}
        result = resolve_secrets_in_dict(data, _test_resolver)
        assert result == {"outer": {"inner": "resolved_nested/key"}}

    def test_non_string_values_passed_through(self):
        data = {"count": 42, "flag": True, "items": [1, 2, 3]}
        result = resolve_secrets_in_dict(data, _test_resolver)
        assert result == data

    def test_non_prefixed_strings_passed_through(self):
        data = {"name": "plain_value", "host": "localhost"}
        result = resolve_secrets_in_dict(data, _test_resolver)
        assert result == data

    def test_empty_dict_returns_empty(self):
        assert resolve_secrets_in_dict({}, _test_resolver) == {}

    def test_custom_prefix(self):
        data = {"TOKEN": "vault:api/token"}
        result = resolve_secrets_in_dict(data, _test_resolver, prefix="vault:")
        assert result == {"TOKEN": "resolved_api/token"}

    def test_does_not_mutate_input(self):
        data = {"PASSWORD": "secret:db/password"}
        original = dict(data)
        resolve_secrets_in_dict(data, _test_resolver)
        assert data == original


class _SecretTestSettings(MountainAshBaseSettings):
    USERNAME: str = Field(default="admin")
    PASSWORD: str = Field(default="changeme")
    PORT: int = Field(default=5432)


@pytest.mark.unit
class TestResolveSecretsOnInstance:
    def test_resolves_prefixed_string_fields(self):
        instance = _SecretTestSettings(USERNAME="admin", PASSWORD="secret:db/pass")
        resolve_secrets_on_instance(instance, _test_resolver)
        assert instance.PASSWORD == "resolved_db/pass"

    def test_skips_non_string_fields(self):
        instance = _SecretTestSettings(PORT=5432)
        resolve_secrets_on_instance(instance, _test_resolver)
        assert instance.PORT == 5432

    def test_skips_non_prefixed_strings(self):
        instance = _SecretTestSettings(USERNAME="admin", PASSWORD="plaintext")
        resolve_secrets_on_instance(instance, _test_resolver)
        assert instance.PASSWORD == "plaintext"

    def test_resolves_secretstr_field(self):
        class WithSecretStr(MountainAshBaseSettings):
            TOKEN: SecretStr = Field(default=SecretStr("default"))

        instance = WithSecretStr(TOKEN="secret:api/token")
        resolve_secrets_on_instance(instance, _test_resolver)
        assert instance.TOKEN.get_secret_value() == "resolved_api/token"

    def test_skips_settings_source_bookkeeping_fields(self):
        instance = _SecretTestSettings(USERNAME="admin")
        resolve_secrets_on_instance(instance, _test_resolver)
        assert instance.SETTINGS_CLASS is not None
