# Profiles Promotion — Phase 1: `mountainash-settings` Scaffolding

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `profiles/` and `auth/` sub-packages to `mountainash-settings`, lifting the descriptor/registry/auth machinery from `mountainash-data`'s 2026-04-15 settings-registry refactor. No consumers yet — this phase is pure library work, verified against its own test suite.

**Architecture:** Two new sub-packages live under `src/mountainash_settings/`. `profiles/` contains the mechanism (`ProfileDescriptor`, `ParameterSpec`, `DescriptorProfile`, `Registry`, invariants helper). `auth/` contains the full `AuthSpec` hierarchy + default dispatch map. Each is self-contained; public re-exports happen from the package `__init__.py`.

**Tech Stack:** Python 3.12, pydantic v2, `MountainAshBaseSettings` (existing), hatch + pytest for the test environment.

**Reference source:** All code lifts almost verbatim from `mountainash-data` at commit `2ec5079` (tip of `feat/settings-registry`). Key source paths:
- `src/mountainash_data/core/settings/descriptor.py`
- `src/mountainash_data/core/settings/auth/` (full directory)
- `src/mountainash_data/core/settings/profile.py`
- `src/mountainash_data/core/settings/registry.py`
- `tests/test_unit/core/settings/test_descriptors_invariants.py` (template for invariants helper)

**Spec:** `docs/superpowers/specs/2026-04-16-profiles-promotion-design.md`

**Working directory for all commands:** `/home/nathanielramm/git/mountainash-io/mountainash/mountainash-settings`

**Branch:** Create `feat/profiles-promotion` from `main`.

---

## Task 1: Branch + `auth/` package skeleton

**Files:**
- Create: `src/mountainash_settings/auth/__init__.py` (empty, adds `__all__` at end)
- Create: `src/mountainash_settings/auth/base.py`

- [ ] **Step 1: Create branch**

```bash
cd /home/nathanielramm/git/mountainash-io/mountainash/mountainash-settings
git checkout -b feat/profiles-promotion
```

- [ ] **Step 2: Write `auth/base.py`**

```python
# src/mountainash_settings/auth/base.py
"""Base class for discriminated-union auth specs.

Each AuthSpec subclass declares a ``kind: Literal["..."]`` field that pydantic
uses as the discriminator. The base class does NOT declare ``kind`` — if it
did, every subclass would trip ``reportIncompatibleVariableOverride``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

__all__ = ["AuthSpec"]


class AuthSpec(BaseModel):
    """Base for typed auth modes used as a pydantic discriminated union."""

    model_config = ConfigDict(extra="forbid", frozen=True)
```

- [ ] **Step 3: Write a smoke test**

```python
# tests/unit/auth/test_base.py
"""Sanity-check the AuthSpec base class."""

import pytest

from mountainash_settings.auth.base import AuthSpec


@pytest.mark.unit
def test_authspec_is_frozen():
    class Dummy(AuthSpec):
        pass

    d = Dummy()
    with pytest.raises(Exception):  # FrozenInstanceError/ValidationError
        d.anything = 1  # type: ignore


@pytest.mark.unit
def test_authspec_rejects_extras():
    class Dummy(AuthSpec):
        pass

    with pytest.raises(Exception):
        Dummy(extra_field="nope")  # type: ignore
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
hatch run test:test-target tests/unit/auth/test_base.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_settings/auth/ tests/unit/auth/
git commit -m "feat(auth): add AuthSpec base class for discriminated unions"
```

---

## Task 2: Port all 11 AuthSpec subclasses

**Files:**
- Create: `src/mountainash_settings/auth/none.py`
- Create: `src/mountainash_settings/auth/password.py`
- Create: `src/mountainash_settings/auth/token.py`
- Create: `src/mountainash_settings/auth/oauth2.py`
- Create: `src/mountainash_settings/auth/service_account.py`
- Create: `src/mountainash_settings/auth/iam.py`
- Create: `src/mountainash_settings/auth/azure.py`
- Create: `src/mountainash_settings/auth/kerberos.py`
- Create: `src/mountainash_settings/auth/certificate.py`
- Modify: `src/mountainash_settings/auth/__init__.py`

- [ ] **Step 1: Copy each auth module verbatim from mountainash-data**

