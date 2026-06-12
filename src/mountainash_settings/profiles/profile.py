# src/mountainash_settings/profiles/profile.py
"""Generic Profile base for declarative settings profiles.

A subclass declares ``__spec__`` (a :class:`ProfileSpec`); this base uses
pydantic v2's ``__pydantic_init_subclass__`` hook to materialize the spec
into pydantic fields.

During the 26.5.x deprecation window, this class also accepts the old
``__descriptor__`` attribute name; concrete classes that still declare
``__descriptor__`` emit a ``DeprecationWarning`` but install fields
correctly. Removed in 26.6.0.
"""

from __future__ import annotations

import typing as t
import warnings

from pydantic import AfterValidator, SecretStr
from pydantic.fields import FieldInfo

from mountainash_settings import MountainAshBaseSettings

from .lookup import lookup_class_var
from .spec import MISSING, ProfileSpec

__all__ = ["Adapter", "Profile"]

# A target adapter composes credential/config kwargs: it receives the profile
# and the already-merged (base + driver_key renames) dict, and returns the final
# dict. Distinct from the legacy 1-arg ``__adapter__`` which owns the whole
# pipeline (see Profile docstring).
Adapter = t.Callable[["Profile", dict[str, t.Any]], dict[str, t.Any]]

# Sentinel distinguishing "no target argument passed" from an explicit ``None``
# target, so ``emit()`` can fail closed on target-scoped profiles.
_UNSET: t.Any = object()


def _resolve_spec(cls: type) -> ProfileSpec | None:
    """Resolve a class's bound spec from __spec__ (new) or __descriptor__ (old).

    Reads only from cls.__dict__ (not the MRO) because field installation
    must use the spec declared on this class specifically.

    Returns:
        The bound ProfileSpec, or None if neither attribute is set.

    Raises:
        TypeError: If both __spec__ and __descriptor__ are declared with
            different values.
    """
    spec = cls.__dict__.get("__spec__")
    old = cls.__dict__.get("__descriptor__")
    if spec is None and old is not None:
        warnings.warn(
            f"{cls.__name__} declares '__descriptor__' (deprecated). "
            f"Rename to '__spec__' before mountainash-settings 26.6.0.",
            DeprecationWarning, stacklevel=4,
        )
        # Install __spec__ as an alias so instance properties and methods
        # that read self.__spec__ keep working during the 26.5.x deprecation
        # window. Without this, __descriptor__-only classes have fields
        # installed but profile_name/backend/provider_type/_default_kwargs()
        # raise AttributeError.
        cls.__spec__ = old
        return old
    if spec is not None and old is not None and spec is not old:
        raise TypeError(
            f"{cls.__name__} declares both '__spec__' and '__descriptor__' "
            f"with conflicting values: {spec!r} vs {old!r}"
        )
    return spec


