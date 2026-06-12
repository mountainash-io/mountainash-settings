# Unified Emission — Phase 1 (Settings Substrate) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the generic `Profile.emit(target)` primitive plus target-aware `driver_key` and a keyed `__adapters__` map to `mountainash-settings`, with zero output change for existing bare-string specs and fail-closed behavior for target-scoped profiles.

**Architecture:** This is the foundational, dependency-free phase of the design spec at `mountainash-auth-client/docs/superpowers/specs/2026-06-12-unified-profile-kwargs-emission-design.md`. It touches only `mountainash-settings`. No auth-client or transport code changes here — those are Phases 2–3 and depend on this landing first. Everything added is additive: existing `_default_kwargs()` call sites keep working (new `target` parameter defaults), the legacy single `__adapter__` hook is preserved, and bare-string `driver_key` output is byte-for-byte identical.

**Tech Stack:** Python 3.12, pydantic v2, `dataclasses` (frozen), pytest (markers: `unit`), hatch, ruff.

---

## Background the implementer needs

Read these before starting:

- **Spec:** `mountainash-auth-client/docs/superpowers/specs/2026-06-12-unified-profile-kwargs-emission-design.md` — sections "The one settings change", "Emission safety contract", "Backward compatibility". This plan implements only the settings substrate described there.
- **Current code:**
  - `src/mountainash_settings/profiles/spec.py` — `ParameterSpec` (frozen dataclass, `kw_only=True`) and `ProfileSpec`. `driver_key: str | None` today.
  - `src/mountainash_settings/profiles/profile.py` — `Profile(MountainAshBaseSettings)`. Has `__adapter__: ClassVar[Callable[[Profile], dict] | None] = None` (a **1-arg, owns-the-pipeline** hook that is currently *never invoked by settings core* — domain subclasses call it themselves). Has `_default_kwargs(self)` (no params today) that maps `driver_key → value`, skips `None`, unwraps `SecretStr`, applies `transform`.
  - `tests/unit/profiles/test_profile.py` — existing test patterns (`DUMMY_SPEC`, `DummyProfile`, `@pytest.mark.unit`).

### Critical reconciliation (the spec's `emit()` pseudocode is slightly wrong)

The spec's `emit()` sketch calls `adapter(self, merged)` for **both** the new per-target adapters and the legacy `__adapter__`. But the legacy `__adapter__` is **1-arg** (`Callable[[Profile], dict]`) and owns its own pipeline. Calling it with two args would break it.

**Resolution used by this plan (encode exactly this):**
- New `__adapters__` entries use a **2-arg compose** signature: `Adapter = Callable[[Profile, dict], dict]` — they receive the already-merged `base + renames` dict and return the final dict.
- The legacy `__adapter__` (1-arg, owns-pipeline) is retained and, when `emit()` falls back to it, is invoked as `__adapter__(self)` — it ignores `base`/merged, exactly as today.
- `emit()` dispatch order: per-target `__adapters__[target]` (2-arg) → legacy `__adapter__` (1-arg) → return merged.

### Commands

- Run one test file: `hatch run test:test tests/unit/profiles/test_profile.py -q`
- Run one test: `hatch run test:test tests/unit/profiles/test_profile.py::TestEmit::test_name -v`
- Lint: `hatch run ruff:check src tests` (auto-fix: `hatch run ruff:fix`)
- Full suite (final task): `hatch run test:test`

All new tests live in a new file `tests/unit/profiles/test_emit.py` (keeps `test_profile.py` focused; `emit`/`__adapters__`/target-aware `driver_key` are one cohesive responsibility).

---

## File Structure

