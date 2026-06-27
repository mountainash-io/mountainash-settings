# Profile.register_adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a generic, copy-on-write-safe `Profile.register_adapter` primitive to mountainash-settings so downstream packages can register an `emit()` adapter for a `Hashable` target on an existing `Profile` subclass after class definition.

**Architecture:** Three additions to `mountainash_settings/profiles/profile.py`: a module-level `_check_two_positional` validation helper, two classmethods on `Profile` (`register_adapter`, `registered_adapters`), and a thin module-level `emit_adapter` decorator. All mutation runs under a module `threading.RLock`. No change to `emit()` semantics — it already reads `type(self).__adapters__`. The `emit_adapter` decorator is re-exported from `mountainash_settings.profiles`.

**Tech Stack:** Python 3.12, pydantic v2, pytest (`hatch run test:*`), mypy, ruff.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-06-27-profile-register-adapter-design.md`.
- Edit only `src/mountainash_settings/profiles/profile.py` and `src/mountainash_settings/profiles/__init__.py` (plus the new test file and a doc note). No change to `emit()` behavior or the three-tier order.
- `Adapter` type alias already exists: `Callable[[Profile, dict[str, Any]], dict[str, Any]]` (profile.py:33).
- `__adapters__` is `ClassVar[dict[Hashable, Adapter]] = {}` on `Profile` (profile.py:96) — a single shared default; copy-on-write before mutating.
- Conflict policy: idempotent by object identity (`is`); different adapter for an existing target → `ValueError` unless `overwrite=True`.
- Root registration (`cls is Profile`) → `TypeError`.
- Targets are opaque `Hashable`; the primitive does not namespace them (consumers do).
- Run a single test: `hatch run test:test-target-quick tests/unit/profiles/test_register_adapter.py -v`.
- Full gate: `hatch run test:test`, `hatch run mypy:check`, `hatch run ruff:check` all green.
- Commit message trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

## File Structure

- **Modify** `src/mountainash_settings/profiles/profile.py` — add `import inspect`, `import threading`; module-level `_REGISTER_LOCK` + `_check_two_positional`; `Profile.register_adapter`, `Profile.registered_adapters`; module-level `emit_adapter` decorator; add `emit_adapter` to `__all__`.
- **Modify** `src/mountainash_settings/profiles/__init__.py` — import and re-export `emit_adapter`.
- **Create** `tests/unit/profiles/test_register_adapter.py` — all behavior tests. Each test defines its **own** local `Profile` subclass for isolation (a fresh class has no `__adapters__` in its `__dict__`, so it inherits `Profile`'s and is GC'd after the test).
- **Modify** `docs/profile-spec-pattern.md` — short subsection documenting `register_adapter`.

---

### Task 1: `register_adapter` core (validation, copy-on-write, conflict policy)

**Files:**
- Modify: `src/mountainash_settings/profiles/profile.py` (imports near line 16; helper after the `_UNSET` sentinel ~line 37; classmethod inside `Profile`)
- Test: `tests/unit/profiles/test_register_adapter.py`

**Interfaces:**
- Consumes: `Profile` (profile.py), `Adapter` alias (profile.py:33), existing `_UNSET` sentinel (profile.py:37).
- Produces:
  - `Profile.register_adapter(cls, target: Hashable, adapter: Adapter, *, overwrite: bool = False) -> None`
  - module-level `_check_two_positional(adapter: Callable[..., Any]) -> None` (raises `TypeError` if not 2-positional-callable; accepts un-introspectable C callables)
  - module-level `_REGISTER_LOCK: threading.RLock`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/profiles/test_register_adapter.py`:

