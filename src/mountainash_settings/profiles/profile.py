# src/mountainash_settings/profiles/profile.py
"""Generic DescriptorProfile base for declarative settings profiles.

A subclass declares ``__descriptor__`` (a :class:`ProfileDescriptor`); this
base uses pydantic v2's ``__pydantic_init_subclass__`` hook to materialize the
descriptor into pydantic fields and compose the :class:`AuthSpec` union into
the ``auth`` field. Consumers add their own domain-specific output methods
(e.g. ``to_driver_kwargs()``) in their own subclasses.
"""

from __future__ import annotations

import typing as t

from pydantic import AfterValidator, SecretStr
from pydantic.fields import FieldInfo

from mountainash_settings import MountainAshBaseSettings
from mountainash_settings.auth import auth_to_driver_kwargs

from .descriptor import MISSING, ProfileDescriptor

__all__ = ["DescriptorProfile"]


class DescriptorProfile(MountainAshBaseSettings):
    """Declarative settings base — subclasses set ``__descriptor__`` only.

    Public contract:
        - :attr:`backend` / :attr:`profile_name` — descriptor name.
        - :attr:`provider_type` — descriptor provider_type.
        - :meth:`_default_kwargs` — 1:1 ``driver_key`` mappings from the descriptor.
        - :meth:`_auth_kwargs` — default auth dispatch (consumers may override).
        - ``__adapter__`` — if set, adapter owns the output pipeline.
    """

    __descriptor__: t.ClassVar[ProfileDescriptor]
    __adapter__: t.ClassVar[
        t.Callable[["DescriptorProfile"], dict[str, t.Any]] | None
    ] = None

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: t.Any) -> None:
        """Install fields described by ``__descriptor__`` on the subclass."""
        super().__pydantic_init_subclass__(**kwargs)
        desc = cls.__dict__.get("__descriptor__")
        if desc is None:
            return  # intermediate subclass without its own descriptor

        new_fields: dict[str, tuple[t.Any, FieldInfo]] = {}

        # 1. Descriptor parameters → pydantic fields
        for spec in desc.parameters:
            ptype: t.Any = SecretStr if spec.secret else spec.type
            if spec.validator is not None:
                ptype = t.Annotated[ptype, AfterValidator(spec.validator)]
            if spec.default is MISSING:
                info = FieldInfo(
                    annotation=ptype,
                    default=...,
                    description=spec.description,
                )
            else:
                info = FieldInfo(
                    annotation=ptype,
                    default=spec.default,
                    description=spec.description,
                )
            new_fields[spec.name] = (ptype, info)

        # 2. auth field as discriminated union of descriptor.auth_modes
        if desc.auth_modes:
            auth_union: t.Any
            if len(desc.auth_modes) == 1:
                auth_union = desc.auth_modes[0]
                auth_info = FieldInfo(annotation=auth_union, default=...)
            else:
                auth_union = t.Union[tuple(desc.auth_modes)]  # type: ignore[valid-type]
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
        return self.__descriptor__.name

    @property
    def backend(self) -> str:
        """Alias for ``profile_name`` — preserves naming from mountainash-data."""
        return self.__descriptor__.name

    @property
    def provider_type(self) -> t.Any:
        return self.__descriptor__.provider_type

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
        desc = type(self).__dict__.get("__descriptor__")
        if desc is None:
            for base in type(self).__mro__[1:]:
                cand = base.__dict__.get("__descriptor__")
                if cand is not None:
                    desc = cand
                    break
        if desc is None:
            return
        for spec in desc.parameters:
            if spec.template is None:
                continue
            current = getattr(self, spec.name, None)
            # Only apply template when value matches the declared default
            # (caller-provided explicit values win).
            spec_default = spec.default if spec.default is not MISSING else None
            if current not in (spec_default, None, ""):
                continue
            new_val = self.init_setting_from_template(
                template_str=spec.template,
                current_value=None,  # force template evaluation
                reinitialise=reinitialise,
            )
            object.__setattr__(self, spec.name, new_val)

    # --- Kwargs helpers ------------------------------------------------------

    def _default_kwargs(self) -> dict[str, t.Any]:
        """Emit 1:1 ``driver_key`` mappings from the descriptor.

        - Skips ``None`` values.
        - Unwraps :class:`SecretStr` via ``.get_secret_value()``.
        - Applies ``ParameterSpec.transform`` if set.
        """
        out: dict[str, t.Any] = {}
        for spec in self.__descriptor__.parameters:
            if spec.driver_key is None:
                continue
            val = getattr(self, spec.name, None)
            if val is None:
                continue
            # Accommodates both pydantic-coerced (SecretStr) and
            # setattr-bypass (raw str) construction paths.
            if isinstance(val, SecretStr):
                val = val.get_secret_value()
            if spec.transform is not None:
                val = spec.transform(val)
            out[spec.driver_key] = val
        return out

    def _auth_kwargs(self) -> dict[str, t.Any]:
        """Default auth dispatch. Domain adapters typically override."""
        auth = getattr(self, "auth", None)
        if auth is None:
            return {}
        return auth_to_driver_kwargs(auth)