- **Modify** `src/mountainash_settings/profiles/spec.py` — widen `ParameterSpec.driver_key` type, exclude it from the hash (`field(hash=False)`), update docstring.
- **Modify** `src/mountainash_settings/profiles/profile.py` — add `Adapter` alias, `_UNSET` sentinel, `__adapters__` classvar; make `_default_kwargs(target=None)` target-aware; add `_resolve_driver_key`, `_is_targeted`, `_known_targets`, `_knows_target`, `emit`.
- **Modify** `src/mountainash_settings/profiles/invariants.py` — make `test_driver_keys_unique` dict-`driver_key` safe (per-target uniqueness).
- **Modify** `src/mountainash_settings/profiles/__init__.py` and `src/mountainash_settings/__init__.py` — export `Adapter`.
- **Create** `tests/unit/profiles/test_emit.py` — all Phase 1 tests.

---

### Task 1: Target-aware `driver_key` type + resolution

**Files:**
- Modify: `src/mountainash_settings/profiles/spec.py` (the `driver_key` field + its docstring)
- Modify: `src/mountainash_settings/profiles/profile.py` (`_default_kwargs` gains `target`; add `_resolve_driver_key`)
- Test: `tests/unit/profiles/test_emit.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/profiles/test_emit.py`:

```python
# tests/unit/profiles/test_emit.py
"""Unit tests for target-aware driver_key, __adapters__, and Profile.emit()."""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from mountainash_settings.profiles import ParameterSpec, ProfileSpec
from mountainash_settings.profiles.profile import Profile


# A bare-string spec — behaves exactly as before this change.
BARE_SPEC = ProfileSpec(
    name="bare",
    provider_type="bare",
    parameters=[
        ParameterSpec(name="HOST", type=str, tier="core", driver_key="host"),
        ParameterSpec(name="PASSWORD", type=str, tier="core", secret=True,
                      driver_key="password", default=None),
    ],
)


class BareProfile(Profile):
    __spec__ = BARE_SPEC


# A target-scoped spec — driver_key is a {target: key} dict.
SCOPED_SPEC = ProfileSpec(
    name="scoped",
    provider_type="scoped",
    parameters=[
        ParameterSpec(name="USERNAME", type=str, tier="core",
                      driver_key={"paramiko": "username"}),
        ParameterSpec(name="PASSWORD", type=str, tier="core", secret=True,
                      driver_key={"paramiko": "password"}),
    ],
)


class ScopedProfile(Profile):
    __spec__ = SCOPED_SPEC


@pytest.mark.unit
class TestTargetAwareDriverKey:
    def test_bare_driver_key_unchanged_no_target(self):
        p = BareProfile(HOST="h", PASSWORD="s")
        assert p._default_kwargs() == {"host": "h", "password": "s"}

    def test_bare_driver_key_ignores_target(self):
        p = BareProfile(HOST="h", PASSWORD="s")
        # A bare string means "all targets" — passing a target changes nothing.
        assert p._default_kwargs("anything") == {"host": "h", "password": "s"}

    def test_scoped_emits_for_matching_target(self):
        p = ScopedProfile(USERNAME="u", PASSWORD="s")
        assert p._default_kwargs("paramiko") == {"username": "u", "password": "s"}

    def test_scoped_skips_for_other_target(self):
        p = ScopedProfile(USERNAME="u", PASSWORD="s")
        assert p._default_kwargs("http") == {}

    def test_scoped_skips_for_none_target(self):
        p = ScopedProfile(USERNAME="u", PASSWORD="s")
        assert p._default_kwargs(None) == {}

    def test_spec_with_dict_driver_key_is_hashable(self):
        # ParameterSpec is a frozen dataclass; its auto-generated __hash__ must
        # not choke on a dict driver_key. driver_key is excluded from the hash
        # (field(hash=False)) but stays in __eq__.
        param = ParameterSpec(name="X", type=str, tier="core",
                              driver_key={"paramiko": "x"})
        assert isinstance(hash(param), int)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `hatch run test:test tests/unit/profiles/test_emit.py::TestTargetAwareDriverKey -q`
Expected: FAIL — `test_scoped_*` fail because `_default_kwargs("paramiko")` raises `TypeError` (the method takes no `target` arg yet), and `test_spec_with_dict_driver_key_is_hashable` fails with `TypeError: unhashable type: 'dict'` (the frozen-dataclass auto-`__hash__` currently includes `driver_key`). (`test_bare_*` may already pass.)

- [ ] **Step 3: Widen the `driver_key` type in `spec.py` (and exclude it from the hash)**

In `src/mountainash_settings/profiles/spec.py`, change the field and its docstring line. `field` is already imported (`from dataclasses import dataclass, field`).

Field (in `class ParameterSpec`):

```python
    # dict driver_keys are unhashable; ParameterSpec is a frozen dataclass whose
    # auto __hash__ would crash on a dict field. Exclude driver_key from the hash
    # (it stays in __eq__) so dict-scoped specs remain hashable.
    driver_key: str | dict[t.Hashable, str] | None = field(default=None, hash=False)
