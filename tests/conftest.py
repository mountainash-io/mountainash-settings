import pytest
import tempfile
from pathlib import Path
from typing import Dict, Any
from unittest.mock import MagicMock, patch
from pydantic_settings import BaseSettings
from upath import UPath

from mountainash_settings import SettingsParameters
from mountainash_settings.settings.app.app_settings import AppSettings


class MockBaseSettings(BaseSettings):
    """Mock settings class for testing."""
    test_field: str = "default_value"
    test_int: int = 42
    test_bool: bool = True


@pytest.fixture
def mock_settings_class():
    """Provides a mock settings class for testing."""
    return MockBaseSettings


@pytest.fixture
def sample_settings_parameters():
    """Provides sample settings parameters for testing."""
    return SettingsParameters.create(
        namespace="test",
        config_files="test_config.yaml",
        env_prefix="TEST_"
    )


@pytest.fixture
def sample_kwargs():
    """Provides sample kwargs for testing."""
    return {
        "DEBUG": True,
        "VERBOSE": False,
        "_env_prefix": "TEST_",
        "custom_field": "value"
    }


@pytest.fixture
def temp_config_file():
    """Creates a temporary config file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
DEBUG: true
LOCALE_TIMEZONE: "EST"
CUSTOM_SETTING: "test_value"
""")
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


@pytest.fixture
def temp_config_files():
    """Creates multiple temporary config files for testing."""
    files = []
    
    # Primary config
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
DEBUG: true
PRIMARY_SETTING: "primary_value"
""")
        files.append(f.name)
    
    # Secondary config
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
SECONDARY_SETTING: "secondary_value"
OVERRIDE_SETTING: "overridden"
""")
        files.append(f.name)
    
    yield files
    
    # Cleanup
    for file_path in files:
        Path(file_path).unlink(missing_ok=True)


@pytest.fixture
def app_settings_instance():
    """Provides an AppSettings instance for testing."""
    return AppSettings()


@pytest.fixture
def mock_get_platform_slash():
    """Mock the get_platform_slash function."""
    with patch('mountainash_settings.settings.app.app_settings.get_platform_slash') as mock:
        mock.return_value = "/"
        yield mock


@pytest.fixture(autouse=True)
def mock_datetime_for_tests():
    """Auto-use fixture to mock datetime for consistent test results."""
    from datetime import datetime
    with patch('mountainash_settings.settings.app.app_settings.datetime') as mock_datetime:
        # Set a fixed datetime for predictable testing
        mock_datetime.now.return_value = datetime(2024, 1, 15, 14, 30, 45)
        yield mock_datetime


# Test markers for categorizing tests
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line("markers", "unit: marks tests as unit tests")
    config.addinivalue_line("markers", "integration: marks tests as integration tests") 
    config.addinivalue_line("markers", "performance: marks tests as performance tests")
    config.addinivalue_line("markers", "slow: marks tests as slow running")


@pytest.fixture(scope="session")
def test_data_dir():
    """Provides path to test data directory."""
    return Path(__file__).parent / "data"


@pytest.fixture
def temp_dir():
    """Provides a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)