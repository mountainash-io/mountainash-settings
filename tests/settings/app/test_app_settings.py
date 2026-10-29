from datetime import datetime
from typing import ClassVar, Literal

import pytest
from pydantic import Field, field_validator

from mountainash_settings import SettingsParameters
from mountainash_settings.settings.app.app_settings import AppSettings
from mountainash_settings.settings.app.app_settings_templates import AppSettingsTemplates
from mountainash_settings.settings_cache.settings_manager import SettingsManager


class CustomTemplates(AppSettingsTemplates):
    RUNDATETIME_TEMPLATE: str = "{RUNDATE}/{RUNTIME}"


class TestAppSettings:

    def test_initialization_with_defaults_succeeds(self):
        settings = AppSettings()
        assert settings.DEBUG is False
        assert settings.LOCALE_TIMEZONE == "UTC"
        # assert settings.PLATFORM_SLASH is not None

    def test_pandera_framework_field_exists(self, pandas_app_settings):
        """Test that the Pandas framework field exists and has correct default."""
        assert hasattr(pandas_app_settings, 'PANDERA_DATAFRAME_FRAMEWORK')
        assert pandas_app_settings.PANDERA_DATAFRAME_FRAMEWORK == "pandas"

    def test_initialization_with_config_files_accepts_single_file(self, temp_yaml_file):
        settings = AppSettings(config_files=temp_yaml_file)
        assert settings.DEBUG is True
        assert settings.LOCALE_TIMEZONE == "EST"

    def test_initialization_with_config_files_accepts_list(self, temp_multiple_yaml_files):
        class OrderedApp(AppSettings):
            OVERRIDE_SETTING: str = "default"

        settings = OrderedApp(config_files=temp_multiple_yaml_files)
        assert settings.DEBUG is True
        assert settings.OVERRIDE_SETTING == "from_secondary"

    def test_initialization_with_settings_parameters_succeeds(self):
        params = SettingsParameters.create(DEBUG=True, LOCALE_TIMEZONE="EST")
        settings = AppSettings(settings_parameters=params)
        assert settings.DEBUG is True
        assert settings.LOCALE_TIMEZONE == "EST"

    def test_initialization_with_kwargs_succeeds(self):
        settings = AppSettings(DEBUG=True, LOCALE_TIMEZONE="EST")
        assert settings.DEBUG is True
        assert settings.LOCALE_TIMEZONE == "EST"

    def test_direct_timestamp_defaults_capture_one_instant(self, app_clock):
        app_clock.append(datetime(2032, 1, 1, 0, 0, 1))
        first = AppSettings()
        second = AppSettings()
        assert (first.RUNDATE, first.RUNTIME, first.RUNDATETIME) == (
            "20311231", "235959", "20311231T235959",
        )
        assert (second.RUNDATE, second.RUNTIME, second.RUNDATETIME) == (
            "20320101", "000001", "20320101T000001",
        )

    def test_post_init_initializes_rundatetime_from_template(self):
        settings = AppSettings(RUNDATE="20240115", RUNTIME="143045")

        # Call post_init and verify RUNDATETIME is set
        settings.post_init()

        assert settings.RUNDATETIME == "20240115T143045"

def test_cached_timestamp_survives_overrides_and_reinitialization(app_clock, isolated_settings_manager):
    manager = isolated_settings_manager
    params = SettingsParameters.create(settings_class=AppSettings)
    overridden = manager.get_or_create_settings(
        SettingsParameters.create(settings_class=AppSettings, RUNDATE="19990101")
    )
    assert (overridden.RUNDATE, overridden.RUNTIME, overridden.RUNDATETIME) == (
        "19990101", "235959", "19990101T235959",
    )
    app_clock[0] = datetime(2032, 1, 1, 0, 0, 1)
    ordinary = manager.get_or_create_settings(params)
    refreshed = manager.get_or_create_settings(params, reinitialise=True)
    for result in (ordinary, refreshed):
        assert (result.RUNDATE, result.RUNTIME, result.RUNDATETIME) == (
            "20311231", "235959", "20311231T235959",
        )
    assert refreshed is not ordinary
    independent = SettingsManager().get_or_create_settings(params)
    assert (independent.RUNDATE, independent.RUNTIME) == ("20320101", "000001")