```

Docstring — replace the `driver_key:` entry under `Attributes:` with:

```python
        driver_key: Output-kwarg name for 1:1 mappings. A bare ``str`` (e.g.
            ``"sslcert"``) maps for every target. A ``dict[Hashable, str]``
            scopes the mapping per emission target — e.g.
            ``{TargetFamily.PARAMIKO: "password"}`` emits only when
            ``emit(PARAMIKO)`` / ``_default_kwargs(PARAMIKO)`` is called.
            ``None`` means a domain adapter handles emission.
```

- [ ] **Step 4: Make `_default_kwargs` target-aware in `profile.py`**

In `src/mountainash_settings/profiles/profile.py`, replace the existing `_default_kwargs` method with the version below and add the `_resolve_driver_key` static helper directly above it:

```python
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `hatch run test:test tests/unit/profiles/test_emit.py::TestTargetAwareDriverKey -q`
Expected: PASS (6 passed)

- [ ] **Step 6: Commit**

```bash
git add src/mountainash_settings/profiles/spec.py src/mountainash_settings/profiles/profile.py tests/unit/profiles/test_emit.py
git commit -m "feat(profiles): target-aware driver_key resolution"
```

---

### Task 2: `__adapters__` map + `Adapter` type alias

**Files:**
- Modify: `src/mountainash_settings/profiles/profile.py` (module-level `Adapter` + `_UNSET`; `__adapters__` classvar)
- Test: `tests/unit/profiles/test_emit.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/profiles/test_emit.py`:

```python
@pytest.mark.unit
class TestAdaptersMap:
    def test_adapters_default_empty(self):
        # A profile that declares no adapters has an empty map.
        assert BareProfile.__adapters__ == {}

    def test_adapters_declarable(self):
        def _http(profile, kw):
            return {**kw, "marker": "http"}

        class Adapted(Profile):
            __spec__ = BARE_SPEC
            __adapters__ = {"http": _http}

        assert "http" in Adapted.__adapters__
        # Base Profile is unaffected (no leakage across classes).
        assert BareProfile.__adapters__ == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `hatch run test:test tests/unit/profiles/test_emit.py::TestAdaptersMap -q`
Expected: FAIL — `AttributeError: type object 'BareProfile' has no attribute '__adapters__'`

- [ ] **Step 3: Add `Adapter`, `_UNSET`, and `__adapters__`**

In `src/mountainash_settings/profiles/profile.py`:

Add at module level, just after the existing imports / `__all__` line (top of file, before `def _resolve_spec`):

```python
# A target adapter composes credential/config kwargs: it receives the profile
# and the already-merged (base + driver_key renames) dict, and returns the final
# dict. Distinct from the legacy 1-arg ``__adapter__`` which owns the whole
# pipeline (see Profile docstring).
Adapter = t.Callable[["Profile", dict[str, t.Any]], dict[str, t.Any]]

# Sentinel distinguishing "no target argument passed" from an explicit ``None``
# target, so ``emit()`` can fail closed on target-scoped profiles.
_UNSET: t.Any = object()
```

Update `__all__` at the top of the file:

```python
__all__ = ["Adapter", "Profile"]
```

In `class Profile`, add the `__adapters__` classvar directly below the existing `__adapter__` declaration:

```python
    __adapters__: t.ClassVar[dict[t.Hashable, "Adapter"]] = {}
