from mountainash_settings import SettingsUtils, SettingsManager, MountainAshBaseSettings
from typing import Any, List
import pytest



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
    assert "SETTINGS_NAMESPACE" not in settings.SETTINGS_SOURCE_KWARGS


def test_init_dummy_sets_defaults():
    settings = MountainAshBaseSettings(_dummy=True)
    assert settings.SETTINGS_NAMESPACE == "DUMMY"
    assert settings.SETTINGS_CLASS == MountainAshBaseSettings
    assert settings.SETTINGS_CLASS_NAME == "MountainAshBaseSettings"
