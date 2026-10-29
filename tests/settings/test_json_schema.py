"""Class-level schemas omit Python class identity without changing runtime fields."""

import json

import pytest
from pydantic import BaseModel, Field, SecretStr

from mountainash_settings import MountainAshBaseSettings
from tests.fixtures.settings_classes import TestSettings


@pytest.mark.parametrize("mode,port_name", [
    ("validation", "port_in"), ("serialization", "port_out"),
])
def test_schema_preserves_application_fields_without_constructing_settings(mode, port_name):
    def runtime_default():
        raise AssertionError("Schema generation must not evaluate runtime defaults")

    class Database(BaseModel):
        HOST: str

    class Settings(MountainAshBaseSettings):
        PORT: int = Field(default=5432, ge=1, le=65535,
                          validation_alias="port_in", serialization_alias="port_out")
        TOKEN: SecretStr
        DATABASE: Database
        GENERATED: str = Field(default_factory=runtime_default)

        def __init__(self, **kwargs):
            raise AssertionError("Schema generation must not load settings sources")

    schema = Settings.model_json_schema(mode=mode)
    assert json.loads(json.dumps(schema)) == schema
    properties = schema["properties"]
    assert "SETTINGS_CLASS" not in properties
    assert "SETTINGS_CLASS_NAME" in properties
    assert "SETTINGS_SOURCE_ENV_PREFIX" in properties
    assert properties[port_name]["type"] == "integer"
    assert properties[port_name]["default"] == 5432
    assert properties[port_name]["minimum"] == 1
    assert properties[port_name]["maximum"] == 65535
    assert port_name not in schema["required"]
    assert set(schema["required"]) == {"TOKEN", "DATABASE"}
    assert properties["TOKEN"]["type"] == "string"
    assert properties["TOKEN"]["writeOnly"] is True
    assert properties["DATABASE"]["$ref"] == "#/$defs/Database"
    assert schema["$defs"]["Database"]["required"] == ["HOST"]
    assert "default" not in properties["GENERATED"]


def test_schema_omission_retains_runtime_class_field(isolated_settings_manager):
    settings = TestSettings(TEST_VAL_1="configured")
    assert settings.SETTINGS_CLASS is TestSettings
    assert settings.model_dump()["SETTINGS_CLASS"] is TestSettings
    parameters = settings.extract_settings_parameters()
    assert parameters.settings_class is TestSettings
    assert parameters.get_settings().TEST_VAL_1 == "configured"
