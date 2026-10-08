"""Installed public typing contract; checked by tools/qualify_typing.py."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, ClassVar, assert_type

from pydantic import Field, ValidationError

from mountainash_settings import (
    MountainAshBaseSettings, Profile, ProfileField, ProfileSpec, Registry,
    SettingsParameters, get_settings, get_settings_manager,
)


class AppSettings(MountainAshBaseSettings):
    PORT: int = 5432


class SpecialSettings(AppSettings):
    LABEL: str = "special"


class DatabaseProfile(Profile, name="database", provider_type="database"):
    HOST: str = ProfileField(default="localhost")


class ExplicitProfile(Profile):
    __spec__: ClassVar[ProfileSpec] = ProfileSpec(
        name="explicit", provider_type="database", parameters=[],
    )
    HOST: str = "localhost"


class FileSettings(MountainAshBaseSettings):
    DATABASE: str


class AliasedSettings(MountainAshBaseSettings):
    DATABASE: str = Field(alias="database")


params = SettingsParameters.create(settings_class=AppSettings)
app = assert_type(AppSettings.get_settings(), AppSettings)
assert_type(app.PORT, int)
assert_type(get_settings(settings_class=AppSettings), AppSettings)
assert_type(get_settings(params, AppSettings), AppSettings)
assert_type(get_settings(params, settings_class=AppSettings), AppSettings)
assert_type(get_settings(settings_parameters=params), MountainAshBaseSettings)
assert_type(get_settings(params, None), MountainAshBaseSettings)
assert_type(get_settings_manager().get_or_create_settings(params), MountainAshBaseSettings)
assert_type(AppSettings.get_settings(params), AppSettings)
assert_type(SpecialSettings.get_settings(), SpecialSettings)
# The class method promises its receiving class, even for a narrower override.
override = assert_type(AppSettings.get_settings(settings_class=SpecialSettings), AppSettings)
assert isinstance(override, SpecialSettings)
assert override.LABEL == "special"
assert app.PORT == 5432

database = assert_type(DatabaseProfile.get_settings(), DatabaseProfile)
assert_type(database.HOST, str)
assert_type(get_settings(settings_class=DatabaseProfile), DatabaseProfile)
explicit = assert_type(ExplicitProfile.get_settings(), ExplicitProfile)
assert_type(explicit.HOST, str)
registry = Registry("database")
assert DatabaseProfile.__spec__ is not None
registry.register(DatabaseProfile.__spec__, DatabaseProfile)
assert_type(registry.get_settings_class("database"), type[Profile])

# Conflicting selectors still fail instead of returning a falsely typed result.
try:
    get_settings(params, settings_class=SpecialSettings)
except ValueError:
    pass
else:
    raise AssertionError("conflicting class selectors accepted")

try:
    AppSettings.get_settings(settings_class=ExplicitProfile)
except TypeError:
    pass
else:
    raise AssertionError("class-method receiver check lost")

constructed = assert_type(
    AppSettings(env_prefix="MAS_TYPING_", config_files=[]), AppSettings,
)
assert_type(constructed.PORT, int)
constructed_child = assert_type(
    SpecialSettings(env_prefix="MAS_TYPING_", PORT="6000"), SpecialSettings,
)
assert_type(constructed_child.LABEL, str)
assert constructed_child.PORT == 6000

constructor_params = SettingsParameters(
    settings_class=AppSettings, kwargs={"PORT": 6001},
)
assert AppSettings(settings_parameters=constructor_params).PORT == 6001
assert AppSettings(template_settings_parameters=constructor_params, PORT=5432).PORT == 5432
assert AppSettings(secrets_dir=None, secret_store=None, PORT=5432).PORT == 5432

# Embedded fixture bytes travel in the already-hashed consumer.py.
env_key = "MAS_TYPING_REQUIRED_DATABASE"
prior_value = os.environ.pop(env_key, None)
try:
    with TemporaryDirectory(prefix="settings-typing-") as directory:
        source = Path(directory) / "settings.json"
        source.write_text('{"DATABASE": "reports_db"}', encoding="utf-8")
        file_settings = assert_type(
            FileSettings(config_files=[str(source)], env_prefix="MAS_TYPING_REQUIRED_"),
            FileSettings,
        )
        assert_type(file_settings.DATABASE, str)
        assert file_settings.DATABASE == "reports_db"
finally:
    if prior_value is not None:
        os.environ[env_key] = prior_value

constructed_profile = assert_type(
    DatabaseProfile(env_prefix="MAS_TYPING_", HOST="db.example.com"), DatabaseProfile,
)
assert_type(constructed_profile.HOST, str)
assert constructed_profile.HOST == "db.example.com"
assert AliasedSettings(database="reports_db").DATABASE == "reports_db"
assert AppSettings.model_validate({"PORT": 6002}).PORT == 6002
assert "PORT" in AppSettings.model_json_schema()["properties"]
assert isinstance(constructed.model_dump(), dict)
try:
    AppSettings(PORT="not-an-integer")
except ValidationError:
    pass
else:
    raise AssertionError("constructor bypassed validation")

if TYPE_CHECKING:
    # warn-unused-ignores makes every expected rejection mandatory. If retrieval
    # regresses to Any, these assignments stop failing and the gate turns red.
    app.PORT = "wrong"  # type: ignore[assignment]
    database.HOST = 123  # type: ignore[assignment]
    explicit.HOST = 123  # type: ignore[assignment]
    get_settings(settings_class=AppSettings).PORT = "wrong"  # type: ignore[assignment]
    get_settings(settings_class=int)  # type: ignore[type-var]
    registry.register("wrong", DatabaseProfile)  # type: ignore[arg-type]
    constructed.PORT = "wrong"  # type: ignore[assignment]
    constructed_child.LABEL = 123  # type: ignore[assignment]
    constructed_profile.HOST = 123  # type: ignore[assignment]
    constructed.NONEXISTENT  # type: ignore[attr-defined]
