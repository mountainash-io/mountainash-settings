import pytest
from mountainash_settings import SettingsManager, get_settings_manager

# Fixture to create an instance of SettingsManager before each test
@pytest.fixture
def settings_manager() -> SettingsManager:
    return get_settings_manager()


# Test case for validating config files existence
def test_validate_config_files_exist(settings_manager):
    with pytest.raises(FileNotFoundError):
        # Assuming a non-existing file path
        settings_manager.validate_config_files_exist(config_files=["non_existing_file.yaml"])

# Test case for validating kwargs keys
def test_validate_kwargs_keys(settings_manager):
    with pytest.raises(ValueError):
        # Assuming an invalid key in the kwargs dictionary
        settings_manager.validate_kwargs_keys(settings_class=None, kwargs={"invalid_key": "value"})

# Parameterized test case for testing is_namespace_initialised method
@pytest.mark.parametrize("namespace, expected_result", [("test_ns", False), ("default_ns", True)])
def test_is_namespace_initialised(settings_manager, namespace, expected_result):
    settings_manager.app_settings_objects = {"default_ns": None}
    assert settings_manager.is_namespace_initialised(namespace) == expected_result

# Test case for initializing new config
def test_init_config(settings_manager):
    settings_namespace = "test_ns"
    settings_class = type("FakeMountainAshBaseSettings", (), {})  # Creating a fake class for testing

    with pytest.raises(AttributeError):
        obj_settings = settings_manager.init_config(settings_namespace=settings_namespace, settings_class=settings_class)
    
    # assert obj_settings is not None
    # assert isinstance(obj_settings, settings_class)

# You can add more test cases similarly for other methods in the class
