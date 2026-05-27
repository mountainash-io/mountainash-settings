from typing import Any, List, Optional, Type, Union

import pytest
# from pydantic_settings import SettingsConfigDict, BaseSettings
from pydantic import Field
from pytest_check import check
from upath import UPath

from mountainash_settings import SettingsManager, MountainAshBaseSettings, SettingsParameters
from mountainash_settings import get_settings_manager, get_settings
from mountainash_settings.secrets import register_secrets_resolver, clear_secrets_registry


@pytest.fixture
def settings_manager() -> SettingsManager:
    settings_manager: SettingsManager = get_settings_manager()
    # settings_manager: SettingsManager = SettingsManager()
    return settings_manager

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


def test_init_sets_kwargs():
    kwargs: dict[str, Any] = {"TEST_VAL_1": "value1", "TEST_VAL_2": "value2"}
    settings = TestSettings(**kwargs)
    assert settings.SETTINGS_SOURCE_KWARGS == kwargs


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
        assert app_settings.TEST_VAL_1 == None
        assert app_settings.TEST_VAL_2 == None



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
        assert app_settings.TEST_VAL_1 == "TEST_VAL_1_File_2"
        assert app_settings.TEST_VAL_2 == "TEST_VAL_2_File_2"




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

def _test_resolver(path: str) -> str:
    return f"resolved_{path}"


@pytest.fixture
def secrets_registry():
    """Register a test resolver and clean up after."""
    clear_secrets_registry()
    register_secrets_resolver("test", _test_resolver)
    yield
    clear_secrets_registry()


class _SecretsTestSettings(MountainAshBaseSettings):
    USERNAME: str = Field(default="default_user")
    PASSWORD: str = Field(default="default_pass")


class TestSecretsResolution:
    def test_kwargs_secret_resolved_on_construction(self, secrets_registry):
        settings = _SecretsTestSettings(
            settings_parameters=SettingsParameters.create(
                settings_class=_SecretsTestSettings,
                secrets_provider="test",
                PASSWORD="secret:db/password",
            )
        )
        assert settings.PASSWORD == "resolved_db/password"

    def test_config_file_secret_resolved_post_construction(self, secrets_registry):
        settings = _SecretsTestSettings(
            settings_parameters=SettingsParameters.create(
                settings_class=_SecretsTestSettings,
                secrets_provider="test",
                config_files=["tests/config/secrets_test.yaml"],
                env_prefix="SECRETSTEST_",
            )
        )
        assert settings.PASSWORD == "resolved_db/password"
        assert settings.USERNAME == "admin"

    def test_no_provider_leaves_secret_prefix_as_literal(self):
        settings = _SecretsTestSettings(PASSWORD="secret:db/password")
        assert settings.PASSWORD == "secret:db/password"

    def test_cache_hit_runtime_override_resolves_secret(self, secrets_registry):
        from mountainash_settings.settings_cache.settings_functions import _get_settings

        params_base = SettingsParameters.create(
            settings_class=_SecretsTestSettings,
            secrets_provider="test",
            config_files=["tests/config/secrets_test.yaml"],
        )

        # First call — constructs and caches
        settings1 = get_settings(settings_parameters=params_base)
        assert settings1.PASSWORD == "resolved_db/password"

        # Second call — cache hit with runtime override containing a secret ref
        settings2 = get_settings(
            settings_parameters=params_base,
            PASSWORD="secret:other/password",
        )
        assert settings2.PASSWORD == "resolved_other/password"
        # Original cached instance untouched
        assert settings1.PASSWORD == "resolved_db/password"

        # Cleanup: clear the lru_cache entry we just created
        _get_settings.cache_clear()

    def test_nested_frozen_model_secret_resolved_from_yaml(self, secrets_registry):
        from fixtures.auth_stubs import StubPasswordAuth as PasswordAuth

        class _NestedAuthSettings(MountainAshBaseSettings):
            APP_NAME: str = Field(default="default")
            auth: PasswordAuth

        settings = _NestedAuthSettings(
            settings_parameters=SettingsParameters.create(
                settings_class=_NestedAuthSettings,
                secrets_provider="test",
                config_files=["tests/config/nested_secrets_test.yaml"],
                env_prefix="NESTEDSECTEST_",
            )
        )
        assert settings.APP_NAME == "test_app"
        assert settings.auth.username == "admin"
        assert settings.auth.password.get_secret_value() == "resolved_db/production/password"

    def test_nested_model_secret_in_kwargs_resolved(self, secrets_registry):
        from fixtures.auth_stubs import StubPasswordAuth as PasswordAuth

        class _NestedAuthSettings(MountainAshBaseSettings):
            APP_NAME: str = Field(default="default")
            auth: PasswordAuth

        settings = _NestedAuthSettings(
            settings_parameters=SettingsParameters.create(
                settings_class=_NestedAuthSettings,
                secrets_provider="test",
                auth={"kind": "password", "username": "admin", "password": "secret:db/password"},
            )
        )
        assert settings.auth.password.get_secret_value() == "resolved_db/password"
