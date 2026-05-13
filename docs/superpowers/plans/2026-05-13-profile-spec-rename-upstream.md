# Profile / ProfileSpec rename — mountainash-settings 26.5.0 upstream implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the upstream half of the [profile-spec rename design](../specs/2026-05-13-profile-spec-rename-design.md) in `mountainash-settings 26.5.0`. Rename `ProfileDescriptor` → `ProfileSpec` and `DescriptorProfile` → `Profile`, add a public `lookup_class_var()` helper, tighten the `Registry` API with type constraints, switch `@register` to an argument-free form, and ship deprecation aliases for one release cycle.

**Architecture:** Two new modules (`spec.py`, `lookup.py`) house the renamed types and the public helper. `descriptor.py` becomes a re-export shim with PEP 562 `__getattr__` for deprecation warnings. `profile.py`, `registry.py`, and `invariants.py` are updated in place. Deprecation warnings fire on three layers: module-level (PEP 562 `__getattr__`), class-attribute (`__pydantic_init_subclass__` fallback), and decorator form (`@register(spec)` old shape). `Registry.register()` mirrors `__spec__` to `__descriptor__` during 26.5.x so downstream *readers* of the old attribute keep working until 26.6.0.

**Tech Stack:** Python 3.12+, pydantic 2.x, pydantic-settings 2.x, pytest, hatch.

**Spec:** `docs/superpowers/specs/2026-05-13-profile-spec-rename-design.md`

