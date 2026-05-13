# src/mountainash_settings/profiles/profile.py
"""Generic Profile base for declarative settings profiles.

A subclass declares ``__spec__`` (a :class:`ProfileSpec`); this base uses
pydantic v2's ``__pydantic_init_subclass__`` hook to materialize the spec
into pydantic fields and compose the :class:`AuthSpec` union into the
``auth`` field.

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
from mountainash_settings.auth import auth_to_driver_kwargs

from .lookup import lookup_class_var
from .spec import MISSING, ProfileSpec

__all__ = ["Profile"]


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
        - :meth:`_auth_kwargs` — default auth dispatch (consumers may override).
        - ``__adapter__`` — if set, adapter owns the output pipeline.

    Public from 26.5.0. Previously named ``DescriptorProfile``.
    """

    __spec__: t.ClassVar[ProfileSpec]
    __adapter__: t.ClassVar[
        t.Callable[["Profile"], dict[str, t.Any]] | None
    ] = None

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

        # 2. auth field as discriminated union of spec.auth_modes
        if spec.auth_modes:
            auth_union: t.Any
            if len(spec.auth_modes) == 1:
                auth_union = spec.auth_modes[0]
                auth_info = FieldInfo(annotation=auth_union, default=...)
            else:
                auth_union = t.Union[tuple(spec.auth_modes)]  # type: ignore[valid-type]
                auth_info = FieldInfo(
                    annotation=auth_union,
                    default=...,
                    discriminator="kind",
                )
            new_fields["auth"] = (auth_union, auth_info)

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

    def _default_kwargs(self) -> dict[str, t.Any]:
        """Emit 1:1 ``driver_key`` mappings from the spec.

        - Skips ``None`` values.
        - Unwraps :class:`SecretStr` via ``.get_secret_value()``.
        - Applies ``ParameterSpec.transform`` if set.
        """
        out: dict[str, t.Any] = {}
        for param in self.__spec__.parameters:
            if param.driver_key is None:
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
            out[param.driver_key] = val
        return out

    def _auth_kwargs(self) -> dict[str, t.Any]:
        """Default auth dispatch. Domain adapters typically override."""
        auth = getattr(self, "auth", None)
        if auth is None:
            return {}
        return auth_to_driver_kwargs(auth)
