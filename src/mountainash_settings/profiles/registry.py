# src/mountainash_settings/profiles/registry.py
"""Per-domain registry of profile specs and settings classes.

Each consumer domain instantiates one :class:`Registry`. The optional
``spec_type`` and ``profile_type`` keyword arguments lock in a typed
contract: only specs that subclass ``spec_type`` and classes that subclass
``profile_type`` can be registered.

Example::

    DATABASES_REGISTRY = Registry(
        "databases",
        spec_type=BackendSpec,
        profile_type=ConnectionProfile,
    )
    register = DATABASES_REGISTRY.decorator()

    @register
    class PostgreSQLAuthSettings(ConnectionProfile):
        __spec__ = POSTGRESQL_SPEC
"""

from __future__ import annotations

import typing as t

from .spec import ProfileSpec

if t.TYPE_CHECKING:
    from .profile import Profile

__all__ = ["Registry"]


T = t.TypeVar("T", bound="Profile")


class Registry:
    """Mutable, name-keyed store of specs + their profile classes."""

    def __init__(
        self,
        name: str,
        *,
        spec_type: type[ProfileSpec] | None = None,
        profile_type: type | None = None,
    ) -> None:
        """Construct a Registry with optional type constraints.

        Args:
            name: Registry name (used in error messages and test IDs).
            spec_type: Required base class for registered specs. When
                ``None`` (the default), any spec-like object is accepted,
                preserving backwards compatibility. Passing ``ProfileSpec`` or
                a stricter subclass enforces an ``isinstance`` check in
                ``register()``.
            profile_type: Required base class for registered profile classes.
                When ``None`` (the default), any class is accepted. Passing
                ``Profile`` or a stricter subclass enforces an ``issubclass``
                check in ``register()``.
        """
        self.name = name
        self._spec_type = spec_type
        self._profile_type = profile_type
        self._descriptors: dict[str, ProfileSpec] = {}
        self._classes: dict[str, type["Profile"]] = {}

    def __len__(self) -> int:
        return len(self._descriptors)

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name in self._descriptors

    @property
    def descriptors(self) -> dict[str, ProfileSpec]:
        """Read-only view of the spec dict.

        Named ``descriptors`` for backwards compatibility with the pre-rename
        ``Registry`` API; returns ``ProfileSpec`` instances.
        """
        return dict(self._descriptors)

    def register(
        self,
        spec: ProfileSpec,
        cls: type["Profile"],
    ) -> None:
        """Register ``cls`` under ``spec.name``.

        Validates ``spec`` against the registry's ``spec_type`` and ``cls``
        against the registry's ``profile_type``. Sets ``cls.__spec__`` and,
        during the 26.5.x deprecation window, also mirrors to
        ``cls.__descriptor__`` so downstream code reading the old attribute
        continues to work until 26.6.0.

        Raises:
            TypeError: if ``spec`` is not an instance of ``self._spec_type``
                or ``cls`` is not a subclass of ``self._profile_type``.
            ValueError: if ``spec.name`` is already registered.
        """
        if self._spec_type is not None and not isinstance(spec, self._spec_type):
            raise TypeError(
                f"Registry {self.name!r}: spec_type mismatch — expected "
                f"{self._spec_type.__name__}, got {type(spec).__name__}"
            )
        if self._profile_type is not None and not issubclass(cls, self._profile_type):
            raise TypeError(
                f"Registry {self.name!r}: profile_type mismatch — expected "
                f"a subclass of {self._profile_type.__name__}, got "
                f"{cls.__name__} (MRO does not include "
                f"{self._profile_type.__name__})"
            )
        if spec.name in self._descriptors:
            existing = self._classes.get(spec.name)
            where = (
                f"{existing.__module__}.{existing.__qualname__}"
                if existing is not None
                else "<unknown class>"
            )
            raise ValueError(
                f"Profile {spec.name!r} is already registered "
                f"in {self.name} registry by {where}"
            )
        self._descriptors[spec.name] = spec
        self._classes[spec.name] = cls
        cls.__spec__ = spec
        # Deprecation-window mirror: downstream readers of cls.__descriptor__
        # continue to see the spec until the 26.6.0 removal. Dropped in 26.6.0.
        cls.__descriptor__ = spec

    def decorator(
        self,
    ) -> t.Callable[..., t.Any]:
        """Return a ``@register`` decorator bound to this registry.

        Supports two call shapes:

        - Bare ``@register`` (canonical from 26.5.0): reads ``cls.__spec__``
          and registers under its name.
        - ``@register(spec)`` (deprecated): emits ``DeprecationWarning``;
          validates the argument matches ``cls.__spec__`` if declared.

        Disambiguation: the bare form is detected by ``isinstance(arg, type)``
        because Python passes the decorated class directly. The with-spec
        form is detected by ``isinstance(arg, ProfileSpec)``.
        """
        import warnings as _warnings

        # Import ProfileDescriptor lazily to avoid circular imports; it is the
        # pre-rename name for ProfileSpec (Task 8 will make it a true alias).
        try:
            from .descriptor import ProfileDescriptor as _ProfileDescriptor
        except ImportError:
            _ProfileDescriptor = None  # type: ignore[assignment,misc]

        def _outer(arg: t.Any) -> t.Any:
            # Bare form: the decorator was applied without arguments, so
            # Python passes the class itself as `arg`.
            if isinstance(arg, type):
                cls = arg
                spec = cls.__dict__.get("__spec__")
                if spec is None:
                    raise TypeError(
                        f"{cls.__name__} has no '__spec__' attribute declared. "
                        f"Use `@register` only on classes that declare "
                        f"`__spec__ = <YOUR_SPEC>` in their body."
                    )
                self.register(spec, cls)
                return cls

            # With-spec form (deprecated). Accept both ProfileSpec and
            # ProfileDescriptor (the pre-rename alias) during the 26.5.x window.
            _spec_types = (ProfileSpec,) if _ProfileDescriptor is None else (ProfileSpec, _ProfileDescriptor)
            if isinstance(arg, _spec_types):
                spec = arg
                _warnings.warn(
                    "@register(spec) is deprecated. Use '@register' "
                    "(no argument); the spec will be read from the "
                    "class's __spec__ attribute. Removed in 26.6.0.",
                    DeprecationWarning, stacklevel=2,
                )

                def _wrap(cls: type[T]) -> type[T]:
                    body_spec = cls.__dict__.get("__spec__")
                    if body_spec is not None and body_spec is not spec:
                        raise TypeError(
                            f"{cls.__name__}: @register(spec) and "
                            f"class-body __spec__ disagree: "
                            f"{spec!r} vs {body_spec!r}"
                        )
                    self.register(spec, cls)
                    return cls

                return _wrap

            raise TypeError(
                f"@register expected either no arguments (the class) or a "
                f"ProfileSpec instance, got {type(arg).__name__}"
            )

        return _outer

    def get_descriptor(self, name: str) -> ProfileSpec:
        """Return the spec for ``name``.

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

    def get_settings_class(self, name: str) -> type["Profile"]:
        """Return the profile class for ``name``.

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
    ) -> tuple[dict[str, ProfileSpec], dict[str, type["Profile"]]]:
        """Snapshot for later :meth:`_reset_for_tests` restore."""
        return self._descriptors.copy(), self._classes.copy()

    def _reset_for_tests(
        self,
        descriptors_snapshot: dict[str, ProfileSpec],
        classes_snapshot: dict[str, type["Profile"]],
    ) -> None:
        """Restore descriptors + classes dicts to snapshots (test-only)."""
        self._descriptors.clear()
        self._descriptors.update(descriptors_snapshot)
        self._classes.clear()
        self._classes.update(classes_snapshot)
