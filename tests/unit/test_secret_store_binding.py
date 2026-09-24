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
