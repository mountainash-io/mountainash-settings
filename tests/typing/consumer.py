"""Installed public typing contract; checked by tools/qualify_typing.py."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, ClassVar, Generic, Protocol, TypeVar, assert_type, runtime_checkable

from pydantic import Field, ValidationError

from mountainash_settings import (
    MountainAshBaseSettings, Profile, ProfileField, ProfileSpec, Registry,
    SettingsParameters, get_settings, get_settings_manager,
)
from mountainash_settings.profiles import spec_invariants_for


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


class DomainSpec(ProfileSpec):
    pass


class DomainProfile(Profile):
    def url(self) -> str:
        return "db://example"


class ConcreteDomain(DomainProfile, name="domain", provider_type="database", spec_type=DomainSpec):
    LABEL: str = "concrete"


@runtime_checkable
class DomainProtocol(Protocol):
    def url(self) -> str: ...


class FactoryObject:
    def __call__(self) -> DomainProfile:
        return DomainProfile()


def domain_factory() -> DomainProfile:
    return DomainProfile()


nominal = Registry("nominal", spec_type=DomainSpec, profile_type=DomainProfile)
structural = Registry("structural", spec_type=DomainSpec, profile_type=DomainProtocol)
assert_type(nominal, Registry[DomainSpec, DomainProfile])
assert_type(structural, Registry[DomainSpec, DomainProtocol])
decorated = assert_type(nominal.decorator()(ConcreteDomain), type[ConcreteDomain])
assert_type(decorated().LABEL, str)
assert decorated().LABEL == "concrete"
assert_type(structural.decorator()(ConcreteDomain), type[ConcreteDomain])
assert_type(nominal.get_spec("domain"), DomainSpec)
assert_type(nominal.specs, dict[str, DomainSpec])
assert_type(nominal.get_settings_class("domain"), type[DomainProfile])
assert_type(structural.get_settings_class("domain"), type[DomainProtocol])
assert structural.get_settings_class("domain")().url() == "db://example"
snapshot = assert_type(
    nominal._snapshot_for_tests(),
    tuple[dict[str, DomainSpec], dict[str, type[DomainProfile]]],
)
nominal._reset_for_tests(*snapshot)
spec_invariants_for(nominal)
spec_invariants_for(structural)
assert_type(Registry("base"), Registry[ProfileSpec, Profile])
assert_type(Registry("spec", spec_type=DomainSpec), Registry[DomainSpec, Profile])
assert_type(Registry("profile", profile_type=DomainProfile), Registry[ProfileSpec, DomainProfile])
assert_type(Registry("protocol", profile_type=DomainProtocol), Registry[ProfileSpec, DomainProtocol])
assert_type(Registry("none", spec_type=None, profile_type=None), Registry[ProfileSpec, Profile])
assert_type(Registry("partial", spec_type=DomainSpec, profile_type=None), Registry[DomainSpec, Profile])


def optional_registry(spec: type[DomainSpec] | None, profile: type[DomainProfile] | None) -> None:
    selected = Registry("optional", spec_type=spec, profile_type=profile)
    assert_type(
        selected,
        Registry[DomainSpec, DomainProfile] | Registry[DomainSpec, Profile]
        | Registry[ProfileSpec, DomainProfile] | Registry[ProfileSpec, Profile],
    )


def class_variable_registry(profile: type[DomainProfile]) -> None:
    assert_type(Registry("variable", profile_type=profile), Registry[ProfileSpec, DomainProfile])


if TYPE_CHECKING:
    Registry("factory", profile_type=domain_factory)  # type: ignore[call-overload]
    Registry("factory-both", spec_type=DomainSpec, profile_type=domain_factory)  # type: ignore[call-overload]
    Registry("lambda", profile_type=lambda: DomainProfile())  # type: ignore[call-overload]
    Registry("callable", profile_type=FactoryObject())  # type: ignore[call-overload]
    Registry("instance", profile_type=DomainProfile())  # type: ignore[call-overload]
    Registry("spec-factory", spec_type=lambda: DomainSpec(name="x", provider_type="x", parameters=[]))  # type: ignore[call-overload]
    bad_default: Registry[DomainSpec, DomainProfile] = Registry("bad")  # type: ignore[assignment]
    bad_none: Registry[DomainSpec, DomainProfile] = Registry("bad-none", spec_type=DomainSpec, profile_type=None)  # type: ignore[assignment]
    bad_explicit: Registry[DomainSpec, DomainProfile] = Registry[DomainSpec, DomainProfile]("bad-explicit")  # type: ignore[assignment]
    nominal.register(ProfileSpec(name="bad", provider_type="bad", parameters=[]), ConcreteDomain)  # type: ignore[arg-type]
    nominal.register(DomainSpec(name="bad", provider_type="bad", parameters=[]), ExplicitProfile)  # type: ignore[arg-type]

    class PlainRegistry(Registry):  # type: ignore[misc]
        pass

    class SpecializedRegistry(Registry[DomainSpec, DomainProfile]):  # type: ignore[misc]
        pass

    RegistrySpecT = TypeVar("RegistrySpecT", bound=ProfileSpec)
    RegistryProfileT = TypeVar("RegistryProfileT")

    class GenericRegistry(Registry[RegistrySpecT, RegistryProfileT], Generic[RegistrySpecT, RegistryProfileT]):  # type: ignore[misc]
        pass
