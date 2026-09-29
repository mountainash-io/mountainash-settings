"""Class declarations project native fields without replacing Pydantic behavior."""

from dataclasses import dataclass, field

import pytest
from pydantic import ValidationError

from mountainash_settings import (
    FACTORY_DEFAULT, MISSING, MountainAshBaseSettings, ParameterSpec,
    Profile, ProfileField, ProfileSpec,
)


@dataclass(frozen=True, kw_only=True)
class DatabaseSpec(ProfileSpec):
    default_port: int = 5432
    supported_auth: tuple[type, ...] = ()

    def __post_init__(self):
        if not self.supported_auth:
            raise ValueError("supported_auth required")


def test_profile_field_retains_native_field_behavior():
    from mountainash_settings import ProfileField

    calls = []

    def tags():
        calls.append(True)
        return []

    class Settings(MountainAshBaseSettings):
        PORT: int = ProfileField(default=5432, ge=1, le=65535)
        TAGS: list[str] = ProfileField(default_factory=tags)

    assert calls == []
    first, second = Settings(), Settings()
    first.TAGS.append("local")
    assert second.TAGS == []
    assert len(calls) == 2
    with pytest.raises(ValidationError):
        Settings(PORT=0)


@pytest.mark.parametrize("option,value", [
    ("tier", None), ("tier", "standard"), ("driver_key", 123),
    ("driver_key", {"http": 123}), ("transform", "credential-value"),
    ("template", 123),
])
def test_profile_field_rejects_invalid_options_without_values(option, value):
    from mountainash_settings import ProfileField

    with pytest.raises(TypeError, match=option) as error:
        ProfileField(**{option: value})
    assert "credential-value" not in str(error.value)


def test_domain_header_types_and_constructor():
    class Base(Profile, spec_type=DatabaseSpec, driver_keys="lower"):
        pass

    with pytest.raises(TypeError, match="Bad.*default_port") as error:
        class Bad(Base, default_port="credential-value"):
            pass
    assert "credential-value" not in str(error.value)
    assert error.value.__context__ is None
    with pytest.raises(TypeError, match="unknown_option"):
        class Unknown(Base, unknown_option=True):
            pass
    with pytest.raises(TypeError, match="supported_auth"):
        class InvalidTypes(Base, supported_auth=(object(),)):
            pass
    with pytest.raises(ValueError, match="supported_auth"):
        class MissingAuth(Base, name="missing", provider_type="db"):
            pass

    class Concrete(Base, name="concrete", provider_type="db", supported_auth=(object,)):
        pass

    assert isinstance(Concrete.__spec__, DatabaseSpec)
    assert Concrete.__spec__.default_port == 5432
    assert Concrete.__spec__.supported_auth == (object,)
    assert Concrete().emit() == {}


def test_generated_headers_reject_explicit_spec():
    explicit = ProfileSpec(name="explicit", provider_type="db", parameters=[])
    with pytest.raises(TypeError, match="Mixed.*explicit.*generated"):
        class Mixed(Profile, name="mixed", provider_type="db"):
            __spec__ = explicit


def test_independent_profile_bases_rejected():
    class Left(Profile, driver_keys="lower"):
        pass

    class Right(Profile, driver_keys=None):
        pass

    with pytest.raises(TypeError, match="Combined.*profile.*bases"):
        class Combined(Left, Right, name="combined", provider_type="db"):
            pass

    class Behavior:
        def label(self):
            return "mixed in"

    class Valid(Behavior, Left, name="valid", provider_type="db"):
        pass

    assert Valid().label() == "mixed in"


@pytest.mark.parametrize("identity", [
    {"name": "half"}, {"provider_type": "db"},
    {"name": "half", "provider_type": None}, {"name": None, "provider_type": "db"},
])
def test_generated_identity_pair_rejected(identity):
    with pytest.raises(TypeError, match="Half.*identity"):
        class Half(Profile, **identity):
            pass


@pytest.mark.parametrize("name", ["", "Upper", 123])
def test_generated_identity_name_shape_rejected(name):
    with pytest.raises(TypeError, match="BadName.*name"):
        class BadName(Profile, name=name, provider_type="db"):
            pass


@pytest.mark.parametrize("option", ["title", "frozen", "env_prefix", "parameters", "model_config"])
def test_reserved_headers_rejected_before_pydantic_consumes_them(option):
    with pytest.raises(TypeError, match=f"Reserved.*{option}"):
        class Reserved(Profile, name="reserved", provider_type="db", **{option: True}):
            pass


def test_spec_metadata_cannot_collide_with_config_controls():
    @dataclass(frozen=True, kw_only=True)
    class CollisionSpec(ProfileSpec):
        title: str = "ambiguous"

    with pytest.raises(TypeError, match="Collision.*title"):
        class Collision(Profile, spec_type=CollisionSpec):
            pass