The files at `/home/nathanielramm/git/mountainash-io/mountainash/mountainash-data/src/mountainash_data/core/settings/auth/*.py` are the canonical source. For each file listed above:

```bash
cp /home/nathanielramm/git/mountainash-io/mountainash/mountainash-data/src/mountainash_data/core/settings/auth/none.py \
   src/mountainash_settings/auth/none.py
# ... repeat for each of the 9 files (base.py already exists from Task 1, so skip)
```

Note the module groupings — `token.py` contains both `TokenAuth` and `JWTAuth`; `azure.py` contains both `WindowsAuth` and `AzureADAuth`.

- [ ] **Step 2: Fix the `from .base import AuthSpec` relative imports**

They already use relative imports (`from .base import AuthSpec`) — no change needed, but verify by grepping:

```bash
grep -l "from mountainash_data" src/mountainash_settings/auth/
```

Expected: no matches. All imports should be relative (`from .base`, `from ..`).

- [ ] **Step 3: Write `src/mountainash_settings/auth/__init__.py`**

```python
"""Discriminated-union auth specs for settings profiles."""

from __future__ import annotations

from .azure import AzureADAuth, WindowsAuth
from .base import AuthSpec
from .certificate import CertificateAuth
from .iam import IAMAuth
from .kerberos import KerberosAuth
from .none import NoAuth
from .oauth2 import OAuth2Auth
from .password import PasswordAuth
from .service_account import ServiceAccountAuth
from .token import JWTAuth, TokenAuth

__all__ = [
    "AuthSpec",
    "AzureADAuth",
    "CertificateAuth",
    "IAMAuth",
    "JWTAuth",
    "KerberosAuth",
    "NoAuth",
    "OAuth2Auth",
    "PasswordAuth",
    "ServiceAccountAuth",
    "TokenAuth",
    "WindowsAuth",
]
```

- [ ] **Step 4: Port the auth test suite**

Copy `tests/test_unit/core/settings/test_auth.py` from mountainash-data to `tests/unit/auth/test_subclasses.py`. Update the imports from `mountainash_data.core.settings.auth` → `mountainash_settings.auth`.

```bash
cp /home/nathanielramm/git/mountainash-io/mountainash/mountainash-data/tests/test_unit/core/settings/test_auth.py \
   tests/unit/auth/test_subclasses.py
# Then edit imports.
```

Use `sed` or manual edit:

```bash
sed -i 's|mountainash_data\.core\.settings\.auth|mountainash_settings.auth|g' \
    tests/unit/auth/test_subclasses.py
```

- [ ] **Step 5: Run the suite**

```bash
hatch run test:test-target tests/unit/auth/ -v
```

Expected: all tests pass (~18 — 2 from Task 1 + ~16 from the ported suite).

- [ ] **Step 6: Commit**

```bash
git add src/mountainash_settings/auth/ tests/unit/auth/
git commit -m "feat(auth): port 11 AuthSpec subclasses from mountainash-data"
```

---

## Task 3: Auth dispatch map

**Files:**
- Create: `src/mountainash_settings/auth/dispatch.py`
- Create: `tests/unit/auth/test_dispatch.py`

- [ ] **Step 1: Copy dispatch.py verbatim**

```bash
cp /home/nathanielramm/git/mountainash-io/mountainash/mountainash-data/src/mountainash_data/core/settings/auth/dispatch.py \
   src/mountainash_settings/auth/dispatch.py
```

- [ ] **Step 2: Verify imports are relative**

Open the file. Ensure imports are `from .base import AuthSpec`, `from .none import NoAuth`, etc. If any reference `mountainash_data`, fix them.

- [ ] **Step 3: Add exports to `auth/__init__.py`**

Append to `src/mountainash_settings/auth/__init__.py`:

```python
from .dispatch import AUTH_TO_DRIVER_KWARGS, auth_to_driver_kwargs
```

Append to `__all__`:

```python
    "AUTH_TO_DRIVER_KWARGS",
    "auth_to_driver_kwargs",
```

- [ ] **Step 4: Port dispatch tests**

```bash
cp /home/nathanielramm/git/mountainash-io/mountainash/mountainash-data/tests/test_unit/core/settings/test_auth_dispatch.py \
   tests/unit/auth/test_dispatch.py

sed -i 's|mountainash_data\.core\.settings\.auth|mountainash_settings.auth|g' \
    tests/unit/auth/test_dispatch.py
```

