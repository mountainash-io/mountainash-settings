# tests/unit/profiles/test_register_adapter.py
"""Unit tests for Profile.register_adapter / registered_adapters / emit_adapter."""

from __future__ import annotations

import functools

import pytest

from mountainash_settings.profiles import ParameterSpec, ProfileSpec
from mountainash_settings.profiles.profile import Profile

SPEC = ProfileSpec(
    name="reg",
    provider_type="reg",
    parameters=[ParameterSpec(name="HOST", type=str, tier="core", driver_key="host")],
)


def _adapter(profile, merged):
    """A valid 2-arg compose adapter."""
    return {**merged, "marked": True}


def _make_cls():
    """A fresh Profile subclass with no own __adapters__ (inherits the default)."""
    class _RegProfile(Profile):
        __spec__ = SPEC

    return _RegProfile


@pytest.mark.unit
class TestRegisterAdapter:
    def test_registers_and_owns_a_fresh_dict(self):
        cls = _make_cls()
        assert "__adapters__" not in cls.__dict__  # inheriting the default
        cls.register_adapter("t1", _adapter)
        assert "__adapters__" in cls.__dict__       # copy-on-write created own dict
        assert cls.__adapters__["t1"] is _adapter

    def test_copy_on_write_does_not_pollute_profile_or_siblings(self):
        sibling = _make_cls()
        cls = _make_cls()
        before = dict(Profile.__adapters__)
        cls.register_adapter("t1", _adapter)
        assert Profile.__adapters__ == before          # shared default untouched
        assert "__adapters__" not in sibling.__dict__   # sibling unaffected
        assert dict(sibling.__adapters__) == before

    def test_root_registration_rejected(self):
        before = dict(Profile.__adapters__)
        with pytest.raises(TypeError, match="concrete Profile subclass"):
            Profile.register_adapter("t1", _adapter)
        assert Profile.__adapters__ == before

    def test_non_callable_rejected(self):
        cls = _make_cls()
        with pytest.raises(TypeError, match="callable"):
            cls.register_adapter("t1", 123)

    def test_one_arg_callable_rejected(self):
        cls = _make_cls()
        with pytest.raises(TypeError, match="two positional"):
            cls.register_adapter("t1", lambda profile: {})

    def test_star_args_callable_accepted(self):
        cls = _make_cls()
        cls.register_adapter("t1", lambda *a: {})
        assert "t1" in cls.__adapters__

    def test_idempotent_same_object(self):
        cls = _make_cls()
        cls.register_adapter("t1", _adapter)
        cls.register_adapter("t1", _adapter)  # no raise
        assert cls.__adapters__["t1"] is _adapter

    def test_conflict_different_object_raises(self):
        cls = _make_cls()
        cls.register_adapter("t1", _adapter)
        with pytest.raises(ValueError, match="already has an adapter"):
            cls.register_adapter("t1", lambda p, m: m)

    def test_conflict_overwrite_replaces(self):
        cls = _make_cls()
        cls.register_adapter("t1", _adapter)

        def other(p, m):
            return m

        cls.register_adapter("t1", other, overwrite=True)
        assert cls.__adapters__["t1"] is other

    def test_partial_identity_caveat(self):
        cls = _make_cls()
        a = functools.partial(lambda p, m, x: m, x=1)
        b = functools.partial(lambda p, m, x: m, x=1)
        cls.register_adapter("t1", a)
        with pytest.raises(ValueError, match="already has an adapter"):
            cls.register_adapter("t1", b)  # distinct partial objects

    def test_uninspectable_callable_accepted(self, monkeypatch):
        # C/builtin callables where inspect.signature raises ValueError must be
        # accepted after the callable() check (spec §3.2 step 1 fallback).
        cls = _make_cls()

        def boom(_obj):
            raise ValueError("no signature for C callables")

        monkeypatch.setattr(
            "mountainash_settings.profiles.profile.inspect.signature", boom
        )
        cls.register_adapter("t1", _adapter)  # would reject if the fallback were missing
        assert cls.__adapters__["t1"] is _adapter

    def test_concurrent_conflicting_registration_serialized(self):
        # The RLock makes copy-on-write + conflict-check + insert atomic: two
        # threads racing different adapters onto the same target → exactly one
        # wins, the other sees the conflict. Without the lock both could observe
        # "absent" and insert, yielding zero errors.
        import threading

        cls = _make_cls()
        barrier = threading.Barrier(2)
        errors: list[ValueError] = []

        def a(p, m):
            return m

        def b(p, m):
            return m

        def worker(adapter):
            barrier.wait()  # maximize contention
            try:
                cls.register_adapter("t1", adapter)
            except ValueError as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=worker, args=(a,)),
            threading.Thread(target=worker, args=(b,)),
        ]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        assert len(errors) == 1                    # exactly one conflict
        assert cls.__adapters__["t1"] in (a, b)    # one winner recorded


@pytest.mark.unit
class TestRegisteredAdapters:
    def test_returns_copy_not_live_dict(self):
        cls = _make_cls()
        cls.register_adapter("t1", _adapter)
        snapshot = cls.registered_adapters()
        snapshot["t2"] = _adapter        # mutate the returned copy
        assert "t2" not in cls.__adapters__  # class map unaffected

    def test_reflects_inherited_entries(self):
        cls = _make_cls()
        # No own registration yet → reflects the inherited (empty) default.
        assert cls.registered_adapters() == dict(Profile.__adapters__)
