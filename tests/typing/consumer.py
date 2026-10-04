"""Installed public typing contract; checked by tools/qualify_typing.py."""
from typing import TYPE_CHECKING, ClassVar, assert_type

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

if TYPE_CHECKING:
    # warn-unused-ignores makes every expected rejection mandatory. If retrieval
    # regresses to Any, these assignments stop failing and the gate turns red.
    app.PORT = "wrong"  # type: ignore[assignment]
    database.HOST = 123  # type: ignore[assignment]
    explicit.HOST = 123  # type: ignore[assignment]
    get_settings(settings_class=AppSettings).PORT = "wrong"  # type: ignore[assignment]
    get_settings(settings_class=int)  # type: ignore[type-var]
    registry.register("wrong", DatabaseProfile)  # type: ignore[arg-type]
