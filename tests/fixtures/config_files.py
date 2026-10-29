"""Shared configuration inputs, each writable file owned by pytest's tmp_path."""

import json
from itertools import count
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    """Locate static test inputs independently of the working directory."""
    return Path(__file__).resolve().parents[1] / "data"


@pytest.fixture
def temp_yaml_file(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text('''
DEBUG: true
LOCALE_TIMEZONE: "EST"
CUSTOM_SETTING: "test_value"
TEST_VAL_1: "yaml_value_1"
TEST_VAL_2: "yaml_value_2"
''', encoding="utf-8")
    return str(path)


@pytest.fixture
def temp_toml_file(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('''
DEBUG = true
LOCALE_TIMEZONE = "EST"
CUSTOM_SETTING = "test_value"
TEST_VAL_1 = "toml_value_1"
TEST_VAL_2 = "toml_value_2"
''', encoding="utf-8")
    return str(path)


@pytest.fixture
def temp_json_file(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({
        "DEBUG": True,
        "LOCALE_TIMEZONE": "EST",
        "CUSTOM_SETTING": "test_value",
        "TEST_VAL_1": "json_value_1",
        "TEST_VAL_2": "json_value_2",
    }, indent=2), encoding="utf-8")
    return str(path)


@pytest.fixture
def temp_env_file(tmp_path):
    path = tmp_path / "config.env"
    path.write_text('''DEBUG=true
LOCALE_TIMEZONE=EST
CUSTOM_SETTING=test_value
TEST_VAL_1=env_value_1
TEST_VAL_2=env_value_2
''', encoding="utf-8")
    return str(path)


@pytest.fixture
def temp_dotenv_file(tmp_path):
    path = tmp_path / ".env"
    path.write_text('''DEBUG=true
LOCALE_TIMEZONE=EST
CUSTOM_SETTING=dotenv_value
TEST_VAL_1=dotenv_value_1
TEST_VAL_2=dotenv_value_2
''', encoding="utf-8")
    return str(path)


@pytest.fixture
def temp_multiple_yaml_files(tmp_path):
    primary = tmp_path / "primary.yaml"
    primary.write_text('''
DEBUG: true
PRIMARY_SETTING: "primary_value"
OVERRIDE_SETTING: "from_primary"
''', encoding="utf-8")
    secondary = tmp_path / "secondary.yaml"
    secondary.write_text('''
SECONDARY_SETTING: "secondary_value"
OVERRIDE_SETTING: "from_secondary"
''', encoding="utf-8")
    return [str(primary), str(secondary)]


@pytest.fixture
def create_config_file(tmp_path):
    """Create uniquely named inputs while retaining the fixtures' format syntax."""
    sequence = count()

    def create(file_type: str, content: dict) -> str:
        path = tmp_path / f"config-{next(sequence)}.{file_type}"
        with path.open("w", encoding="utf-8") as output:
            if file_type in ("yaml", "yml"):
                for key, value in content.items():
                    if isinstance(value, str):
                        output.write(f'{key}: "{value}"\n')
                    else:
                        output.write(f"{key}: {value}\n")
            elif file_type == "toml":
                for key, value in content.items():
                    if isinstance(value, str):
                        output.write(f'{key} = "{value}"\n')
                    else:
                        output.write(f"{key} = {value}\n")
            elif file_type == "json":
                json.dump(content, output, indent=2)
            elif file_type == "env":
                for key, value in content.items():
                    output.write(f"{key}={value}\n")
            else:
                raise ValueError(f"Unsupported file type: {file_type}")
        return str(path)

    return create
