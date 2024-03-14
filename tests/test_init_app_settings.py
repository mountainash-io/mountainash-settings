import pytest
from pydantic_settings import BaseSettings
from mountainash_settings.settings import SettingsManager, SettingsUtils,  SettingsParameters
from mountainash_settings.app_settings import  AppSettings
from typing import List
from upath import UPath


# def test_init_config_no_namepsce(_is_default):

#     namespace = None

#     # Test the init_config method
#     default_init = AppSettingsManager.init_config(app_settings_parameters=namespace)
#     default_get: AppSettings = AppSettingsManager.get_config(app_settings_parameters=SettingsUtils.default_namespace)

#     assert default_init == default_get

def test_init_config():

    settings_namespace = "test_init_config"

    # Test the init_config method
    SettingsManager.init_config(settings_namespace=settings_namespace, settings_class=AppSettings)
    app_settings: AppSettings = SettingsManager.get_config(settings_namespace=settings_namespace, settings_class=AppSettings)

    assert isinstance(app_settings, AppSettings)

def test_init_config_with_one_file():

    namespace = "test_init_config_with_one_file"
    setting_params: SettingsParameters = SettingsUtils.prepare_settings_parameters(settings_namespace=namespace, settings_class=AppSettings)

    # Test the init_config method
    SettingsManager.init_config(settings_namespace=namespace, settings_class=AppSettings, config_files="./tests/config_testing1.env")
    config: AppSettings = SettingsManager.get_config(settings_namespace=namespace, settings_class=AppSettings)

    assert isinstance(config, AppSettings)
    assert config.RUNTIME == '000001'


def test_init_config_with_two_files():

    namespace = "test_init_config_with_two_files"
    config_files: List[str] = ["./tests/config_testing1.env", "./tests/config_testing2.env"]

    # Test the init_config method
    SettingsManager.init_config(settings_namespace=namespace, settings_class=AppSettings, config_files=config_files)
    config: AppSettings = SettingsManager.get_config(settings_namespace=namespace, settings_class=AppSettings)

    assert isinstance(config, AppSettings)
    assert config.RUNTIME == '000001'
    assert config.PORTFOLIO_NAME == "ABC"




def test_init_config_with_multiple_upath_and_kwarg():
    # Arrange
    namespace = "test_init_config_with_multiple_upath_and_kwarg"
    config_files: List[UPath] = [UPath("./tests/config_testing1.env"), UPath("./tests/config_testing2.env")]
    kwargs = {"ORGANISATION_TLA": "XYZ"}

    # Act
    app_settings: AppSettings = SettingsManager.init_config(settings_namespace=namespace, settings_class=AppSettings, config_files=config_files, **kwargs)

    # Assert
    assert namespace in SettingsManager.app_settings_objects
    assert app_settings.RUNTIME == "000001"
    assert app_settings.PORTFOLIO_NAME == "ABC"
    assert app_settings.ORGANISATION_TLA == "XYZ"


def test_init_second_config_with_one_file_changed():

    namespace = "test_init_config_with_one_file_changed"

    # Test the init_config method
    SettingsManager.init_config(settings_namespace=namespace, settings_class=AppSettings, config_files="./tests/config_testing1.env")

    with pytest.raises(ValueError):
        SettingsManager.init_config(settings_namespace=namespace, settings_class=AppSettings, config_files="./tests/config_testing2.env")


def test_init_config_with_kwargs():

    namespace = "test_init_config_with_kwargs"

    SettingsManager.init_config(settings_namespace=namespace, settings_class=AppSettings, BATCH_ID='value1', BATCH_VERSION='value2')
    config: AppSettings = SettingsManager.get_config(settings_namespace=namespace, settings_class=AppSettings)

    assert config.BATCH_ID == 'value1'
    assert config.BATCH_VERSION == 'value2'


def test_init_config_with_kwargs_override():

    namespace = "test_init_config_with_kwargs_override"

    SettingsManager.init_config(settings_namespace=namespace, settings_class=AppSettings, BATCH_ID='value1', BATCH_VERSION='value2')

    #Original Values
    config: AppSettings = SettingsManager.get_config(settings_namespace=namespace, settings_class=AppSettings)
    assert config.BATCH_ID == 'value1'
    assert config.BATCH_VERSION == 'value2'

    #Should have over-ridden values on a copy of the original
    config2: AppSettings = SettingsManager.get_config(settings_namespace=namespace, settings_class=AppSettings, BATCH_ID='ABC', BATCH_VERSION='123')
    assert config2.BATCH_ID == 'ABC'
    assert config2.BATCH_VERSION == '123'

    #Should still have the original values
    config3: AppSettings = SettingsManager.get_config(settings_namespace=namespace, settings_class=AppSettings)
    assert config3.BATCH_ID == 'value1'
    assert config3.BATCH_VERSION == 'value2'


