"""Consumer-shaped contracts through the public generated-profile API."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import pytest
from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator

from mountainash_settings import ParameterSpec, Profile, ProfileField, ProfileSpec, Registry, SettingsParameters
from mountainash_settings.secrets.memory import MemorySecretStore


# Shapes inspected in mountainash-data/core/settings/descriptor.py and
# mountainash-transport/settings/profile_spec.py; no sibling runtime dependency.
@dataclass(frozen=True, kw_only=True)
class DatabaseSpec(ProfileSpec):
    default_port: int = 5432
    supported_auth: tuple[type, ...] = ()


@dataclass(frozen=True, kw_only=True)
class StorageSpec(ProfileSpec):
    read_only: bool = False


def test_database_domain_metadata_transforms_and_optional_secrets():
    class Database(Profile, spec_type=DatabaseSpec, driver_keys="lower"):
        HOST: str = "localhost"
        DATABASE_PATH: Path = ProfileField(default=Path("database"), driver_key="path", transform=str)
        PASSWORD: SecretStr | None = None

    class Concrete(Database, name="database", provider_type="sql", supported_auth=(object,)):
        pass

    class Explicit(Profile):
        __spec__ = DatabaseSpec(name="explicit", provider_type="sql", supported_auth=(object,), parameters=[
            ParameterSpec(name="HOST", type=str, tier="core", default="localhost", driver_key="host"),
            ParameterSpec(name="DATABASE_PATH", type=Path, tier="core", default=Path("database"), driver_key="path", transform=str),
            ParameterSpec(name="PASSWORD", type=str, tier="core", secret=True, default=None, driver_key="password"),
        ])

    registry = Registry("database", spec_type=DatabaseSpec, profile_type=Database)
    registry.decorator()(Concrete)
    assert registry.get_spec("database").supported_auth == (object,)
    assert registry.get_spec("database").default_port == 5432
    assert Concrete().emit() == Explicit().emit() == {"host": "localhost", "path": "database"}
    assert Concrete(PASSWORD="example").emit() == Explicit(PASSWORD="example").emit() == {
        "host": "localhost", "path": "database", "password": "example",
    }
    register_storage = Registry("storage", spec_type=StorageSpec).decorator()
    with pytest.raises(TypeError, match="spec_type"):
        register_storage(Concrete)


def test_storage_target_adapter_receives_mapped_values_and_excluded_credentials():
    def http(profile, kwargs):
        return {**kwargs, "headers": {
            **kwargs.get("headers", {}),
            "Authorization": "Bearer " + profile.TOKEN.get_secret_value(),
        }}

    class Service(Profile, spec_type=StorageSpec, name="service", provider_type="http", read_only=True):
        HOST: str = ProfileField(default="example.test", driver_key={"http": "host", "file": "endpoint"})
        TOKEN: SecretStr = ProfileField(driver_key=None)
        RETRIES: int = 3
        LOCAL_NOTE: str = "private"
        __adapters__ = {"http": http}

    base = {"headers": {"X-Client": "report"}}
    profile = Service(TOKEN="example")
    assert profile.emit("http", base=base) == {
        "host": "example.test", "headers": {"X-Client": "report", "Authorization": "Bearer example"},
    }
    assert base == {"headers": {"X-Client": "report"}}
    assert profile.emit("file") == {"endpoint": "example.test"}
    with pytest.raises(ValueError, match="target-scoped"):
        profile.emit()
    with pytest.raises(ValueError, match="no emission"):
        profile.emit("other")


def test_explicit_oauth_parent_exclusions_and_adapter_survive_generated_child():
    # Inheritance shape inspected in mountainash-wearables/connections/auth_identity.py.
    def oauth(profile, kwargs):
        return {**kwargs, "token": profile.ACCESS_TOKEN.get_secret_value()}

    class OAuth(Profile):
        __spec__ = ProfileSpec(name="oauth", provider_type="oauth", parameters=[
            ParameterSpec(name="ACCESS_TOKEN", type=str, tier="core", secret=True),
            ParameterSpec(name="CLIENT_SECRET", type=str, tier="core", secret=True),
        ])
        __adapters__ = {"http": oauth}

    class Service(OAuth, name="service", provider_type="service", driver_keys="lower"):
        HOST: str = "example.test"

    store = MemorySecretStore()
    store.set("oauth", {"token": "access", "client": "client"})
    profile = Service(ACCESS_TOKEN="secret:oauth.token", CLIENT_SECRET="secret:oauth.client", secret_store=store)
    assert profile.emit("http") == {"host": "example.test", "token": "access"}
    assert OAuth(ACCESS_TOKEN="access", CLIENT_SECRET="client").emit("http") == {"token": "access"}


def test_generated_template_uses_captured_baseline_with_local_overrides(tmp_path, isolated_settings_manager):
    config = tmp_path / "settings.json"
    config.write_text('{"HOST": "baseline", "PORT": 5432}')

    class Database(Profile, name="template", provider_type="db"):
        HOST: str
        PORT: int
        URL: str | None = ProfileField(default=None, template="{HOST}:{PORT}")
        TAGS: list[str] = ProfileField(default_factory=list)

    params = SettingsParameters.create(settings_class=Database, config_files=[config])
    first = isolated_settings_manager.get_or_create_settings(params)
    assert first.URL == "baseline:5432"
    first.TAGS.append("local")
    config.write_text('{"HOST": "changed-on-disk", "PORT": 1111}')
    changed = SettingsParameters.create(settings_class=Database, config_files=[config], HOST="local")
    second = isolated_settings_manager.get_or_create_settings(changed, reinitialise=True)
    assert second.URL == "local:5432"
    assert second.TAGS == []
    assert first.URL == "baseline:5432"
    explicit = SettingsParameters.create(settings_class=Database, config_files=[config], URL="explicit")
    assert isolated_settings_manager.get_or_create_settings(explicit, reinitialise=True).URL == "explicit"


@pytest.mark.parametrize("annotation", [SecretStr | None, Annotated[SecretStr, Field(description="secret")]])
def test_generated_secret_template_failure_has_no_value_or_exception_chain(annotation):
    class Sensitive(Profile, name="sensitive", provider_type="db"):
        RAW: str = "secret-canary"
        TOKEN: annotation = ProfileField(default=None, template="{RAW}")

        @field_validator("TOKEN")
        @classmethod
        def reject(cls, value):
            raise ValueError("validator-canary")

    assert next(p for p in Sensitive.__spec__.parameters if p.name == "TOKEN").secret
    with pytest.raises(ValueError, match="TOKEN") as error:
        Sensitive()
    assert "secret-canary" not in str(error.value)
    assert "validator-canary" not in str(error.value)
    assert error.value.__context__ is None
    assert error.value.__cause__ is None


def test_generated_model_retains_aliases_validators_and_assignment_validation(monkeypatch):
    monkeypatch.setenv("PROFILE_TEST_HOST", "EXAMPLE.TEST")

    class Service(Profile, name="native", provider_type="http", driver_keys="lower"):
        HOST: str = ProfileField(validation_alias="PROFILE_TEST_HOST")
        PORT: int = ProfileField(default=443, ge=1)
        URL: str = ProfileField(default_factory=lambda data: "https://" + data["HOST"])

        @field_validator("HOST")
        @classmethod
        def lowercase(cls, value):
            return value.lower()

        @model_validator(mode="after")
        def secure_port(self):
            if self.PORT != 443:
                raise ValueError("secure port required")
            return self

    profile = Service()
    assert profile.emit() == {"host": "example.test", "port": 443, "url": "https://example.test"}
    with pytest.raises(ValidationError, match="secure port"):
        Service(PORT=80)
    with pytest.raises(ValidationError):
        profile.PORT = 0