```

> **NOTE for implementers:** `{}` is a mutable class default shared by every
> subclass that does not override it. Subclasses MUST assign a *new* dict
> (`__adapters__ = {"http": ...}`) — never mutate the inherited one in place
> (`Cls.__adapters__["http"] = ...`), which would leak adapters into the base
> `Profile` and all siblings. All emission reads via `type(self).__adapters__`,
> so a subclass that assigns its own dict is fully isolated.

- [ ] **Step 4: Run test to verify it passes**

Run: `hatch run test:test tests/unit/profiles/test_emit.py::TestAdaptersMap -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_settings/profiles/profile.py tests/unit/profiles/test_emit.py
git commit -m "feat(profiles): add __adapters__ map and Adapter type alias"
```

---

### Task 3: `emit()` with fail-closed targeting + adapter dispatch

**Files:**
- Modify: `src/mountainash_settings/profiles/profile.py` (add `_is_targeted`, `_known_targets`, `_knows_target`, `emit`)
- Test: `tests/unit/profiles/test_emit.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/profiles/test_emit.py`:

```python
def _http_basic(profile, kw):
    # Copy-on-write nested container; sole producer of the Authorization key.
    token = f"{profile.USERNAME}:{profile.PASSWORD.get_secret_value()}"
    return {**kw, "headers": {**kw.get("headers", {}), "Authorization": token}}


# Profile that is target-scoped via an adapter only (no dict driver_keys).
class HttpAdaptedProfile(Profile):
    __spec__ = SCOPED_SPEC
    __adapters__ = {"http": _http_basic}


# Legacy owns-the-pipeline adapter (1-arg).
def _legacy_adapter(profile):
    kw = profile._default_kwargs()
    kw["legacy"] = True
    return kw


class LegacyAdaptedProfile(Profile):
    __spec__ = BARE_SPEC
    __adapter__ = staticmethod(_legacy_adapter)


@pytest.mark.unit
class TestEmit:
    def test_untargeted_emit_equals_default_kwargs(self):
        p = BareProfile(HOST="h", PASSWORD="s")
        assert p.emit() == p._default_kwargs() == {"host": "h", "password": "s"}

    def test_untargeted_emit_layers_base(self):
        p = BareProfile(HOST="h")
        assert p.emit(base={"region": "x"}) == {"region": "x", "host": "h"}

    def test_targeted_profile_no_target_raises(self):
        p = ScopedProfile(USERNAME="u", PASSWORD="s")
        with pytest.raises(ValueError, match="target-scoped"):
            p.emit()

    def test_targeted_profile_unknown_target_raises(self):
        p = ScopedProfile(USERNAME="u", PASSWORD="s")
        with pytest.raises(ValueError, match="no emission for target"):
            p.emit("ftp")

    def test_targeted_profile_known_target_emits(self):
        p = ScopedProfile(USERNAME="u", PASSWORD="s")
        assert p.emit("paramiko") == {"username": "u", "password": "s"}

    def test_per_target_adapter_composes_onto_base(self):
        p = HttpAdaptedProfile(USERNAME="u", PASSWORD="pw")
        out = p.emit("http", base={"timeout": 5})
        assert out["timeout"] == 5
        assert out["headers"]["Authorization"] == "u:pw"
        # SCOPED_SPEC driver_keys are paramiko-only, so no stray username/password.
        assert "username" not in out and "password" not in out

    def test_legacy_adapter_owns_pipeline(self):
        p = LegacyAdaptedProfile(HOST="h", PASSWORD="s")
        # Not target-scoped (no __adapters__, no dict driver_keys) → emit() allowed.
        out = p.emit()
        assert out == {"host": "h", "password": "s", "legacy": True}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `hatch run test:test tests/unit/profiles/test_emit.py::TestEmit -q`
Expected: FAIL — `AttributeError: 'BareProfile' object has no attribute 'emit'`

- [ ] **Step 3: Implement `emit` and its targeting helpers**

