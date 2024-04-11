from typing import Any, List, Optional, Type, Union

import pytest
from pydantic_settings import SettingsConfigDict
from pydantic import Field
from pytest_check import check
from upath import UPath

from mountainash_settings import SettingsUtils, SettingsManager, MountainAshBaseSettings, SettingsParameters

from mountainash_settings.settings_functions import get_settings_manager, get_settings


@pytest.fixture
def settings_manager() -> SettingsManager:
    settings_manager: SettingsManager = get_settings_manager()
    # settings_manager: SettingsManager = SettingsManager()
    return settings_manager

def test_init_sets_namespace():
    namespace = "test"
    settings = MountainAshBaseSettings(SETTINGS_NAMESPACE=namespace)
    assert settings.SETTINGS_NAMESPACE == namespace


def test_init_sets_kwargs():
    kwargs: dict[str, Any] = {"key1": "value1", "key2": "value2"}
    settings = MountainAshBaseSettings(**kwargs)
    assert settings.SETTINGS_SOURCE_KWARGS == kwargs


def test_init_sets_env_file():
    env_file = "test.env"
    settings = MountainAshBaseSettings(_env_file=env_file)
    assert settings.SETTINGS_SOURCE_ENV_FILES == env_file


def test_init_sets_env_prefix():
    prefix = "PREFIX_"
    settings = MountainAshBaseSettings(_env_prefix=prefix)
    assert settings.SETTINGS_SOURCE_ENV_PREFIX == prefix


def test_init_removes_special_kwargs():
    kwargs: dict[str, Any] = {"SETTINGS_NAMESPACE": "test", "key1": "value1"}
    settings = MountainAshBaseSettings(**kwargs)

    if settings.SETTINGS_SOURCE_KWARGS:
        assert "SETTINGS_NAMESPACE" not in settings.SETTINGS_SOURCE_KWARGS


def test_init_dummy_sets_defaults():
    settings = MountainAshBaseSettings(_dummy=True)
    assert settings.SETTINGS_NAMESPACE == "DUMMY"
    assert settings.SETTINGS_CLASS == MountainAshBaseSettings
    assert settings.SETTINGS_CLASS_NAME == "MountainAshBaseSettings"


## ============================================================
## Test using variables with a prefix in the test config files, and in kwargs!
        
class TestSettings(MountainAshBaseSettings):
    def __init__(
        self,
        # _env_file=None,
        # _env_prefix=None,
        _dummy=False,
        **kwargs
    ) -> None:

        super().__init__(
            # _env_file=_env_file,
            # _env_prefix=_env_prefix,
            _dummy=_dummy,
            **kwargs
        )

    # App Settings
    TEST_VAL_1: str =                    Field(default=None)
    TEST_VAL_2: str =                    Field(default=None)


def get_test_settings(settings_parameters: SettingsParameters,
                     settings_class:     Optional[Type[TestSettings]] = TestSettings, 
                     settings_namespace: Optional[str] = None,
                     config_files: Optional[Union[UPath, str, List[UPath|str]]]  = None,
                     **kwargs
                     ) -> TestSettings:
    
    settings_class = TestSettings
    
    test_settings: MountainAshBaseSettings = get_settings(settings_parameters=settings_parameters, 
                                                          settings_class=settings_class, 
                                                          settings_namespace=settings_namespace, 
                                                          config_files=config_files,
                                                            **kwargs)



    if isinstance(test_settings, TestSettings):
        return test_settings
    else:
        raise ValueError("The settings object retrieved is not of type AppSettings.")


# One File - No prefix
# def test_init_config_valid_init_file(settings_manager: SettingsManager):
#     namespace = "test_init_config_valid_init_file"
#     config_files: List[Any] = ["./tests/config_testing1.env"]
#     kwargs = {}
    
#     settings_parameters = SettingsUtils.prepare_settings_parameters(settings_namespace=namespace, settings_class=TestSettings, config_files=config_files, p_kwargs=kwargs)

#     app_settings: TestSettings =     get_test_settings(settings_parameters=settings_parameters)

#     with check:
#         assert app_settings.TEST_VAL_1 == "ABC"
#         assert app_settings.TEST_VAL_2 == "000001"

# def test_init_config_valid_init_file_2(settings_manager: SettingsManager):
#     namespace = "test_init_config_valid_init_file_2"
#     config_files: List[Any] = ["./tests/config_testing2.env"]
#     kwargs = {}
    
#     settings_parameters = SettingsUtils.prepare_settings_parameters(settings_namespace=namespace, settings_class=TestSettings, config_files=config_files, p_kwargs=kwargs)

#     app_settings: TestSettings =     get_test_settings(settings_parameters=settings_parameters)

#     with check:
#         assert app_settings.TEST_VAL_1 == "ABC-2"
#         assert app_settings.TEST_VAL_2 == "000001-2"

# # One File with prefix
# def test_init_config_valid_init_file_prefix(settings_manager: SettingsManager):
#     namespace = "test_init_config_valid_init_file_prefix"
#     config_files: List[str] = ["./tests/config_testing1.env"]
#     kwargs = {"_env_prefix": "TESTING_PREFIX_"}
    
#     settings_parameters = SettingsUtils.prepare_settings_parameters(settings_namespace=namespace, settings_class=TestSettings, config_files=config_files, p_kwargs=kwargs)

#     app_settings: TestSettings =     get_test_settings(settings_parameters=settings_parameters)

#     with check:
#         assert app_settings.TEST_VAL_1 == "JKL"
#         assert app_settings.TEST_VAL_2 == "000002"