class Profile(MountainAshBaseSettings):
    """Declarative settings base — subclasses set ``__spec__`` only.

    Public contract:
        - :attr:`backend` / :attr:`profile_name` — spec name.
        - :attr:`provider_type` — spec provider_type.
        - :meth:`_default_kwargs` — 1:1 ``driver_key`` mappings from the spec.
        - :meth:`emit` — target-aware kwargs: ``driver_key`` renames →
          per-target ``__adapters__`` (2-arg compose) → legacy ``__adapter__``
          (1-arg, owns-pipeline) → merged dict.
        - ``__adapters__`` — per-target adapter map (``{target: Adapter}``).
        - ``__adapter__`` — legacy all-targets adapter; owns the output pipeline.

    Public from 26.5.0. Previously named ``DescriptorProfile``.
    """

    __spec__: t.ClassVar[ProfileSpec]
    __adapter__: t.ClassVar[
        t.Callable[["Profile"], dict[str, t.Any]] | None
    ] = None
    __adapters__: t.ClassVar[dict[t.Hashable, "Adapter"]] = {}

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: t.Any) -> None:
        """Install fields described by ``__spec__`` on the subclass."""
        super().__pydantic_init_subclass__(**kwargs)
        spec = _resolve_spec(cls)
        if spec is None:
            return  # intermediate subclass without its own spec

        new_fields: dict[str, tuple[t.Any, FieldInfo]] = {}

        # 1. Spec parameters → pydantic fields
        for param in spec.parameters:
            ptype: t.Any = SecretStr if param.secret else param.type
            if param.validator is not None:
                ptype = t.Annotated[ptype, AfterValidator(param.validator)]
            if param.default is MISSING:
                info = FieldInfo(
                    annotation=ptype,
                    default=...,
                    description=param.description,
                )
            else:
                info = FieldInfo(
                    annotation=ptype,
                    default=param.default,
                    description=param.description,
                )
            new_fields[param.name] = (ptype, info)

        for name, (annotation, info) in new_fields.items():
            cls.model_fields[name] = info
            cls.__annotations__[name] = annotation

        cls.model_rebuild(force=True)

    # --- Public properties ---------------------------------------------------

    @property
    def profile_name(self) -> str:
        return self.__spec__.name

    @property
    def backend(self) -> str:
        """Alias for ``profile_name`` — preserves naming from mountainash-data."""
        return self.__spec__.name

    @property
    def provider_type(self) -> t.Any:
        return self.__spec__.provider_type

    # --- Template wiring -----------------------------------------------------

    def post_init(
        self,
        template_settings_parameters: t.Any = None,
        reinitialise: t.Optional[bool] = False,
    ) -> None:
        """Resolve any ``ParameterSpec.template`` fields.

        Runs ``init_setting_from_template`` for each parameter with a
        template string. Respects explicit user-provided values — templates
        only populate fields that match their declared default.
        """
        super().post_init(
            template_settings_parameters=template_settings_parameters,
            reinitialise=reinitialise,
        )
        spec = lookup_class_var(type(self), "__spec__")
        if spec is None:
            spec = lookup_class_var(type(self), "__descriptor__")
        if spec is None:
            return
        for param in spec.parameters:
            if param.template is None:
                continue
            current = getattr(self, param.name, None)
            # Only apply template when value matches the declared default
            # (caller-provided explicit values win).
            param_default = param.default if param.default is not MISSING else None
            if current not in (param_default, None, ""):
                continue
            new_val = self.init_setting_from_template(
                template_str=param.template,
                current_value=None,  # force template evaluation
                reinitialise=reinitialise,
            )
            object.__setattr__(self, param.name, new_val)

    # --- Kwargs helpers ------------------------------------------------------

    @staticmethod
    def _resolve_driver_key(
        driver_key: str | dict[t.Hashable, str] | None,
        target: t.Hashable,
    ) -> str | None:
        """Resolve a param's output key for ``target``.

        - ``None`` → not emitted via driver_key (adapter territory).
        - bare ``str`` → that key for every target.
        - ``dict`` → ``driver_key.get(target)`` (``None`` skips this param
          for this target).
        """
        if driver_key is None:
            return None
        if isinstance(driver_key, str):
            return driver_key
        return driver_key.get(target)

    def _default_kwargs(self, target: t.Hashable = None) -> dict[str, t.Any]:
        """Emit ``driver_key`` mappings from the spec for ``target``.

        - Resolves each param's key via :meth:`_resolve_driver_key`.
        - Skips params whose resolved key is ``None`` and ``None`` values.
        - Unwraps :class:`SecretStr` via ``.get_secret_value()``.
        - Applies ``ParameterSpec.transform`` if set.
        """
        out: dict[str, t.Any] = {}
        for param in self.__spec__.parameters:
            key = self._resolve_driver_key(param.driver_key, target)
            if key is None:
                continue
            val = getattr(self, param.name, None)
            if val is None:
                continue
            # Accommodates both pydantic-coerced (SecretStr) and
            # setattr-bypass (raw str) construction paths.
            if isinstance(val, SecretStr):
                val = val.get_secret_value()
            if param.transform is not None:
                val = param.transform(val)
            out[key] = val
        return out

    # --- Targeting helpers ---------------------------------------------------

    def _is_targeted(self) -> bool:
        """True if emission depends on a target (any per-target adapter or any
        dict-scoped ``driver_key``)."""
        if type(self).__adapters__:
            return True
        return any(
            isinstance(p.driver_key, dict) for p in self.__spec__.parameters
        )

    def _known_targets(self) -> set[t.Hashable]:
        """Every target this profile can emit for: adapter keys ∪ dict
        driver_key keys."""
        targets: set[t.Hashable] = set(type(self).__adapters__)
        for param in self.__spec__.parameters:
            if isinstance(param.driver_key, dict):
                targets.update(param.driver_key)
        return targets

    def _knows_target(self, target: t.Hashable) -> bool:
        return target in self._known_targets()

    # --- Emission ------------------------------------------------------------

    def emit(
        self,
        target: t.Hashable = _UNSET,
        *,
        base: dict[str, t.Any] | None = None,
    ) -> dict[str, t.Any]:
        """Produce SDK kwargs for ``target``, layered onto ``base``.

        Three-tier: ``driver_key`` renames, then the per-target adapter in
        ``__adapters__`` (2-arg compose), else the legacy ``__adapter__``
        (1-arg, owns-pipeline), else the merged dict.

        Fail-closed: a target-scoped profile (dict driver_keys or any
        ``__adapters__``) emitted with no explicit target raises rather than
        silently dropping output. An unknown explicit target on such a profile
        also raises.

        ``base`` is treated as caller-owned: only a shallow copy is taken here,
        so adapters must copy-on-write any nested container they touch.
        """
        if target is _UNSET:
            if self._is_targeted():
                raise ValueError(
                    f"{type(self).__name__} is target-scoped; "
                    f"call emit(<target>)."
                )
            target = None
        elif (
            target is not None
            and self._is_targeted()
            and not self._knows_target(target)
        ):
            known = sorted(self._known_targets(), key=repr)
            raise ValueError(
                f"{type(self).__name__} has no emission for target "
                f"{target!r}; known: {known}."
            )

        merged = {**(base or {}), **self._default_kwargs(target)}

        adapter = type(self).__adapters__.get(target)
        if adapter is not None:
            return adapter(self, merged)
        if type(self).__adapter__ is not None:
            return type(self).__adapter__(self)  # legacy 1-arg owns-pipeline
        return merged