In `src/mountainash_settings/profiles/profile.py`, add these methods to `class Profile` (place them directly after `_default_kwargs`):

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `hatch run test:test tests/unit/profiles/test_emit.py::TestEmit -q`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_settings/profiles/profile.py tests/unit/profiles/test_emit.py
git commit -m "feat(profiles): add Profile.emit() with fail-closed targeting"
```

---

### Task 4: Copy-on-write / double-emit top-level safety

**Files:**
- Test: `tests/unit/profiles/test_emit.py` (behavior already implemented in Task 3; this task locks it with regression tests)

> These are **regression-lock tests, not red→green TDD** — the behavior already
> landed in Task 3, so they pass immediately. The double-emit test also
> documents the *contract* (an adapter must copy-on-write nested containers) by
> exercising a test-local adapter; it does not enforce that contract in product
> code (product adapters arrive in Phase 2 and carry their own tests).

- [ ] **Step 1: Write the regression-lock tests**

Append to `tests/unit/profiles/test_emit.py`:

```python
@pytest.mark.unit
class TestEmitSafety:
    def test_emit_does_not_mutate_base_top_level(self):
        p = BareProfile(HOST="h")
        base = {"region": "x"}
        p.emit(base=base)
        # emit() shallow-copies base; caller's dict is untouched.
        assert base == {"region": "x"}

    def test_double_emit_from_shared_base_is_isolated(self):
        # Config emit, then a credential-style adapter emit layered on top,
        # from the same starting base. The first result must not be mutated
        # by the second.
        config = BareProfile(HOST="h")
        first = config.emit(base={"timeout": 5})

        cred = HttpAdaptedProfile(USERNAME="u", PASSWORD="pw")
        second = cred.emit("http", base=first)

        # first still has no Authorization header; the nested header dict the
        # adapter built is its own (copy-on-write), not first's.
        assert "headers" not in first
        assert second["headers"]["Authorization"] == "u:pw"
        assert second["timeout"] == 5 and second["host"] == "h"
```

- [ ] **Step 2: Run test to verify it passes** (behavior already present from Task 3)

Run: `hatch run test:test tests/unit/profiles/test_emit.py::TestEmitSafety -q`
Expected: PASS (2 passed)

> Note: these tests guard the contract rather than drive new code. The
> top-level shallow copy is in `emit()` (`{**(base or {})}`) and the
> nested copy-on-write is in the test's `_http_basic` adapter. If either
> regresses later, these fail. (If `test_emit_does_not_mutate_base_top_level`
> somehow fails now, the `emit()` merge is mutating `base` — re-check the
> `merged = {**(base or {}), ...}` line.)

- [ ] **Step 3: Commit**

```bash
git add tests/unit/profiles/test_emit.py
git commit -m "test(profiles): lock copy-on-write and double-emit isolation"
```

---

### Task 5: Back-compat — output equivalence + dict-driver_key construction

**Files:**
- Test: `tests/unit/profiles/test_emit.py`

- [ ] **Step 1: Write the failing/confirming test**

Append to `tests/unit/profiles/test_emit.py`:

```python
@pytest.mark.unit
class TestBackCompat:
    def test_existing_default_kwargs_call_sites_unbroken(self):
        # Domain code calls _default_kwargs() with no args; still valid.
        p = BareProfile(HOST="h", PASSWORD="s")
        assert p._default_kwargs() == {"host": "h", "password": "s"}

    def test_secret_unwrapped_under_target_resolution(self):
        # SecretStr unwrap still happens for a target-scoped secret field.
        p = ScopedProfile(USERNAME="u", PASSWORD="s")
        out = p._default_kwargs("paramiko")
        assert out["password"] == "s"
        assert not isinstance(out["password"], SecretStr)

    def test_dict_driver_key_constructs_and_installs_fields(self):
        # A spec with a dict driver_key builds its pydantic fields normally.
        p = ScopedProfile(USERNAME="u", PASSWORD="s")
        assert p.USERNAME == "u"
        assert isinstance(p.PASSWORD, SecretStr)

    def test_transform_applies_under_target(self):
        spec = ProfileSpec(
            name="tf2", provider_type="tf2",
            parameters=[
                ParameterSpec(name="FLAG", type=bool, tier="core", default=True,
                              driver_key={"boto": "flag"},
                              transform=lambda v: 1 if v else 0),
            ],
        )

        class P(Profile):
            __spec__ = spec

        assert P(FLAG=True).emit("boto") == {"flag": 1}