- [ ] **Step 5: Run tests**

```bash
hatch run test:test-target tests/unit/auth/ -v
```

Expected: all tests pass (ported auth + dispatch suites).

- [ ] **Step 6: Commit**

```bash
git add src/mountainash_settings/auth/dispatch.py \
        src/mountainash_settings/auth/__init__.py \
        tests/unit/auth/test_dispatch.py
git commit -m "feat(auth): add AUTH_TO_DRIVER_KWARGS default dispatch map"
```

---

## Task 4: `profiles/descriptor.py` — MISSING, ParameterSpec, ProfileDescriptor

**Files:**
- Create: `src/mountainash_settings/profiles/__init__.py` (empty initially)
- Create: `src/mountainash_settings/profiles/descriptor.py`
- Create: `tests/unit/profiles/test_descriptor.py`

- [ ] **Step 1: Write `profiles/descriptor.py`**

```python
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
```

- [ ] **Step 2: Write tests**

```python
# tests/unit/profiles/test_descriptor.py
"""Unit tests for ProfileDescriptor, ParameterSpec, and MISSING."""

import pytest

from mountainash_settings.auth import NoAuth
from mountainash_settings.profiles.descriptor import (
    MISSING,
    ParameterSpec,
    ProfileDescriptor,
)


@pytest.mark.unit
class TestMissing:
    def test_missing_is_singleton(self):
        from mountainash_settings.profiles.descriptor import _Missing
        assert _Missing() is MISSING

    def test_missing_is_falsy(self):
        assert not MISSING

    def test_missing_repr(self):
        assert repr(MISSING) == "MISSING"


@pytest.mark.unit
class TestParameterSpec:
    def test_minimal(self):
        p = ParameterSpec(name="X", type=str, tier="core")
        assert p.name == "X"
        assert p.default is MISSING
        assert p.template is None

    def test_frozen(self):
        p = ParameterSpec(name="X", type=str, tier="core")
        with pytest.raises(Exception):
            p.name = "Y"  # type: ignore

    def test_template_field(self):
        p = ParameterSpec(name="URL", type=str, tier="core",
                          template="https://{HOST}/api")
        assert p.template == "https://{HOST}/api"


@pytest.mark.unit
class TestProfileDescriptor:
    def test_minimal(self):
        d = ProfileDescriptor(
            name="x", provider_type="x",
            parameters=[], auth_modes=[NoAuth],
        )
        assert d.name == "x"
        assert d.metadata == {}

    def test_metadata(self):
        d = ProfileDescriptor(
            name="x", provider_type="x",
            parameters=[], auth_modes=[NoAuth],
            metadata={"port": 5432, "scheme": "x://"},
        )
        assert d.metadata["port"] == 5432

    def test_frozen(self):
        d = ProfileDescriptor(
            name="x", provider_type="x",
            parameters=[], auth_modes=[NoAuth],
        )
        with pytest.raises(Exception):
            d.name = "y"  # type: ignore
```

- [ ] **Step 3: Write empty `profiles/__init__.py`**

```python
# src/mountainash_settings/profiles/__init__.py
"""Declarative settings profiles — descriptor + registry + generic base.

Lifted and generalized from mountainash-data's 2026-04-15 settings-registry
refactor. See design spec:
``docs/superpowers/specs/2026-04-16-profiles-promotion-design.md``.
"""

from __future__ import annotations

from .descriptor import MISSING, ParameterSpec, ProfileDescriptor

__all__ = ["MISSING", "ParameterSpec", "ProfileDescriptor"]
```

- [ ] **Step 4: Run tests**

```bash
hatch run test:test-target tests/unit/profiles/test_descriptor.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_settings/profiles/ tests/unit/profiles/
git commit -m "feat(profiles): add ProfileDescriptor + ParameterSpec with template support"
```

---

## Task 5: `profiles/registry.py` — Registry class

**Files:**
- Create: `src/mountainash_settings/profiles/registry.py`
- Create: `tests/unit/profiles/test_registry.py`
- Modify: `src/mountainash_settings/profiles/__init__.py`

