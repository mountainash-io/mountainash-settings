"""Per-domain registry of canonical profile specs and classes."""
from __future__ import annotations

import typing as t

from typing_extensions import TypeVar

from .spec import ProfileSpec

if t.TYPE_CHECKING:
    from .profile import Profile

__all__ = ["Registry"]
_T = t.TypeVar("_T", bound="Profile")
_SpecT = TypeVar("_SpecT", bound=ProfileSpec, default=ProfileSpec)
_ProfileT = TypeVar("_ProfileT", default="Profile")


@t.final
class Registry(t.Generic[_SpecT, _ProfileT]):
    """Name-keyed profiles with optional stricter spec and profile bases."""

    @t.overload
    def __init__(self: Registry[ProfileSpec, Profile], name: str, *,
                 spec_type: None = None, profile_type: None = None) -> None: ...

    @t.overload
    def __init__(self: Registry[_SpecT, Profile], name: str, *,
                 spec_type: type[_SpecT], profile_type: None = None) -> None: ...

    # The uninhabited branch avoids mypy 1.10.1's direct-TypeType abstract
    # class check without admitting factories. Installed controls pin this.
    @t.overload
    def __init__(self, name: str, *, spec_type: type[_SpecT],
                 profile_type: type[_ProfileT] | type[t.Never]) -> None: ...

    @t.overload
    def __init__(self: Registry[ProfileSpec, _ProfileT], name: str, *,
                 spec_type: None = None,
                 profile_type: type[_ProfileT] | type[t.Never]) -> None: ...

    def __init__(
        self, name: str, *, spec_type: type[_SpecT] | None = None,
        profile_type: type[_ProfileT] | None = None,
    ) -> None:
        from .profile import Profile

        self.name = name
        self._spec_type = spec_type or ProfileSpec
        self._profile_type = t.cast(type[_ProfileT], profile_type or Profile)
        self._specs: dict[str, _SpecT] = {}
        self._classes: dict[str, type[_ProfileT]] = {}

    def __len__(self) -> int:
        return len(self._specs)

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name in self._specs

    @property
    def specs(self) -> dict[str, _SpecT]:
        """Return a defensive copy of registered specs."""
        return dict(self._specs)

    def register(self, spec: _SpecT, cls: type[_ProfileT]) -> None:
        from .profile import Profile, _require_materializable_profile

        if not isinstance(spec, ProfileSpec) or not isinstance(spec, self._spec_type):
            raise TypeError(f"Registry {self.name!r}: spec_type mismatch")
        if not isinstance(cls, type) or not issubclass(cls, Profile) or not issubclass(cls, self._profile_type):
            raise TypeError(f"Registry {self.name!r}: profile_type mismatch")
        profile_cls = t.cast(type[Profile], cls)
        _require_materializable_profile(profile_cls)
        if profile_cls._profile_declaration is not None and spec is not profile_cls.__spec__:
            raise TypeError(f"Registry {self.name!r}: generated profile requires its published spec")
        if spec.name in self._specs:
            existing = self._classes[spec.name]
            raise ValueError(
                f"Profile {spec.name!r} is already registered in {self.name} registry "
                f"by {existing.__module__}.{existing.__qualname__}"
            )
        self._specs[spec.name] = spec
        self._classes[spec.name] = cls
        profile_cls.__spec__ = spec

    def decorator(self) -> t.Callable[[type[_T]], type[_T]]:
        """Return a bare decorator for an own explicit or completed generated spec."""
        from .profile import Profile, _require_materializable_profile

        def decorate(cls: type[_T]) -> type[_T]:
            if not isinstance(cls, type) or not issubclass(cls, Profile):
                raise TypeError("Registration requires a Profile subclass")
            _require_materializable_profile(cls)
            spec = cls.__dict__.get("__spec__")
            if not isinstance(spec, ProfileSpec):
                raise TypeError("Registration requires a class-body __spec__: ProfileSpec")
            self.register(t.cast(_SpecT, spec), t.cast(type[_ProfileT], cls))
            return cls

        return decorate

    def get_spec(self, name: str) -> _SpecT:
        try:
            return self._specs[name]
        except KeyError:
            known = ", ".join(sorted(self._specs)) or "<none>"
            raise KeyError(f"No profile registered under {name!r} in {self.name} registry. Known: {known}") from None

    def get_settings_class(self, name: str) -> type[_ProfileT]:
        try:
            return self._classes[name]
        except KeyError:
            known = ", ".join(sorted(self._classes)) or "<none>"
            raise KeyError(f"No settings class registered under {name!r} in {self.name} registry. Known: {known}") from None

    def _snapshot_for_tests(self) -> tuple[dict[str, _SpecT], dict[str, type[_ProfileT]]]:
        return self._specs.copy(), self._classes.copy()

    def _reset_for_tests(
        self, specs_snapshot: dict[str, _SpecT], classes_snapshot: dict[str, type[_ProfileT]],
    ) -> None:
        self._specs.clear()
        self._specs.update(specs_snapshot)
        self._classes.clear()
        self._classes.update(classes_snapshot)