def test_timestamp_defaults_belong_to_context_not_manager(app_clock, monkeypatch, isolated_settings_manager):
    params = [SettingsParameters.create(settings_class=AppSettings, env_prefix=prefix)
              for prefix in ("CLOCK_FIRST_", "CLOCK_SECOND_")]
    for prefix in ("CLOCK_FIRST_", "CLOCK_SECOND_"):
        for field in ("RUNDATE", "RUNTIME", "RUNDATETIME"):
            monkeypatch.delenv(prefix + field, raising=False)
    first = isolated_settings_manager.get_or_create_settings(params[0])
    app_clock[0] = datetime(2032, 1, 1, 0, 0, 1)
    second = isolated_settings_manager.get_or_create_settings(params[1])
    again = isolated_settings_manager.get_or_create_settings(params[0])
    assert (first.RUNDATE, first.RUNTIME) == ("20311231", "235959")
    assert (second.RUNDATE, second.RUNTIME) == ("20320101", "000001")
    assert (again.RUNDATE, again.RUNTIME) == ("20311231", "235959")


@pytest.mark.parametrize("cached", [False, True], ids=["direct", "cached"])
@pytest.mark.parametrize("source, expected", [
    ("yaml", ("20010203", "040506", "20010203T040506")),
    ("env", ("20040506", "070809", "20040506T070809")),
    ("date", ("19990101", "235959", "19990101T235959")),
    ("time", ("20311231", "112233", "20311231T112233")),
    ("explicit", ("20311231", "235959", "chosen")),
])
def test_timestamp_source_precedence(cached, source, expected, app_clock, monkeypatch,
                                     create_config_file, isolated_settings_manager):
    kwargs = {}
    files = None
    if source in ("yaml", "env"):
        files = create_config_file("yaml", {"RUNDATE": "20010203", "RUNTIME": "040506"})
    if source == "env":
        monkeypatch.setenv("CLOCK_RUNDATE", "20040506")
        monkeypatch.setenv("CLOCK_RUNTIME", "070809")
    elif source == "date":
        kwargs = {"RUNDATE": "19990101"}
    elif source == "time":
        kwargs = {"RUNTIME": "112233"}
    elif source == "explicit":
        kwargs = {"RUNDATETIME": "chosen"}
    params = SettingsParameters.create(settings_class=AppSettings, config_files=files,
                                       env_prefix="CLOCK_", **kwargs)
    result = (isolated_settings_manager.get_or_create_settings(params) if cached
              else AppSettings(settings_parameters=params))
    assert (result.RUNDATE, result.RUNTIME, result.RUNDATETIME) == expected


def test_reinitialization_uses_effective_fields_and_preserves_runtime_value(app_clock, isolated_settings_manager):
    manager = isolated_settings_manager
    manager.get_or_create_settings(SettingsParameters.create(settings_class=AppSettings))
    params = SettingsParameters.create(settings_class=AppSettings, RUNTIME="112233")
    unchanged = manager.get_or_create_settings(params)
    refreshed = manager.get_or_create_settings(params, reinitialise=True)
    explicit = manager.get_or_create_settings(
        SettingsParameters.create(settings_class=AppSettings, RUNTIME="112233", RUNDATETIME="chosen"),
        reinitialise=True,
    )
    assert unchanged.RUNDATETIME == "20311231T235959"
    assert refreshed.RUNDATETIME == "20311231T112233"
    assert explicit.RUNDATETIME == "chosen"


def test_custom_timestamp_template(app_clock):
    result = AppSettings(template_settings_parameters=SettingsParameters.create(settings_class=CustomTemplates))
    assert result.RUNDATETIME == "20311231/235959"


@pytest.mark.parametrize("cached", [False, True], ids=["direct", "cached"])
def test_timestamp_subclass_defaults_alias_and_validation(cached, app_clock, isolated_settings_manager):
    seen = []

    class SpecializedApp(AppSettings):
        RUNDATE: str = "19800101"
        RUNTIME: str = Field(default="010203", validation_alias="clock_time")

        @field_validator("RUNTIME")
        @classmethod
        def observe_time(cls, value):
            seen.append(value)
            return value

    params = SettingsParameters.create(settings_class=SpecializedApp, clock_time="040506")
    result = (isolated_settings_manager.get_or_create_settings(params) if cached
              else SpecializedApp(settings_parameters=params))
    assert (result.RUNDATE, result.RUNTIME, result.RUNDATETIME) == (
        "19800101", "040506", "19800101T040506",
    )
    assert seen == ["040506"]