```python
# tests/unit/profiles/test_register_adapter.py
"""Unit tests for Profile.register_adapter / registered_adapters / emit_adapter."""

from __future__ import annotations

import functools

import pytest

from mountainash_settings.profiles import ParameterSpec, ProfileSpec
from mountainash_settings.profiles.profile import Profile

SPEC = ProfileSpec(
    name="reg",
    provider_type="reg",
    parameters=[ParameterSpec(name="HOST", type=str, tier="core", driver_key="host")],
)


def _adapter(profile, merged):
    """A valid 2-arg compose adapter."""
    return {**merged, "marked": True}


def _make_cls():
    """A fresh Profile subclass with no own __adapters__ (inherits the default)."""
    class _RegProfile(Profile):
        __spec__ = SPEC

    return _RegProfile


@pytest.mark.unit
class TestRegisterAdapter:
    def test_registers_and_owns_a_fresh_dict(self):
        cls = _make_cls()
        assert "__adapters__" not in cls.__dict__  # inheriting the default
        cls.register_adapter("t1", _adapter)
        assert "__adapters__" in cls.__dict__       # copy-on-write created own dict
        assert cls.__adapters__["t1"] is _adapter

    def test_copy_on_write_does_not_pollute_profile_or_siblings(self):
        sibling = _make_cls()
        cls = _make_cls()
        before = dict(Profile.__adapters__)
        cls.register_adapter("t1", _adapter)
        assert Profile.__adapters__ == before          # shared default untouched
        assert "__adapters__" not in sibling.__dict__   # sibling unaffected
        assert sibling.registered_adapters() == before

    def test_root_registration_rejected(self):
        before = dict(Profile.__adapters__)
        with pytest.raises(TypeError, match="concrete Profile subclass"):
            Profile.register_adapter("t1", _adapter)
        assert Profile.__adapters__ == before

    def test_non_callable_rejected(self):
        cls = _make_cls()
        with pytest.raises(TypeError, match="callable"):
            cls.register_adapter("t1", 123)

    def test_one_arg_callable_rejected(self):
        cls = _make_cls()
        with pytest.raises(TypeError, match="two positional"):
            cls.register_adapter("t1", lambda profile: {})

    def test_star_args_callable_accepted(self):
        cls = _make_cls()
        cls.register_adapter("t1", lambda *a: {})
        assert "t1" in cls.registered_adapters()

    def test_idempotent_same_object(self):
        cls = _make_cls()
        cls.register_adapter("t1", _adapter)
        cls.register_adapter("t1", _adapter)  # no raise
        assert cls.__adapters__["t1"] is _adapter

    def test_conflict_different_object_raises(self):
        cls = _make_cls()
        cls.register_adapter("t1", _adapter)
        with pytest.raises(ValueError, match="already has an adapter"):
            cls.register_adapter("t1", lambda p, m: m)

    def test_conflict_overwrite_replaces(self):
        cls = _make_cls()
        cls.register_adapter("t1", _adapter)

        def other(p, m):
            return m

        cls.register_adapter("t1", other, overwrite=True)
        assert cls.__adapters__["t1"] is other

    def test_partial_identity_caveat(self):
        cls = _make_cls()
        a = functools.partial(lambda p, m, x: m, x=1)
        b = functools.partial(lambda p, m, x: m, x=1)
        cls.register_adapter("t1", a)
        with pytest.raises(ValueError, match="already has an adapter"):
            cls.register_adapter("t1", b)  # distinct partial objects
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `hatch run test:test-target-quick tests/unit/profiles/test_register_adapter.py::TestRegisterAdapter -v`
Expected: FAIL — `AttributeError: type object '_RegProfile' has no attribute 'register_adapter'`.

- [ ] **Step 3: Add imports**

In `src/mountainash_settings/profiles/profile.py`, change the import block (currently `import typing as t` / `import warnings` near line 16) to add `inspect` and `threading`:

```python
import inspect
import threading
import typing as t
import warnings
```

- [ ] **Step 4: Add the lock and validation helper**

In the same file, immediately after the `_UNSET: t.Any = object()` sentinel (~line 37), add:

```python
# Serializes register_adapter's copy-on-write + conflict-check + insert. Registration
# is import-time (already serialized by the import lock); this is defence-in-depth.
_REGISTER_LOCK = threading.RLock()


def _check_two_positional(adapter: t.Callable[..., t.Any]) -> None:
    """Raise ``TypeError`` unless ``adapter`` can be called with two positional args.

    For C callables / builtins where ``inspect.signature`` is unavailable, accept
    after the caller's ``callable()`` check rather than guess.
    """
    try:
        sig = inspect.signature(adapter)
    except (ValueError, TypeError):
        return  # cannot introspect (C callable) — accept
    try:
        sig.bind(_UNSET, _UNSET)
    except TypeError as exc:
        raise TypeError(
            "adapter must accept two positional args (profile, merged); "
            f"{getattr(adapter, '__name__', adapter)!r} does not: {exc}"
        ) from None
