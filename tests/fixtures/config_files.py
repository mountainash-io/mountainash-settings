"""
Configuration file fixtures for testing.

This module provides reusable fixtures for creating temporary
configuration files in various formats (YAML, TOML, JSON, .env).
"""

import tempfile
import json
from pathlib import Path
from typing import Dict, Any, List
import pytest


@pytest.fixture
def temp_yaml_file():
    """Creates a temporary YAML config file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
DEBUG: true
LOCALE_TIMEZONE: "EST"
CUSTOM_SETTING: "test_value"
TEST_VAL_1: "yaml_value_1"
TEST_VAL_2: "yaml_value_2"
""")
        temp_path = f.name

    yield temp_path

    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


@pytest.fixture
def temp_toml_file():
    """Creates a temporary TOML config file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
        f.write("""
DEBUG = true
LOCALE_TIMEZONE = "EST"
CUSTOM_SETTING = "test_value"
TEST_VAL_1 = "toml_value_1"
TEST_VAL_2 = "toml_value_2"
""")
        temp_path = f.name

    yield temp_path

    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


@pytest.fixture
def temp_json_file():
    """Creates a temporary JSON config file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        config = {
            "DEBUG": True,
            "LOCALE_TIMEZONE": "EST",
            "CUSTOM_SETTING": "test_value",
            "TEST_VAL_1": "json_value_1",
            "TEST_VAL_2": "json_value_2"
        }
        json.dump(config, f, indent=2)
        temp_path = f.name

    yield temp_path

    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


@pytest.fixture
def temp_env_file():
    """Creates a temporary .env file for testing (with .env extension)."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
        f.write("""DEBUG=true
LOCALE_TIMEZONE=EST
CUSTOM_SETTING=test_value
TEST_VAL_1=env_value_1
TEST_VAL_2=env_value_2
""")
        temp_path = f.name

    yield temp_path

    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


@pytest.fixture
def temp_dotenv_file(temp_dir):
    """Creates an actual .env dotfile (no extension) for testing."""
    dotenv_path = temp_dir / ".env"
    dotenv_path.write_text("""DEBUG=true
LOCALE_TIMEZONE=EST
CUSTOM_SETTING=dotenv_value
TEST_VAL_1=dotenv_value_1
TEST_VAL_2=dotenv_value_2
""")
    yield str(dotenv_path)

    # Cleanup happens automatically with temp_dir


@pytest.fixture
def temp_config_file(temp_yaml_file):
    """
    Alias for temp_yaml_file for backwards compatibility.

    Many existing tests use temp_config_file, so we provide
    this alias to avoid breaking changes.
    """
    return temp_yaml_file


@pytest.fixture
def temp_multiple_yaml_files():
    """Creates multiple temporary YAML config files for testing priority."""
    files = []

    # Primary config
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
DEBUG: true
PRIMARY_SETTING: "primary_value"
OVERRIDE_SETTING: "from_primary"
""")
        files.append(f.name)

    # Secondary config (should override PRIMARY_SETTING values)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
SECONDARY_SETTING: "secondary_value"
OVERRIDE_SETTING: "from_secondary"
""")
        files.append(f.name)

    yield files

    # Cleanup
    for file_path in files:
        Path(file_path).unlink(missing_ok=True)


@pytest.fixture
def temp_config_files(temp_multiple_yaml_files):
    """
    Alias for temp_multiple_yaml_files for backwards compatibility.
    """
    return temp_multiple_yaml_files


@pytest.fixture
def temp_mixed_config_files():
    """Creates config files in multiple formats for testing."""
    files = []

    # YAML file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
FROM_YAML: "yaml_value"
SHARED_KEY: "from_yaml"
""")
        files.append(f.name)

    # TOML file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
        f.write("""
FROM_TOML = "toml_value"
SHARED_KEY = "from_toml"
""")
        files.append(f.name)

    # JSON file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        config = {
            "FROM_JSON": "json_value",
            "SHARED_KEY": "from_json"
        }
        json.dump(config, f)
        files.append(f.name)

    yield files

    # Cleanup
    for file_path in files:
        Path(file_path).unlink(missing_ok=True)


@pytest.fixture
def temp_template_config_file():
    """Creates a config file with template values for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
app_name: "my_app"
log_dir: "/var/log/apps"
log_file: "logs/{app_name}.log"
full_log_path: "{log_dir}/{app_name}.log"
""")
        temp_path = f.name

    yield temp_path

    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


@pytest.fixture
def temp_dir():
    """Provides a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture(scope="session")
def test_data_dir():
    """Provides path to test data directory."""
    return Path(__file__).parent.parent / "data"


@pytest.fixture
def create_config_file():
    """
    Factory fixture for creating custom config files.

    Usage:
        config_file = create_config_file('yaml', {'KEY': 'value'})
    """
    created_files = []

    def _create(file_type: str, content: Dict[str, Any]) -> str:
        """
        Create a temporary config file of specified type.

        Args:
            file_type: File extension (yaml, toml, json, env)
            content: Dictionary of configuration values

        Returns:
            Path to created file
        """
        suffix = f'.{file_type}'
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix=suffix,
            delete=False
        ) as f:
            if file_type in ('yaml', 'yml'):
                for key, value in content.items():
                    if isinstance(value, str):
                        f.write(f'{key}: "{value}"\n')
                    else:
                        f.write(f'{key}: {value}\n')
            elif file_type == 'toml':
                for key, value in content.items():
                    if isinstance(value, str):
                        f.write(f'{key} = "{value}"\n')
                    else:
                        f.write(f'{key} = {value}\n')
            elif file_type == 'json':
                json.dump(content, f, indent=2)
            elif file_type == 'env':
                for key, value in content.items():
                    f.write(f'{key}={value}\n')
            else:
                raise ValueError(f"Unsupported file type: {file_type}")

            temp_path = f.name
            created_files.append(temp_path)
            return temp_path

    yield _create

    # Cleanup all created files
    for file_path in created_files:
        Path(file_path).unlink(missing_ok=True)
