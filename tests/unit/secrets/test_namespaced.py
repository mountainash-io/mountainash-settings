from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from mountainash_settings.secrets import MemorySecretStore, NamespacedSecretStore


def test_views_isolate_records_markers_and_validate_before_mutation():
    inner = MemorySecretStore()
    oauth = NamespacedSecretStore(inner, "oauth")
    config = NamespacedSecretStore(inner, "config")
    oauth.set("provider.user", {"token": "one"})
    config.set("provider.user", {"token": "two"})
    oauth.delete("provider.user")
    assert inner.get("oauth.provider.user") is None
    assert inner.is_cleared("oauth.provider.user")
    assert config.get("provider.user") == {"token": "two"}
    with pytest.raises(ValueError):
        oauth.set("provider.user\n", {"token": "bad"})
    with pytest.raises(ValueError):
        NamespacedSecretStore(inner, "oauth.")
    assert inner.get("oauth.provider.user") is None
    del oauth
    inner.set("oauth.provider.user", {"token": "still-owned"})
    assert inner.get("oauth.provider.user") == {"token": "still-owned"}


def test_view_and_base_coordinate_the_same_actual_key():
    inner = MemorySecretStore()
    view = NamespacedSecretStore(inner, "oauth")
    started, entered = Event(), Event()

    def contender():
        started.set()
        with inner.transaction("oauth.user"):
            entered.set()
            inner.set("oauth.user", {"value": 2})

    with ThreadPoolExecutor(max_workers=1) as pool:
        with view.transaction("user"):
            view.set("user", {"value": 1})
            future = pool.submit(contender)
            assert started.wait(5)
            assert not entered.wait(0.1)
            assert view.get("user") == {"value": 1}
        future.result(timeout=5)
    assert entered.is_set()
    assert view.get("user") == {"value": 2}