```

- [ ] **Step 5: Add the `register_adapter` classmethod**

Inside `class Profile`, after the `__adapters__` ClassVar declaration (profile.py:96), add:

```python
    @classmethod
    def register_adapter(
        cls,
        target: t.Hashable,
        adapter: "Adapter",
        *,
        overwrite: bool = False,
    ) -> None:
        """Register a per-target ``emit()`` adapter on this Profile subclass.

        ``adapter`` has the 2-arg compose signature ``(profile, merged) -> dict``
        (the same shape as inline ``__adapters__`` entries). After registration,
        ``instance.emit(target, base=...)`` routes through it.

        Safe to call at import time from a downstream package: copies
        ``__adapters__`` onto ``cls`` first if ``cls`` is still inheriting an
        ancestor's map, so registration never mutates a shared/parent dict.

        Idempotent by identity: re-registering the *same* adapter object is a
        no-op; a *different* adapter for an existing target raises unless
        ``overwrite=True``.

        Raises:
            TypeError: if called on ``Profile`` itself, if ``adapter`` is not a
                two-positional-arg callable, or if ``target`` is unhashable.
            ValueError: if ``target`` is already registered to a different
                adapter and ``overwrite`` is False.
        """
        if cls is Profile:
            raise TypeError(
                "register_adapter must be called on a concrete Profile subclass, "
                "not Profile itself (would mutate the shared default adapter map)."
            )
        if not callable(adapter):
            raise TypeError(
                f"adapter must be callable, got {type(adapter).__name__}"
            )
        _check_two_positional(adapter)
        try:
            hash(target)
        except TypeError as exc:
            raise TypeError(f"target must be hashable, got {target!r}") from exc

        with _REGISTER_LOCK:
            # Copy-on-write: ensure cls owns its __adapters__ before mutating, so
            # we never touch Profile's shared default or a parent's map.
            if "__adapters__" not in cls.__dict__:
                cls.__adapters__ = dict(cls.__adapters__)
            existing = cls.__adapters__.get(target, _UNSET)
            if existing is not _UNSET and existing is not adapter and not overwrite:
                raise ValueError(
                    f"{cls.__name__} already has an adapter for target {target!r}; "
                    f"pass overwrite=True to replace it."
                )
            cls.__adapters__[target] = adapter
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `hatch run test:test-target-quick tests/unit/profiles/test_register_adapter.py::TestRegisterAdapter -v`
Expected: PASS (all 10 tests).

- [ ] **Step 7: Commit**

```bash
git add src/mountainash_settings/profiles/profile.py tests/unit/profiles/test_register_adapter.py
git commit -m "feat(profiles): add Profile.register_adapter with copy-on-write safety

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `registered_adapters` introspection

**Files:**
- Modify: `src/mountainash_settings/profiles/profile.py` (classmethod after `register_adapter`)
- Test: `tests/unit/profiles/test_register_adapter.py`

**Interfaces:**
- Produces: `Profile.registered_adapters(cls) -> dict[Hashable, Adapter]` — a **copy** of the effective map (own or inherited).
- Consumed by Task 1's tests (already call `registered_adapters()`), Task 4, and downstream test suites.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/profiles/test_register_adapter.py`:

```python
@pytest.mark.unit
class TestRegisteredAdapters:
    def test_returns_copy_not_live_dict(self):
        cls = _make_cls()
        cls.register_adapter("t1", _adapter)
        snapshot = cls.registered_adapters()
        snapshot["t2"] = _adapter        # mutate the returned copy
        assert "t2" not in cls.__adapters__  # class map unaffected

    def test_reflects_inherited_entries(self):
        cls = _make_cls()
        # No own registration yet → reflects the inherited (empty) default.
        assert cls.registered_adapters() == dict(Profile.__adapters__)
```

- [ ] **Step 2: Run to verify it fails**

Run: `hatch run test:test-target-quick tests/unit/profiles/test_register_adapter.py::TestRegisteredAdapters -v`
Expected: FAIL — `AttributeError: ... has no attribute 'registered_adapters'`.

- [ ] **Step 3: Implement**

In `class Profile`, immediately after `register_adapter`, add:

```python
    @classmethod
    def registered_adapters(cls) -> dict[t.Hashable, "Adapter"]:
        """Return a copy of the effective ``__adapters__`` map for ``cls``.

        Read-only snapshot (own or inherited entries); mutating it does not
        affect the class.
        """
        return dict(cls.__adapters__)
```

- [ ] **Step 4: Run to verify it passes**