def test_header_metadata_is_owned_and_replaced_by_key():
    metadata = {"nested": [1]}

    class Base(Profile, name="base", provider_type="db", metadata=metadata):
        pass

    class Child(Base, name="child", provider_type="db"):
        pass

    class Sibling(Base, name="sibling", provider_type="db", metadata={"other": True}):
        pass

    metadata["nested"].append(2)
    Base.__spec__.metadata["nested"].append(3)
    assert Child.__spec__.metadata == {"nested": [1]}
    assert Sibling.__spec__.metadata == {"other": True}


def test_concrete_metadata_defaults_and_derived_values_are_validated():
    @dataclass(frozen=True, kw_only=True)
    class InvalidDefault(ProfileSpec):
        port: int = "invalid"

    class Base(Profile, spec_type=InvalidDefault):
        pass

    with pytest.raises(TypeError, match="Concrete.*port"):
        class Concrete(Base, name="concrete", provider_type="db"):
            pass

    @dataclass(frozen=True, kw_only=True)
    class InvalidDerived(ProfileSpec):
        port: int = field(init=False)

        def __post_init__(self):
            object.__setattr__(self, "port", "invalid")

    with pytest.raises(TypeError, match="Derived.*port"):
        class Derived(Profile, spec_type=InvalidDerived, name="derived", provider_type="db"):
            pass


def test_domain_metadata_supports_native_model_types_and_callable_identity():
    from typing import Any
    from pydantic import BaseModel

    class Options(BaseModel):
        port: int

    class Handler:
        def __call__(self):
            return "handled"

    @dataclass(frozen=True, kw_only=True)
    class TypedSpec(ProfileSpec):
        options: Options
        handler: Any

    handler = Handler()

    class Typed(Profile, spec_type=TypedSpec, name="typed", provider_type="db",
                options=Options(port=5432), handler=handler):
        pass

    assert Typed.__spec__.options.port == 5432
    assert Typed.__spec__.handler is handler


def test_explicit_spec_installation_does_not_gain_generated_option_validation():
    # Existing explicit specs are not strict class-header declarations.
    class Explicit(Profile):
        __spec__ = ProfileSpec(name="legacy", provider_type="db", parameters=[
            ParameterSpec(name="PORT", type=int, tier="domain-tier", default=5432, driver_key="port"),
        ])

    assert Explicit().emit() == {"port": 5432}


def test_mapping_convention_and_native_redeclaration():
    class Parent(Profile, name="parent", provider_type="db", driver_keys="lower"):
        HOST: str = "localhost"
        PORT: int = ProfileField(default=5432, driver_key="db_port", ge=1)
        LOCAL: str = ProfileField(default="local", driver_key=None)

    class ExplicitOnly(Parent, name="explicit", provider_type="db", driver_keys=None):
        pass

    class Replaced(Parent, name="replaced", provider_type="db"):
        PORT: int = -1

    class Sibling(Parent, name="sibling", provider_type="db"):
        pass

    assert Parent().emit() == {"host": "localhost", "db_port": 5432}
    with pytest.raises(ValidationError):
        Parent(PORT=-1)
    assert ExplicitOnly().emit() == {"db_port": 5432}
    assert Replaced(PORT=-1).emit() == {"host": "localhost", "port": -1}
    assert Sibling().emit() == {"host": "localhost", "db_port": 5432}
    ExplicitOnly.model_rebuild(force=True)
    assert ExplicitOnly().emit() == {"db_port": 5432}
    assert Parent().emit() == {"host": "localhost", "db_port": 5432}
    assert Sibling().emit() == {"host": "localhost", "db_port": 5432}


def test_factory_projection_is_distinct_lazy_and_not_reconstructable():
    from copy import copy, deepcopy
    import pickle

    calls = []

    def tags():
        calls.append(True)
        return []

    class Generated(Profile, name="factory", provider_type="example"):
        REQUIRED: str
        TAGS: list[str] = ProfileField(default_factory=tags)
        LITERAL: list[str] = []

    assert calls == []
    defaults = {p.name: p.default for p in Generated.__spec__.parameters}
    assert defaults["REQUIRED"] is MISSING
    assert defaults["TAGS"] is FACTORY_DEFAULT
    assert copy(defaults["TAGS"]) is FACTORY_DEFAULT
    assert deepcopy(defaults["TAGS"]) is FACTORY_DEFAULT
    assert pickle.loads(pickle.dumps(defaults["TAGS"])) is FACTORY_DEFAULT
    first, second = Generated(REQUIRED="x"), Generated(REQUIRED="y")
    first.TAGS.append("local")
    first.LITERAL.append("local")
    assert second.TAGS == second.LITERAL == []
    assert calls == [True, True]
    with pytest.raises(TypeError, match="Reconstructed.*TAGS.*FACTORY_DEFAULT"):
        class Reconstructed(Profile):
            __spec__ = Generated.__spec__


