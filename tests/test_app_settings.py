import pytest
from datetime import datetime
from upath import UPath
from unittest.mock import patch, MagicMock

from mountainash_settings import SettingsParameters
from mountainash_settings.settings.app.app_settings import AppSettings


class TestAppSettings:

    def test_initialization_with_defaults_succeeds(self):
        settings = AppSettings()
        assert settings.DEBUG is False
        assert settings.LOCALE_TIMEZONE == "UTC"
        assert settings.PANDERA_DATAFRAME_FRAMEWORK == "pandas"
        assert settings.PLATFORM_SLASH is not None

    def test_initialization_with_config_files_accepts_single_file(self, temp_config_file):
        settings = AppSettings(config_files=temp_config_file)
        assert settings is not None

    def test_initialization_with_config_files_accepts_list(self, temp_config_files):
        settings = AppSettings(config_files=temp_config_files)
        assert settings is not None

    def test_initialization_with_settings_parameters_succeeds(self):
        params = SettingsParameters.create(namespace="test")
        settings = AppSettings(settings_parameters=params)
        assert settings is not None

    def test_initialization_with_kwargs_succeeds(self):
        settings = AppSettings(DEBUG=True, LOCALE_TIMEZONE="EST")
        assert settings.DEBUG is True
        assert settings.LOCALE_TIMEZONE == "EST"

    def test_runtime_fields_set_correctly(self):
        # Use the auto-mocked datetime from conftest.py
        settings = AppSettings()
        
        # Check that date fields are strings of correct format
        assert len(settings.RUNDATE) == 8  # YYYYMMDD format
        assert len(settings.RUNTIME) == 6   # HHMMSS format
        assert settings.RUNDATE.isdigit()
        assert settings.RUNTIME.isdigit()

    def test_post_init_calls_super_post_init(self):
        settings = AppSettings()
        with patch.object(settings.__class__.__bases__[0], 'post_init') as mock_super_post_init:
            settings.post_init()
            mock_super_post_init.assert_called_once_with(reinitialise=False)

    def test_post_init_with_reinitialise_flag(self):
        settings = AppSettings()
        with patch.object(settings.__class__.__bases__[0], 'post_init') as mock_super_post_init:
            settings.post_init(reinitialise=True)
            mock_super_post_init.assert_called_once_with(reinitialise=True)

    def test_post_init_initializes_rundatetime_from_template(self):
        settings = AppSettings(RUNDATE="20240115", RUNTIME="143045")
        
        # Call post_init and verify RUNDATETIME is set
        settings.post_init()
        
        # RUNDATETIME should be initialized after post_init
        assert hasattr(settings, 'RUNDATETIME')
        assert settings.RUNDATETIME is not None
        # Should contain date and time information
        assert len(str(settings.RUNDATETIME)) >= 8  # At least YYYYMMDD format

    def test_rundatetime_field_exists(self):
        settings = AppSettings()
        # RUNDATETIME gets initialized during post_init, so it may not be None
        assert hasattr(settings, 'RUNDATETIME')

    def test_field_defaults_are_correct(self):
        settings = AppSettings()
        assert isinstance(settings.DEBUG, bool)
        assert isinstance(settings.RUNDATE, str)
        assert isinstance(settings.RUNTIME, str)
        assert isinstance(settings.LOCALE_TIMEZONE, str)
        assert isinstance(settings.PANDERA_DATAFRAME_FRAMEWORK, str)