```

- [ ] **Step 2: Run test to verify it passes**

Run: `hatch run test:test tests/unit/profiles/test_emit.py::TestBackCompat -q`
Expected: PASS (4 passed)

- [ ] **Step 3: Run the pre-existing profile tests to prove no regression**

Run: `hatch run test:test tests/unit/profiles/test_profile.py -q`
Expected: PASS (all existing tests green — `_default_kwargs()`, `__adapter__` attr, transform, secret unwrap unchanged)

- [ ] **Step 4: Commit**

```bash
git add tests/unit/profiles/test_emit.py
git commit -m "test(profiles): back-compat for bare/dict driver_key and emit equivalence"
```

---

### Task 6: Export `Adapter` + docstrings

**Files:**
- Modify: `src/mountainash_settings/profiles/profile.py` (class docstring mention of `emit`/`__adapters__`)
- Modify: `src/mountainash_settings/profiles/__init__.py` (export `Adapter`)
- Modify: `src/mountainash_settings/__init__.py` (re-export `Adapter`)
- Test: `tests/unit/profiles/test_emit.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/profiles/test_emit.py`:

```python
@pytest.mark.unit
class TestExports:
    def test_adapter_exported_from_profiles(self):
        from mountainash_settings.profiles import Adapter  # noqa: F401

    def test_adapter_exported_from_package_root(self):
        from mountainash_settings import Adapter  # noqa: F401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `hatch run test:test tests/unit/profiles/test_emit.py::TestExports -q`
Expected: FAIL — `ImportError: cannot import name 'Adapter'`

- [ ] **Step 3: Add the exports**

In `src/mountainash_settings/profiles/__init__.py`, add `Adapter` to the `from .profile import ...` line and to `__all__`:

```python
from .profile import Adapter, Profile
```

and add `"Adapter",` to that file's `__all__` list (keep alphabetical placement near `"Profile"`).

In `src/mountainash_settings/__init__.py`, add `Adapter` to the `from .profiles import (...)` block and to the top-level `__all__` (place `"Adapter",` adjacent to the existing `"ParameterSpec"`/`"Profile"` entries).

- [ ] **Step 4: Update the `Profile` class docstring**

In `src/mountainash_settings/profiles/profile.py`, in the `class Profile` docstring "Public contract" list, replace the `__adapter__` bullet with both hooks:

```python
        - :meth:`emit` — target-aware kwargs: ``driver_key`` renames →
          per-target ``__adapters__`` (2-arg compose) → legacy ``__adapter__``
          (1-arg, owns-pipeline) → merged dict.
        - ``__adapters__`` — per-target adapter map (``{target: Adapter}``).
        - ``__adapter__`` — legacy all-targets adapter; owns the output pipeline.
```

- [ ] **Step 5: Run test to verify it passes**

Run: `hatch run test:test tests/unit/profiles/test_emit.py::TestExports -q`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add src/mountainash_settings/profiles/profile.py src/mountainash_settings/profiles/__init__.py src/mountainash_settings/__init__.py tests/unit/profiles/test_emit.py
git commit -m "feat(profiles): export Adapter; document emit/__adapters__"
```

---

### Task 7: Make `spec_invariants_for` dict-`driver_key` safe

The shared `spec_invariants_for` invariant `test_driver_keys_unique`
(`src/mountainash_settings/profiles/invariants.py:63-65`) does
`set(p.driver_key for ...)`. A dict `driver_key` is unhashable, so this raises
`TypeError` the moment any registry holds a target-scoped spec — which Phase 2's
`AUTH_REGISTRY` will. Fix the shared helper here, in the substrate, so Phase 2
inherits a working invariant. Uniqueness becomes **per-target**: a bare string
applies to every target; two dict driver_keys mapping the same key under
*different* targets are not a collision; the same key under the same target is.

**Files:**
- Modify: `src/mountainash_settings/profiles/invariants.py` (`test_driver_keys_unique`)
- Test: `tests/unit/profiles/test_emit.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/profiles/test_emit.py`:

```python
from mountainash_settings.profiles.invariants import spec_invariants_for
from mountainash_settings.profiles.registry import Registry