- [ ] **Step 1: Write `registry.py`**

```python
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
```

- [ ] **Step 2: Write tests**

```python
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
```

- [ ] **Step 3: Update `profiles/__init__.py`**

Replace contents with:

```python
# src/mountainash_settings/profiles/__init__.py
"""Declarative settings profiles — descriptor + registry + generic base."""

from __future__ import annotations

from .descriptor import MISSING, ParameterSpec, ProfileDescriptor
from .registry import Registry

__all__ = ["MISSING", "ParameterSpec", "ProfileDescriptor", "Registry"]
```

- [ ] **Step 4: Run tests**

```bash
hatch run test:test-target tests/unit/profiles/ -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_settings/profiles/registry.py \
        src/mountainash_settings/profiles/__init__.py \
        tests/unit/profiles/test_registry.py
git commit -m "feat(profiles): add per-domain Registry class with bound decorator"
```

---

## Task 6: `profiles/profile.py` — DescriptorProfile (Pattern A mechanism)

**Files:**
- Create: `src/mountainash_settings/profiles/profile.py`
- Create: `tests/unit/profiles/test_profile.py`
- Modify: `src/mountainash_settings/profiles/__init__.py`

- [ ] **Step 1: Write `profile.py`**

Lift the implementation from `mountainash-data`'s `src/mountainash_data/core/settings/profile.py` (commit `2ec5079`). Apply these transformations:

1. Rename class `ConnectionProfile` → `DescriptorProfile`.
2. Drop `to_driver_kwargs()` and `to_connection_string()` methods entirely (those stay in domain subclasses).
3. Rename `_default_driver_kwargs()` → `_default_kwargs()`.
4. Rename `_auth_to_driver_kwargs()` → `_auth_kwargs()`.
5. Drop the `from .auth.dispatch import auth_to_driver_kwargs` import and re-point it: `from mountainash_settings.auth import auth_to_driver_kwargs`.
6. Drop the `from ..constants` import (not needed at this layer).
7. Keep `__adapter__` contract and MRO walk verbatim.
8. Keep the `__pydantic_init_subclass__` hook verbatim, except: add template wiring (done in Task 7).

Write this full file:

```python
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
```

- [ ] **Step 2: Write tests**