def test_init_config_with_kwargs_and_files():

    namespace = "test_init_config_with_kwargs_and_files"
    config_files: List[str] = ["./tests/config_testing1.env", "./tests/config_testing2.env"]
    kwargs = {"ORGANISATION_TLA": "XYZ"}

    app_settings = SettingsManager.init_config(settings_namespace=namespace, settings_class=AppSettings, config_files=config_files, **kwargs)

    assert app_settings.RUNTIME == "000001"
    assert app_settings.PORTFOLIO_NAME == "ABC"
    assert app_settings.ORGANISATION_TLA == "XYZ"



def test_init_config_with_kwargs_and_files_override():

    namespace = "test_init_config_with_kwargs_and_files_override"

    config_files: List[str] = ["./tests/config_testing1.env", "./tests/config_testing2.env"]
    kwargs = {"PORTFOLIO_NAME": "HJK", "ORGANISATION_TLA": "XYZ"}

    app_settings = SettingsManager.init_config(settings_namespace=namespace, settings_class=AppSettings, config_files=config_files, **kwargs)

    assert app_settings.RUNTIME == "000001"
    assert app_settings.PORTFOLIO_NAME == "HJK"
    assert app_settings.ORGANISATION_TLA == "XYZ"

    config2 = SettingsManager.get_config(settings_namespace=namespace)


def test_init_config_empty_namespace():

    namespace = ""

    with pytest.raises(ValueError):
        SettingsManager.init_config(settings_namespace=namespace, settings_class=AppSettings)


def test_init_config_invalid_config_file():
    namespace = "test_init_config_invalid_config_file"
    config_files: str = "non_existing_file.yaml"

    with pytest.raises(FileNotFoundError):
        SettingsManager.init_config(settings_namespace=namespace, settings_class=AppSettings, config_files=config_files)

def test_init_config_invalid_kwargs_attribute():

    namespace = "test_init_config_invalid_kwargs_attribute"
    kwargs = {"invalid_key": "value"}

    with pytest.raises(ValueError):
        config: AppSettings =     SettingsManager.init_config(settings_namespace=namespace, settings_class=AppSettings, **kwargs)

## ============================================================
## Test using variables with a prefix in the test config files, and in kwargs!
        
def test_init_config_valid_init_files_prefix():
    # Arrange
    namespace = "test_init_config_valid_init_files_prefix"
    config_files: List[str] = ["./tests/config_testing1.env", "./tests/config_testing2.env"]
    kwargs = {"_env_prefix": "TESTING_PREFIX_"}

    app_settings: AppSettings =     SettingsManager.init_config(settings_namespace=namespace, settings_class=AppSettings, config_files=config_files, **kwargs)

    assert app_settings.RUNTIME == "000002"
    assert app_settings.PORTFOLIO_NAME == "JKL"

def test_init_config_valid_init_files_prefix_and_kwargs_noprefix():
    # Arrange
    namespace = "test_init_config_valid_init_files_prefix_and_kwargs_noprefix"
    config_files: List[str] = ["./tests/config_testing1.env", "./tests/config_testing2.env"]
    kwargs = {"_env_prefix": "TESTING_PREFIX_", "RUNTIME": "000003"}

    app_settings: AppSettings =     SettingsManager.init_config(settings_namespace=namespace, settings_class=AppSettings, config_files=config_files, **kwargs)

    #This was 000002 in the file, but over-ridden by the kwarg
    assert app_settings.RUNTIME == "000003"
    assert app_settings.PORTFOLIO_NAME == "JKL"

def test_init_config_valid_init_files_prefix_and_kwargs_prefix():
    # Arrange
    namespace = "test_init_config_valid_init_files_prefix_and_kwargs_prefix"
    config_files: List[str] = ["./tests/config_testing1.env", "./tests/config_testing2.env"]
    kwargs = {"_env_prefix": "TESTING_PREFIX_", "TESTING_PREFIX_RUNTIME": "000003"}

    with pytest.raises(ValueError):
        app_settings: AppSettings =     SettingsManager.init_config(settings_namespace=namespace, settings_class=AppSettings, config_files=config_files, **kwargs)