def test_validated_data_factory_is_not_evaluated_for_spec():
    calls = []

    def url(data):
        calls.append(data["HOST"])
        return "https://" + data["HOST"]

    class Service(Profile, name="factorydata", provider_type="http"):
        HOST: str = "example.test"
        URL: str = ProfileField(default_factory=url)

    assert calls == []
    assert next(p for p in Service.__spec__.parameters if p.name == "URL").default is FACTORY_DEFAULT
    assert Service().URL == "https://example.test"
    assert calls == ["example.test"]


def test_explicit_parent_fields_keep_only_effective_native_metadata():
    class Explicit(Profile):
        __spec__ = ProfileSpec(name="explicit", provider_type="db", parameters=[
            ParameterSpec(name="PORT", type=int, tier="core", default=5432, driver_key="db_port"),
            ParameterSpec(name="LOCAL", type=str, tier="core", default="private"),
        ])
        EXTRA: str = "extra"

    class Untouched(Explicit, name="untouched", provider_type="db", driver_keys="lower"):
        pass

    class Replaced(Untouched, name="replaced", provider_type="db"):
        PORT: int = ProfileField(default=6432, tier="advanced")
        EXTRA: str = ProfileField(default="extra", driver_key=None)

    assert Explicit().emit() == {"db_port": 5432}
    assert Untouched().emit() == {"db_port": 5432, "extra": "extra"}
    assert Replaced().emit() == {"port": 6432}
    assert next(p for p in Replaced.__spec__.parameters if p.name == "PORT").tier == "advanced"


def test_projection_excludes_framework_and_non_fields():
    from typing import ClassVar
    from pydantic import PrivateAttr, computed_field

    class Generated(Profile, name="membership", provider_type="db", driver_keys="lower"):
        SETTINGS_SOURCE_ENV_PREFIX: str | None = ProfileField(default=None)
        SETTINGS_APPLICATION_LABEL: str = "application"
        CLASS_LABEL: ClassVar[str] = "class"
        _private: str = PrivateAttr(default="private")

        @computed_field
        @property
        def COMPUTED(self) -> str:
            return "computed"

    assert [p.name for p in Generated.__spec__.parameters] == ["SETTINGS_APPLICATION_LABEL"]
    assert Generated().emit() == {"settings_application_label": "application"}


@pytest.mark.parametrize("option,value", [
    ("driver_key", None), ("tier", "core"), ("transform", None), ("template", None),
])
def test_framework_field_cannot_carry_profile_options(option, value):
    with pytest.raises(TypeError, match=f"Excluded.*SETTINGS_SOURCE_ENV_PREFIX.*{option}"):
        class Excluded(Profile, name="excluded", provider_type="db"):
            SETTINGS_SOURCE_ENV_PREFIX: str | None = ProfileField(default=None, **{option: value})


def test_generated_fields_require_uppercase_and_native_override_annotations():
    from pydantic import PydanticUserError

    with pytest.raises(TypeError, match="Lower.*port"):
        class Lower(Profile, name="lower", provider_type="db"):
            port: int = 5432

    class Parent(Profile, name="parent", provider_type="db"):
        PORT: int = 5432

    with pytest.raises(PydanticUserError, match="non-annotated"):
        class Invalid(Parent, name="invalid", provider_type="db"):
            PORT = 6432


@pytest.mark.parametrize("first,second", [
    ("port", "port"), ("port", {"http": "port"}),
    ({"http": "port"}, {"http": "port"}),
])
def test_duplicate_emission_keys_rejected(first, second):
    first_field = ProfileField(default=1, driver_key=first)
    second_field = ProfileField(default=2, driver_key=second)
    with pytest.raises(TypeError, match="Collision.*(FIRST|SECOND).*(key|mapping)"):
        class Collision(Profile, name="collision", provider_type="db"):
            FIRST: int = first_field
            SECOND: int = second_field


def test_disjoint_target_keys_and_mapping_ownership():
    mapping = {"http": "port"}

    class Targeted(Profile, name="targeted", provider_type="db"):
        FIRST: int = ProfileField(default=1, driver_key=mapping)
        SECOND: int = ProfileField(default=2, driver_key={"sql": "port"})

    mapping["http"] = "mutated"
    assert Targeted().emit("http") == {"port": 1}
    assert Targeted().emit("sql") == {"port": 2}