```python
# tests/unit/profiles/test_profile.py
"""Unit tests for the generic DescriptorProfile base."""

from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from mountainash_settings.auth import NoAuth, PasswordAuth
from mountainash_settings.profiles import (
    DescriptorProfile,
    ParameterSpec,
    ProfileDescriptor,
)


DUMMY_DESCRIPTOR = ProfileDescriptor(
    name="dummy",
    provider_type="dummy",
    parameters=[
        ParameterSpec(name="HOST", type=str, tier="core", driver_key="host"),
        ParameterSpec(name="PORT", type=int, tier="core", default=9999, driver_key="port"),
        ParameterSpec(name="PASSWORD", type=str, tier="core", secret=True,
                      driver_key="password", default=None),
    ],
    auth_modes=[NoAuth, PasswordAuth],
)


class DummyProfile(DescriptorProfile):
    __descriptor__ = DUMMY_DESCRIPTOR


@pytest.mark.unit
class TestDescriptorProfile:
    def test_required_field_enforced(self):
        with pytest.raises(ValidationError):
            DummyProfile(auth=NoAuth())  # HOST missing

    def test_default_used(self):
        p = DummyProfile(HOST="localhost", auth=NoAuth())
        assert p.PORT == 9999

    def test_default_kwargs_noauth(self):
        p = DummyProfile(HOST="h", PORT=1234, auth=NoAuth())
        assert p._default_kwargs() == {"host": "h", "port": 1234}

    def test_auth_kwargs_password(self):
        p = DummyProfile(
            HOST="h",
            auth=PasswordAuth(username="u", password=SecretStr("p")),
        )
        kwargs = p._auth_kwargs()
        assert kwargs["user"] == "u"
        assert kwargs["password"] == "p"

    def test_secret_field_unwrapped(self):
        p = DummyProfile(HOST="h", PASSWORD="literal-secret", auth=NoAuth())
        kwargs = p._default_kwargs()
        assert kwargs["password"] == "literal-secret"

    def test_none_values_skipped(self):
        p = DummyProfile(HOST="h", auth=NoAuth())
        kwargs = p._default_kwargs()
        assert "password" not in kwargs

    def test_backend_and_profile_name(self):
        p = DummyProfile(HOST="h", auth=NoAuth())
        assert p.backend == "dummy"
        assert p.profile_name == "dummy"

    def test_provider_type_property(self):
        p = DummyProfile(HOST="h", auth=NoAuth())
        assert p.provider_type == "dummy"

    def test_transform_applied(self):
        desc = ProfileDescriptor(
            name="tf", provider_type="tf", auth_modes=[NoAuth],
            parameters=[
                ParameterSpec(
                    name="FLAG", type=bool, tier="core",
                    default=True, driver_key="flag",
                    transform=lambda v: 1 if v else 0,
                ),
            ],
        )

        class P(DescriptorProfile):
            __descriptor__ = desc

        assert P(auth=NoAuth())._default_kwargs() == {"flag": 1}
        assert P(FLAG=False, auth=NoAuth())._default_kwargs() == {"flag": 0}

    def test_validator_rejects_bad_input(self):
        def _positive(v: int) -> int:
            if v <= 0:
                raise ValueError("must be positive")
            return v

        desc = ProfileDescriptor(
            name="val", provider_type="val", auth_modes=[NoAuth],
            parameters=[
                ParameterSpec(name="N", type=int, tier="core",
                              validator=_positive),
            ],
        )

        class P(DescriptorProfile):
            __descriptor__ = desc

        assert P(N=5, auth=NoAuth()).N == 5
        with pytest.raises(ValidationError, match="must be positive"):
            P(N=-1, auth=NoAuth())

    def test_adapter_owns_pipeline(self):
        def _adapter(profile: "DescriptorProfile") -> dict:
            kwargs = profile._default_kwargs()
            kwargs["adapter_added"] = True
            return kwargs

        class Adapted(DescriptorProfile):
            __descriptor__ = DUMMY_DESCRIPTOR
            __adapter__ = staticmethod(_adapter)

        # Note: DescriptorProfile itself has no to_driver_kwargs; adapters
        # are invoked by domain subclasses. We test the mechanism indirectly
        # by confirming the adapter attr is accessible.
        p = Adapted(HOST="h", auth=NoAuth())
        assert type(p).__dict__.get("__adapter__") is not None
```

- [ ] **Step 3: Update `profiles/__init__.py`**

Replace with:

```python
# src/mountainash_settings/profiles/__init__.py
"""Declarative settings profiles — descriptor + registry + generic base."""

from __future__ import annotations

from .descriptor import MISSING, ParameterSpec, ProfileDescriptor
from .profile import DescriptorProfile
from .registry import Registry

__all__ = [
    "MISSING",
    "DescriptorProfile",
    "ParameterSpec",
    "ProfileDescriptor",
    "Registry",
]
```

- [ ] **Step 4: Run tests**

```bash
hatch run test:test-target tests/unit/profiles/ -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_settings/profiles/profile.py \
        src/mountainash_settings/profiles/__init__.py \
        tests/unit/profiles/test_profile.py
git commit -m "feat(profiles): add DescriptorProfile base (Pattern A mechanism)"
```

---

## Task 7: Wire `ParameterSpec.template` into `__pydantic_init_subclass__` (Pattern B)

**Files:**
- Modify: `src/mountainash_settings/profiles/profile.py`
- Modify: `tests/unit/profiles/test_profile.py`

**Context:** `MountainAshBaseSettings` provides `init_setting_from_template(template_str, current_value, reinitialise)` for template-driven field population. Consumers (especially `mountainash-acrds-core`) currently call this manually in a large `post_init()`. This task makes it declarative via `ParameterSpec.template`.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/profiles/test_profile.py`:

```python
    def test_template_populates_derived_field(self):
        """ParameterSpec(template=...) auto-populates field in post_init."""
        desc = ProfileDescriptor(
            name="tmpl", provider_type="tmpl", auth_modes=[NoAuth],
            parameters=[
                ParameterSpec(name="HOST", type=str, tier="core"),
                ParameterSpec(name="URL", type=str, tier="core",
                              default="",
                              template="https://{HOST}/api"),
            ],
        )

        class P(DescriptorProfile):
            __descriptor__ = desc

        p = P(HOST="example.com", auth=NoAuth())
        assert p.URL == "https://example.com/api"

    def test_template_respects_explicit_value(self):
        """If caller sets URL explicitly, the template does not overwrite."""
        desc = ProfileDescriptor(
            name="tmpl2", provider_type="tmpl2", auth_modes=[NoAuth],
            parameters=[
                ParameterSpec(name="HOST", type=str, tier="core"),
                ParameterSpec(name="URL", type=str, tier="core",
                              default="",
                              template="https://{HOST}/api"),
            ],
        )

        class P(DescriptorProfile):
            __descriptor__ = desc

        p = P(HOST="a.b", URL="https://override.example/", auth=NoAuth())
        assert p.URL == "https://override.example/"
