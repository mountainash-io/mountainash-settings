# src/mountainash_settings/profiles/descriptor.py
"""Declarative descriptors for settings profiles.

A :class:`ProfileDescriptor` captures everything the generic
:class:`DescriptorProfile` base needs to install pydantic fields for a given
configuration. A :class:`ParameterSpec` describes one field within a
descriptor.

Extends the ``BackendDescriptor`` from mountainash-data's 2026-04-15 refactor
by renaming for generality (not all profiles are for "backends") and adding
``ParameterSpec.template`` for declarative template-driven derived fields.
"""

from __future__ import annotations

import typing as t
from dataclasses import dataclass, field

__all__ = ["MISSING", "ParameterSpec", "ProfileDescriptor"]


class _Missing:
    """Sentinel indicating a required (no-default) field.

    Pydantic ``Field(...)`` is emitted when a :class:`ParameterSpec` default
    is this sentinel; ``Field(default=...)`` otherwise.
    """

    _instance: "t.ClassVar[_Missing | None]" = None

    def __new__(cls) -> "_Missing":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "MISSING"

    def __bool__(self) -> bool:
        return False


MISSING: _Missing = _Missing()


@dataclass(frozen=True, kw_only=True)
class ParameterSpec:
    """One settings field on a profile.

    Attributes:
        name: Settings-facing uppercase name (e.g. ``"SSL_CERT"``).
        type: Pydantic-compatible annotation (``str``, ``int | None``, enum, …).
        tier: ``"core"`` or ``"advanced"`` — audit-style severity tier.
        default: Default value; :data:`MISSING` means the field is required.
        description: Optional docstring for generated schemas / help output.
        driver_key: Output-kwarg name for 1:1 mappings (e.g. ``"sslcert"``).
            ``None`` means a domain adapter handles emission.
        secret: If ``True``, wrap ``type`` as :class:`pydantic.SecretStr` and
            auto-unwrap via ``.get_secret_value()`` at the kwargs boundary.
        transform: Optional callable applied when emitting kwargs.
        validator: Optional pydantic-compatible field-level validator.
        template: Optional template string; when set,
            :class:`DescriptorProfile` auto-wires ``init_setting_from_template``
            in ``post_init`` to populate this field.
    """

    name: str
    type: t.Any
    tier: t.Literal["core", "advanced"]
    default: t.Any = MISSING
    description: str = ""
    driver_key: str | None = None
    secret: bool = False
    transform: t.Callable[[t.Any], t.Any] | None = None
    validator: t.Callable[[t.Any], t.Any] | None = None
    template: str | None = None


@dataclass(frozen=True, kw_only=True)
class ProfileDescriptor:
    """Immutable description of a single settings profile.

    Attributes:
        name: Short name (conventionally lowercase, e.g. ``"postgresql"``).
        provider_type: Canonical provider identifier (domain-specific enum).
        parameters: Ordered list of :class:`ParameterSpec`.
        auth_modes: List of :class:`AuthSpec` subclasses this profile accepts.
        metadata: Bag of domain-specific metadata (e.g. port, URL scheme,
            dialect name). Domains wanting strong typing may subclass
            ``ProfileDescriptor`` and add typed fields instead.
    """

    name: str
    provider_type: t.Any
    parameters: list[ParameterSpec]
    auth_modes: list[type]  # list[type[AuthSpec]] — forward-refd to avoid cycle
    metadata: dict[str, t.Any] = field(default_factory=dict)