Run: `hatch run test:test-target-quick tests/unit/profiles/test_register_adapter.py::TestRegisteredAdapters -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_settings/profiles/profile.py tests/unit/profiles/test_register_adapter.py
git commit -m "feat(profiles): add Profile.registered_adapters introspection

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `emit_adapter` decorator + package export

**Files:**
- Modify: `src/mountainash_settings/profiles/profile.py` (decorator after the `Profile` class; add to `__all__`)
- Modify: `src/mountainash_settings/profiles/__init__.py` (import + `__all__`)
- Test: `tests/unit/profiles/test_register_adapter.py`

**Interfaces:**
- Produces: `emit_adapter(profile_cls, target, *, overwrite=False)` — decorator returning the wrapped fn unchanged after registering it; exported from `mountainash_settings.profiles`.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/profiles/test_register_adapter.py` (and add `emit_adapter` to the top-of-file import from `mountainash_settings.profiles`):

```python
from mountainash_settings.profiles import emit_adapter  # add to existing imports


@pytest.mark.unit
class TestEmitAdapterDecorator:
    def test_decorator_registers_and_returns_fn(self):
        cls = _make_cls()

        @emit_adapter(cls, "t1")
        def my_adapter(profile, merged):
            return {**merged, "via": "decorator"}

        assert cls.__adapters__["t1"] is my_adapter
        assert my_adapter.__name__ == "my_adapter"  # returned unchanged

    def test_decorator_honors_overwrite(self):
        cls = _make_cls()
        cls.register_adapter("t1", _adapter)

        @emit_adapter(cls, "t1", overwrite=True)
        def replacement(profile, merged):
            return merged

        assert cls.__adapters__["t1"] is replacement
```

- [ ] **Step 2: Run to verify it fails**

Run: `hatch run test:test-target-quick tests/unit/profiles/test_register_adapter.py::TestEmitAdapterDecorator -v`
Expected: FAIL — `ImportError: cannot import name 'emit_adapter'`.

- [ ] **Step 3: Implement the decorator**

In `profile.py`, after the `Profile` class definition (module level, end of file), add:

```python
def emit_adapter(
    profile_cls: type["Profile"],
    target: t.Hashable,
    *,
    overwrite: bool = False,
) -> t.Callable[["Adapter"], "Adapter"]:
    """Decorator form of :meth:`Profile.register_adapter`.

    Registers the decorated 2-arg adapter on ``profile_cls`` for ``target`` and
    returns it unchanged.
    """
    def _wrap(fn: "Adapter") -> "Adapter":
        profile_cls.register_adapter(target, fn, overwrite=overwrite)
        return fn

    return _wrap
```

Then update `__all__` at the top of `profile.py`:

```python
__all__ = ["Adapter", "Profile", "emit_adapter"]
```

- [ ] **Step 4: Export from the package**

In `src/mountainash_settings/profiles/__init__.py`, update the profile import (currently `from .profile import Adapter, Profile`, line 11) to:

```python
from .profile import Adapter, Profile, emit_adapter
```

And add `"emit_adapter"` to that file's `__all__` list (after `"Adapter"`).

- [ ] **Step 5: Run to verify it passes**

Run: `hatch run test:test-target-quick tests/unit/profiles/test_register_adapter.py::TestEmitAdapterDecorator -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/mountainash_settings/profiles/profile.py src/mountainash_settings/profiles/__init__.py tests/unit/profiles/test_register_adapter.py
git commit -m "feat(profiles): add emit_adapter decorator and export it

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: End-to-end `emit()` routing + inheritance ordering

**Files:**
- Test: `tests/unit/profiles/test_register_adapter.py`

**Interfaces:**
- Consumes: `Profile.register_adapter`, `Profile.emit` (profile.py:256), `_default_kwargs` (driver_key).
- Produces: no new code — verifies a registered adapter participates in `emit()` and fail-closed semantics, and locks in the documented inheritance-ordering behavior (spec §3.3 / settings spec F-4).

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/profiles/test_register_adapter.py`:

```python
@pytest.mark.unit
class TestEmitIntegration:
    def test_registered_adapter_routes_through_emit(self):
        cls = _make_cls()

        def layer(profile, merged):
            return {**merged, "token": "abc"}

        cls.register_adapter("dbx", layer)
        p = cls(HOST="h")
        # emit merges driver_key (_default_kwargs) then runs the adapter.
        assert p.emit("dbx", base={"timeout": 5}) == {
            "timeout": 5, "host": "h", "token": "abc",
        }

    def test_unregistered_target_fails_closed(self):
        cls = _make_cls()
        cls.register_adapter("dbx", _adapter)  # makes the profile target-scoped
        p = cls(HOST="h")
        with pytest.raises(ValueError):
            p.emit("not-registered")

    def test_child_first_severs_parent_propagation(self):
        # Documents the F-4 ordering semantics: a child that registers first owns
        # its own dict and does NOT see a target the parent registers later.
        class Parent(Profile):
            __spec__ = SPEC

        class Child(Parent):
            pass

        Child.register_adapter("c", _adapter)   # child snapshots its own dict
        Parent.register_adapter("p", _adapter)  # later parent registration
        assert "c" in Child.registered_adapters()
        assert "p" not in Child.registered_adapters()   # severed
        assert "p" in Parent.registered_adapters()

    def test_parent_first_propagates_to_unregistered_child(self):
        class Parent(Profile):
            __spec__ = SPEC

        class Child(Parent):
            pass

        Parent.register_adapter("p", _adapter)  # child has no own dict yet
        assert "p" in Child.registered_adapters()  # inherits live
```

- [ ] **Step 2: Run to verify they pass (no new impl needed)**

Run: `hatch run test:test-target-quick tests/unit/profiles/test_register_adapter.py::TestEmitIntegration -v`
Expected: PASS. (If `test_unregistered_target_fails_closed` does not raise, re-check `emit()`'s `_is_targeted`/`_knows_target` path — but no code change should be required.)

- [ ] **Step 3: Run the whole new test module**

Run: `hatch run test:test-target-quick tests/unit/profiles/test_register_adapter.py -v`
Expected: PASS (all classes).

- [ ] **Step 4: Commit**

```bash
git add tests/unit/profiles/test_register_adapter.py
git commit -m "test(profiles): emit() routing + inheritance-ordering for register_adapter

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Docs + full quality gate

**Files:**
- Modify: `docs/profile-spec-pattern.md`

**Interfaces:**
- Consumes: everything above. Produces: documentation; the green full-suite/type/lint gate.

- [ ] **Step 1: Document the primitive**

Append a subsection to `docs/profile-spec-pattern.md`:

```markdown
## Extending emission: `register_adapter`

`emit()` targets are any `Hashable`, so other domains can add their own. To
register an `emit()` adapter for a target on a profile class after definition:

    from mountainash_settings.profiles import emit_adapter

    @emit_adapter(PasswordAuthProfile, MyTarget.POSTGRES)
    def _postgres(auth, base):
        return {**base, "user": auth.USERNAME,
                "password": auth.PASSWORD.get_secret_value()}

`Profile.register_adapter(target, adapter, *, overwrite=False)` is the
non-decorator form. It is copy-on-write-safe (never mutates a parent/shared
adapter map), idempotent for the same adapter object, and raises on a conflicting
re-registration. Register on the **concrete** class you mean (registering on a
base does not propagate to a child that already registered). Use a
package-namespaced target type (an `Enum` / frozen dataclass), never bare strings.
`registered_adapters()` returns a read-only copy for introspection.
```

- [ ] **Step 2: Run the full suite**

Run: `hatch run test:test`
Expected: PASS (existing suite + the new module; no regressions in `test_emit.py`).

- [ ] **Step 3: Type check**

Run: `hatch run mypy:check`
Expected: clean (no new errors in `profiles/profile.py` / `profiles/__init__.py`).

- [ ] **Step 4: Lint**

Run: `hatch run ruff:check`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add docs/profile-spec-pattern.md
git commit -m "docs(profiles): document register_adapter / emit_adapter extension point

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- §3.1 API classmethod → Task 1. §3.2 behavior (root reject [F-1], trial-bind validation [F-2], copy-on-write, identity idempotence [F-3], conflict) → Task 1. §3.3 inheritance + ordering [F-4] → Task 4. §3.4 introspection [F-7] → Task 2. §3.5 concurrency [F-5] → `_REGISTER_LOCK` in Task 1. §3.6 namespaced targets [F-6] → doc note Task 5. §3.7 decorator → Task 3. §6 tests → Tasks 1-4. §7 rollout → commits per task. Test-isolation fixture: replaced by per-test local subclasses (simpler, fully isolated) — covered in every test.
- No spec requirement left without a task.

**Placeholder scan:** none — every code/test step shows complete code; every run step gives the exact command + expected result.

**Type consistency:** `register_adapter(target, adapter, *, overwrite=False) -> None`, `registered_adapters() -> dict`, `emit_adapter(profile_cls, target, *, overwrite=False)`, `_check_two_positional(adapter) -> None`, `_REGISTER_LOCK` — names used identically across tasks and tests. `_UNSET` reused as the both "missing" marker and bind probe (existing module sentinel).