def test_nested_direct_construction_does_not_borrow_cache_defaults(app_clock, isolated_settings_manager):
    nested = []
    constructing = False

    class NestedApp(AppSettings):
        def post_init(self, **kwargs):
            nonlocal constructing
            if not constructing:
                constructing = True
                try:
                    app_clock[0] = datetime(2032, 1, 1, 0, 0, 1)
                    nested.append(type(self)())
                finally:
                    constructing = False
            super().post_init(**kwargs)

    outer = isolated_settings_manager.get_or_create_settings(SettingsParameters.create(settings_class=NestedApp))
    assert (outer.RUNDATE, outer.RUNTIME) == ("20311231", "235959")
    assert (nested[0].RUNDATE, nested[0].RUNTIME) == ("20320101", "000001")


def test_timestamp_policy_is_inherited_class_configuration(app_clock):
    class Child(AppSettings):
        pass

    result = Child(RUN_TIMESTAMP_SCOPE="process")
    assert Child.RUN_TIMESTAMP_SCOPE == "context"
    assert "RUN_TIMESTAMP_SCOPE" not in Child.model_fields
    assert "RUN_TIMESTAMP_SCOPE" not in result.model_dump()
    app_clock[0] = datetime(2032, 1, 1, 0, 0, 1)
    assert Child().RUNDATE == "20320101"


@pytest.mark.parametrize("cached", [False, True], ids=["direct", "cached"])
def test_invalid_timestamp_policy_rejected(cached, isolated_settings_manager):
    class InvalidApp(AppSettings):
        RUN_TIMESTAMP_SCOPE: ClassVar[Literal["context", "process"]] = "invalid"

    with pytest.raises(ValueError, match="RUN_TIMESTAMP_SCOPE"):
        if cached:
            isolated_settings_manager.get_or_create_settings(SettingsParameters.create(settings_class=InvalidApp))
        else:
            InvalidApp()


def test_default_capture_failure_releases_waiter_and_retries(app_clock, monkeypatch, isolated_settings_manager, capture_signals):
    from concurrent.futures import ThreadPoolExecutor

    from mountainash_settings.settings.app import _timestamps

    entered, release, waiting = capture_signals
    completed = []

    class ObservedApp(AppSettings):
        def post_init(self, **kwargs):
            super().post_init(**kwargs)
            completed.append((self.RUNDATE, self.RUNTIME))

    def failing_clock():
        entered.set()
        assert release.wait(5), "clock release timed out"
        raise ValueError("timestamp-capture-probe")

    monkeypatch.setattr(_timestamps, "_now", failing_clock)
    manager = isolated_settings_manager
    params = SettingsParameters.create(settings_class=ObservedApp)
    with ThreadPoolExecutor(max_workers=2) as pool:
        try:
            owner = pool.submit(manager.get_or_create_settings, params)
            assert entered.wait(5), "default capture was not reached"
            waiter = pool.submit(manager.get_or_create_settings, params)
            assert waiting.wait(5), "contender never reached the wait boundary"
            release.set()
            with pytest.raises(ValueError, match="timestamp-capture-probe"):
                owner.result(timeout=5)
            with pytest.raises(ValueError, match="capture failed"):
                waiter.result(timeout=5)
        finally:
            release.set()
    assert not manager.is_initialised(params)
    assert completed == []
    with pytest.raises(ValueError, match="not initialised"):
        manager.get_settings_object(params)
    monkeypatch.setattr(_timestamps, "_now", lambda: datetime(2032, 1, 1, 0, 0, 1))
    retried = manager.get_or_create_settings(params)
    assert manager.is_initialised(params)
    assert (retried.RUNDATE, retried.RUNTIME) == ("20320101", "000001")
    monkeypatch.setattr(_timestamps, "_now", lambda: datetime(2033, 1, 1, 0, 0, 2))
    again = manager.get_or_create_settings(params)
    assert (again.RUNDATE, again.RUNTIME) == ("20320101", "000001")
    assert completed == [("20320101", "000001"), ("20320101", "000001")]