@pytest.mark.unit
class TestInvariantsDictDriverKeys:
    def _invariant_instance(self):
        # spec_invariants_for only needs the registry for parametrize IDs and
        # registry.name; we call the method directly with (name, spec).
        return spec_invariants_for(Registry("tmp"))()

    def test_dict_scoped_distinct_targets_not_a_collision(self):
        inst = self._invariant_instance()
        spec = ProfileSpec(name="ok", provider_type="ok", parameters=[
            ParameterSpec(name="A", type=str, tier="core", driver_key={"http": "x"}),
            ParameterSpec(name="B", type=str, tier="core", driver_key={"boto": "x"}),
        ])
        inst.test_driver_keys_unique("ok", spec)  # must not raise

    def test_same_key_same_target_is_a_collision(self):
        inst = self._invariant_instance()
        spec = ProfileSpec(name="bad", provider_type="bad", parameters=[
            ParameterSpec(name="A", type=str, tier="core", driver_key={"http": "x"}),
            ParameterSpec(name="B", type=str, tier="core", driver_key={"http": "x"}),
        ])
        with pytest.raises(AssertionError, match="duplicate driver_key for target"):
            inst.test_driver_keys_unique("bad", spec)

    def test_bare_key_collides_within_each_target(self):
        inst = self._invariant_instance()
        spec = ProfileSpec(name="mix", provider_type="mix", parameters=[
            ParameterSpec(name="A", type=str, tier="core", driver_key="x"),
            ParameterSpec(name="B", type=str, tier="core", driver_key={"http": "x"}),
        ])
        with pytest.raises(AssertionError, match="duplicate driver_key for target"):
            inst.test_driver_keys_unique("mix", spec)

    def test_bare_keys_still_checked(self):
        inst = self._invariant_instance()
        spec = ProfileSpec(name="bare2", provider_type="bare2", parameters=[
            ParameterSpec(name="A", type=str, tier="core", driver_key="x"),
            ParameterSpec(name="B", type=str, tier="core", driver_key="x"),
        ])
        with pytest.raises(AssertionError, match="duplicate bare driver_key"):
            inst.test_driver_keys_unique("bare2", spec)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `hatch run test:test tests/unit/profiles/test_emit.py::TestInvariantsDictDriverKeys -q`
Expected: FAIL — `test_dict_scoped_*` raise `TypeError: unhashable type: 'dict'` from the current `set(...)`; the collision tests raise `TypeError` instead of `AssertionError`.

- [ ] **Step 3: Rewrite `test_driver_keys_unique` in `invariants.py`**

Replace the existing method (`src/mountainash_settings/profiles/invariants.py:63-65`) with:

```python
        def test_driver_keys_unique(self, name: str, spec: t.Any) -> None:
            # Per-target output keys must be unique. A bare-string driver_key
            # applies to every target; a dict driver_key applies per named
            # target. (dicts are unhashable, so a set() over raw values would
            # crash — resolve to per-target keys first.)
            from collections import defaultdict

            bare: list[str] = []
            per_target: dict[t.Hashable, list[str]] = defaultdict(list)
            for p in spec.parameters:
                dk = p.driver_key
                if not dk:
                    continue
                if isinstance(dk, str):
                    bare.append(dk)
                else:  # dict[Hashable, str]
                    for target, key in dk.items():
                        per_target[target].append(key)

            assert len(bare) == len(set(bare)), (
                f"duplicate bare driver_key in {name}"
            )
            for target, keys in per_target.items():
                combined = keys + bare  # bare keys apply to every target
                assert len(combined) == len(set(combined)), (
                    f"duplicate driver_key for target {target!r} in {name}"
                )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `hatch run test:test tests/unit/profiles/test_emit.py::TestInvariantsDictDriverKeys -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Confirm the existing invariant tests still pass**