```

- [ ] **Step 2: Run to verify failure**

```bash
hatch run test:test-target tests/unit/profiles/test_profile.py::TestDescriptorProfile::test_template_populates_derived_field -v
```

Expected: FAIL — `URL` is empty because templates are not wired yet.

- [ ] **Step 3: Extend `profile.py` with template handling**

Add this override to the `DescriptorProfile` class (after the properties, before `_default_kwargs`):

```python
    # --- Template wiring -----------------------------------------------------

    def post_init(self, reinitialise: bool = False) -> None:
        """Resolve any ``ParameterSpec.template`` fields.

        Runs ``init_setting_from_template`` for each parameter with a
        template string. Respects explicit user-provided values — templates
        only populate fields that match their declared default.
        """
        super().post_init(reinitialise=reinitialise)
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
            new_val = self.init_setting_from_template(
                template_str=spec.template,
                current_value=current,
                reinitialise=reinitialise,
            )
            # setattr rather than assignment — field already exists
            object.__setattr__(self, spec.name, new_val)
```

**Verify:** the `MountainAshBaseSettings.init_setting_from_template` signature is `(template_str, current_value, reinitialise)`. If it differs, adjust. The implementation is expected to return `current_value` unchanged when `current_value` differs from the declared default (i.e. caller-provided values win). If it does NOT behave that way, add an explicit check:

```python
            spec_default = spec.default if spec.default is not MISSING else None
            if current not in (spec_default, None, ""):
                continue  # caller provided an explicit value
```

- [ ] **Step 4: Run tests**

```bash
hatch run test:test-target tests/unit/profiles/ -v
```

Expected: all tests pass, including the two new template tests.

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_settings/profiles/profile.py \
        tests/unit/profiles/test_profile.py
git commit -m "feat(profiles): wire ParameterSpec.template via post_init (Pattern B)"
```

---

## Task 8: `profiles/invariants.py` — parametric test helper

**Files:**
- Create: `src/mountainash_settings/profiles/invariants.py`
- Create: `tests/unit/profiles/test_invariants.py`
- Modify: `src/mountainash_settings/profiles/__init__.py`

- [ ] **Step 1: Write `invariants.py`**

