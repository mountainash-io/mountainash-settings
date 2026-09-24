import pytest

from mountainash_settings.resolve import resolve_references_in_dict
from mountainash_settings.secrets import SecretCapabilityError


class _Reader:
    def __init__(self, records):
        self.records = records
    def get(self, key):
        return self.records.get(key)


@pytest.mark.unit
def test_reader_only_store_resolves():
    out = resolve_references_in_dict({"P": "secret:db.password"}, _Reader({"db": {"password": "pw"}}))
    assert out == {"P": "pw"}


@pytest.mark.unit
def test_reference_without_store_fails_value_free():
    with pytest.raises(SecretCapabilityError) as info:
        resolve_references_in_dict({"P": "secret:db.password"}, None)
    assert "db" not in str(info.value)
    assert info.value.__cause__ is None and info.value.__context__ is None
    assert info.value.__suppress_context__ is True


@pytest.mark.unit
def test_no_reference_without_store_is_untouched():
    assert resolve_references_in_dict({"P": "plain"}, None) == {"P": "plain"}


@pytest.mark.unit
def test_missing_field_is_keyerror():
    with pytest.raises(KeyError):
        resolve_references_in_dict({"P": "secret:db.nope"}, _Reader({"db": {"password": "pw"}}))


from pydantic import Field
from mountainash_settings import MountainAshBaseSettings, SettingsParameters, get_settings


@pytest.fixture(autouse=True)
def _fresh_settings_manager(monkeypatch):
    from mountainash_settings.settings_cache import settings_functions
    fresh = SettingsManager()
    monkeypatch.setattr(settings_functions, "_SETTINGS_MANAGER", fresh, raising=False)
    yield


from mountainash_settings.settings_cache.settings_manager import SettingsManager


class _StoreSettings(MountainAshBaseSettings):
    PASSWORD: str = Field(default="unset")


class _FalseyReader(_Reader):
    def __bool__(self):
        return False


class _HostileReader(_Reader):
    def __eq__(self, other):
        raise AssertionError("store __eq__ called")
    def __hash__(self):
        raise AssertionError("store __hash__ called")


def _params(store, **kw):
    return SettingsParameters.create(settings_class=_StoreSettings, secret_store=store, **kw)


@pytest.mark.unit
def test_two_equal_content_stores_never_share_a_cache_entry():
    a = _Reader({"db": {"password": "a"}}); b = _Reader({"db": {"password": "b"}})
    assert get_settings(settings_parameters=_params(a, PASSWORD="secret:db.password")).PASSWORD == "a"
    assert get_settings(settings_parameters=_params(b, PASSWORD="secret:db.password")).PASSWORD == "b"


@pytest.mark.unit
def test_runtime_reference_resolves_fresh_each_call():
    store = _Reader({"db": {"password": "first"}})
    assert get_settings(settings_parameters=_params(store, PASSWORD="secret:db.password")).PASSWORD == "first"
    store.records["db"]["password"] = "second"
    assert get_settings(settings_parameters=_params(store, PASSWORD="secret:db.password")).PASSWORD == "second"


@pytest.mark.unit
def test_falsey_store_still_resolves():
    store = _FalseyReader({"db": {"password": "pw"}})
    assert get_settings(settings_parameters=_params(store, PASSWORD="secret:db.password")).PASSWORD == "pw"


@pytest.mark.unit
def test_hostile_store_methods_not_called_by_cache():
    store = _HostileReader({"db": {"password": "pw"}})
    assert get_settings(settings_parameters=_params(store, PASSWORD="secret:db.password")).PASSWORD == "pw"
    assert get_settings(settings_parameters=_params(store)).PASSWORD == "unset"


@pytest.mark.unit
def test_cached_reference_without_store_fails():
    with pytest.raises(SecretCapabilityError):
        get_settings(settings_parameters=_params(None, PASSWORD="secret:db.password"))


@pytest.mark.unit
def test_direct_construction_binds_store():
    store = _Reader({"db": {"password": "pw"}})
    s = _StoreSettings(PASSWORD="secret:db.password", secret_store=store)
    assert s.PASSWORD == "pw"
    assert "secret_store" not in s.model_dump()
    assert "_Reader" not in repr(s)


@pytest.mark.unit
def test_extract_preserves_store_identity():
    store = _Reader({"db": {"password": "pw"}})
    s = _StoreSettings(PASSWORD="secret:db.password", secret_store=store)
    assert s.extract_settings_parameters().secret_store is store


@pytest.mark.unit
def test_cached_instance_extract_preserves_store_identity():
    store = _Reader({})
    s = get_settings(settings_parameters=_params(store))
    assert s.extract_settings_parameters().secret_store is store
