
import pytest
from pydantic_settings import BaseSettings
from mountainash_settings.settings import SettingsUtils, SettingsParameters
from mountainash_settings.app_settings import  get_app_settings, AppSettings

from typing import List, Any
from upath import UPath
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

## ============================================================
# Test transferrring Settings Parameters from one config to init another
def test_init_config_settings_parameters_match_originals():

    namespace = "test_init_config_settings_parameters_match_originals"
    config_files: List[Any] = ["./tests/config_testing1.env", "./tests/config_testing2.env"]
    kwargs: dict[str, Any] = {"PORTFOLIO_NAME": "HJK", "ORGANISATION_TLA": "XYZ"}

    settings_parameters_original = SettingsUtils.prepare_settings_parameters(settings_namespace=namespace, settings_class=AppSettings, config_files=config_files, p_kwargs=kwargs)

    config = get_app_settings(app_settings_parameters=settings_parameters_original)
    settings_parameters_derived = SettingsUtils.get_settings_parameters(config)

    #Should have over-ridden values on a copy of the original
    namespace2=f"altered_{namespace}"   

    extracted_config_files = SettingsUtils.extract_config_files_from_settings_parameters(settings_parameters=settings_parameters_derived)
    extracted_kwargs = SettingsUtils.extract_kwargs_from_settings_parameters(settings_parameters=settings_parameters_derived)

    assert extracted_config_files == SettingsUtils.format_config_file_list(config_files=config_files)
    assert extracted_kwargs == SettingsUtils.format_kwargs_dict(p_kwargs=kwargs)

    namespace2=f"altered_{namespace}"   
    config2: AppSettings = get_app_settings(app_settings_parameters=settings_parameters_derived, settings_namespace=namespace2)

    assert config2.RUNTIME == "000001"
    assert config2.PORTFOLIO_NAME == "HJK"
    assert config2.ORGANISATION_TLA == "XYZ"


# def test_init_config_with_files_settings_parameters_altered_namespace():

#     namespace = "test_init_config_with_files_settings_parameters_altered_namespace"
#     config = AppSettingsManager.init_config(settings_parameters=namespace, config_files="./tests/config_testing1.env")

#     #Should have over-ridden values on a copy of the original
#     namespace2=f"altered_{namespace}"
#     settings_parameters = config.get_hashable_parameters()
#     config2: AppSettings = get_app_settings(app_settings_parameters=namespace2, settings_parameters=settings_parameters)
#     assert config2.RUNTIME == '000001'
    

def test_get_config_with_kwargs_settings_parameters():

    namespace = "test_get_config_with_kwargs_settings_parameters"
    settings_parameters = SettingsUtils.prepare_settings_parameters(settings_namespace=namespace, settings_class=AppSettings)
    config: AppSettings = get_app_settings(app_settings_parameters=settings_parameters, BATCH_ID='value1', BATCH_VERSION='value2')

    #Should have over-ridden values on a copy of the original
    settings_parameters_derived: SettingsParameters = SettingsUtils.get_settings_parameters(config)
    config2: AppSettings = get_app_settings(app_settings_parameters=settings_parameters_derived)

    assert config.BATCH_ID == 'value1'
    assert config.BATCH_VERSION == 'value2'

    assert config2.BATCH_ID == 'value1'
    assert config2.BATCH_VERSION == 'value2'

    assert config.SETTINGS_NAMESPACE == config2.SETTINGS_NAMESPACE
    assert config.SETTINGS_SOURCE_KWARGS == config2.SETTINGS_SOURCE_KWARGS

def test_get_config_with_files_settings_parameters():

    namespace = "test_get_config_with_files_settings_parameters"
    config_files: List[Any] = ["./tests/config_testing1.env", "./tests/config_testing2.env"]
    app_settings_parameters = SettingsUtils.prepare_settings_parameters(settings_namespace=namespace, settings_class=AppSettings, config_files=config_files)


    config: AppSettings = get_app_settings(app_settings_parameters=app_settings_parameters)
    settings_parameters_derived: SettingsParameters = SettingsUtils.get_settings_parameters(config)

    config2: AppSettings = get_app_settings(app_settings_parameters=settings_parameters_derived)

    assert config.RUNTIME == '000001'
    assert config.PORTFOLIO_NAME == 'ABC'

    assert config2.RUNTIME == '000001'
    assert config2.PORTFOLIO_NAME == 'ABC'

    assert config.SETTINGS_NAMESPACE == config2.SETTINGS_NAMESPACE
    assert config.SETTINGS_SOURCE_ENV_FILES == config2.SETTINGS_SOURCE_ENV_FILES


def test_get_config_with_settings_parameters_and_kwargs():

    namespace = "test_get_config_with_files_settings_parameters"
    config_files: List[Any] = ["./tests/config_testing1.env", "./tests/config_testing2.env"]

    kwargs: dict[str, Any] = {"PORTFOLIO_NAME": "HJK", "ORGANISATION_TLA": "XYZ"}

    settings_parameters: SettingsParameters = SettingsUtils.prepare_settings_parameters(settings_namespace=namespace, settings_class=AppSettings, config_files=config_files)
    config: AppSettings = get_app_settings(app_settings_parameters=settings_parameters)

    settings_parameters_derived: SettingsParameters = SettingsUtils.get_settings_parameters(objSettings=config)
    config2: AppSettings = get_app_settings(app_settings_parameters=settings_parameters_derived, **kwargs)


    assert config.RUNTIME == '000001'
    assert config.PORTFOLIO_NAME == 'ABC'
    assert config.ORGANISATION_TLA == 'ORG'

    assert config2.RUNTIME == '000001'
    assert config2.PORTFOLIO_NAME == 'HJK'
    assert config2.ORGANISATION_TLA == 'XYZ'

    assert config.SETTINGS_NAMESPACE == config2.SETTINGS_NAMESPACE    
    assert config.SETTINGS_SOURCE_KWARGS != config2.SETTINGS_SOURCE_KWARGS    


