from typing import Any, List, Optional, Type, Union

import pytest
# from pydantic_settings import SettingsConfigDict, BaseSettings
from pydantic import Field, ValidationError, field_validator
from pytest_check import check
from upath import UPath

from mountainash_settings import SettingsManager, MountainAshBaseSettings, SettingsParameters
from mountainash_settings import get_settings
from mountainash_settings.secrets import SecretCapabilityError


@pytest.fixture
def settings_manager(monkeypatch) -> SettingsManager:
    manager = SettingsManager()
    monkeypatch.setattr(
        "mountainash_settings.settings_cache.settings_functions.get_settings_manager",
        lambda: manager,
    )
    return manager

##############
# Test Settings Class
class TestSettings(MountainAshBaseSettings):
    def __init__(
        self,
        config_files: Optional[List[UPath|str]] = None,
        settings_parameters:   Optional[SettingsParameters] = None,
        # _dummy=False,
        **kwargs
    ) -> None:

        super().__init__(
            config_files=config_files,
            settings_parameters=settings_parameters,
            # _dummy=_dummy,
            **kwargs
        )

    # App Settings
    TEST_VAL_1: str =                    Field(default=None)
    TEST_VAL_2: str =                    Field(default=None)


def get_test_settings(settings_parameters: SettingsParameters,
                     settings_class:     Optional[Type[TestSettings]] = TestSettings,
                     config_files: Optional[Union[UPath, str, List[UPath|str]]]  = None,
                     **kwargs
                     ) -> TestSettings:


    test_settings: TestSettings = TestSettings.get_settings(settings_parameters=settings_parameters,
                                                          settings_class=settings_class,
                                                          config_files=config_files,
                                                          **kwargs)
    if isinstance(test_settings, TestSettings):
        return test_settings
    else:
        raise ValueError("The settings object retrieved is not of type TestSettings.")


################
# TESTS #




def test_init_sets_env_file():
    env_file = [UPath("./tests/config_testing1.env")]

    sp = SettingsParameters.create(settings_class=TestSettings, config_files= env_file)

    settings = TestSettings(settings_parameters=sp)

    for file in env_file:
        assert file in settings.SETTINGS_SOURCE_ENV_FILES


def test_init_sets_env_prefix():
    prefix = "PREFIX_"

    sp = SettingsParameters.create(settings_class=TestSettings, env_prefix= prefix)

    settings = TestSettings(settings_parameters=sp)
    assert settings.SETTINGS_SOURCE_ENV_PREFIX == prefix


## ============================================================
## Test using variables with a prefix in the test config files, and in kwargs!


def test_init_no_file(settings_manager: SettingsManager):
    config_files: List[Any] = []#"./tests/config_testing1.env"]
    kwargs = {}

    settings_parameters = SettingsParameters.create( settings_class=TestSettings, config_files=config_files, kwargs=kwargs)

    app_settings: TestSettings =     get_test_settings(settings_parameters=settings_parameters)

    with check:
        assert app_settings.TEST_VAL_1 is None
        assert app_settings.TEST_VAL_2 is None

def test_init_no_file_kwarg(settings_manager: SettingsManager):
    config_files: List[Any] = []#"./tests/config_testing1.env"]
    kwargs = {"TEST_VAL_1": "ABC", "TEST_VAL_2": "XYZ"}

    settings_parameters = SettingsParameters.create(settings_class=TestSettings, config_files=config_files, kwargs=kwargs)

    app_settings: TestSettings =     get_test_settings(settings_parameters=settings_parameters)

    with check:
        #Getting None here!
        assert app_settings.TEST_VAL_1 == "ABC"
        assert app_settings.TEST_VAL_2 == "XYZ"


def test_init_file(settings_manager: SettingsManager):
    config_files: List[Any] = ["./tests/config_testing1.env"]
    kwargs = {}

    settings_parameters = SettingsParameters.create(settings_class=TestSettings, config_files=config_files, kwargs=kwargs)

    app_settings: TestSettings =     get_test_settings(settings_parameters=settings_parameters)

    with check:
        assert app_settings.TEST_VAL_1 == "TEST_VAL_1_File_1"
        assert app_settings.TEST_VAL_2 == "TEST_VAL_2_File_1"


