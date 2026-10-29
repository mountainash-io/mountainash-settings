from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from mountainash_settings.secrets import MemorySecretStore


def test_owned_records_and_rejected_write_preserve_clear_state():
    store = MemorySecretStore()
    data = {"items": [{"token": "old"}]}
    store.set("account", data)
    data["items"][0]["token"] = "caller-change"
    first = store.get("account")
    first["items"][0]["token"] = "reader-change"
    assert store.get("account") == {"items": [{"token": "old"}]}
    store.delete("account")
    with pytest.raises(ValueError):
        store.set("account", {"bad": float("nan")})
    assert store.get("account") is None
    assert store.is_cleared("account")
    store.set("account", {})
    assert store.get("account") == {}
    assert not store.is_cleared("account")


def test_transaction_is_reentrant_and_coordinates_real_contenders():
    store = MemorySecretStore()
    entered = Event()
    started = Event()

    def contender():
        started.set()
        with store.transaction("account"):
            entered.set()
            store.set("account", {"value": 2})

    with ThreadPoolExecutor(max_workers=1) as pool:
        with store.transaction("account"):
            with store.transaction("account"):
                store.set("account", {"value": 1})
            future = pool.submit(contender)
            assert started.wait(5)
            assert not entered.wait(0.1)
            assert store.get("account") == {"value": 1}
            with store.transaction("independent"):
                store.set("independent", {"value": 3})
        future.result(timeout=5)
    assert entered.is_set()
    assert store.get("account") == {"value": 2}
    assert store.get("independent") == {"value": 3}
