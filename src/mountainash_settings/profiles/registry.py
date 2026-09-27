"""Per-domain registry of canonical profile specs and classes."""
from __future__ import annotations

import typing as t

from .spec import ProfileSpec

if t.TYPE_CHECKING:
    from .profile import Profile

__all__ = ["Registry"]
T = t.TypeVar("T", bound="Profile")


class Registry:
    """Name-keyed profiles with optional stricter spec and profile bases."""

    def __init__(
        self, name: str, *, spec_type: type[ProfileSpec] | None = None,
        profile_type: type[Profile] | None = None,
    ) -> None:
        from .profile import Profile

        self.name = name
        self._spec_type = spec_type or ProfileSpec
        self._profile_type = profile_type or Profile
        self._specs: dict[str, ProfileSpec] = {}
        self._classes: dict[str, type[Profile]] = {}

    def __len__(self) -> int:
        return len(self._specs)

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name in self._specs

    @property
    def specs(self) -> dict[str, ProfileSpec]:
        """Return a defensive copy of registered specs."""
        return dict(self._specs)

    def register(self, spec: ProfileSpec, cls: type[Profile]) -> None:
        from .profile import Profile

        if not isinstance(spec, ProfileSpec) or not isinstance(spec, self._spec_type):
            raise TypeError(f"Registry {self.name!r}: spec_type mismatch")
        if not isinstance(cls, type) or not issubclass(cls, Profile) or not issubclass(cls, self._profile_type):
            raise TypeError(f"Registry {self.name!r}: profile_type mismatch")
        if spec.name in self._specs:
            existing = self._classes[spec.name]
            raise ValueError(
                f"Profile {spec.name!r} is already registered in {self.name} registry "
                f"by {existing.__module__}.{existing.__qualname__}"
            )
        self._specs[spec.name] = spec
        self._classes[spec.name] = cls
        cls.__spec__ = spec

    def decorator(self) -> t.Callable[[type[T]], type[T]]:
        """Return a bare class decorator requiring a class-body spec."""
        from .profile import Profile

        def decorate(cls: type[T]) -> type[T]:
            if not isinstance(cls, type) or not issubclass(cls, Profile):
                raise TypeError("Registration requires a Profile subclass")
            spec = cls.__dict__.get("__spec__")
            if not isinstance(spec, ProfileSpec):
                raise TypeError("Registration requires a class-body __spec__: ProfileSpec")
            self.register(spec, cls)
            return cls

        return decorate

    def get_spec(self, name: str) -> ProfileSpec:
        try:
            return self._specs[name]
        except KeyError:
            known = ", ".join(sorted(self._specs)) or "<none>"
            raise KeyError(f"No profile registered under {name!r} in {self.name} registry. Known: {known}") from None

    def get_settings_class(self, name: str) -> type[Profile]:
        try:
            return self._classes[name]
        except KeyError:
            known = ", ".join(sorted(self._classes)) or "<none>"
            raise KeyError(f"No settings class registered under {name!r} in {self.name} registry. Known: {known}") from None

    def _snapshot_for_tests(self) -> tuple[dict[str, ProfileSpec], dict[str, type[Profile]]]:
        return self._specs.copy(), self._classes.copy()

    def _reset_for_tests(
        self, specs_snapshot: dict[str, ProfileSpec], classes_snapshot: dict[str, type[Profile]],
    ) -> None:
        self._specs.clear()
        self._specs.update(specs_snapshot)
        self._classes.clear()
        self._classes.update(classes_snapshot)