def test_init_file_and_kwarg(settings_manager: SettingsManager):
    config_files: List[Any] = ["./tests/config_testing1.env"]
    kwargs = {"TEST_VAL_1": "ABC"}

    settings_parameters = SettingsParameters.create(settings_class=TestSettings, config_files=config_files, kwargs=kwargs)

    app_settings: TestSettings =     get_test_settings(settings_parameters=settings_parameters)

    with check:
        #kwargs not working here
        assert app_settings.TEST_VAL_1 == "ABC"
        assert app_settings.TEST_VAL_2 == "TEST_VAL_2_File_1"

def test_init_file_and_kwarg2(settings_manager: SettingsManager):
    config_files: List[Any] = ["./tests/config_testing1.env"]
    kwargs = {"TEST_VAL_2": "XYZ"}

    settings_parameters = SettingsParameters.create(settings_class=TestSettings, config_files=config_files, kwargs=kwargs)

    app_settings: TestSettings =     get_test_settings(settings_parameters=settings_parameters)

    with check:
        assert app_settings.TEST_VAL_1 == "TEST_VAL_1_File_1"
        #kwargs not working here
        assert app_settings.TEST_VAL_2 == "XYZ"



def test_init_file_prefix1(settings_manager: SettingsManager):
    config_files: List[Any] = ["./tests/config_testing1.env"]
    kwargs = {}

    settings_parameters = SettingsParameters.create(settings_class=TestSettings,
                                                    config_files=config_files,
                                                    env_prefix="PREFIX_",
                                                    kwargs=kwargs)

    app_settings: TestSettings =     get_test_settings(settings_parameters=settings_parameters)

    with check:
        assert app_settings.TEST_VAL_1 == "TEST_VAL_1_File_1"
        assert app_settings.TEST_VAL_2 == "TEST_VAL_2_File_1"

def test_init_file_prefix2(settings_manager: SettingsManager):
    config_files: List[Any] = ["./tests/config_testing_prefix1.env"]
    kwargs = {}

    settings_parameters = SettingsParameters.create(settings_class=TestSettings,
                                                    config_files=config_files,
                                                    env_prefix="PREFIX_",
                                                    kwargs=kwargs)

    app_settings: TestSettings =     get_test_settings(settings_parameters=settings_parameters)

    with check:
        assert app_settings.TEST_VAL_1 == "TEST_VAL_1_File_Prefix1"
        assert app_settings.TEST_VAL_2 == "TEST_VAL_2_File_Prefix1"

def test_init_file_prefix3(settings_manager: SettingsManager):
    config_files: List[Any] = ["./tests/config_testing_prefix1.env"]
    kwargs = {}

    settings_parameters = SettingsParameters.create(settings_class=TestSettings, config_files=config_files, kwargs=kwargs)

    app_settings: TestSettings =     get_test_settings(settings_parameters=settings_parameters)

    with check:
        assert app_settings.TEST_VAL_1 is None
        assert app_settings.TEST_VAL_2 is None

def test_init_file_prefix_prefers_prefixed_value(settings_manager, tmp_path):
    env_file = tmp_path / "both.env"
    env_file.write_text(
        'TEST_VAL_1="unprefixed"\n'
        'PREFIX_TEST_VAL_1="prefixed"\n'
    )
    params = SettingsParameters.create(
        settings_class=TestSettings,
        config_files=[env_file],
        env_prefix="PREFIX_",
    )

    settings = get_test_settings(settings_parameters=params)

    assert settings.TEST_VAL_1 == "prefixed"