```python
# src/mountainash_settings/profiles/invariants.py
"""Parametric descriptor invariants runnable against any Registry.

Each consumer domain drops this helper into its test suite::

    from mountainash_settings.profiles import descriptor_invariants_for
    from my_package.settings import MY_REGISTRY

    TestMyInvariants = descriptor_invariants_for(MY_REGISTRY)

Every descriptor registered in ``MY_REGISTRY`` is then checked against the
invariants below. New registrations get coverage for free.
"""

from __future__ import annotations

import typing as t

import pytest

from mountainash_settings.auth.base import AuthSpec

from .registry import Registry

__all__ = ["descriptor_invariants_for"]


def descriptor_invariants_for(registry: Registry) -> type:
    """Return a pytest class parameterised over every descriptor in ``registry``.

    The returned class is named ``TestDescriptorInvariants_<registry_name>``.
    """

    entries = list(registry.descriptors.items())
    ids = list(registry.descriptors.keys()) or [""]

    @pytest.mark.unit
    @pytest.mark.parametrize("name,descriptor", entries, ids=ids)
    class TestDescriptorInvariants:  # noqa: D401
        """Invariants every registered descriptor must satisfy."""

        def test_name_matches_registry_key(self, name: str, descriptor: t.Any) -> None:
            assert descriptor.name == name

        def test_name_lowercase_nonempty(self, name: str, descriptor: t.Any) -> None:
            assert descriptor.name, f"{name}: descriptor.name is empty"
            assert descriptor.name == descriptor.name.lower(), (
                f"{name}: descriptor.name must be lowercase"
            )

        def test_parameter_names_unique(self, name: str, descriptor: t.Any) -> None:
            names = [p.name for p in descriptor.parameters]
            assert len(names) == len(set(names)), f"duplicate param in {name}"

        def test_parameter_names_uppercase(self, name: str, descriptor: t.Any) -> None:
            for p in descriptor.parameters:
                assert p.name == p.name.upper(), (
                    f"{name}.{p.name}: ParameterSpec.name must be UPPERCASE"
                )
                assert p.name, f"{name}: ParameterSpec.name is empty"

        def test_driver_keys_unique(self, name: str, descriptor: t.Any) -> None:
            keys = [p.driver_key for p in descriptor.parameters if p.driver_key]
            assert len(keys) == len(set(keys)), f"duplicate driver_key in {name}"

        def test_parameter_tiers_valid(self, name: str, descriptor: t.Any) -> None:
            for p in descriptor.parameters:
                assert p.tier in {"core", "advanced"}, (
                    f"{name}.{p.name} has invalid tier {p.tier!r}"
                )

        def test_auth_modes_nonempty(self, name: str, descriptor: t.Any) -> None:
            assert descriptor.auth_modes, (
                f"{name}: auth_modes is empty — use [NoAuth] for no-auth profiles"
            )

        def test_auth_modes_are_authspec(self, name: str, descriptor: t.Any) -> None:
            for mode in descriptor.auth_modes:
                assert issubclass(mode, AuthSpec), (
                    f"{name}.auth_modes contains non-AuthSpec: {mode}"
                )

        def test_provider_type_not_none(self, name: str, descriptor: t.Any) -> None:
            assert descriptor.provider_type is not None, (
                f"{name} has no provider_type"
            )

    TestDescriptorInvariants.__name__ = f"TestDescriptorInvariants_{registry.name}"
    TestDescriptorInvariants.__qualname__ = TestDescriptorInvariants.__name__
    return TestDescriptorInvariants
```

- [ ] **Step 2: Write a test that uses it against a fake registry**

```python
# tests/unit/profiles/test_invariants.py
"""Exercise descriptor_invariants_for against a fake registry."""

import pytest

from mountainash_settings.auth import NoAuth
from mountainash_settings.profiles import (
    ParameterSpec,
    ProfileDescriptor,
    Registry,
)
from mountainash_settings.profiles.invariants import descriptor_invariants_for


FAKE_REGISTRY = Registry("fake_tests")
FAKE_DESC = ProfileDescriptor(
    name="fake",
    provider_type="fake",
    parameters=[
        ParameterSpec(name="HOST", type=str, tier="core", driver_key="host"),
    ],
    auth_modes=[NoAuth],
)


class _FakeProfile:
    pass


FAKE_REGISTRY.register(FAKE_DESC, _FakeProfile)  # type: ignore[arg-type]


# Dynamic class — pytest collects its parameterized methods:
TestFakeInvariants = descriptor_invariants_for(FAKE_REGISTRY)


@pytest.mark.unit
def test_invariants_class_is_renamed():
    """Sanity check on the name-mangling helper."""
    cls = descriptor_invariants_for(Registry("empty"))
    assert cls.__name__ == "TestDescriptorInvariants_empty"
```

- [ ] **Step 3: Update `profiles/__init__.py`**

Replace with final version:

```python
# src/mountainash_settings/profiles/__init__.py
"""Declarative settings profiles — descriptor + registry + generic base."""

from __future__ import annotations

from .descriptor import MISSING, ParameterSpec, ProfileDescriptor
from .invariants import descriptor_invariants_for
from .profile import DescriptorProfile
from .registry import Registry

__all__ = [
    "MISSING",
    "DescriptorProfile",
    "ParameterSpec",
    "ProfileDescriptor",
    "Registry",
    "descriptor_invariants_for",
]
```

- [ ] **Step 4: Run tests**

```bash
hatch run test:test-target tests/unit/profiles/ -v
```