Run: `hatch run test:test tests/unit/profiles/test_invariants.py -q`
Expected: PASS (bare-string specs behave exactly as before)

- [ ] **Step 6: Commit**

```bash
git add src/mountainash_settings/profiles/invariants.py tests/unit/profiles/test_emit.py
git commit -m "fix(profiles): per-target driver_key uniqueness invariant"
```

---

### Task 8: Full-suite + lint gate

**Files:** none (verification only)

- [ ] **Step 1: Run the full settings test suite**

Run: `hatch run test:test`
Expected: PASS — entire suite green, including `tests/unit/profiles/` and any consumer of `_default_kwargs`. `ParameterSpec` hashability is preserved by `field(hash=False)` on `driver_key` (Task 1), so specs with dict driver_keys still hash; `spec_invariants_for` is dict-safe after Task 7. If any pre-existing test still fails, STOP and report — do not silence it.

- [ ] **Step 2: Lint**

Run: `hatch run ruff:check src tests`
Expected: `All checks passed!` (auto-fix with `hatch run ruff:fix` if needed, then re-run)

- [ ] **Step 3: Final commit (only if ruff:fix changed anything)**

```bash
git add -A
git commit -m "chore(profiles): ruff clean for unified-emission phase 1"
```

---

## Self-Review

**1. Spec coverage** (against the spec's "The one settings change" + "Backward compatibility" + safety contract):
- `__adapter__` → keyed `__adapters__` → Task 2. ✅
- target-aware `driver_key` (`str | dict[Hashable,str] | None`) → Task 1. ✅
- `emit(target)` with `_UNSET` fail-closed guard + `_is_targeted`/`_knows_target` diagnostics → Task 3. ✅
- target-aware `_default_kwargs(target)` → Task 1. ✅
- output-equivalence for bare-string specs; targeted profiles fail closed → Tasks 1, 3, 5. ✅
- copy-on-write / double-emit safety (rule 1, top-level) → Task 4. ✅
- API-surface change acknowledged + introspection still works → Task 5 (`test_dict_driver_key_constructs_and_installs_fields`). ✅
- frozen-dataclass hash hazard (dict `driver_key` unhashable) → Task 1 `field(hash=False)` + `test_spec_with_dict_driver_key_is_hashable`. ✅
- shared `spec_invariants_for` survives dict `driver_key` (would otherwise `TypeError` once Phase 2's `AUTH_REGISTRY` holds scoped specs) → Task 7 per-target uniqueness. ✅
- **Out of Phase 1 (correctly absent):** the "no bare driver_key behind adapter" invariant (rule 4) needs the profile *class* + registry and lands with auth-client's `AUTH_REGISTRY` in **Phase 2**; the `TargetFamily` enum is auth-client's (Phase 2); runtime disjointness policing is deferred per the spec. No gap.

**2. Placeholder scan:** No TBD/TODO; every code step shows complete code; every command has expected output. ✅

**3. Type consistency:** `Adapter = Callable[[Profile, dict], dict]` (2-arg) used consistently in Task 2 def, Task 3 dispatch, and the test adapters. Legacy `__adapter__` is 1-arg throughout (Task 3 dispatch calls `__adapter__(self)`; `LegacyAdaptedProfile` defines `_legacy_adapter(profile)`). `_default_kwargs(target=None)`, `emit(target=_UNSET, *, base=None)`, `_resolve_driver_key`, `_is_targeted`, `_known_targets`, `_knows_target` names match between defs and call sites. ✅

---

## Execution Handoff

Phase 1 is intentionally small and dependency-free; Phases 2 (auth-client adapters + `TargetFamily` + rule-4 invariant) and 3 (transport wiring + `_core/auth` deletion) get their own plans once this lands on `develop`.
