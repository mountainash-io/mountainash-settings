"""Unit tests for the public lookup_class_var helper."""

import pytest

from mountainash_settings.profiles.lookup import lookup_class_var


class _Base:
    __marker__ = "from_base"


class _Mid(_Base):
    pass


class _Leaf(_Mid):
    __marker__ = "from_leaf"


class _Bare:
    pass


@pytest.mark.unit
class TestLookupClassVar:
    def test_returns_own_dict_value(self):
        assert lookup_class_var(_Leaf, "__marker__") == "from_leaf"

    def test_walks_mro_to_base(self):
        assert lookup_class_var(_Mid, "__marker__") == "from_base"

    def test_returns_none_when_absent(self):
        assert lookup_class_var(_Bare, "__nonexistent__") is None

    def test_returns_first_match_in_mro_order(self):
        # _Leaf overrides — confirms it's the leaf's value, not the base's
        assert lookup_class_var(_Leaf, "__marker__") != "from_base"
