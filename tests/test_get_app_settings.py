import pytest
from pydantic_settings import BaseSettings
from mountainash_settings.settings import SettingsManager,  SettingsUtils,  SettingsParameters, MountainAshBaseSettings
from mountainash_settings.app_settings import  get_app_settings, AppSettings

from datetime import datetime
from typing import List, Any

# class TestAppSettingsManager:
#
#     @classmethod
#     def setup_class(cls):
#         # Set up any initial configurations needed for the tests
#         pass

def test_set_default_config():
    namespace = SettingsUtils.default_namespace

    app_settings: MountainAshBaseSettings = SettingsManager.get_config(settings_namespace=namespace, settings_class=AppSettings)
    assert isinstance(app_settings, AppSettings)

def test_get_config_no_namespace():

    with pytest.raises(ValueError):
        app_settings: MountainAshBaseSettings = SettingsManager.get_config(settings_namespace=None, settings_class=AppSettings)
  
def test_get_config_uninitialised():

    namespace = "test_get_config_uninitialised"
    app_settings: MountainAshBaseSettings = SettingsManager.get_config(settings_namespace=namespace, settings_class=AppSettings)
    assert isinstance(app_settings, AppSettings)


def test_get_app_settings_no_namespace():

    namespace = None

    with pytest.raises(ValueError):
        setting_params: SettingsParameters = SettingsUtils.prepare_settings_parameters(settings_namespace=namespace, settings_class=AppSettings)
        app_settings: AppSettings = get_app_settings(app_settings_parameters=setting_params)
        # assert isinstance(app_settings, AppSettings)
  
def test_get_app_settings_no_namespace_is_default():

    namespace = None

    # Test the init_config method
    with pytest.raises(ValueError):
        setting_params: SettingsParameters = SettingsUtils.prepare_settings_parameters(settings_namespace=namespace, settings_class=AppSettings)

        test = get_app_settings(app_settings_parameters=setting_params)
        default = get_app_settings(app_settings_parameters=setting_params, settings_namespace=SettingsUtils.default_namespace)

    # assert test == default

def test_get_app_settings_default_namespace():

    namespace = SettingsUtils.default_namespace
    setting_params: SettingsParameters = SettingsUtils.prepare_settings_parameters(settings_namespace=namespace, settings_class=AppSettings)

    # Test the init_config method
    test = get_app_settings(app_settings_parameters=setting_params)
    default = get_app_settings(app_settings_parameters=setting_params, settings_namespace=SettingsUtils.default_namespace)

    assert test == default

def test_get_app_settings_not_default():

    namespace = SettingsUtils.default_namespace
    setting_params: SettingsParameters = SettingsUtils.prepare_settings_parameters(settings_namespace=namespace, settings_class=AppSettings)

    # Test the init_config method
    test = get_app_settings(app_settings_parameters=setting_params)
    not_default = get_app_settings(app_settings_parameters=setting_params, settings_namespace="test_get_app_settings_default_namespace")

    assert test != not_default

def test_get_app_settings_not_default2():

    namespace = "test_get_app_settings_default_namespace2"
    setting_params: SettingsParameters = SettingsUtils.prepare_settings_parameters(settings_namespace=namespace, settings_class=AppSettings)

    # Test the init_config method
    test = get_app_settings(app_settings_parameters=setting_params)
    default = get_app_settings(app_settings_parameters=setting_params, settings_namespace=SettingsUtils.default_namespace)

    assert test != default





def test_get_app_settings_custom_namespace():

    namespace = f"totally_new_namespace_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    setting_params: SettingsParameters = SettingsUtils.prepare_settings_parameters(settings_namespace=namespace, settings_class=AppSettings)

    app_settings: AppSettings = get_app_settings(app_settings_parameters=setting_params)
    assert app_settings is not None

def test_get_app_settings_custom_config_files():
    
    namespace = "test_get_app_settings_custom_config_files"
    config_files: List[Any] = ["./tests/config_testing1.env", "./tests/config_testing2.env"]
    setting_params: SettingsParameters = SettingsUtils.prepare_settings_parameters(settings_namespace=namespace, settings_class=AppSettings, config_files=config_files)

    app_settings: AppSettings = get_app_settings(app_settings_parameters=setting_params)

    assert app_settings is not None

def test_get_app_settings_kwargs():

    namespace = "test_get_app_settings_kwargs"
    kwargs = {"ORGANISATION_TLA": "XYZ", "PORTFOLIO_NAME": "ABC"}
    setting_params: SettingsParameters = SettingsUtils.prepare_settings_parameters(settings_namespace=namespace, settings_class=AppSettings, p_kwargs=kwargs)

    app_settings: AppSettings = get_app_settings(app_settings_parameters=setting_params)

    assert app_settings is not None

def test_get_app_settings_custom_kwargs():

    namespace = "test_get_app_settings_custom_kwargs"
    kwargs: dict[str, Any] = {"ORGANISATION_TLA": "XYZ", "PORTFOLIO_NAME": "ABC"}
    setting_params: SettingsParameters = SettingsUtils.prepare_settings_parameters(settings_namespace=namespace, settings_class=AppSettings)

    app_settings: AppSettings = get_app_settings(app_settings_parameters=setting_params, **kwargs)

    assert app_settings is not None


def test_get_app_settings_custom_namespace_config_files_kwargs():
    namespace = "test_get_app_settings_custom_namespace_config_files_kwargs"
    config_files: List[Any] = ["./tests/config_testing1.env", "./tests/config_testing2.env"]
    kwargs: dict[str, Any] = {"ORGANISATION_TLA": "XYZ", "PORTFOLIO_NAME": "ABCDEFG!"}

    setting_params: SettingsParameters = SettingsUtils.prepare_settings_parameters(settings_namespace=namespace, settings_class=AppSettings,  config_files=config_files, p_kwargs=kwargs)

    app_settings = get_app_settings(app_settings_parameters=setting_params, config_files=config_files, **kwargs)

    assert app_settings is not None

def test_get_app_settings_custom_namespace_config_files_kwargs_modified_params():
    namespace = "test_get_app_settings_custom_namespace_config_files_kwargs_mod"

    config_files: List[Any] = ["./tests/config_testing1.env"]
    kwargs: dict[str, Any] = {"ORGANISATION_TLA": "XYZ"}

    config_files_mod: List[Any] = ["./tests/config_testing2.env"]
    kwargs_mod: dict[str, Any] = {"ORGANISATION_TLA": "XYZ", "PORTFOLIO_NAME": "ABCDEFG!"}

    setting_params: SettingsParameters = SettingsUtils.prepare_settings_parameters(settings_namespace=namespace, settings_class=AppSettings,  config_files=config_files, p_kwargs=kwargs)

    app_settings = get_app_settings(app_settings_parameters=setting_params, config_files=config_files_mod, **kwargs_mod)

    assert app_settings is not None


# def test_validate_protected_attributes():

#     namespace = "test_validate_protected_attributes"
#     AppSettingsManager.init_config(app_settings_parameters=namespace, BATCH_ID='valueX', BATCH_VERSION='valueY')

#     with pytest.raises(ValueError):
#         AppSettingsManager.validate_protected_attributes(app_settings_parameters=namespace)

        