def test_init_config_valid_init_two_files_noprefix(settings_manager: SettingsManager):
    # Arrange
    config_files: List[Any] = [ "./tests/config_testing1.env", "./tests/config_testing2.env"]
    kwargs = {}

    settings_parameters = SettingsParameters.create(settings_class=TestSettings, config_files=config_files, kwargs=kwargs)
    app_settings: TestSettings =     get_test_settings(settings_parameters=settings_parameters)

    #TEST_VAL_2 was 000002 in the file, but over-ridden by the kwarg
    with check:
        assert app_settings.TEST_VAL_1 == "TEST_VAL_1_File_2"
        assert app_settings.TEST_VAL_2 == "TEST_VAL_2_File_2"

def test_init_config_valid_init_files_reverse_noprefix(settings_manager: SettingsManager):
    config_files: List[Any] = ["./tests/config_testing2.env", "./tests/config_testing1.env"]
    kwargs = {}

    settings_parameters = SettingsParameters.create(settings_class=TestSettings, config_files=config_files, kwargs=kwargs)
    app_settings: TestSettings =     get_test_settings(settings_parameters=settings_parameters)

    #TEST_VAL_2 was 000002 in the file, but over-ridden by the kwarg
    with check:
        assert app_settings.TEST_VAL_1 == "TEST_VAL_1_File_1"
        assert app_settings.TEST_VAL_2 == "TEST_VAL_2_File_1"




def test_init_config_valid_init_files_override_and_kwargs_noprefix(settings_manager: SettingsManager):
    # Arrange
    config_files: List[Any] = ["./tests/config_testing1.env"]
    kwargs = {"TEST_VAL_2": "000003"}

    settings_parameters = SettingsParameters.create(settings_class=TestSettings, config_files=config_files, kwargs=kwargs)
    app_settings: TestSettings =     get_test_settings(settings_parameters=settings_parameters)

    with check:
        assert app_settings.TEST_VAL_1 == "TEST_VAL_1_File_1"
        #kwargs not working here
        assert app_settings.TEST_VAL_2 == "000003"

def test_init_config_valid_init_files_override_and_kwargs_noprefix2(settings_manager: SettingsManager):
    # Arrange
    config_files: List[Any] = [ "./tests/config_testing2.env"]
    kwargs = {"TEST_VAL_1": "ABC"}

    settings_parameters = SettingsParameters.create(settings_class=TestSettings, config_files=config_files, kwargs=kwargs)
    app_settings: TestSettings =     get_test_settings(settings_parameters=settings_parameters)

    #TEST_VAL_2 was 000002 in the file, but over-ridden by the kwarg
    with check:
        #kwargs not working here
        assert app_settings.TEST_VAL_1 == "ABC"
        assert app_settings.TEST_VAL_2 == "TEST_VAL_2_File_2"


# --- Secrets Resolution Integration Tests ---

class _TestBackendData(dict):
    """Dict that returns 'resolved_key/field' for any field lookup."""
    def __init__(self, key: str):
        super().__init__()
        self._key = key

    def __contains__(self, field):
        return True

    def __getitem__(self, field):
        return f"resolved_{self._key}/{field}"

    def __len__(self):
        return 2


class _TestBackend:
    def get(self, key: str) -> dict | None:
        return _TestBackendData(key)

    def set(self, key: str, data: dict) -> None:
        pass

    def delete(self, key: str) -> None:
        pass

    def transaction(self, key: str):
        from contextlib import nullcontext
        return nullcontext()


@pytest.fixture
def secrets_registry():
    """Provide a bindable test store for secret_store=."""
    return _TestBackend()


class _SecretsTestSettings(MountainAshBaseSettings):
    USERNAME: str = Field(default="default_user")
    PASSWORD: str = Field(default="default_pass")



class _ContainerSecretsSettings(MountainAshBaseSettings):
    CONNECTION: dict[str, Any] = Field(default_factory=dict)
    ENDPOINTS: list[Any] = Field(default_factory=list)

