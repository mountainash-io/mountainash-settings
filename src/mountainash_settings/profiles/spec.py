# src/mountainash_settings/profiles/spec.py
"""Declarative specifications for settings profiles.

A ProfileSpec captures everything the generic Profile base needs to install
pydantic fields for a given configuration. A ParameterSpec describes one field
within a spec.

This module is the canonical home for these types.
"""

from __future__ import annotations

import typing as t
from dataclasses import dataclass, field

__all__ = ["FACTORY_DEFAULT", "FactoryDefault", "MISSING", "Missing", "ParameterSpec", "ProfileSpec"]


class Missing:
    """Sentinel indicating a required (no-default) field.

    Pydantic ``Field(...)`` is emitted when a ParameterSpec default is this
    sentinel; ``Field(default=...)`` otherwise.

    """

    _instance: "t.ClassVar[Missing | None]" = None

    def __new__(cls) -> "Missing":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "MISSING"

    def __bool__(self) -> bool:
        return False


MISSING: Missing = Missing()


class FactoryDefault:
    """A generated parameter has a factory on its owning class, not a literal default."""

    _instance: t.ClassVar[FactoryDefault | None] = None

    def __new__(cls) -> FactoryDefault:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "FACTORY_DEFAULT"

    def __reduce__(self) -> tuple[type[FactoryDefault], tuple[()]]:
        return (FactoryDefault, ())


FACTORY_DEFAULT = FactoryDefault()


@dataclass(frozen=True, kw_only=True)
class ParameterSpec:
    """One settings field on a profile.

    Attributes:
        name: Settings-facing uppercase name (e.g. ``"SSL_CERT"``).
        type: Pydantic-compatible annotation (``str``, ``int | None``, enum, …).
        tier: ``"core"`` or ``"advanced"`` — audit-style severity tier.
        default: Literal default, :data:`MISSING` for required fields, or
            :data:`FACTORY_DEFAULT` for generated fields with native factories.
            Generated specs describe fields; they cannot reconstruct factories,
            aliases or decorator validators from the owning class.
        description: Optional docstring for generated schemas / help output.
        driver_key: Output-kwarg name for 1:1 mappings. A bare ``str`` (e.g.
            ``"sslcert"``) maps for every target. A ``dict[Hashable, str]``
            scopes the mapping per emission target — e.g.
            ``{TargetFamily.PARAMIKO: "password"}`` emits only when
            ``emit(PARAMIKO)`` / ``_default_kwargs(PARAMIKO)`` is called.
            ``None`` means a domain adapter handles emission.
        secret: If ``True``, wrap ``type`` as :class:`pydantic.SecretStr` and
            auto-unwrap via ``.get_secret_value()`` at the kwargs boundary.
        transform: Optional callable applied when emitting kwargs.
        validator: Optional pydantic-compatible field-level validator.
        template: Optional template string; when set, :class:`Profile`
            auto-wires ``init_setting_from_template`` in ``post_init`` to
            populate this field.
    """

    name: str
    type: t.Any
    tier: t.Literal["core", "advanced"]
    default: t.Any = MISSING
    description: str = ""
    # dict driver_keys are unhashable; ParameterSpec is a frozen dataclass whose
    # auto __hash__ would crash on a dict field. Exclude driver_key from the hash
    # (it stays in __eq__) so dict-scoped specs remain hashable.
    driver_key: str | dict[t.Hashable, str] | None = field(default=None, hash=False)
    secret: bool = False
    transform: t.Callable[[t.Any], t.Any] | None = None
    validator: t.Callable[[t.Any], t.Any] | None = None
    template: str | None = None


@dataclass(frozen=True, kw_only=True)
class ProfileSpec:
    """Immutable specification of a single settings profile.

    Attributes:
        name: Short name (conventionally lowercase, e.g. ``"postgresql"``).
        provider_type: Canonical provider identifier (domain-specific enum).
        parameters: Ordered list of :class:`ParameterSpec`.
        metadata: Bag of domain-specific metadata (e.g. port, URL scheme,
            dialect name). Domains wanting strong typing may subclass
            ``ProfileSpec`` and add typed fields instead.

    """

    name: str
    provider_type: t.Any
    parameters: list[ParameterSpec]
    metadata: dict[str, t.Any] = field(default_factory=dict)
