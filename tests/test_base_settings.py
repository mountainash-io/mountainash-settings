from typing import Any, List, Optional, Type, Union

import pytest
# from pydantic_settings import SettingsConfigDict, BaseSettings
from pydantic import Field
from pytest_check import check
from upath import UPath

from mountainash_settings import SettingsManager, MountainAshBaseSettings, SettingsParameters

from mountainash_settings import get_settings_manager, get_settings


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
                     settings_namespace: Optional[str] = None,
                     config_files: Optional[Union[UPath, str, List[UPath|str]]]  = None,
                     **kwargs
                     ) -> TestSettings:


    test_settings: TestSettings = TestSettings.get_settings(settings_parameters=settings_parameters,
                                                          settings_class=settings_class,
                                                          settings_namespace=settings_namespace,
                                                          config_files=config_files,
                                                          **kwargs)
    if isinstance(test_settings, TestSettings):
        return test_settings
    else:
        raise ValueError("The settings object retrieved is not of type TestSettings.")


################
# TESTS #

def test_init_sets_namespace():
    namespace = "test"
    sp = SettingsParameters.create(settings_class=TestSettings, namespace = namespace)

    settings = TestSettings(settings_parameters=sp)
    assert settings.SETTINGS_NAMESPACE == namespace


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


# def test_init_removes_special_kwargs():
#     kwargs: dict[str, Any] = {"SETTINGS_NAMESPACE": "test", "TEST_VAL_1": "value1"}
#     settings = TestSettings(**kwargs)

#     if settings.SETTINGS_SOURCE_KWARGS:
#         assert "SETTINGS_NAMESPACE" not in settings.SETTINGS_SOURCE_KWARGS



## ============================================================
## Test using variables with a prefix in the test config files, and in kwargs!




def test_init_no_file(settings_manager: SettingsManager):
    namespace = "test_init_no_file"
    config_files: List[Any] = []#"./tests/config_testing1.env"]
    kwargs = {}

    settings_parameters = SettingsParameters.create( settings_class=TestSettings,namespace=namespace, config_files=config_files, kwargs=kwargs)

    app_settings: TestSettings =     get_test_settings(settings_parameters=settings_parameters)

    with check:
        assert app_settings.TEST_VAL_1 is None
        assert app_settings.TEST_VAL_2 is None

def test_init_no_file_kwarg(settings_manager: SettingsManager):
    namespace = "test_init_no_file_kwarg"
    config_files: List[Any] = []#"./tests/config_testing1.env"]
    kwargs = {"TEST_VAL_1": "ABC", "TEST_VAL_2": "XYZ"}

    settings_parameters = SettingsParameters.create(settings_class=TestSettings, namespace=namespace, config_files=config_files, kwargs=kwargs)

    app_settings: TestSettings =     get_test_settings(settings_parameters=settings_parameters)

    with check:
        #Getting None here!
        assert app_settings.TEST_VAL_1 == "ABC"
        assert app_settings.TEST_VAL_2 == "XYZ"


def test_init_file(settings_manager: SettingsManager):
    namespace = "test_init_file"
    config_files: List[Any] = ["./tests/config_testing1.env"]
    kwargs = {}

    settings_parameters = SettingsParameters.create(settings_class=TestSettings, namespace=namespace, config_files=config_files, kwargs=kwargs)

    app_settings: TestSettings =     get_test_settings(settings_parameters=settings_parameters)

    with check:
        assert app_settings.TEST_VAL_1 == "TEST_VAL_1_File_1"
        assert app_settings.TEST_VAL_2 == "TEST_VAL_2_File_1"


def test_init_file_and_kwarg(settings_manager: SettingsManager):
    namespace = "test_init_file_and_kwarg"
    config_files: List[Any] = ["./tests/config_testing1.env"]
    kwargs = {"TEST_VAL_1": "ABC"}

    settings_parameters = SettingsParameters.create(settings_class=TestSettings, namespace=namespace, config_files=config_files, kwargs=kwargs)

    app_settings: TestSettings =     get_test_settings(settings_parameters=settings_parameters)

    with check:
        #kwargs not working here
        assert app_settings.TEST_VAL_1 == "ABC"
        assert app_settings.TEST_VAL_2 == "TEST_VAL_2_File_1"