class TestSecretsResolution:
    def test_kwargs_secret_resolved_on_construction(self, secrets_registry):
        settings = _SecretsTestSettings(
            settings_parameters=SettingsParameters.create(
                settings_class=_SecretsTestSettings,
                secret_store=secrets_registry,
                PASSWORD="secret:db.password",
            )
        )
        assert settings.PASSWORD == "resolved_db/password"

    def test_config_file_secret_resolved_post_construction(self, secrets_registry):
        settings = _SecretsTestSettings(
            settings_parameters=SettingsParameters.create(
                settings_class=_SecretsTestSettings,
                secret_store=secrets_registry,
                config_files=["tests/config/secrets_test.yaml"],
                env_prefix="SECRETSTEST_",
            )
        )
        assert settings.PASSWORD == "resolved_db/password"
        assert settings.USERNAME == "admin"

    def test_no_store_raises_capability_error(self):
        with pytest.raises(SecretCapabilityError):
            _SecretsTestSettings(PASSWORD="secret:db.password")

    def test_cache_hit_runtime_override_resolves_secret(
        self, secrets_registry, settings_manager
    ):
        params_base = SettingsParameters.create(
            settings_class=_SecretsTestSettings,
            secret_store=secrets_registry,
            config_files=["tests/config/secrets_test.yaml"],
        )

        settings1 = get_settings(settings_parameters=params_base)
        assert settings1.PASSWORD == "resolved_db/password"

        settings2 = get_settings(
            settings_parameters=params_base,
            PASSWORD="secret:other.password",
        )
        assert settings2.PASSWORD == "resolved_other/password"
        assert settings1.PASSWORD == "resolved_db/password"

    def test_config_file_container_secrets_resolve(self, secrets_registry, tmp_path):
        config = tmp_path / "containers.toml"
        config.write_text(
            'ENDPOINTS = ["secret:api.token"]\n'
            '[CONNECTION]\n'
            'password = "secret:db.password"\n'
        )
        settings = _ContainerSecretsSettings(
            settings_parameters=SettingsParameters.create(
                settings_class=_ContainerSecretsSettings,
                secret_store=secrets_registry,
                config_files=[config],
            )
        )
        assert settings.CONNECTION == {"password": "resolved_db/password"}
        assert settings.ENDPOINTS == ["resolved_api/token"]

    def test_cache_hit_container_override_resolves(self, secrets_registry, settings_manager):
        params = SettingsParameters.create(
            settings_class=_ContainerSecretsSettings,
            secret_store=secrets_registry,
        )
        get_settings(settings_parameters=params)

        overridden = get_settings(
            settings_parameters=params,
            CONNECTION={"password": "secret:other.password"},
        )

        assert overridden.CONNECTION == {"password": "resolved_other/password"}

    def test_nested_frozen_model_secret_resolved_from_yaml(self, secrets_registry):
        from pydantic import BaseModel, ConfigDict, SecretStr
        import typing as t

        class PasswordAuth(BaseModel):
            model_config = ConfigDict(frozen=True, extra="forbid")
            kind: t.Literal["password"] = "password"
            username: str
            password: SecretStr

        class _NestedAuthSettings(MountainAshBaseSettings):
            APP_NAME: str = Field(default="default")
            auth: PasswordAuth

        settings = _NestedAuthSettings(
            settings_parameters=SettingsParameters.create(
                settings_class=_NestedAuthSettings,
                secret_store=secrets_registry,
                config_files=["tests/config/nested_secrets_test.yaml"],
                env_prefix="NESTEDSECTEST_",
            )
        )
        assert settings.APP_NAME == "test_app"
        assert settings.auth.username == "admin"
        assert settings.auth.password.get_secret_value() == "resolved_db.production/password"

    def test_nested_model_secret_in_kwargs_resolved(self, secrets_registry):
        from pydantic import BaseModel, ConfigDict, SecretStr
        import typing as t

        class PasswordAuth(BaseModel):
            model_config = ConfigDict(frozen=True, extra="forbid")
            kind: t.Literal["password"] = "password"
            username: str
            password: SecretStr

        class _NestedAuthSettings(MountainAshBaseSettings):
            APP_NAME: str = Field(default="default")
            auth: PasswordAuth

        settings = _NestedAuthSettings(
            settings_parameters=SettingsParameters.create(
                settings_class=_NestedAuthSettings,
                secret_store=secrets_registry,
                auth={"kind": "password", "username": "admin", "password": "secret:db.password"},
            )
        )
        assert settings.auth.password.get_secret_value() == "resolved_db/password"