def test_get_config_with_settings_parameters_and_kwargs2():

    namespace = "test_get_config_with_settings_parameters_and_kwargs2"
    config_files: List[Any] = ["./tests/config_testing1.env", "./tests/config_testing2.env"]
    kwargs: dict[str, Any] = {"PORTFOLIO_NAME": "HJK", "ORGANISATION_TLA": "XYZ"}

    settings_parameters: SettingsParameters = SettingsUtils.prepare_settings_parameters(settings_namespace=namespace, settings_class=AppSettings, config_files=config_files, p_kwargs=kwargs)

    config: AppSettings = get_app_settings(app_settings_parameters=settings_parameters)
    settings_parameters_derived: SettingsParameters = SettingsUtils.get_settings_parameters(objSettings=config)


    config2: AppSettings = get_app_settings(app_settings_parameters=settings_parameters_derived, **kwargs)

    assert config.RUNTIME == '000001'
    assert config.PORTFOLIO_NAME == 'HJK'
    assert config.ORGANISATION_TLA == 'XYZ'

    assert config2.RUNTIME == '000001'
    assert config2.PORTFOLIO_NAME == 'HJK'
    assert config2.ORGANISATION_TLA == 'XYZ'

    assert config.SETTINGS_NAMESPACE == config2.SETTINGS_NAMESPACE    
    assert config.SETTINGS_SOURCE_KWARGS == config2.SETTINGS_SOURCE_KWARGS    



# def test_get_config_with_settings_parameters_multithreaded():

#     namespace = "test_get_config_with_settings_parameters_multithreaded"
#     config_files: List[str] = ["./tests/config_testing1.env", "./tests/config_testing2.env"]

#     settings_parameters: AppSettingsParameters = SettingsUtils.prepare_settings_parameters(settings_namespace=namespace, config_files=config_files)

#     config: AppSettings = get_app_settings(app_settings_parameters=settings_parameters)
#     settings_parameters_derived: AppSettingsParameters = SettingsUtils.get_settings_parameters(config)

#     iterables = range(4)

#     def fn_get_and_assert_settings(iterable):
#         config2: AppSettings = get_app_settings(app_settings_parameters=settings_parameters_derived)
#         assert config2.RUNTIME == '000001'
#         assert config2.PORTFOLIO_NAME == 'ABC'

#     with ProcessPoolExecutor(max_workers=4) as executor:
#         executor.map(fn_get_and_assert_settings, iterables)
            

# def fn_get_and_assert_settings(iterable):

#     namespace = "test_get_config_with_settings_parameters_multiprocess"
#     settings_parameters: AppSettingsParameters = SettingsUtils.prepare_settings_parameters(settings_namespace=namespace)

#     config2: AppSettings = get_app_settings(app_settings_parameters=settings_parameters)
#     message = f"Thread:{iterable} - RUNTIME: {config2.RUNTIME}, PORTFOLIO_NAME: {config2.PORTFOLIO_NAME}"

#     return message

# def test_get_config_with_settings_parameters_multiprocess():

#     namespace = "test_get_config_with_settings_parameters_multiprocess"
#     config_files: List[str] = ["./tests/config_testing1.env", "./tests/config_testing2.env"]
#     kwargs = {"PORTFOLIO_NAME": "HJK", "ORGANISATION_TLA": "XYZ"}    

#     settings_parameters: AppSettingsParameters = SettingsUtils.prepare_settings_parameters(settings_namespace=namespace, config_files=config_files, p_kwargs=kwargs)

#     config: AppSettings = get_app_settings(app_settings_parameters=settings_parameters)

#     iterables = range(8) 

#         # assert config2.RUNTIME == '000001'
#         # assert config2.PORTFOLIO_NAME == 'ABC'

#         # raise Exception("ProcessPoolExecutor Complete")

#     with ProcessPoolExecutor(max_workers=4) as executor:
#         messages = list(executor.map(fn_get_and_assert_settings, iterables))

#     print(messages)

#     raise Exception("Test Complete")

# def fn_get_and_assert_settings2(iterable):

#     namespace = "test_get_config_with_settings_parameters_multithread"

#     config2: AppSettings = get_app_settings(app_settings_parameters=namespace)
#     message = f"Thread:{iterable} - RUNTIME: {config2.RUNTIME}, PORTFOLIO_NAME: {config2.PORTFOLIO_NAME}"

#     return message

# def test_get_config_with_settings_parameters_multithread():

#     namespace = "test_get_config_with_settings_parameters_multithread"
#     config_files: List[str] = ["./tests/config_testing1.env", "./tests/config_testing2.env"]
#     kwargs = {"PORTFOLIO_NAME": "HJK", "ORGANISATION_TLA": "XYZ"}    

#     config = get_app_settings(app_settings_parameters=namespace, config_files=config_files, **kwargs)
#     settings_parameters = config.get_hashable_parameters()

#     iterables = range(9,16)

#         # assert config2.RUNTIME == '000001'
#         # assert config2.PORTFOLIO_NAME == 'ABC'

#         # raise Exception("ProcessPoolExecutor Complete")

#     with ThreadPoolExecutor(max_workers=4) as executor:
#         messages = list(executor.map(fn_get_and_assert_settings2, iterables))

#     print(messages)

#     raise Exception("Test Complete")


