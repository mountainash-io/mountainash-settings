"""Generated specs become admissible only after concrete model completion."""

from functools import partial

import pytest
from pydantic import BaseModel
from pydantic_settings import SettingsConfigDict

from mountainash_settings import (
    Profile, ProfileField, ProfileSpec, Registry, SettingsParameters,
    get_settings, lookup_class_var,
)


@pytest.mark.parametrize("state", ["intermediate", "unresolved", "deferred"])
@pytest.mark.parametrize("route", ["direct", "public", "manager", "registry"])
def test_incomplete_profile_rejected_before_source_capture(state, route, isolated_settings_manager):
    class Parent(Profile, name="parent", provider_type="example"):
        HOST: str = "localhost"

        @classmethod
        def settings_capture_sources(cls, sources):
            raise AssertionError("source capture before admission")

    if state == "intermediate":
        class Child(Parent):
            pass
    elif state == "unresolved":
        class Child(Parent, name="child", provider_type="example"):
            PAYLOAD: "PayloadNotYetDeclared"
    else:
        class Child(Parent, name="child", provider_type="example"):
            model_config = SettingsConfigDict(defer_build=True)

    assert Child.__spec__ is None
    assert lookup_class_var(Child, "__spec__") is None
    params = SettingsParameters.create(settings_class=Child)
    message = "intermediate" if state == "intermediate" else "incomplete"
    if route == "direct":
        invoke = Child
    elif route == "public":
        invoke = partial(get_settings, settings_parameters=params)
    elif route == "manager":
        invoke = partial(isolated_settings_manager.get_or_create_settings, params)
    else:
        register = Registry("incomplete").decorator()
        invoke = partial(register, Child)
    with pytest.raises(TypeError, match=f"Child.*{message}"):
        invoke()
    assert not isolated_settings_manager.is_initialised(params)


def test_forward_completion_publishes_owned_spec_and_preserves_identity(isolated_settings_manager):
    class Parent(Profile, name="parent", provider_type="example", driver_keys="lower"):
        HOST: str = ProfileField(default="localhost", driver_key="server")

    class Child(Parent, name="child", provider_type="example"):
        PAYLOAD: "PayloadForCompletionProbe" = ProfileField(driver_key=None)

    assert Child.__spec__ is None

    class PayloadForCompletionProbe(BaseModel):
        VALUE: int

    assert Child.model_rebuild(_types_namespace={"PayloadForCompletionProbe": PayloadForCompletionProbe}) is True
    spec = Child.__spec__
    assert spec is not None
    assert spec is not Parent.__spec__
    assert lookup_class_var(Child, "__spec__") is spec
    assert [p.name for p in spec.parameters] == ["HOST", "PAYLOAD"]
    Child.model_rebuild(force=True)
    assert Child.__spec__ is spec
    registry = Registry("completion")
    registry.decorator()(Child)
    Child.model_rebuild(force=True)
    assert Child.__spec__ is spec
    assert registry.get_spec("child") is spec
    assert Child(PAYLOAD={"VALUE": 1}).emit() == {"server": "localhost"}
    params = SettingsParameters.create(settings_class=Child, PAYLOAD={"VALUE": 2})
    assert isolated_settings_manager.get_or_create_settings(params).PAYLOAD.VALUE == 2
    wrong_registry = Registry("wrong")
    other_spec = ProfileSpec(name="other", provider_type="example", parameters=[])
    with pytest.raises(TypeError, match="published"):
        wrong_registry.register(other_spec, Child)


def test_deferred_generated_profile_requires_explicit_rebuild():
    class Deferred(Profile, name="deferred", provider_type="db"):
        model_config = SettingsConfigDict(defer_build=True)
        PORT: int = 5432

    assert Deferred.__spec__ is None
    with pytest.raises(TypeError, match="Deferred.*incomplete.*model_rebuild"):
        Deferred()
    Deferred.model_rebuild()
    assert Deferred.__spec__.name == "deferred"
    assert Deferred().PORT == 5432


def test_rebuild_retains_caller_namespace_resolution():
    class Delayed(Profile, name="delayed", provider_type="db"):
        VALUE: "LaterLocalType"

    LaterLocalType = int
    Delayed.model_rebuild()
    assert Delayed(VALUE="42").VALUE == 42


def test_class_creation_resolves_existing_local_type_without_rebuild():
    LocalPayload = int

    class Ready(Profile, name="ready", provider_type="db"):
        VALUE: "LocalPayload"

    assert Ready.__spec__ is not None
    assert Ready(VALUE="42").VALUE == 42


def test_explicit_intermediate_remains_constructible():
    class Intermediate(Profile):
        VALUE: int = 1

    assert Intermediate().VALUE == 1