**Out of scope:** downstream `mountainash-data` migration (separate plan that follows the spec's migration guide), removal release `26.6.0`, package profile refresh.

---

## File structure

**New files:**
- `src/mountainash_settings/profiles/spec.py` — canonical home for `ProfileSpec`, `Missing`, `MISSING`, `ParameterSpec`. Ports the contents of the existing `descriptor.py` with renames.
- `src/mountainash_settings/profiles/lookup.py` — public `lookup_class_var(cls, name)` helper.
- `tests/unit/profiles/test_spec.py` — replaces `test_descriptor.py` (which is deleted at the end).
- `tests/unit/profiles/test_lookup.py` — covers the new helper.
- `tests/unit/profiles/test_deprecation.py` — covers all deprecation paths.

**Modified files:**
- `src/mountainash_settings/profiles/descriptor.py` — converted to compatibility shim. Re-imports `MISSING` and `ParameterSpec` (unchanged names). PEP 562 `__getattr__` for deprecated `ProfileDescriptor` and `_Missing`.
- `src/mountainash_settings/profiles/profile.py` — class rename, `__spec__` attribute, MRO fallback for `__descriptor__`, uses `lookup_class_var`.
- `src/mountainash_settings/profiles/registry.py` — constructor `spec_type`/`profile_type` constraints, argument-free `@register` form (with old form deprecated), `__spec__` mirrored to `__descriptor__` on register.
- `src/mountainash_settings/profiles/invariants.py` — rename `descriptor_invariants_for` to `spec_invariants_for`; rename generated class.
- `src/mountainash_settings/profiles/__init__.py` — new exports + `__getattr__` deprecation shim.
- `src/mountainash_settings/__init__.py` — re-exports at top level + `__getattr__` deprecation shim.
- `src/mountainash_settings/__version__.py` — bump to `26.5.0`.
- `tests/unit/profiles/test_profile.py` — references updated (`DescriptorProfile` → `Profile`, `__descriptor__` → `__spec__`).
- `tests/unit/profiles/test_registry.py` — new tests for constraints, bare `@register`, mirror behaviour.
- `tests/unit/profiles/test_invariants.py` — references updated.
- `tests/unit/test_public_api.py` — references updated.
- `docs/quickstart.md` — names updated.
- `docs/advanced-usage.md` — names updated.
- `docs/README.md` (project README) — names updated.

**Renamed files:**
- `docs/profile-descriptor-pattern.md` → `docs/profile-spec-pattern.md`.
- `tests/unit/profiles/test_descriptor.py` → `tests/unit/profiles/test_spec.py`.

---

## Task 1: Public `lookup_class_var()` helper

**Files:**
- Create: `src/mountainash_settings/profiles/lookup.py`
- Create: `tests/unit/profiles/test_lookup.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/profiles/test_lookup.py`:

```python
"""Unit tests for the public lookup_class_var helper."""

import pytest

from mountainash_settings.profiles.lookup import lookup_class_var


class _Base:
    __marker__ = "from_base"


class _Mid(_Base):
    pass


class _Leaf(_Mid):
    __marker__ = "from_leaf"


class _Bare:
    pass


@pytest.mark.unit
class TestLookupClassVar:
    def test_returns_own_dict_value(self):
        assert lookup_class_var(_Leaf, "__marker__") == "from_leaf"

    def test_walks_mro_to_base(self):
        assert lookup_class_var(_Mid, "__marker__") == "from_base"

    def test_returns_none_when_absent(self):
        assert lookup_class_var(_Bare, "__nonexistent__") is None

    def test_returns_first_match_in_mro_order(self):
        # _Leaf overrides — confirms it's the leaf's value, not the base's
        assert lookup_class_var(_Leaf, "__marker__") != "from_base"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
hatch run test:test tests/unit/profiles/test_lookup.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'mountainash_settings.profiles.lookup'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/mountainash_settings/profiles/lookup.py`:

```python
"""Public MRO-walking helper for class-level attribute lookup.

Used by Profile to resolve __spec__ (and __descriptor__ during deprecation)
and __adapter__. Exposed as public API so downstream consumers can use it
for their own class-level dunder lookups without depending on private symbols.
"""

from __future__ import annotations

import typing as t

__all__ = ["lookup_class_var"]


def lookup_class_var(cls: type, name: str) -> t.Any | None:
    """Walk cls.__mro__ and return the first __dict__ value for `name`.

    Returns None when the attribute is not found anywhere in the MRO.

    Args:
        cls: The class to start from.
        name: The attribute name to look up.

    Returns:
        The first value found in any class's __dict__ along the MRO,
        or None if no class in the MRO defines `name`.
    """
    for klass in cls.__mro__:
        if name in klass.__dict__:
            return klass.__dict__[name]
    return None
```

- [ ] **Step 4: Run test to verify it passes**

```bash
hatch run test:test tests/unit/profiles/test_lookup.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Run full test suite to verify no regression**

```bash
hatch run test:test
```

Expected: all existing tests still pass; new test file appears in summary.

- [ ] **Step 6: Commit**

```bash
git add src/mountainash_settings/profiles/lookup.py tests/unit/profiles/test_lookup.py
git commit -m "feat(profiles): add public lookup_class_var helper

New mountainash_settings.profiles.lookup module exposes lookup_class_var(cls, name),
which walks __mro__ and returns the first matching attribute. Used internally
by Profile for __spec__ and __adapter__ lookup; documented as supported public
API from 26.5.0 so downstream consumers can adopt it without taking a
private-dependency risk.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Create `spec.py` with `ProfileSpec` and `Missing`

**Files:**
- Create: `src/mountainash_settings/profiles/spec.py`
- Create: `tests/unit/profiles/test_spec.py`
- Reference: `src/mountainash_settings/profiles/descriptor.py` (verbatim port source)

- [ ] **Step 1: Write the test file (port + rename of existing `test_descriptor.py`)**

Create `tests/unit/profiles/test_spec.py`:

```python
# tests/unit/profiles/test_spec.py
"""Unit tests for ProfileSpec, ParameterSpec, Missing, and MISSING."""

import pytest

from mountainash_settings.auth import NoAuth
from mountainash_settings.profiles.spec import (
    MISSING,
    Missing,
    ParameterSpec,
    ProfileSpec,
)


@pytest.mark.unit
class TestMissing:
    def test_missing_is_singleton(self):
        assert Missing() is MISSING

    def test_missing_is_falsy(self):
        assert not MISSING

    def test_missing_repr(self):
        assert repr(MISSING) == "MISSING"


@pytest.mark.unit
class TestParameterSpec:
    def test_minimal(self):
        p = ParameterSpec(name="X", type=str, tier="core")
        assert p.name == "X"
        assert p.type is str
        assert p.tier == "core"
        assert p.default is MISSING
        assert p.driver_key is None
        assert p.secret is False
        assert p.transform is None
        assert p.validator is None
        assert p.template is None

    def test_with_default(self):
        p = ParameterSpec(name="X", type=int, tier="core", default=42)
        assert p.default == 42

    def test_secret_flag(self):
        p = ParameterSpec(name="PWD", type=str, tier="core", secret=True)
        assert p.secret is True

    def test_frozen(self):
        p = ParameterSpec(name="X", type=str, tier="core")
        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            p.name = "Y"


@pytest.mark.unit
class TestProfileSpec:
    def test_minimal(self):
        spec = ProfileSpec(
            name="test",
            provider_type="test",
            parameters=[],
            auth_modes=[NoAuth],
        )
        assert spec.name == "test"
        assert spec.provider_type == "test"
        assert spec.parameters == []
        assert spec.auth_modes == [NoAuth]
        assert spec.metadata == {}

    def test_with_parameters(self):
        params = [ParameterSpec(name="HOST", type=str, tier="core", driver_key="host")]
        spec = ProfileSpec(
            name="test",
            provider_type="test",
            parameters=params,
            auth_modes=[NoAuth],
        )
        assert spec.parameters == params

    def test_frozen(self):
        spec = ProfileSpec(
            name="test",
            provider_type="test",
            parameters=[],
            auth_modes=[NoAuth],
        )
        with pytest.raises(Exception):  # FrozenInstanceError
            spec.name = "other"

    def test_metadata(self):
        spec = ProfileSpec(
            name="test",
            provider_type="test",
            parameters=[],
            auth_modes=[NoAuth],
            metadata={"port": 5432},
        )
        assert spec.metadata == {"port": 5432}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
hatch run test:test tests/unit/profiles/test_spec.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'mountainash_settings.profiles.spec'`.

- [ ] **Step 3: Create `spec.py` (verbatim port of descriptor.py with renames)**

Create `src/mountainash_settings/profiles/spec.py`:

```python
# src/mountainash_settings/profiles/spec.py
"""Declarative specifications for settings profiles.

A ProfileSpec captures everything the generic Profile base needs to install
pydantic fields for a given configuration. A ParameterSpec describes one field
within a spec.

This module is the canonical home for these types. The old module
`mountainash_settings.profiles.descriptor` remains as a compatibility shim
exporting `ProfileDescriptor` (alias for `ProfileSpec`) and `_Missing`
(alias for `Missing`) with DeprecationWarning until 26.6.0.
"""

from __future__ import annotations

import typing as t
from dataclasses import dataclass, field

__all__ = ["MISSING", "Missing", "ParameterSpec", "ProfileSpec"]


class Missing:
    """Sentinel indicating a required (no-default) field.

    Pydantic ``Field(...)`` is emitted when a ParameterSpec default is this
    sentinel; ``Field(default=...)`` otherwise.

    Public from mountainash-settings 26.5.0. Previously available as the
    private ``_Missing`` class in ``mountainash_settings.profiles.descriptor``.
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
        template: Optional template string; when set, :class:`Profile`
            auto-wires ``init_setting_from_template`` in ``post_init`` to
            populate this field.
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
class ProfileSpec:
    """Immutable specification of a single settings profile.

    Attributes:
        name: Short name (conventionally lowercase, e.g. ``"postgresql"``).
        provider_type: Canonical provider identifier (domain-specific enum).
        parameters: Ordered list of :class:`ParameterSpec`.
        auth_modes: List of :class:`AuthSpec` subclasses this profile accepts.
        metadata: Bag of domain-specific metadata (e.g. port, URL scheme,
            dialect name). Domains wanting strong typing may subclass
            ``ProfileSpec`` and add typed fields instead.

    Public from 26.5.0. Previously named ``ProfileDescriptor``.
    """

    name: str
    provider_type: t.Any
    parameters: list[ParameterSpec]
    auth_modes: list[type]  # list[type[AuthSpec]] — forward-refd to avoid cycle
    metadata: dict[str, t.Any] = field(default_factory=dict)
```

- [ ] **Step 4: Run new test to verify it passes**

```bash
hatch run test:test tests/unit/profiles/test_spec.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Run full suite — existing `test_descriptor.py` must still pass**

```bash
hatch run test:test tests/unit/profiles/
```

Expected: both test files pass. `descriptor.py` still defines its own `ProfileDescriptor`/`_Missing`/`MISSING`/`ParameterSpec` — the two modules coexist briefly.

- [ ] **Step 6: Commit**

```bash
git add src/mountainash_settings/profiles/spec.py tests/unit/profiles/test_spec.py
git commit -m "feat(profiles): add spec.py with renamed ProfileSpec and Missing

New canonical module mountainash_settings.profiles.spec exposes:
- ProfileSpec (was ProfileDescriptor)
- Missing (was _Missing, now public)
- MISSING (unchanged)
- ParameterSpec (unchanged)

Old names remain available from descriptor.py in this commit; the
descriptor.py shim conversion comes in a later task.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Rename `DescriptorProfile` to `Profile`; new `__spec__` attribute and fallback

**Files:**
- Modify: `src/mountainash_settings/profiles/profile.py`
- Modify: `tests/unit/profiles/test_profile.py`

- [ ] **Step 1: Update the test file to use new names**

Open `tests/unit/profiles/test_profile.py`. Replace all occurrences:

- `from mountainash_settings.profiles import DescriptorProfile, ParameterSpec, ProfileDescriptor` → `from mountainash_settings.profiles import Profile, ParameterSpec, ProfileSpec`
- `DescriptorProfile` → `Profile` (class references)
- `ProfileDescriptor` → `ProfileSpec` (constructor references)
- `__descriptor__` → `__spec__` (in class bodies)
- `DUMMY_DESCRIPTOR` → `DUMMY_SPEC` (consistency)

Add new tests at the end of the file:

```python
@pytest.mark.unit
class TestSpecAttributeFallback:
    """Tests for the __spec__ / __descriptor__ deprecation fallback."""

    def test_old_descriptor_attribute_emits_warning(self):
        """A class declaring only __descriptor__ (no __spec__) still works
        but emits DeprecationWarning at class creation."""
        with pytest.warns(DeprecationWarning, match="__descriptor__.*deprecated"):
            class OldStyleProfile(Profile):
                __descriptor__ = DUMMY_SPEC

        # Field installation still works from the old attribute
        instance = OldStyleProfile(HOST="h", auth=NoAuth())
        assert instance.HOST == "h"

    def test_conflicting_spec_and_descriptor_raises(self):
        """Declaring both __spec__ and __descriptor__ with different values raises."""
        OTHER_SPEC = ProfileSpec(
            name="other", provider_type="other",
            parameters=[ParameterSpec(name="HOST", type=str, tier="core", driver_key="host")],
            auth_modes=[NoAuth],
        )
        with pytest.raises(TypeError, match="conflicting"):
            class ConflictProfile(Profile):
                __spec__ = DUMMY_SPEC
                __descriptor__ = OTHER_SPEC

    def test_matching_spec_and_descriptor_no_warning(self):
        """Declaring both pointing at the same object works without warning."""
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            class BothProfile(Profile):
                __spec__ = DUMMY_SPEC
                __descriptor__ = DUMMY_SPEC
            # No warning raised — test passes by reaching this line
        assert BothProfile.__spec__ is DUMMY_SPEC
```

Also add at the top of the file:

```python
import warnings
```

- [ ] **Step 2: Run test to verify it fails**

```bash
hatch run test:test tests/unit/profiles/test_profile.py -v
```

Expected: FAIL — `ImportError: cannot import name 'Profile' from 'mountainash_settings.profiles'`.

- [ ] **Step 3: Update `profile.py`**

Open `src/mountainash_settings/profiles/profile.py`. Replace its full contents with:

```python
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
            DeprecationWarning, stacklevel=3,
        )
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
```

- [ ] **Step 4: Run the updated `test_profile.py`**

```bash
hatch run test:test tests/unit/profiles/test_profile.py -v
```

Expected: all tests pass, including the three new `TestSpecAttributeFallback` tests.

- [ ] **Step 5: Confirm no other test files broke**

```bash
hatch run test:test tests/unit/profiles/
```

Expected: `test_descriptor.py`, `test_invariants.py`, `test_registry.py`, `test_spec.py`, `test_lookup.py`, `test_profile.py` all pass. `test_descriptor.py` still uses old name `ProfileDescriptor` which is still importable from `descriptor.py`.

- [ ] **Step 6: Confirm the broader test suite is green**

```bash
hatch run test:test
```

Expected: full suite passes. Existing code that still uses `DescriptorProfile` (none in this repo yet — Profile is the new name) works because `DescriptorProfile` does not yet have an alias (will be added in Task 9).

- [ ] **Step 7: Commit**

```bash
git add src/mountainash_settings/profiles/profile.py tests/unit/profiles/test_profile.py
git commit -m "feat(profiles): rename DescriptorProfile to Profile, add __spec__ attribute

- Profile class replaces DescriptorProfile (old name aliased in Task 9).
- Class attribute __spec__ replaces __descriptor__.
- __pydantic_init_subclass__ accepts either attribute; raises TypeError
  on conflict, emits DeprecationWarning on __descriptor__-only.
- post_init() uses the public lookup_class_var helper for MRO walks.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Add `Registry` constructor type constraints

**Files:**
- Modify: `src/mountainash_settings/profiles/registry.py`
- Modify: `tests/unit/profiles/test_registry.py`

- [ ] **Step 1: Write failing tests for the constructor constraints**

Open `tests/unit/profiles/test_registry.py`. Add at the end:

```python
from mountainash_settings.profiles import Profile, ProfileSpec, Registry, ParameterSpec
from mountainash_settings.auth import NoAuth


class _CustomSpec(ProfileSpec):
    pass


class _CustomProfile(Profile):
    pass


@pytest.mark.unit
class TestRegistryConstraints:
    def test_default_construction_unchanged(self):
        """Registry() with no constraints still works (backwards compatible)."""
        reg = Registry("default_test")
        assert reg.name == "default_test"

    def test_spec_type_accepts_matching(self):
        """spec_type=_CustomSpec accepts _CustomSpec instances."""
        reg = Registry("custom_spec_test", spec_type=_CustomSpec)
        spec = _CustomSpec(
            name="custom", provider_type="custom",
            parameters=[ParameterSpec(name="HOST", type=str, tier="core", driver_key="host")],
            auth_modes=[NoAuth],
        )
        class P(Profile):
            __spec__ = spec
        reg.register(spec, P)  # should not raise
        assert "custom" in reg

    def test_spec_type_rejects_plain_profilespec(self):
        """spec_type=_CustomSpec rejects a plain ProfileSpec instance."""
        reg = Registry("reject_test", spec_type=_CustomSpec)
        plain = ProfileSpec(
            name="plain", provider_type="plain",
            parameters=[ParameterSpec(name="HOST", type=str, tier="core", driver_key="host")],
            auth_modes=[NoAuth],
        )
        class P(Profile):
            __spec__ = plain
        with pytest.raises(TypeError, match="spec_type"):
            reg.register(plain, P)

    def test_profile_type_accepts_matching(self):
        """profile_type=_CustomProfile accepts _CustomProfile subclasses."""
        reg = Registry("profile_match", profile_type=_CustomProfile)
        spec = ProfileSpec(
            name="cm", provider_type="cm",
            parameters=[ParameterSpec(name="HOST", type=str, tier="core", driver_key="host")],
            auth_modes=[NoAuth],
        )
        class P(_CustomProfile):
            __spec__ = spec
        reg.register(spec, P)
        assert "cm" in reg

    def test_profile_type_rejects_non_subclass(self):
        """profile_type=_CustomProfile rejects a plain Profile subclass."""
        reg = Registry("profile_reject", profile_type=_CustomProfile)
        spec = ProfileSpec(
            name="pr", provider_type="pr",
            parameters=[ParameterSpec(name="HOST", type=str, tier="core", driver_key="host")],
            auth_modes=[NoAuth],
        )
        class P(Profile):
            __spec__ = spec
        with pytest.raises(TypeError, match="profile_type"):
            reg.register(spec, P)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
hatch run test:test tests/unit/profiles/test_registry.py::TestRegistryConstraints -v
```

Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'spec_type'`.

- [ ] **Step 3: Update `registry.py`**

Open `src/mountainash_settings/profiles/registry.py`. Replace its contents with:

```python
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
        spec_type: type[ProfileSpec] = ProfileSpec,
        profile_type: type | None = None,
    ) -> None:
        """Construct a Registry with optional type constraints.

        Args:
            name: Registry name (used in error messages and test IDs).
            spec_type: Required base class for registered specs. Defaults to
                ``ProfileSpec``. Passing a stricter subclass narrows what
                ``register()`` accepts.
            profile_type: Required base class for registered profile classes.
                Defaults to ``Profile`` (resolved lazily to avoid a circular
                import). Passing a stricter subclass narrows what
                ``register()`` accepts.
        """
        self.name = name
        self._spec_type = spec_type
        # Resolve Profile lazily to break the circular import (Profile
        # imports Registry-adjacent symbols).
        if profile_type is None:
            from .profile import Profile
            profile_type = Profile
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
        if not isinstance(spec, self._spec_type):
            raise TypeError(
                f"Registry {self.name!r}: spec_type mismatch — expected "
                f"{self._spec_type.__name__}, got {type(spec).__name__}"
            )
        if not issubclass(cls, self._profile_type):
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

        - Bare ``@register`` (new canonical form): reads ``cls.__spec__`` and
          registers under its name.
        - ``@register(spec)`` (deprecated): emits ``DeprecationWarning``;
          validates the argument matches ``cls.__spec__`` if declared.
        """
        # NOTE: The bare/with-arg disambiguation in this method is implemented
        # in a later task (Task 5). For now, only the with-arg form works.

        def _outer(spec: ProfileSpec) -> t.Callable[[type[T]], type[T]]:
            def _wrap(cls: type[T]) -> type[T]:
                self.register(spec, cls)
                return cls
            return _wrap

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
```

- [ ] **Step 4: Run the new constraint tests**

```bash
hatch run test:test tests/unit/profiles/test_registry.py::TestRegistryConstraints -v
```

Expected: 5 tests pass.

- [ ] **Step 5: Run full registry tests**

```bash
hatch run test:test tests/unit/profiles/test_registry.py -v
```

Expected: existing tests + new tests all pass.

- [ ] **Step 6: Run full suite**

```bash
hatch run test:test
```

Expected: full suite passes.

- [ ] **Step 7: Commit**

```bash
git add src/mountainash_settings/profiles/registry.py tests/unit/profiles/test_registry.py
git commit -m "feat(profiles): Registry constructor accepts spec_type/profile_type

Registry(name, *, spec_type=ProfileSpec, profile_type=Profile) lets
domain-specific registries declare their constraints at construction time.
register() raises TypeError on spec or class type mismatch. Default values
preserve the existing wide-open behaviour for callers that don't pass
constraints.

Also mirrors __spec__ to __descriptor__ on register() during the 26.5.x
deprecation window (dropped in 26.6.0) so downstream code reading the old
attribute keeps working.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Argument-free `@register` decorator (with old-form deprecation)

**Files:**
- Modify: `src/mountainash_settings/profiles/registry.py` (only `decorator()` method)
- Modify: `tests/unit/profiles/test_registry.py`

- [ ] **Step 1: Write failing tests for the new decorator shapes**

Append to `tests/unit/profiles/test_registry.py`:

```python
@pytest.mark.unit
class TestBareRegisterDecorator:
    """Tests for the new argument-free @register form."""

    def test_bare_register_reads_spec_from_class(self):
        reg = Registry("bare_test")
        register = reg.decorator()

        spec = ProfileSpec(
            name="bare", provider_type="bare",
            parameters=[ParameterSpec(name="HOST", type=str, tier="core", driver_key="host")],
            auth_modes=[NoAuth],
        )

        @register
        class BareProfile(Profile):
            __spec__ = spec

        assert "bare" in reg
        assert reg.get_settings_class("bare") is BareProfile

    def test_bare_register_raises_when_spec_missing(self):
        reg = Registry("bare_missing")
        register = reg.decorator()

        with pytest.raises(TypeError, match="__spec__"):
            @register
            class NoSpecProfile(Profile):
                pass  # no __spec__ declared

    def test_old_form_emits_deprecation_warning(self):
        reg = Registry("old_form")
        register = reg.decorator()

        spec = ProfileSpec(
            name="old", provider_type="old",
            parameters=[ParameterSpec(name="HOST", type=str, tier="core", driver_key="host")],
            auth_modes=[NoAuth],
        )

        with pytest.warns(DeprecationWarning, match="@register\\(spec\\).*deprecated"):
            @register(spec)
            class OldFormProfile(Profile):
                __spec__ = spec

        assert "old" in reg

    def test_old_form_drift_catch(self):
        """@register(SPEC_A) on a class with __spec__ = SPEC_B raises."""
        reg = Registry("drift_test")
        register = reg.decorator()

        spec_a = ProfileSpec(
            name="a", provider_type="a",
            parameters=[ParameterSpec(name="HOST", type=str, tier="core", driver_key="host")],
            auth_modes=[NoAuth],
        )
        spec_b = ProfileSpec(
            name="b", provider_type="b",
            parameters=[ParameterSpec(name="HOST", type=str, tier="core", driver_key="host")],
            auth_modes=[NoAuth],
        )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            with pytest.raises(TypeError, match="disagree"):
                @register(spec_a)
                class DriftProfile(Profile):
                    __spec__ = spec_b
```

- [ ] **Step 2: Run test to verify it fails**

```bash
hatch run test:test tests/unit/profiles/test_registry.py::TestBareRegisterDecorator -v
```

Expected: FAIL — bare `@register` tries to invoke the current `_outer(spec)` with a class, which won't pass `isinstance(spec, ProfileSpec)`.

- [ ] **Step 3: Update `Registry.decorator()`**

In `src/mountainash_settings/profiles/registry.py`, replace the `decorator()` method body with:

```python
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

            # With-spec form (deprecated).
            if isinstance(arg, ProfileSpec):
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
```

- [ ] **Step 4: Run the new tests**

```bash
hatch run test:test tests/unit/profiles/test_registry.py::TestBareRegisterDecorator -v
```

Expected: 4 tests pass.

- [ ] **Step 5: Run full registry tests and confirm constraints still hold**

```bash
hatch run test:test tests/unit/profiles/test_registry.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Run full suite**

```bash
hatch run test:test
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add src/mountainash_settings/profiles/registry.py tests/unit/profiles/test_registry.py
git commit -m "feat(profiles): @register supports argument-free form

@register (no args) reads cls.__spec__ and registers — the new canonical
form, naming the spec exactly once. @register(spec) still works during
deprecation with a DeprecationWarning, and additionally raises TypeError
if the argument disagrees with cls.__spec__ (drift catch).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Verify mirror behaviour with an integration test

**Files:**
- Modify: `tests/unit/profiles/test_registry.py`

The mirror logic landed in Task 4. This task adds the explicit integration test that the spec mandates.

- [ ] **Step 1: Add the mirror test**

Append to `tests/unit/profiles/test_registry.py`:

```python
@pytest.mark.unit
class TestSpecDescriptorMirror:
    """Tests for the __spec__ → __descriptor__ deprecation mirror.

    During 26.5.x, Registry.register() sets both attributes to the same
    object so downstream code reading cls.__descriptor__ keeps working.
    This whole class is deleted in 26.6.0.
    """

    def test_bare_register_mirrors_spec_to_descriptor(self):
        reg = Registry("mirror_test")
        register = reg.decorator()

        spec = ProfileSpec(
            name="mirror", provider_type="mirror",
            parameters=[ParameterSpec(name="HOST", type=str, tier="core", driver_key="host")],
            auth_modes=[NoAuth],
        )

        @register
        class MirrorProfile(Profile):
            __spec__ = spec

        # Both class-level attributes resolve to the same object
        assert MirrorProfile.__spec__ is spec
        assert MirrorProfile.__descriptor__ is spec
        assert MirrorProfile.__descriptor__ is MirrorProfile.__spec__

        # And on instances too
        instance = MirrorProfile(HOST="h", auth=NoAuth())
        assert instance.__descriptor__ is spec
        assert instance.__spec__ is spec
```

- [ ] **Step 2: Run the mirror test**

```bash
hatch run test:test tests/unit/profiles/test_registry.py::TestSpecDescriptorMirror -v
```

Expected: 1 test passes (the mirror logic was already implemented in Task 4).

- [ ] **Step 3: Commit**

```bash
git add tests/unit/profiles/test_registry.py
git commit -m "test(profiles): assert __spec__/__descriptor__ mirror on register

Locks in the deprecation contract that downstream readers of
cls.__descriptor__ keep working through 26.5.x. Whole test class is
deleted in 26.6.0 when the mirror is dropped.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Rename `descriptor_invariants_for` → `spec_invariants_for`

**Files:**
- Modify: `src/mountainash_settings/profiles/invariants.py`
- Modify: `tests/unit/profiles/test_invariants.py`

- [ ] **Step 1: Update the test file to use new names**

Open `tests/unit/profiles/test_invariants.py`. Replace:

- `from mountainash_settings.profiles.invariants import descriptor_invariants_for` → `from mountainash_settings.profiles.invariants import spec_invariants_for`
- All `descriptor_invariants_for(` call sites → `spec_invariants_for(`
- Any `TestDescriptorInvariants_*` references → `TestSpecInvariants_*`

The two occurrences of the dynamic class name in the test file should be updated to expect the new prefix.

- [ ] **Step 2: Run test to verify it fails**

```bash
hatch run test:test tests/unit/profiles/test_invariants.py -v
```

Expected: FAIL — `ImportError: cannot import name 'spec_invariants_for' from 'mountainash_settings.profiles.invariants'`.

- [ ] **Step 3: Update `invariants.py`**

Open `src/mountainash_settings/profiles/invariants.py`. Replace its contents with:

```python
# src/mountainash_settings/profiles/invariants.py
"""Parametric spec invariants runnable against any Registry.

Each consumer domain drops this helper into its test suite::

    from mountainash_settings.profiles import spec_invariants_for
    from my_package.settings import MY_REGISTRY

    TestMyInvariants = spec_invariants_for(MY_REGISTRY)

Every spec registered in ``MY_REGISTRY`` is then checked against the
invariants below. New registrations get coverage for free.

Public from 26.5.0. Previously named ``descriptor_invariants_for``.
"""

from __future__ import annotations

import typing as t

from mountainash_settings.auth.base import AuthSpec

from .registry import Registry

__all__ = ["spec_invariants_for"]


def spec_invariants_for(registry: Registry) -> type:
    """Return a pytest class parameterised over every spec in ``registry``.

    The returned class is named ``TestSpecInvariants_<registry_name>``.
    """

    # Lazy import: keeps ``mountainash_settings`` importable in non-test envs.
    import pytest

    entries = list(registry.descriptors.items())
    ids = list(registry.descriptors.keys()) or [""]

    @pytest.mark.unit
    @pytest.mark.parametrize("name,spec", entries, ids=ids)
    class TestSpecInvariants:  # noqa: D401
        """Invariants every registered spec must satisfy."""

        def test_name_matches_registry_key(self, name: str, spec: t.Any) -> None:
            assert spec.name == name

        def test_name_lowercase_nonempty(self, name: str, spec: t.Any) -> None:
            assert spec.name, f"{name}: spec.name is empty"
            assert spec.name == spec.name.lower(), (
                f"{name}: spec.name must be lowercase"
            )

        def test_parameter_names_unique(self, name: str, spec: t.Any) -> None:
            names = [p.name for p in spec.parameters]
            assert len(names) == len(set(names)), f"duplicate param in {name}"

        def test_parameter_names_uppercase(self, name: str, spec: t.Any) -> None:
            for p in spec.parameters:
                assert p.name == p.name.upper(), (
                    f"{name}.{p.name}: ParameterSpec.name must be UPPERCASE"
                )
                assert p.name, f"{name}: ParameterSpec.name is empty"

        def test_driver_keys_unique(self, name: str, spec: t.Any) -> None:
            keys = [p.driver_key for p in spec.parameters if p.driver_key]
            assert len(keys) == len(set(keys)), f"duplicate driver_key in {name}"

        def test_parameter_tiers_valid(self, name: str, spec: t.Any) -> None:
            for p in spec.parameters:
                assert p.tier in {"core", "advanced"}, (
                    f"{name}.{p.name} has invalid tier {p.tier!r}"
                )

        def test_auth_modes_nonempty(self, name: str, spec: t.Any) -> None:
            assert spec.auth_modes, (
                f"{name}: auth_modes is empty — use [NoAuth] for no-auth profiles"
            )

        def test_auth_modes_are_authspec(self, name: str, spec: t.Any) -> None:
            for mode in spec.auth_modes:
                assert issubclass(mode, AuthSpec), (
                    f"{name}.auth_modes contains non-AuthSpec: {mode}"
                )

        def test_provider_type_not_none(self, name: str, spec: t.Any) -> None:
            assert spec.provider_type is not None, (
                f"{name} has no provider_type"
            )

    TestSpecInvariants.__name__ = f"TestSpecInvariants_{registry.name}"
    TestSpecInvariants.__qualname__ = TestSpecInvariants.__name__
    return TestSpecInvariants
```

- [ ] **Step 4: Run the invariants test**

```bash
hatch run test:test tests/unit/profiles/test_invariants.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Run full suite**

```bash
hatch run test:test
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/mountainash_settings/profiles/invariants.py tests/unit/profiles/test_invariants.py
git commit -m "feat(profiles): rename descriptor_invariants_for to spec_invariants_for

Function and generated test class renamed:
- descriptor_invariants_for() -> spec_invariants_for()
- TestDescriptorInvariants_<name> -> TestSpecInvariants_<name>
- parametrize ID 'descriptor' -> 'spec'

Old name aliased in Task 9.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Convert `descriptor.py` to a compatibility shim

**Files:**
- Modify: `src/mountainash_settings/profiles/descriptor.py`
- Delete: `tests/unit/profiles/test_descriptor.py` (superseded by `test_spec.py` from Task 2)

The current `descriptor.py` is the live canonical home for `ProfileDescriptor` etc. After this task, it becomes a thin shim that re-exports from `spec.py` and warns on deprecated names.

- [ ] **Step 1: Replace `descriptor.py` contents**

Open `src/mountainash_settings/profiles/descriptor.py`. Replace its full contents with:

```python
# src/mountainash_settings/profiles/descriptor.py
"""Compatibility shim for the pre-26.5.0 module location.

The canonical home for ``ProfileSpec``, ``Missing``, ``MISSING``, and
``ParameterSpec`` is :mod:`mountainash_settings.profiles.spec`. This module
re-exports ``MISSING`` and ``ParameterSpec`` (whose names have not changed)
and intercepts the renamed symbols ``ProfileDescriptor`` and ``_Missing``
via PEP 562 module-level ``__getattr__`` so existing imports keep working
with a ``DeprecationWarning``.

Removed in 26.6.0.

``BackendDescriptor`` is intentionally NOT aliased here — it is owned by
the ``mountainash-data`` package, not by ``mountainash-settings``. Its
compatibility shim lives in ``mountainash-data``'s own ``descriptor.py``.
"""

from __future__ import annotations

import typing as t
import warnings

# Re-export unchanged-name symbols transparently for callers that did
# ``from mountainash_settings.profiles.descriptor import MISSING, ParameterSpec``.
from .spec import MISSING, ParameterSpec  # noqa: F401

__all__ = ["MISSING", "ParameterSpec", "ProfileDescriptor", "_Missing"]


def __getattr__(name: str) -> t.Any:
    """PEP 562 module __getattr__ for deprecated symbols.

    Resolves ``ProfileDescriptor`` to ``ProfileSpec`` and ``_Missing`` to
    ``Missing``. Each lookup emits a ``DeprecationWarning`` naming the
    new symbol and the 26.6.0 removal version.
    """
    if name == "ProfileDescriptor":
        from .spec import ProfileSpec
        warnings.warn(
            "'ProfileDescriptor' is renamed to 'ProfileSpec' in "
            "mountainash-settings 26.5.0. The old name will be removed "
            "in 26.6.0. Import from mountainash_settings instead.",
            DeprecationWarning, stacklevel=2,
        )
        return ProfileSpec
    if name == "_Missing":
        from .spec import Missing
        warnings.warn(
            "'_Missing' is renamed to 'Missing' (now public) in "
            "mountainash-settings 26.5.0. The old name will be removed "
            "in 26.6.0. Import from mountainash_settings instead.",
            DeprecationWarning, stacklevel=2,
        )
        return Missing
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

- [ ] **Step 2: Delete the superseded test file**

```bash
git rm tests/unit/profiles/test_descriptor.py
```

(`test_spec.py` from Task 2 covers the same behaviour under the new names. Deprecation behaviour is tested separately in Task 11.)

- [ ] **Step 3: Confirm the shim resolves old imports correctly**

```bash
hatch run test:test -q -W default::DeprecationWarning -c /dev/null << 'PYTHON'
PYTHON
```

Run a quick interactive check instead:

```bash
hatch run test:test --co tests/unit/profiles/ 2>&1 | tail -5
```

And:

```bash
hatch run python -W error::DeprecationWarning -c "
from mountainash_settings.profiles.spec import ProfileSpec, Missing
# Verify deprecated imports still work but warn
import warnings
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter('always')
    from mountainash_settings.profiles.descriptor import ProfileDescriptor, _Missing
    assert ProfileDescriptor is ProfileSpec
    assert _Missing is Missing
    assert len(w) == 2
    assert all(issubclass(warning.category, DeprecationWarning) for warning in w)
print('OK')
"
```

Expected: `OK`.

- [ ] **Step 4: Run full suite**

```bash
hatch run test:test
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_settings/profiles/descriptor.py tests/unit/profiles/test_descriptor.py
git commit -m "refactor(profiles): convert descriptor.py to compatibility shim

descriptor.py now re-exports MISSING and ParameterSpec from spec.py
(unchanged names) and uses PEP 562 __getattr__ to intercept the renamed
ProfileDescriptor and _Missing with DeprecationWarning.

BackendDescriptor is intentionally NOT aliased here — it's a
mountainash-data symbol owned downstream.

test_descriptor.py removed; equivalent coverage in test_spec.py and
test_deprecation.py (next task).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: Update `profiles/__init__.py` exports and deprecation `__getattr__`

**Files:**
- Modify: `src/mountainash_settings/profiles/__init__.py`

- [ ] **Step 1: Replace the file**

Open `src/mountainash_settings/profiles/__init__.py`. Replace its full contents with:

```python
# src/mountainash_settings/profiles/__init__.py
"""Declarative settings profiles — spec + registry + generic base."""

from __future__ import annotations

import typing as t
import warnings

from .lookup import lookup_class_var
from .invariants import spec_invariants_for
from .profile import Profile
from .registry import Registry
from .spec import MISSING, Missing, ParameterSpec, ProfileSpec

__all__ = [
    "MISSING",
    "Missing",
    "ParameterSpec",
    "Profile",
    "ProfileSpec",
    "Registry",
    "lookup_class_var",
    "spec_invariants_for",
]


_DEPRECATED: dict[str, tuple[str, t.Any]] = {
    "ProfileDescriptor":         ("ProfileSpec", ProfileSpec),
    "DescriptorProfile":         ("Profile", Profile),
    "descriptor_invariants_for": ("spec_invariants_for", spec_invariants_for),
}


def __getattr__(name: str) -> t.Any:
    """PEP 562 module __getattr__ for deprecated top-level names.

    Resolves the pre-26.5.0 names to their renamed equivalents and emits a
    ``DeprecationWarning`` per access. Removed in 26.6.0.
    """
    if name in _DEPRECATED:
        new_name, obj = _DEPRECATED[name]
        warnings.warn(
            f"{name!r} is renamed to {new_name!r} in mountainash-settings "
            f"26.5.0. The old name will be removed in 26.6.0.",
            DeprecationWarning, stacklevel=2,
        )
        return obj
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

- [ ] **Step 2: Confirm new imports resolve from the package root**

```bash
hatch run python -c "
from mountainash_settings.profiles import (
    MISSING, Missing, ParameterSpec, Profile, ProfileSpec,
    Registry, lookup_class_var, spec_invariants_for,
)
print('new names OK')
"
```

Expected: `new names OK`.

- [ ] **Step 3: Confirm deprecated imports resolve with a warning**

```bash
hatch run python -c "
import warnings
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter('always')
    from mountainash_settings.profiles import (
        ProfileDescriptor, DescriptorProfile, descriptor_invariants_for,
    )
    assert len(w) == 3
    assert all(issubclass(warning.category, DeprecationWarning) for warning in w)
print('deprecated names OK')
"
```

Expected: `deprecated names OK`.

- [ ] **Step 4: Run full suite**

```bash
hatch run test:test
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_settings/profiles/__init__.py
git commit -m "feat(profiles): export new names from package root; deprecate old names

profiles/__init__.py exports ProfileSpec, Profile, Missing, lookup_class_var,
and spec_invariants_for as the canonical public names. The old names
ProfileDescriptor, DescriptorProfile, and descriptor_invariants_for resolve
via PEP 562 __getattr__ with DeprecationWarning until 26.6.0.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: Update top-level `mountainash_settings/__init__.py`

**Files:**
- Modify: `src/mountainash_settings/__init__.py`

- [ ] **Step 1: Read the current file**

```bash
sed -n '1,80p' src/mountainash_settings/__init__.py
```

Note the current export structure — the file already exports many profile-related symbols.

- [ ] **Step 2: Update the imports and `__all__` block**

Open `src/mountainash_settings/__init__.py`. Find the existing block:

```python
from .profiles import (
    MISSING,
    DescriptorProfile,
    ParameterSpec,
    ProfileDescriptor,
    Registry,
    descriptor_invariants_for,
)
```

Replace it with:

```python
from .profiles import (
    MISSING,
    Missing,
    ParameterSpec,
    Profile,
    ProfileSpec,
    Registry,
    lookup_class_var,
    spec_invariants_for,
)
```

Update the `__all__` block: replace the corresponding old-name entries with the new ones. Replace:

```python
    # Profiles
    "MISSING",
    "DescriptorProfile",
    "ParameterSpec",
    "ProfileDescriptor",
    "Registry",
    "descriptor_invariants_for",
```

With:

```python
    # Profiles
    "MISSING",
    "Missing",
    "ParameterSpec",
    "Profile",
    "ProfileSpec",
    "Registry",
    "lookup_class_var",
    "spec_invariants_for",
```

- [ ] **Step 3: Add the top-level `__getattr__` deprecation shim**

Append to the end of `src/mountainash_settings/__init__.py`:

```python


# --- Deprecation aliases (PEP 562) ------------------------------------------
# Resolves pre-26.5.0 names with DeprecationWarning. Removed in 26.6.0.

import typing as _t
import warnings as _warnings

_DEPRECATED: dict[str, tuple[str, _t.Any]] = {
    "ProfileDescriptor":         ("ProfileSpec", ProfileSpec),
    "DescriptorProfile":         ("Profile", Profile),
    "descriptor_invariants_for": ("spec_invariants_for", spec_invariants_for),
}


def __getattr__(name: str) -> _t.Any:
    if name in _DEPRECATED:
        new_name, obj = _DEPRECATED[name]
        _warnings.warn(
            f"{name!r} is renamed to {new_name!r} in mountainash-settings "
            f"26.5.0. The old name will be removed in 26.6.0.",
            DeprecationWarning, stacklevel=2,
        )
        return obj
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

- [ ] **Step 4: Update `tests/unit/test_public_api.py`**

Open `tests/unit/test_public_api.py`. Replace:

- `DescriptorProfile` → `Profile`
- `ProfileDescriptor` → `ProfileSpec`
- `descriptor_invariants_for` → `spec_invariants_for`

Run the test to confirm:

```bash
hatch run test:test tests/unit/test_public_api.py -v
```

Expected: all pass.

- [ ] **Step 5: Confirm new and old top-level imports both work**

```bash
hatch run python -c "
# New names
from mountainash_settings import (
    Profile, ProfileSpec, Missing, lookup_class_var, spec_invariants_for,
)
# Old names via __getattr__
import warnings
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter('always')
    from mountainash_settings import (
        ProfileDescriptor, DescriptorProfile, descriptor_invariants_for,
    )
    assert len(w) == 3
    assert all(issubclass(warning.category, DeprecationWarning) for warning in w)
print('top-level imports OK')
"
```

Expected: `top-level imports OK`.

- [ ] **Step 6: Run full suite**

```bash
hatch run test:test
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add src/mountainash_settings/__init__.py tests/unit/test_public_api.py
git commit -m "feat(profiles): re-export new names at package top level

mountainash_settings.__init__ exports ProfileSpec, Profile, Missing,
lookup_class_var, and spec_invariants_for in __all__. Old names
(ProfileDescriptor, DescriptorProfile, descriptor_invariants_for) resolve
via PEP 562 __getattr__ with DeprecationWarning until 26.6.0.

test_public_api updated to use new names.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 11: Comprehensive deprecation test module

**Files:**
- Create: `tests/unit/profiles/test_deprecation.py`

- [ ] **Step 1: Write the test module**

Create `tests/unit/profiles/test_deprecation.py`:

```python
# tests/unit/profiles/test_deprecation.py
"""Tests for all deprecation paths added in mountainash-settings 26.5.0.

Every test here will be DELETED in 26.6.0 along with the deprecation
shims it covers.
"""

from __future__ import annotations

import warnings

import pytest

from mountainash_settings.auth import NoAuth


@pytest.mark.unit
class TestModuleLevelDeprecations:
    """PEP 562 __getattr__ deprecation shims."""

    def test_profiles_profiledescriptor_warns_and_resolves(self):
        from mountainash_settings.profiles import ProfileSpec
        with pytest.warns(DeprecationWarning, match="ProfileDescriptor.*renamed.*ProfileSpec"):
            from mountainash_settings.profiles import ProfileDescriptor
        assert ProfileDescriptor is ProfileSpec

    def test_profiles_descriptorprofile_warns_and_resolves(self):
        from mountainash_settings.profiles import Profile
        with pytest.warns(DeprecationWarning, match="DescriptorProfile.*renamed.*Profile"):
            from mountainash_settings.profiles import DescriptorProfile
        assert DescriptorProfile is Profile

    def test_profiles_descriptor_invariants_for_warns_and_resolves(self):
        from mountainash_settings.profiles import spec_invariants_for
        with pytest.warns(DeprecationWarning, match="descriptor_invariants_for.*renamed.*spec_invariants_for"):
            from mountainash_settings.profiles import descriptor_invariants_for
        assert descriptor_invariants_for is spec_invariants_for

    def test_descriptor_module_profiledescriptor_warns(self):
        from mountainash_settings.profiles.spec import ProfileSpec
        with pytest.warns(DeprecationWarning, match="ProfileDescriptor.*renamed.*ProfileSpec"):
            from mountainash_settings.profiles.descriptor import ProfileDescriptor
        assert ProfileDescriptor is ProfileSpec

    def test_descriptor_module_missing_warns(self):
        from mountainash_settings.profiles.spec import Missing
        with pytest.warns(DeprecationWarning, match="_Missing.*renamed.*Missing"):
            from mountainash_settings.profiles.descriptor import _Missing
        assert _Missing is Missing

    def test_top_level_old_names_warn(self):
        from mountainash_settings import Profile, ProfileSpec, spec_invariants_for
        with pytest.warns(DeprecationWarning):
            from mountainash_settings import ProfileDescriptor
        with pytest.warns(DeprecationWarning):
            from mountainash_settings import DescriptorProfile
        with pytest.warns(DeprecationWarning):
            from mountainash_settings import descriptor_invariants_for
        assert ProfileDescriptor is ProfileSpec
        assert DescriptorProfile is Profile
        assert descriptor_invariants_for is spec_invariants_for

    def test_unknown_attribute_still_raises(self):
        from mountainash_settings import profiles
        with pytest.raises(AttributeError, match="no attribute 'NotARealName'"):
            profiles.NotARealName


@pytest.mark.unit
class TestRegisterMirrorOnNewForm:
    """The bare @register form still mirrors __spec__ to __descriptor__ during 26.5.x."""

    def test_new_form_class_has_descriptor_attribute(self):
        from mountainash_settings.profiles import (
            ParameterSpec, Profile, ProfileSpec, Registry,
        )

        reg = Registry("mirror_new_form_test")
        register = reg.decorator()

        spec = ProfileSpec(
            name="newform", provider_type="newform",
            parameters=[ParameterSpec(name="HOST", type=str, tier="core", driver_key="host")],
            auth_modes=[NoAuth],
        )

        @register
        class NewFormProfile(Profile):
            __spec__ = spec

        # The class declared only __spec__, but the mirror sets __descriptor__ too
        assert NewFormProfile.__spec__ is spec
        assert NewFormProfile.__descriptor__ is spec

        # And instances see both
        instance = NewFormProfile(HOST="h", auth=NoAuth())
        assert instance.__descriptor__ is spec
```

- [ ] **Step 2: Run the new tests**

```bash
hatch run test:test tests/unit/profiles/test_deprecation.py -v
```

Expected: all 8 tests pass.

- [ ] **Step 3: Run full suite**

```bash
hatch run test:test
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add tests/unit/profiles/test_deprecation.py
git commit -m "test(profiles): cover all 26.5.0 deprecation paths

New tests/unit/profiles/test_deprecation.py asserts every deprecated entry
point still resolves, emits DeprecationWarning, and points at the right
new symbol. Also verifies the __spec__ -> __descriptor__ mirror on
classes registered via the new bare @register form.

Entire file is deleted in 26.6.0 along with the shims it covers.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 12: Update `docs/quickstart.md`

**Files:**
- Modify: `docs/quickstart.md`

- [ ] **Step 1: Find every old-name reference**

```bash
grep -nE "ProfileDescriptor|DescriptorProfile|descriptor_invariants_for|__descriptor__|POSTGRESQL_DESCRIPTOR|_Missing" docs/quickstart.md
```

- [ ] **Step 2: Apply renames**

In `docs/quickstart.md`, replace:

- `ProfileDescriptor` → `ProfileSpec`
- `DescriptorProfile` → `Profile`
- `descriptor_invariants_for` → `spec_invariants_for`
- `__descriptor__` → `__spec__`
- `POSTGRESQL_DESCRIPTOR` → `POSTGRESQL_SPEC`
- Any `@register(POSTGRESQL_DESCRIPTOR)` → `@register`
- Update the section heading/anchor for connection profiles to use `Profile` and `ProfileSpec` consistently.

Also update the import in the "connection profiles" example to:

```python
from mountainash_settings import (
    Profile, ProfileSpec, ParameterSpec, Registry,
    MISSING, NoAuth, PasswordAuth,
)
```

And the example body:

```python
POSTGRESQL_SPEC = ProfileSpec(
    name="postgresql",
    provider_type="postgresql",
    parameters=[
        ParameterSpec(name="HOST",     type=str, tier="core",     driver_key="host"),
        ParameterSpec(name="PORT",     type=int, tier="core",     driver_key="port",   default=5432),
        ParameterSpec(name="DATABASE", type=str, tier="core",     driver_key="dbname"),
        ParameterSpec(name="PASSWORD", type=str, tier="core",     driver_key="password",
                      secret=True, default=None),
    ],
    auth_modes=[NoAuth, PasswordAuth],
)

DATABASES = Registry("databases")
register = DATABASES.decorator()

@register
class PostgreSQLSettings(Profile):
    __spec__ = POSTGRESQL_SPEC
```

- [ ] **Step 3: Verify no stray old names remain**

```bash
grep -nE "ProfileDescriptor|DescriptorProfile|descriptor_invariants_for|__descriptor__|POSTGRESQL_DESCRIPTOR|_Missing" docs/quickstart.md && echo "STRAY" || echo "clean"
```

Expected: `clean`.

- [ ] **Step 4: Commit**

```bash
git add docs/quickstart.md
git commit -m "docs(quickstart): use new profile/spec names

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 13: Update `docs/advanced-usage.md`

**Files:**
- Modify: `docs/advanced-usage.md`

- [ ] **Step 1: Find every old-name reference**

```bash
grep -nE "ProfileDescriptor|DescriptorProfile|descriptor_invariants_for|__descriptor__|_Missing" docs/advanced-usage.md
```

- [ ] **Step 2: Apply the same renames as Task 12**

In `docs/advanced-usage.md`, replace:

- `ProfileDescriptor` → `ProfileSpec`
- `DescriptorProfile` → `Profile`
- `descriptor_invariants_for` → `spec_invariants_for`
- `__descriptor__` → `__spec__`
- Any `POSTGRESQL_DESCRIPTOR` → `POSTGRESQL_SPEC`
- Any `REDSHIFT_DESCRIPTOR` → `REDSHIFT_SPEC`
- All `@register(<SPEC>)` calls → `@register`

For the "Profile invariant tests" section, update the example imports and the generated class name from `TestDatabaseInvariants_databases` to use `TestSpecInvariants_databases` in any expected pytest output blocks.

For the "Building typed connection profiles" example in the auth-modes section, update the imports and class body the same way.

- [ ] **Step 3: Verify no stray old names remain**

```bash
grep -nE "ProfileDescriptor|DescriptorProfile|descriptor_invariants_for|__descriptor__|_Missing" docs/advanced-usage.md && echo "STRAY" || echo "clean"
```

Expected: `clean`.

- [ ] **Step 4: Commit**

```bash
git add docs/advanced-usage.md
git commit -m "docs(advanced-usage): use new profile/spec names

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 14: Rename `docs/profile-descriptor-pattern.md` → `docs/profile-spec-pattern.md` and update

**Files:**
- Rename + modify: `docs/profile-descriptor-pattern.md` → `docs/profile-spec-pattern.md`

- [ ] **Step 1: Move the file**

```bash
git mv docs/profile-descriptor-pattern.md docs/profile-spec-pattern.md
```

- [ ] **Step 2: Update the file's heading and references**

Open `docs/profile-spec-pattern.md`. Update:

- Top-level heading from `# The ProfileDescriptor Pattern: Why and When` to `# The ProfileSpec Pattern: Why and When`.
- All occurrences of `ProfileDescriptor` → `ProfileSpec`.
- All occurrences of `DescriptorProfile` → `Profile`.
- All `__descriptor__` → `__spec__`.
- `BackendDescriptor` references — keep these. They describe the mountainash-data subclass which the user will rename to `BackendSpec` as part of their downstream migration, but in the prose of this doc the explanation of "you can subclass ProfileSpec for domain-specific metadata" is still accurate using `BackendSpec` examples. Replace `BackendDescriptor` examples with `BackendSpec` examples.
- Any references to `descriptor_invariants_for` → `spec_invariants_for`.
- Any `*_DESCRIPTOR` example constants → `*_SPEC`.

In the "What you give up" section, the line about IDE go-to-definition mentions a field `HOST` and references `__descriptor__` as the magic attribute — update to `__spec__`.

- [ ] **Step 3: Verify no stray old names remain**

```bash
grep -nE "ProfileDescriptor|DescriptorProfile|descriptor_invariants_for|__descriptor__|BackendDescriptor|_Missing" docs/profile-spec-pattern.md && echo "STRAY" || echo "clean"
```

Expected: `clean`.

- [ ] **Step 4: Commit**

```bash
git add -A docs/
git commit -m "docs: rename profile-descriptor-pattern.md to profile-spec-pattern.md

Renames the why-when explanation doc and updates all type references
to the new vocabulary.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 15: Update `README.md`

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Find old-name references**

```bash
grep -nE "ProfileDescriptor|DescriptorProfile|descriptor_invariants_for|__descriptor__|POSTGRESQL_DESCRIPTOR|profile-descriptor-pattern\.md" README.md
```

- [ ] **Step 2: Apply renames**

In `README.md`, replace:

- `ProfileDescriptor` → `ProfileSpec`
- `DescriptorProfile` → `Profile`
- `descriptor_invariants_for` → `spec_invariants_for`
- `__descriptor__` → `__spec__`
- `POSTGRESQL_DESCRIPTOR` → `POSTGRESQL_SPEC`
- `docs/profile-descriptor-pattern.md` → `docs/profile-spec-pattern.md`
- The `@DATABASES.decorator()(POSTGRESQL_DESCRIPTOR)` example → split into `register = DATABASES.decorator()` + `@register` bare form.
- The "Declarative connection profiles" code block: imports, descriptor declaration, and class body all updated.

- [ ] **Step 3: Verify no stray old names**

```bash
grep -nE "ProfileDescriptor|DescriptorProfile|descriptor_invariants_for|__descriptor__|POSTGRESQL_DESCRIPTOR|profile-descriptor-pattern\.md" README.md && echo "STRAY" || echo "clean"
```

Expected: `clean`.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs(readme): use new profile/spec names; link to renamed pattern doc

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 16: Bump version to 26.5.0

**Files:**
- Modify: `src/mountainash_settings/__version__.py`

- [ ] **Step 1: Update the version string**

Open `src/mountainash_settings/__version__.py`. Replace:

```python
__version__="26.4.2"
```

With:

```python
__version__="26.5.0"
```

- [ ] **Step 2: Verify the package imports the new version**

```bash
hatch run python -c "import mountainash_settings; print(mountainash_settings.__version__)"
```

Expected: `26.5.0`.

- [ ] **Step 3: Commit**

```bash
git add src/mountainash_settings/__version__.py
git commit -m "release: bump version to 26.5.0

Profile/ProfileSpec rename with deprecation aliases. See
docs/superpowers/specs/2026-05-13-profile-spec-rename-design.md for the
full design and migration guide.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 17: Final verification

**Files:** none (verification only).

- [ ] **Step 1: Run the entire test suite**

```bash
hatch run test:test
```

Expected: all tests pass.

- [ ] **Step 2: Run with deprecation warnings turned into errors for the new-name surface**

This step confirms the project's own code does not depend on the deprecated names internally.

```bash
hatch run test:test -W "error::DeprecationWarning" -W "default::DeprecationWarning:mountainash_settings.profiles.descriptor" -W "default::DeprecationWarning:mountainash_settings.profiles.__init__" -W "default::DeprecationWarning:mountainash_settings.__init__" -W "default::DeprecationWarning:tests.unit.profiles.test_deprecation"
```

(The `-W default::DeprecationWarning:<module>` filters explicitly allow deprecation warnings *originating from* the shim modules and from the dedicated deprecation tests; warnings from anywhere else still fail.)

Expected: all tests pass. If any other module emits a `DeprecationWarning`, fix that module by switching to the new names.

- [ ] **Step 3: Lint and type-check**

```bash
hatch run ruff:check
hatch run mypy:check
```

Expected: clean.

- [ ] **Step 4: Verify the package builds**

```bash
hatch build
```

Expected: builds without error. New wheel under `dist/`.

- [ ] **Step 5: Confirm git tree is clean**

```bash
git status
```

Expected: working tree clean, branch `develop` ahead of `origin/develop` by N commits (where N is the number of task commits).

- [ ] **Step 6: Inspect the commit log for the PR description**

```bash
git log --oneline origin/develop..HEAD
```

Expected output (commit subjects):

```
release: bump version to 26.5.0
docs(readme): use new profile/spec names; link to renamed pattern doc
docs: rename profile-descriptor-pattern.md to profile-spec-pattern.md
docs(advanced-usage): use new profile/spec names
docs(quickstart): use new profile/spec names
test(profiles): cover all 26.5.0 deprecation paths
feat(profiles): re-export new names at package top level
feat(profiles): export new names from package root; deprecate old names
refactor(profiles): convert descriptor.py to compatibility shim
feat(profiles): rename descriptor_invariants_for to spec_invariants_for
test(profiles): assert __spec__/__descriptor__ mirror on register
feat(profiles): @register supports argument-free form
feat(profiles): Registry constructor accepts spec_type/profile_type
feat(profiles): rename DescriptorProfile to Profile, add __spec__ attribute
feat(profiles): add spec.py with renamed ProfileSpec and Missing
feat(profiles): add public lookup_class_var helper
docs(spec): address codex adversarial review findings
```

(Plus `Update README.md and remove deprecated files` and earlier project state.)

- [ ] **Step 7: Open the PR targeting `develop`**

```bash
gh pr create --base develop --title "feat(profiles): rename ProfileDescriptor/DescriptorProfile to ProfileSpec/Profile (26.5.0)" --body "$(cat <<'EOF'
## Summary

Implements the 26.5.0 upstream half of [docs/superpowers/specs/2026-05-13-profile-spec-rename-design.md](docs/superpowers/specs/2026-05-13-profile-spec-rename-design.md).

- `ProfileDescriptor` → `ProfileSpec`
- `DescriptorProfile` → `Profile`
- `__descriptor__` → `__spec__` (mirrored to the old name during 26.5.x for downstream readers)
- `descriptor_invariants_for` → `spec_invariants_for`
- `_Missing` → `Missing` (now public)
- New public helper `lookup_class_var()`
- `Registry(spec_type=, profile_type=)` constructor constraints
- Argument-free `@register` (old `@register(spec)` form deprecated)

Old names remain available via PEP 562 module `__getattr__` and class-attribute fallback with `DeprecationWarning`. All deprecation aliases are scheduled for removal in 26.6.0.

## Test plan
- [ ] `hatch run test:test` passes
- [ ] `hatch run ruff:check` clean
- [ ] `hatch run mypy:check` clean
- [ ] Manual: `from mountainash_settings import ProfileDescriptor` emits a `DeprecationWarning`
- [ ] Manual: `from mountainash_settings import ProfileSpec, Profile, lookup_class_var, spec_invariants_for` all resolve

## Removal commitment
The deprecation aliases will be removed in mountainash-settings **26.6.0**. Downstream consumers (mountainash-data, others) should follow the [migration guide](docs/superpowers/specs/2026-05-13-profile-spec-rename-design.md#migration-guide-for-downstream-consumers) before that release.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR URL printed.

---

## Self-review checklist (run after writing the plan)

Skim the spec and verify each in-scope requirement is implemented by a task:

| Spec section | Implemented by |
|---|---|
| `lookup_class_var` public helper | Task 1 |
| `ProfileSpec` rename + `Missing` public | Task 2 |
| `Profile` class rename + `__spec__` + `__descriptor__` fallback | Task 3 |
| `Registry(spec_type=, profile_type=)` constraints | Task 4 |
| Argument-free `@register` + old-form deprecation | Task 5 |
| `__spec__` → `__descriptor__` mirror on register | Tasks 4 (impl) + 6 (test) |
| `spec_invariants_for` rename | Task 7 |
| `descriptor.py` compatibility shim | Task 8 |
| `profiles/__init__.py` exports + deprecation `__getattr__` | Task 9 |
| Top-level `__init__.py` exports + deprecation `__getattr__` | Task 10 |
| Comprehensive deprecation tests | Task 11 |
| `docs/quickstart.md` rename sweep | Task 12 |
| `docs/advanced-usage.md` rename sweep | Task 13 |
| Rename `docs/profile-descriptor-pattern.md` | Task 14 |
| `README.md` rename sweep | Task 15 |
| Version bump to 26.5.0 | Task 16 |
| Verification + PR | Task 17 |

Gaps: none.

Type/method consistency: `lookup_class_var` signature is consistent across Tasks 1, 3, 8. `Registry.register()` signature is consistent across Tasks 4, 5, 6. `Profile.__pydantic_init_subclass__` reads `__spec__` first in Tasks 3 and 11 alike.