def test_init_file_and_kwarg2(settings_manager: SettingsManager):
    namespace = "test_init_file_and_kwarg2"
    config_files: List[Any] = ["./tests/config_testing1.env"]
    kwargs = {"TEST_VAL_2": "XYZ"}

    settings_parameters = SettingsParameters.create(settings_class=TestSettings, namespace=namespace, config_files=config_files, kwargs=kwargs)

    app_settings: TestSettings =     get_test_settings(settings_parameters=settings_parameters)

    with check:
        assert app_settings.TEST_VAL_1 == "TEST_VAL_1_File_1"
        #kwargs not working here
        assert app_settings.TEST_VAL_2 == "XYZ"



def test_init_file_prefix1(settings_manager: SettingsManager):
    namespace = "test_init_file_prefix1"
    config_files: List[Any] = ["./tests/config_testing1.env"]
    kwargs = {}

    settings_parameters = SettingsParameters.create(settings_class=TestSettings,
                                                    namespace=namespace,
                                                    config_files=config_files,
                                                    env_prefix="PREFIX_",
                                                    kwargs=kwargs)

    app_settings: TestSettings =     get_test_settings(settings_parameters=settings_parameters)

    with check:
        assert app_settings.TEST_VAL_1 == "TEST_VAL_1_File_1"
        assert app_settings.TEST_VAL_2 == "TEST_VAL_2_File_1"

def test_init_file_prefix2(settings_manager: SettingsManager):

    namespace = "test_init_file_prefix2"
    config_files: List[Any] = ["./tests/config_testing_prefix1.env"]
    kwargs = {}

    settings_parameters = SettingsParameters.create(settings_class=TestSettings,
                                                    namespace=namespace,
                                                    config_files=config_files,
                                                    env_prefix="PREFIX_",
                                                    kwargs=kwargs)

    app_settings: TestSettings =     get_test_settings(settings_parameters=settings_parameters)

    with check:
        assert app_settings.TEST_VAL_1 == "TEST_VAL_1_File_Prefix1"
        assert app_settings.TEST_VAL_2 == "TEST_VAL_2_File_Prefix1"

def test_init_file_prefix3(settings_manager: SettingsManager):
    namespace = "test_init_file_prefix3r"
    config_files: List[Any] = ["./tests/config_testing_prefix1.env"]
    kwargs = {}

    settings_parameters = SettingsParameters.create(settings_class=TestSettings, namespace=namespace, config_files=config_files, kwargs=kwargs)

    app_settings: TestSettings =     get_test_settings(settings_parameters=settings_parameters)

    with check:
        assert app_settings.TEST_VAL_1 == None
        assert app_settings.TEST_VAL_2 == None



# One File - No prefix
# def test_init_config_valid_init_file(settings_manager: SettingsManager):
#     namespace = "test_init_config_valid_init_file"
#     config_files: List[Any] = ["./tests/config_testing1.env"]
#     kwargs = {}

#     settings_parameters = SettingsParameters.create(namespace=namespace, settings_class=TestSettings, config_files=config_files, kwargs=kwargs)

#     app_settings: TestSettings =     get_test_settings(settings_parameters=settings_parameters)

#     with check:
#         assert app_settings.TEST_VAL_1 == "ABC"
#         assert app_settings.TEST_VAL_2 == "000001"

# def test_init_config_valid_init_file_2(settings_manager: SettingsManager):
#     namespace = "test_init_config_valid_init_file_2"
#     config_files: List[Any] = ["./tests/config_testing2.env"]
#     kwargs = {}

#     settings_parameters = SettingsParameters.create(namespace=namespace, settings_class=TestSettings, config_files=config_files, kwargs=kwargs)

#     app_settings: TestSettings =     get_test_settings(settings_parameters=settings_parameters)

#     with check:
#         assert app_settings.TEST_VAL_1 == "ABC-2"
#         assert app_settings.TEST_VAL_2 == "000001-2"

# # One File with prefix
# def test_init_config_valid_init_file_prefix(settings_manager: SettingsManager):
#     namespace = "test_init_config_valid_init_file_prefix"
#     config_files: List[str] = ["./tests/config_testing1.env"]
#     kwargs = {"_env_prefix": "TESTING_PREFIX_"}

#     settings_parameters = SettingsParameters.create(namespace=namespace, settings_class=TestSettings, config_files=config_files, kwargs=kwargs)