# def test_init_config_valid_init_file_2_prefix(settings_manager: SettingsManager):
#     namespace = "test_init_config_valid_init_file_2_prefix"
#     config_files: List[Any] = ["./tests/config_testing2.env"]
#     kwargs = {"_env_prefix": "TESTING_PREFIX_"}
    
#     settings_parameters = SettingsUtils.prepare_settings_parameters(settings_namespace=namespace, settings_class=TestSettings, config_files=config_files, p_kwargs=kwargs)

#     app_settings: TestSettings =     get_test_settings(settings_parameters=settings_parameters)

#     with check:
#         assert app_settings.TEST_VAL_1 == "JKL-2"
#         assert app_settings.TEST_VAL_2 == "000002-2"

# # Two files

# def test_init_config_valid_init_two_files_prefix(settings_manager: SettingsManager):
#     # Arrange
#     namespace = "test_init_config_valid_init_two_files_prefix"
#     config_files: List[Any] = ["./tests/config_testing1.env", "./tests/config_testing2.env"]
#     kwargs = {"_env_prefix": "TESTING_PREFIX_"}

#     settings_parameters = SettingsUtils.prepare_settings_parameters(settings_namespace=namespace, settings_class=TestSettings, config_files=config_files, p_kwargs=kwargs)

#     app_settings: TestSettings =     get_test_settings(settings_parameters=settings_parameters)

#     with check:
#         assert app_settings.TEST_VAL_1 == "JKL-2"
#         assert app_settings.TEST_VAL_2 == "000002-2"
# def test_init_config_valid_init_two_files_reverse_prefix(settings_manager: SettingsManager):
#     namespace = "test_init_config_valid_init_two_files_reverse_prefix"
#     config_files: List[Any] =  ["./tests/config_testing2.env", "./tests/config_testing1.env"]
#     kwargs = {"_env_prefix": "TESTING_PREFIX_"}

#     settings_parameters = SettingsUtils.prepare_settings_parameters(settings_namespace=namespace, settings_class=TestSettings, config_files=config_files, p_kwargs=kwargs)

#     app_settings: TestSettings =     get_test_settings(settings_parameters=settings_parameters)

#     with check:
#         assert app_settings.TEST_VAL_1 == "JKL"
#         assert app_settings.TEST_VAL_2 == "000002"


def test_init_config_valid_init_two_files_noprefix(settings_manager: SettingsManager):
    # Arrange
    namespace = "test_init_config_valid_init_two_files_noprefix"
    config_files: List[Any] = [ "./tests/config_testing1.env", "./tests/config_testing2.env"]
    kwargs = {}

    settings_parameters = SettingsUtils.prepare_settings_parameters(settings_namespace=namespace, settings_class=TestSettings, config_files=config_files, p_kwargs=kwargs)
    app_settings: TestSettings =     get_test_settings(settings_parameters=settings_parameters)

    #TEST_VAL_2 was 000002 in the file, but over-ridden by the kwarg
    with check:
        assert app_settings.TEST_VAL_1 == "TEST_VAL_1_File_2"
        assert app_settings.TEST_VAL_2 == "TEST_VAL_2_File_2"

def test_init_config_valid_init_files_reverse_noprefix(settings_manager: SettingsManager):
    namespace = "test_init_config_valid_init_files_reverse_noprefix"
    config_files: List[Any] = ["./tests/config_testing2.env", "./tests/config_testing1.env"]
    kwargs = {}

    settings_parameters = SettingsUtils.prepare_settings_parameters(settings_namespace=namespace, settings_class=TestSettings, config_files=config_files, p_kwargs=kwargs)
    app_settings: TestSettings =     get_test_settings(settings_parameters=settings_parameters)

    #TEST_VAL_2 was 000002 in the file, but over-ridden by the kwarg
    with check:
        assert app_settings.TEST_VAL_1 == "TEST_VAL_1_File_2"
        assert app_settings.TEST_VAL_2 == "TEST_VAL_2_File_2"





def test_init_config_valid_init_files_override_and_kwargs_noprefix(settings_manager: SettingsManager):
    # Arrange
    namespace = "test_init_config_valid_init_files_override_and_kwargs_noprefix"
    config_files: List[Any] = ["./tests/config_testing1.env"]
    kwargs = {"TEST_VAL_2": "000003"}

    settings_parameters = SettingsUtils.prepare_settings_parameters(settings_namespace=namespace, settings_class=TestSettings, config_files=config_files, p_kwargs=kwargs)
    app_settings: TestSettings =     get_test_settings(settings_parameters=settings_parameters)

    with check:
        assert app_settings.TEST_VAL_1 == "TEST_VAL_1_File_1"
        assert app_settings.TEST_VAL_2 == "000003"

def test_init_config_valid_init_files_override_and_kwargs_noprefix2(settings_manager: SettingsManager):
    # Arrange
    namespace = "test_init_config_valid_init_files_override_and_kwargs_noprefix2"
    config_files: List[Any] = [ "./tests/config_testing2.env"]
    kwargs = {"TEST_VAL_1": "ABC"}

    settings_parameters = SettingsUtils.prepare_settings_parameters(settings_namespace=namespace, settings_class=TestSettings, config_files=config_files, p_kwargs=kwargs)
    app_settings: TestSettings =     get_test_settings(settings_parameters=settings_parameters)

    #TEST_VAL_2 was 000002 in the file, but over-ridden by the kwarg
    with check:
        assert app_settings.TEST_VAL_1 == "ABC"
        assert app_settings.TEST_VAL_2 == "TEST_VAL_2_File_2"
