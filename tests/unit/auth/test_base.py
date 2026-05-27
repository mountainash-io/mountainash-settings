"""Sanity-check the AuthSpec base class."""

import pytest

from mountainash_auth_client import AuthSpec


@pytest.mark.unit
def test_authspec_is_frozen():
    class Dummy(AuthSpec):
        pass

    d = Dummy()
    with pytest.raises(Exception):  # FrozenInstanceError/ValidationError
        d.anything = 1  # type: ignore


@pytest.mark.unit
def test_authspec_rejects_extras():
    class Dummy(AuthSpec):
        pass

    with pytest.raises(Exception):
        Dummy(extra_field="nope")  # type: ignore
