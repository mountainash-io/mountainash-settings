import pytest
from mountainash_settings.settings import  SettingsUtils
from mountainash_settings.app_settings import  get_app_settings, AppSettings

from datetime import datetime
from typing import List, Any
from upath import UPath

# def test_get_app_settings_default_namespace():

#     settings_parameters = SettingsUtils.prepare_settings_parameters(settings_namespace=None, settings_class=AppSettings)

#     app_settings = get_app_settings(app_settings_parameters=settings_parameters)

#     assert app_settings is not None

def test_get_app_settings_custom_namespace():
    # Arrange
    namespace = f"totally_new_namespace_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    app_settings_parameters = SettingsUtils.prepare_settings_parameters(settings_namespace=namespace, settings_class=AppSettings)

    app_settings = get_app_settings(app_settings_parameters=app_settings_parameters)

    assert app_settings is not None

def test_get_app_settings_custom_config_files():
    # Arrange
    namespace = "test_get_app_settings_custom_config_files"

    config_files: List[str|UPath] = ["./tests/config_testing1.env", "./tests/config_testing2.env"]

    app_settings_parameters = SettingsUtils.prepare_settings_parameters(settings_namespace=namespace, settings_class=AppSettings, config_files=config_files)

    # Act
    app_settings = get_app_settings(app_settings_parameters=app_settings_parameters)

    # Assert
    assert app_settings is not None
    # Add more assertions based on the expected behavior of get_app_settings()

def test_get_app_settings_custom_kwargs():
    # Arrange
    namespace = "test_get_app_settings_custom_kwargs"
    kwargs: dict[str, Any] = {"ORGANISATION_TLA": "XYZ", "PORTFOLIO_NAME": "ABC"}

    app_settings_parameters = SettingsUtils.prepare_settings_parameters(settings_namespace=namespace, settings_class=AppSettings)


    # Act
    app_settings = get_app_settings(app_settings_parameters=app_settings_parameters, **kwargs)

    # Assert
    assert app_settings is not None
    # Add more assertions based on the expected behavior of get_app_settings()

def test_get_app_settings_custom_namespace_config_files_kwargs():
    # Arrange
    namespace = "test_get_app_settings_custom_namespace_config_files_kwargs"
    config_files: List[str|UPath] = ["./tests/config_testing1.env", "./tests/config_testing2.env"]
    kwargs: dict[str, Any] = {"ORGANISATION_TLA": "XYZ", "PORTFOLIO_NAME": "ABCDEFG!"}

    app_settings_parameters = SettingsUtils.prepare_settings_parameters(settings_namespace=namespace, settings_class=AppSettings, config_files=config_files, **kwargs)

    # Act
    app_settings = get_app_settings(app_settings_parameters=app_settings_parameters)

    # Assert
    assert app_settings is not None
    # Add more assertions based on the expected behavior of get_app_settings()