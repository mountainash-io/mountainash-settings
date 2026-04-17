# tests/unit/profiles/test_registry.py
"""Unit tests for the Registry class."""

import pytest

from mountainash_settings.auth import NoAuth
from mountainash_settings.profiles.descriptor import ProfileDescriptor
from mountainash_settings.profiles.registry import Registry


def _make_desc(name: str) -> ProfileDescriptor:
    return ProfileDescriptor(
        name=name, provider_type=name, parameters=[], auth_modes=[NoAuth],
    )


@pytest.mark.unit
class TestRegistry:
    def test_register_inserts(self):
        reg = Registry("test")
        desc = _make_desc("foo")

        register = reg.decorator()

        @register(desc)
        class Foo:
            pass

        assert "foo" in reg
        assert reg.get_descriptor("foo") is desc
        assert reg.get_settings_class("foo") is Foo

    def test_duplicate_raises(self):
        reg = Registry("test")
        desc1 = _make_desc("dup")
        desc2 = _make_desc("dup")
        register = reg.decorator()

        @register(desc1)
        class First:
            pass

        with pytest.raises(ValueError, match="already registered"):
            @register(desc2)
            class Second:
                pass

    def test_get_descriptor_unknown_hints(self):
        reg = Registry("storage")
        desc = _make_desc("s3")
        register = reg.decorator()

        @register(desc)
        class S3:
            pass

        with pytest.raises(KeyError, match="Known: s3"):
            reg.get_descriptor("not_a_real_one")

    def test_get_settings_class_unknown_hints(self):
        reg = Registry("storage")
        with pytest.raises(KeyError, match="Known: <none>"):
            reg.get_settings_class("nope")

    def test_duplicate_does_not_pollute_classes(self):
        reg = Registry("test")
        desc1 = _make_desc("inv")
        desc2 = _make_desc("inv")
        register = reg.decorator()

        @register(desc1)
        class First:
            pass

        with pytest.raises(ValueError):
            @register(desc2)
            class Second:
                pass

        assert reg.get_settings_class("inv") is First
        assert reg.get_descriptor("inv") is desc1

    def test_snapshot_and_reset(self):
        reg = Registry("t")
        desc = _make_desc("x")
        reg.decorator()(desc)(type("X", (), {}))
        snap = reg._snapshot_for_tests()

        reg.decorator()(_make_desc("y"))(type("Y", (), {}))
        assert "y" in reg

        reg._reset_for_tests(*snap)
        assert "y" not in reg
        assert "x" in reg

    def test_descriptors_view_is_copy(self):
        reg = Registry("t")
        desc = _make_desc("a")
        reg.decorator()(desc)(type("A", (), {}))

        view = reg.descriptors
        view["fake"] = desc  # mutating the view does not affect the registry
        assert "fake" not in reg