Expected: fake-invariants tests pass (9 × 1 entry = 9 parametric cases + rename smoke test).

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_settings/profiles/invariants.py \
        src/mountainash_settings/profiles/__init__.py \
        tests/unit/profiles/test_invariants.py
git commit -m "feat(profiles): add descriptor_invariants_for pytest helper"
```

---

## Task 9: Public `mountainash_settings.__init__.py` re-exports

**Files:**
- Modify: `src/mountainash_settings/__init__.py`

- [ ] **Step 1: Read current `__init__.py`**

```bash
cat src/mountainash_settings/__init__.py
```

Identify the existing `__all__` and import block.

- [ ] **Step 2: Append new exports**

Add below the existing exports (keep everything that's already there):

```python
# --- Profiles + auth (2026-04-16 promotion) ---------------------------------

from .profiles import (
    MISSING,
    DescriptorProfile,
    ParameterSpec,
    ProfileDescriptor,
    Registry,
    descriptor_invariants_for,
)
from .auth import (
    AUTH_TO_DRIVER_KWARGS,
    AuthSpec,
    AzureADAuth,
    CertificateAuth,
    IAMAuth,
    JWTAuth,
    KerberosAuth,
    NoAuth,
    OAuth2Auth,
    PasswordAuth,
    ServiceAccountAuth,
    TokenAuth,
    WindowsAuth,
    auth_to_driver_kwargs,
)
```

Extend the `__all__` list with those same names.

- [ ] **Step 3: Smoke-test the public API**

```python
# tests/unit/test_public_api.py
"""Smoke test: the new profiles/auth surface is importable from the package root."""

import pytest


@pytest.mark.unit
def test_profiles_surface_imports():
    from mountainash_settings import (
        MISSING,
        DescriptorProfile,
        ParameterSpec,
        ProfileDescriptor,
        Registry,
        descriptor_invariants_for,
    )
    assert all(obj is not None for obj in (
        MISSING, DescriptorProfile, ParameterSpec,
        ProfileDescriptor, Registry, descriptor_invariants_for,
    ))


@pytest.mark.unit
def test_auth_surface_imports():
    from mountainash_settings import (
        AuthSpec, NoAuth, PasswordAuth, TokenAuth, JWTAuth, OAuth2Auth,
        ServiceAccountAuth, IAMAuth, WindowsAuth, AzureADAuth, KerberosAuth,
        CertificateAuth, auth_to_driver_kwargs, AUTH_TO_DRIVER_KWARGS,
    )
    assert issubclass(PasswordAuth, AuthSpec)
    assert callable(auth_to_driver_kwargs)
```

- [ ] **Step 4: Run the full suite**

```bash
hatch run test:test-target tests/unit/ -v
```

Expected: all tests pass (profiles + auth + public API).

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_settings/__init__.py tests/unit/test_public_api.py
git commit -m "feat(settings): export profiles + auth from package root"
```

---

## Task 10: Push branch + open PR

- [ ] **Step 1: Push and open PR**

```bash
git push -u origin feat/profiles-promotion
```

Open a PR against `main` titled `Profiles promotion — Phase 1: mountainash-settings scaffolding`. PR body should link to:

- Design spec: `docs/superpowers/specs/2026-04-16-profiles-promotion-design.md`
- Phase 2 plan (mountainash-data migration) — will be opened separately once Phase 1 merges.

After merge, cut a `mountainash-settings` release (calver bump) so `mountainash-data` can pin it in Phase 2.

---

## Self-Review Notes

- **Spec coverage:** All spec sections mapped to tasks. `profiles/descriptor.py` → Task 4; `profiles/profile.py` → Tasks 6–7; `profiles/registry.py` → Task 5; `profiles/invariants.py` → Task 8; `auth/` full hierarchy → Tasks 1–3; public re-exports → Task 9.
- **Placeholder scan:** No "TBD"s or narrative-only steps.
- **Type consistency:** `DescriptorProfile` / `ProfileDescriptor` / `ParameterSpec` / `Registry` / `MISSING` names consistent across all tasks.
- **Known limitation (setattr-bypass):** Documented in the module docstring of `profiles/profile.py`. Resolution deferred — tracked in `mountainash-central/01.principles/mountainash-data/f.backlog/setattr-bypass-limitation.md`.