# --- MAS-SEC-006 (M7): secret-resolution validation-error boundary ---


class _M7MarkerBackend:
    """Dummy SecretReader with an unmistakable marker and a call counter.

    Per the M7 plan's Task 1: disposable, never logs, and its marker is
    unambiguous enough that any appearance in error text/repr/chain proves
    a leak rather than a coincidence.
    """

    MARKER = "M7-UNMISTAKABLE-SECRET-MARKER-3f9a"

    def __init__(self) -> None:
        self.calls = 0

    def get(self, key: str) -> dict[str, str] | None:
        self.calls += 1
        return {"value": self.MARKER}


class _M7RejectingSettings(MountainAshBaseSettings):
    """A field whose validator always rejects, regardless of input, so the
    same class proves both the disclosure boundary (secret-resolved input)
    and the compatibility boundary (literal input) for MAS-SEC-006."""

    TOKEN: str = Field(default="unset")

    @field_validator("TOKEN")
    @classmethod
    def _reject(cls, v: str) -> str:
        raise ValueError("upstream-validator-rejected")


class TestSecretValidationErrorBoundary:
    """MAS-SEC-006 (M7): a local-record value successfully resolved from a
    ``secret:`` reference must never survive into a later validation
    failure's text, repr, structured payload, cause, or context, on either
    the constructor or cache-hit route. Red until Task 3 adds the guard
    boundary at both routes; the literal-only and missing-reference cases
    are controls that must already pass and must keep passing."""

    def test_constructor_rejecting_validator_sanitizes_resolved_marker(self):
        backend = _M7MarkerBackend()
        with pytest.raises(ValueError) as excinfo:
            _M7RejectingSettings(
                settings_parameters=SettingsParameters.create(
                    settings_class=_M7RejectingSettings,
                    secret_store=backend,
                    TOKEN="secret:db",
                )
            )
        error = excinfo.value
        assert backend.MARKER not in str(error)
        assert backend.MARKER not in repr(error)
        assert "upstream-validator-rejected" not in str(error)
        assert "_M7RejectingSettings" in str(error)
        assert "TOKEN" in str(error)
        assert error.__cause__ is None
        assert error.__context__ is None

    def test_constructor_literal_only_validator_error_stays_ordinary(self):
        """Control: a caller-known literal was never resolved, so the
        ordinary Pydantic diagnostic must remain -- this must NOT sanitize."""
        with pytest.raises(ValidationError, match="upstream-validator-rejected"):
            _M7RejectingSettings(TOKEN="plain-literal-value")

    def test_constructor_missing_reference_keeps_key_error(self):
        """Control: no local-record value was ever produced, so the
        existing descriptive ``KeyError`` contract must be preserved."""
        from mountainash_settings.secrets import MemorySecretStore

        with pytest.raises(KeyError):
            _M7RejectingSettings(
                settings_parameters=SettingsParameters.create(
                    settings_class=_M7RejectingSettings,
                    secret_store=MemorySecretStore(),
                    TOKEN="secret:missing.nonexistent_field_xyz",
                )
            )

    def test_cache_hit_rejecting_validator_sanitizes_resolved_marker(self, settings_manager):
        backend = _M7MarkerBackend()
        params = SettingsParameters.create(
            settings_class=_M7RejectingSettings,
            secret_store=backend,
            TOKEN="secret:db",
        )
        with pytest.raises(ValueError) as excinfo:
            get_settings(settings_parameters=params)
        error = excinfo.value
        assert backend.MARKER not in str(error)
        assert backend.MARKER not in repr(error)
        assert error.__cause__ is None
        assert error.__context__ is None
