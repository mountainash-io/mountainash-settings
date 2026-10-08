"""Model declarations reused across settings and parameter tests."""

from typing import List, Optional, Union

from pydantic import Field
from pydantic_settings import BaseSettings
from upath import UPath

from mountainash_settings import MountainAshBaseSettings, SettingsParameters


class MockBaseSettings(BaseSettings):
    test_field: str = "default_value"
    test_int: int = 42
    test_bool: bool = True


class MockSettings(BaseSettings):
    field1: str = "default1"
    field2: int = 42
    field3: bool = True


class TestSettings(MountainAshBaseSettings):
    """Shared settings model, not a pytest test container."""

    __test__ = False

    def __init__(
        self,
        config_files: Optional[Union[str, UPath, List[Union[str, UPath]]]] = None,
        settings_parameters: Optional[SettingsParameters] = None,
        **kwargs,
    ) -> None:
        super().__init__(
            config_files=config_files,
            settings_parameters=settings_parameters,
            **kwargs,
        )

    TEST_VAL_1: str | None = Field(default=None)
    TEST_VAL_2: str | None = Field(default=None)
    TEST_VAR: str = Field(default="default_value")
    COMPLEX_VAR: dict = Field(default_factory=lambda: {"key": "value"})
