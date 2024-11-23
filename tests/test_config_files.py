# import pytest
# from pydantic import Field
# from upath import UPath
# import os
# from typing import Dict, Any

# from mountainash_settings import MountainAshBaseSettings, AppSettings
# from mountainash_settings.settings_functions import  get_settings

# class TestSettings(MountainAshBaseSettings):
#     TEST_VAR: str = Field(default="default_value")
#     COMPLEX_VAR: Dict[str, Any] = Field(default={"key": "value"})

# @pytest.fixture
# def temp_env(monkeypatch):
#     monkeypatch.setenv("TEST_VAR", "env_value")
#     monkeypatch.setenv("COMPLEX_VAR", '{"key": "env_value"}')

# @pytest.fixture
# def temp_config_file(tmp_path):
#     config_content = """
#     TEST_VAR: config_value
#     COMPLEX_VAR: 
#       key: config_value
#     """
#     config_file = tmp_path / "config.yaml"
#     config_file.write_text(config_content)
#     return config_file

# def test_env_variable_priority(temp_env):
#     settings = TestSettings()
#     assert settings.TEST_VAR == "env_value"
#     assert settings.COMPLEX_VAR == {"key": "env_value"}

# def test_single_config_file(temp_config_file):
#     settings = TestSettings(_env_file=str(temp_config_file))
#     assert settings.TEST_VAR == "config_value"
#     assert settings.COMPLEX_VAR == {"key": "config_value"}

# def test_multiple_config_files(temp_config_file, tmp_path):
#     second_config = tmp_path / "config2.yaml"
#     second_config.write_text("TEST_VAR: second_config_value")
    
#     settings = TestSettings(_env_file=[str(temp_config_file), str(second_config)])
#     assert settings.TEST_VAR == "second_config_value"
#     assert settings.COMPLEX_VAR == {"key": "config_value"}

# def test_kwargs_priority():
#     settings = TestSettings(TEST_VAR="kwarg_value", COMPLEX_VAR={"key": "kwarg_value"})
#     assert settings.TEST_VAR == "kwarg_value"
#     assert settings.COMPLEX_VAR == {"key": "kwarg_value"}

# def test_env_config_kwargs_priority(temp_env, temp_config_file):
#     settings = TestSettings(_env_file=str(temp_config_file), TEST_VAR="kwarg_value")
#     assert settings.TEST_VAR == "kwarg_value"
#     assert settings.COMPLEX_VAR == {"key": "env_value"}

# def test_post_init_override():
#     settings = TestSettings()
#     assert settings.TEST_VAR == "default_value"
    
#     settings.TEST_VAR = "new_value"
#     assert settings.TEST_VAR == "new_value"

# def test_app_settings_initialization():
#     app_settings = AppSettings(RUNDATE="20230101", RUNTIME="120000")
#     assert app_settings.RUNDATE == "20230101"
#     assert app_settings.RUNTIME == "120000"
#     assert app_settings.RUNDATETIME == "20230101T120000"

# def test_app_settings_post_init():
#     app_settings = AppSettings(RUNDATE="20230101", RUNTIME="120000")
#     assert app_settings.RUNDATETIME == "20230101T120000"
    
#     app_settings.RUNDATE = "20230102"
#     app_settings.RUNTIME = "130000"
#     app_settings.post_init()
#     assert app_settings.RUNDATETIME == "20230102T130000"

# def test_get_settings():
#     params = SettingsParameters.create(
#         namespace="test",
#         settings_class=TestSettings,
#         config_files=None,
#         p_kwargs={"TEST_VAR": "param_value"}
#     )
#     settings = get_settings(settings_parameters=params, settings_class=TestSettings)
#     assert settings.TEST_VAR == "param_value"
#     assert settings.SETTINGS_NAMESPACE == "test"

# def test_get_settings_with_config(temp_config_file):
#     params = SettingsParameters.create(
#         namespace="test",
#         settings_class=TestSettings,
#         config_files=[str(temp_config_file)],
#         p_kwargs={"TEST_VAR": "param_value"}
#     )
#     settings = get_settings(settings_parameters=params, settings_class=TestSettings)
#     assert settings.TEST_VAR == "param_value"
#     assert settings.COMPLEX_VAR == {"key": "config_value"}
#     assert settings.SETTINGS_NAMESPACE == "test"

# # Add more tests as needed