#     app_settings: TestSettings =     get_test_settings(settings_parameters=settings_parameters)

#     with check:
#         assert app_settings.TEST_VAL_1 == "JKL"
#         assert app_settings.TEST_VAL_2 == "000002"

# def test_init_config_valid_init_file_2_prefix(settings_manager: SettingsManager):
#     namespace = "test_init_config_valid_init_file_2_prefix"
#     config_files: List[Any] = ["./tests/config_testing2.env"]
#     kwargs = {"_env_prefix": "TESTING_PREFIX_"}

#     settings_parameters = SettingsParameters.create(namespace=namespace, settings_class=TestSettings, config_files=config_files, kwargs=kwargs)

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

#     settings_parameters = SettingsParameters.create(namespace=namespace, settings_class=TestSettings, config_files=config_files, kwargs=kwargs)

#     app_settings: TestSettings =     get_test_settings(settings_parameters=settings_parameters)

#     with check:
#         assert app_settings.TEST_VAL_1 == "JKL-2"
#         assert app_settings.TEST_VAL_2 == "000002-2"
# def test_init_config_valid_init_two_files_reverse_prefix(settings_manager: SettingsManager):
#     namespace = "test_init_config_valid_init_two_files_reverse_prefix"
#     config_files: List[Any] =  ["./tests/config_testing2.env", "./tests/config_testing1.env"]
#     kwargs = {"_env_prefix": "TESTING_PREFIX_"}

#     settings_parameters = SettingsParameters.create(namespace=namespace, settings_class=TestSettings, config_files=config_files, kwargs=kwargs)

#     app_settings: TestSettings =     get_test_settings(settings_parameters=settings_parameters)

#     with check:
#         assert app_settings.TEST_VAL_1 == "JKL"
#         assert app_settings.TEST_VAL_2 == "000002"


def test_init_config_valid_init_two_files_noprefix(settings_manager: SettingsManager):
    # Arrange
    namespace = "test_init_config_valid_init_two_files_noprefix"
    config_files: List[Any] = [ "./tests/config_testing1.env", "./tests/config_testing2.env"]
    kwargs = {}

    settings_parameters = SettingsParameters.create(settings_class=TestSettings, namespace=namespace, config_files=config_files, kwargs=kwargs)
    app_settings: TestSettings =     get_test_settings(settings_parameters=settings_parameters)

    #TEST_VAL_2 was 000002 in the file, but over-ridden by the kwarg
    with check:
        assert app_settings.TEST_VAL_1 == "TEST_VAL_1_File_2"
        assert app_settings.TEST_VAL_2 == "TEST_VAL_2_File_2"

def test_init_config_valid_init_files_reverse_noprefix(settings_manager: SettingsManager):
    namespace = "test_init_config_valid_init_files_reverse_noprefix"
    config_files: List[Any] = ["./tests/config_testing2.env", "./tests/config_testing1.env"]
    kwargs = {}

    settings_parameters = SettingsParameters.create(settings_class=TestSettings, namespace=namespace, config_files=config_files, kwargs=kwargs)
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

    settings_parameters = SettingsParameters.create(settings_class=TestSettings, namespace=namespace, config_files=config_files, kwargs=kwargs)
    app_settings: TestSettings =     get_test_settings(settings_parameters=settings_parameters)

    with check:
        assert app_settings.TEST_VAL_1 == "TEST_VAL_1_File_1"
        #kwargs not working here
        assert app_settings.TEST_VAL_2 == "000003"

def test_init_config_valid_init_files_override_and_kwargs_noprefix2(settings_manager: SettingsManager):
    # Arrange
    namespace = "test_init_config_valid_init_files_override_and_kwargs_noprefix2"
    config_files: List[Any] = [ "./tests/config_testing2.env"]
    kwargs = {"TEST_VAL_1": "ABC"}

    settings_parameters = SettingsParameters.create(settings_class=TestSettings, namespace=namespace, config_files=config_files, kwargs=kwargs)
    app_settings: TestSettings =     get_test_settings(settings_parameters=settings_parameters)

    #TEST_VAL_2 was 000002 in the file, but over-ridden by the kwarg
    with check:
        #kwargs not working here
        assert app_settings.TEST_VAL_1 == "ABC"
        assert app_settings.TEST_VAL_2 == "TEST_VAL_2_File_2"
