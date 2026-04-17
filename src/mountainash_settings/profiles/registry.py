# src/mountainash_settings/profiles/registry.py
"""Per-domain registry of profile descriptors and settings classes.

Each consumer domain instantiates one :class:`Registry` with a name (used in
error messages and test IDs). Example::

    DATABASES_REGISTRY = Registry("databases")
    register = DATABASES_REGISTRY.decorator()

    @register(POSTGRESQL_DESCRIPTOR)
    class PostgreSQLAuthSettings(ConnectionProfile):
        __descriptor__ = POSTGRESQL_DESCRIPTOR
"""

from __future__ import annotations

import typing as t

from .descriptor import ProfileDescriptor

if t.TYPE_CHECKING:
    from .profile import DescriptorProfile

__all__ = ["Registry"]


T = t.TypeVar("T", bound="DescriptorProfile")


class Registry:
    """Mutable, name-keyed store of descriptors + their settings classes."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._descriptors: dict[str, ProfileDescriptor] = {}
        self._classes: dict[str, type["DescriptorProfile"]] = {}

    def __len__(self) -> int:
        return len(self._descriptors)

    def __contains__(self, name: str) -> bool:
        return name in self._descriptors

    @property
    def descriptors(self) -> dict[str, ProfileDescriptor]:
        """Read-only view of the descriptor dict."""
        return dict(self._descriptors)

    def register(
        self,
        descriptor: ProfileDescriptor,
        cls: type["DescriptorProfile"],
    ) -> None:
        """Register ``cls`` under ``descriptor.name``.

        Raises:
            ValueError: if ``descriptor.name`` is already registered.
        """
        if descriptor.name in self._descriptors:
            existing = self._classes.get(descriptor.name)
            where = (
                f"{existing.__module__}.{existing.__qualname__}"
                if existing is not None
                else "<unknown class>"
            )
            raise ValueError(
                f"Profile {descriptor.name!r} is already registered "
                f"in {self.name} registry by {where}"
            )
        self._descriptors[descriptor.name] = descriptor
        self._classes[descriptor.name] = cls
        cls.__descriptor__ = descriptor  # belt-and-braces

    def decorator(
        self,
    ) -> t.Callable[[ProfileDescriptor], t.Callable[[type[T]], type[T]]]:
        """Return a bound ``@register(descriptor)`` class decorator."""

        def _factory(descriptor: ProfileDescriptor) -> t.Callable[[type[T]], type[T]]:
            def _wrap(cls: type[T]) -> type[T]:
                self.register(descriptor, cls)
                return cls
            return _wrap

        return _factory

    def get_descriptor(self, name: str) -> ProfileDescriptor:
        """Return the descriptor for ``name``.

        Raises:
            KeyError: with a hint listing known names.
        """
        try:
            return self._descriptors[name]
        except KeyError:
            known = ", ".join(sorted(self._descriptors)) or "<none>"
            raise KeyError(
                f"No profile registered under {name!r} in {self.name} "
                f"registry. Known: {known}"
            ) from None

    def get_settings_class(self, name: str) -> type["DescriptorProfile"]:
        """Return the settings class for ``name``.

        Raises:
            KeyError: with a hint listing known names.
        """
        try:
            return self._classes[name]
        except KeyError:
            known = ", ".join(sorted(self._classes)) or "<none>"
            raise KeyError(
                f"No settings class registered under {name!r} in "
                f"{self.name} registry. Known: {known}"
            ) from None

    # --- Test seams ---------------------------------------------------------

    def _snapshot_for_tests(
        self,
    ) -> tuple[
        dict[str, ProfileDescriptor],
        dict[str, type["DescriptorProfile"]],
    ]:
        """Snapshot for later :meth:`_reset_for_tests` restore."""
        return self._descriptors.copy(), self._classes.copy()

    def _reset_for_tests(
        self,
        descriptors_snapshot: dict[str, ProfileDescriptor],
        classes_snapshot: dict[str, type["DescriptorProfile"]],
    ) -> None:
        """Restore descriptors + classes dicts to snapshots (test-only)."""
        self._descriptors.clear()
        self._descriptors.update(descriptors_snapshot)
        self._classes.clear()
        self._classes.update(classes_snapshot)
