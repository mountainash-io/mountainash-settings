import base64
import hashlib

import pytest

from mountainash_settings.secrets import to_key_segment
from mountainash_settings.secrets.keys import _layout, _segments


def test_layout_and_full_segment_boundary():
    assert _layout("simple") == (None, "simple")
    assert _layout("domain.leaf") == ("domain", "leaf")
    assert _layout("domain.provider.user") == ("domain", "provider-user")
    for key in ("user\n", "domain.user\n", "", ".user", "domain..user", "../user"):
        with pytest.raises(ValueError) as caught:
            _segments(key)
        assert key not in str(caught.value) or key == ""


def test_encoder_preserves_addresses_and_disjoint_reserved_space():
    assert to_key_segment("ordinary_user") == "ordinary_user"
    for raw in ("person@example.com", "ordinary_user\n", "h_existing", ""):
        expected = "h_" + base64.b32encode(
            hashlib.sha256(raw.encode("utf-8")).digest()
        ).decode("ascii").rstrip("=").lower()
        encoded = to_key_segment(raw)
        assert encoded == expected
        assert _segments(encoded) == [encoded]
    assert to_key_segment("ordinary_user\n") != "ordinary_user"


def test_unencodable_identifier_is_value_free():
    with pytest.raises(ValueError) as caught:
        to_key_segment("\ud800")
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
