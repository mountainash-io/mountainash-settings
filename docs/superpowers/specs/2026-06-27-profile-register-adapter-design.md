# Design Spec: `Profile.register_adapter` — post-hoc emit-adapter registration

**Date:** 2026-06-27
**Status:** Draft — for review
**Repo:** mountainash-settings
**Author:** Nathaniel Ramm (with Claude)

---

## 1. Context & Problem

`Profile.emit(target, *, base)` (profile.py:256) is a domain-agnostic, three-tier
emission pipeline: `driver_key` renames → per-target adapter in `__adapters__`
(2-arg compose `(profile, merged) -> dict`) → legacy `__adapter__`. The target is
**any `Hashable`** — `targets.py` in auth-client states the design intent
explicitly:

> "the spec keeps mountainash-settings domain-agnostic: it stores adapters under
> an opaque `Hashable` key and never imports this enum."

So **other domains are meant to define their own emission targets** and contribute
adapters for them. But that extensibility is **not realized**: `__adapters__` is a
`ClassVar[dict]` populated only by an inline literal at class-definition time
(`PasswordAuthProfile.__adapters__ = {TargetFamily.HTTP: _basic_header}`). There is
**no public, safe way for a downstream package to register an adapter for a new
target on an existing `Profile` subclass.**

### Why hand-mutation is unsafe (the hazard this primitive removes)

`Profile.__adapters__: ClassVar[dict] = {}` (profile.py:96) is a **single shared
default dict**. Subclasses that declare their own literal are isolated, but
subclasses that declare none **inherit the very same object**. In auth-client
today, `NoAuthProfile`, `IAMAuthProfile`, `AzureADAuthProfile`, and
`ServiceAccountAuthProfile` declare no `__adapters__` — they all share
`Profile.__adapters__`. A naive `IAMAuthProfile.__adapters__[my_target] = fn`
mutates that shared dict and **silently pollutes every sibling and `Profile`
itself**. Any downstream registration must first copy-on-write a per-class dict —
subtle correctness that belongs encapsulated in one primitive, not re-implemented
(and mis-implemented) per consumer.

### Driver

The immediate consumer is the mountainash-data → mountainash-auth-client migration:
mountainash-data needs to register per-(auth-profile, ibis-dialect) adapters so the
canonical `auth_profile.emit(dialect_target, base=…)` pattern produces ibis-driver
credentials — without auth-client importing DB drivers and without mountainash-data
hand-mutating shared class state. transport's storage profiles and mountainash-data's
own connection profiles are equally plausible consumers. The capability is generic
`Profile` machinery and belongs here, beside `emit()`.

---

## 2. Goals & Non-Goals

### Goals
1. A public, validated, copy-on-write-safe way to register an emit adapter for a
   target on any `Profile` subclass after class definition.
2. Safe under re-import (idempotent for identical registrations).
3. Loud on genuine conflicts (different adapter for an already-registered target).
4. Zero behavior change to existing inline-`__adapters__` profiles or `emit()`.

### Non-Goals
- Changing `emit()` semantics, the three-tier order, or `driver_key`.
- A target *registry* / namespacing of targets (targets remain opaque `Hashable`,
  owned by their domains).
- OAuth, secrets, or auth-specific concerns (this is generic `Profile` machinery).
- An `unregister` in the public API (test isolation handled by fixture — §6).

---

## 3. Design

### 3.1 API — a classmethod on `Profile`

```python
@classmethod
def register_adapter(
    cls,
    target: t.Hashable,
    adapter: "Adapter",
    *,
    overwrite: bool = False,
) -> None:
    """Register a per-target emit adapter on this Profile subclass.

    ``adapter`` has the 2-arg compose signature ``(profile, merged) -> dict``
    (the same shape as inline ``__adapters__`` entries). After registration,
    ``instance.emit(target, base=…)`` routes through it.

    Safe to call at import time from a downstream package. Copies ``__adapters__``
    onto ``cls`` first if ``cls`` is still inheriting an ancestor's dict, so
    registration never mutates a shared/parent adapter map.
    """
```

### 3.2 Behavior

The whole sequence below runs under a module-level `threading.RLock` (see §3.5).

0. **Reject root registration:** if `cls is Profile`, raise `TypeError`
   (`"register on a concrete Profile subclass, not Profile itself"`). `Profile`
   already holds `__adapters__` in its own `__dict__` (profile.py:96), so the
   copy-on-write guard would *not* fire and the registration would mutate the
   canonical shared dict that every adapter-less subclass inherits — the exact
   pollution §1 warns about. [F-1]
1. **Validate `adapter` is two-positional-callable.** First `callable(adapter)` →
   `TypeError` if not. Then a **trial-bind**: `inspect.signature(adapter).bind(
   _SENTINEL_PROFILE, _SENTINEL_KW)` inside `try/except TypeError` — a binding
   failure (wrong arity, keyword-only 3rd param, …) → `TypeError` with a clear
   message (catches a 1-arg legacy `__adapter__` passed by mistake). For C
   callables / builtins where `inspect.signature` raises `ValueError`, fall back to
   accepting on the bare `callable()` check (cannot introspect; do not guess). [F-2]
2. **Snapshot into `new_map`:** `new_map = dict(cls.__adapters__)` — copy-on-write
   off whatever dict `cls` currently sees (own or inherited). All subsequent reads
   and the insert operate on this private copy; `cls.__adapters__` is not touched
   until step 4's single atomic rebind. Core safety step (§1 hazard). [F-5]
3. **Idempotent / conflict rules on `new_map` (by object identity):**
   - `target` absent → proceed to insert.
   - `target` present and mapped to the **same adapter object** (`is`) → no-op
     (safe under module re-import). The raise below is skipped; step 4 still
     rebinds with an identical copy, which is harmless.
   - `target` present mapped to a **different** object → `ValueError` unless
     `overwrite=True`. The raise precedes step 4, so `cls.__adapters__` is never
     mutated on conflict.
   - Identity is intentional and documented: pass **module-level singleton
     callables**. A freshly-built `functools.partial` or bound method
     (`obj.method`) is a new object each access, so re-registering one trips the
     conflict check even when behaviour is identical — use a module-level wrapper
     instead. [F-3]
4. **Insert then single atomic rebind:** `new_map[target] = adapter` then
   `cls.__adapters__ = new_map` as the final statement. The rebind is the **only**
   write to class state and it happens after the map is fully built. A lock-free
   `emit()` — whether it reads `__adapters__.get(target)` or iterates the dict in
   `_known_targets()` — observes either the old complete dict or the new complete
   dict, never a partially mutated one. This is unconditionally true: on first
   registration (no own dict yet) and on re-registration (own dict already exists).

No change to `emit()`: it already reads `type(self).__adapters__.get(target)`
(profile.py:297) and derives `_is_targeted()` / `_known_targets()` from the same
dict, so a registered target immediately participates in fail-closed semantics
(unknown target → raises; registered target → served).

### 3.3 Inheritance semantics — and the registration-timing limitation [F-4]

`emit()` resolves adapters from a **single class dict** (`type(self).__adapters__.get`,
profile.py:297) — there is **no MRO merge**. Combined with copy-on-write, this gives
a precise but order-sensitive rule that the spec states explicitly rather than
papering over:

- A subclass that never registers and never declares a literal `__adapters__`
  inherits its nearest ancestor's dict live — so registering on a base **does**
  reach such subclasses.
- **The moment a subclass registers anything (or declares a literal), it snapshots
  its own `__adapters__` and permanently severs live inheritance** from ancestors.
  A *later* registration on the parent will **not** propagate to that child.

Consequence — **child-first vs parent-first ordering is observable**: if
`Child.register_adapter(t1)` runs before `Parent.register_adapter(t2)`, `Child`
will not see `t2`. Both orderings are covered by tests (§6).

**Guidance for consumers:** register each adapter on the **exact class** that should
serve it. mountainash-data's auth adapters are registered directly on the concrete
auth-profile classes they bind (`PasswordAuthProfile`, `TokenAuthProfile`, …), which
are effectively leaves for this purpose, so the timing split does not bite. We do
**not** rely on parent→child propagation.

**Escalation (out of scope, no consumer needs it):** if a future consumer genuinely
needs live cross-hierarchy adapter inheritance, the fix is to make `emit()` /
`_known_targets()` walk the MRO and merge `__adapters__` (nearest-wins), a change to
emit() semantics tracked separately — not bolted onto `register_adapter`.

### 3.4 Introspection [F-7]

Add a read-only `registered_adapters(cls) -> dict[Hashable, Adapter]` classmethod
returning a **copy** of the effective adapter map for `cls` (its own dict, or the
inherited one). Low-cost, supports both consumer debugging and the test fixture
(§6). No public `unregister` — test isolation is handled by a fixture that records
and restores `cls.__dict__`'s `__adapters__` state (present-with-contents vs
absent); see §6.

### 3.5 Concurrency [F-5]

Registration is import-time and therefore serialized by Python's import lock in
practice. As defence-in-depth and to make the contract explicit, the
snapshot → conflict-check → insert → rebind sequence (§3.2 steps 2–4) runs under a
module-level `threading.RLock`, so two registrations for the same `(cls, target)`
cannot both observe "absent" and race past the conflict check. `emit()` is **not**
locked (it only reads); the single atomic rebind at the end of step 4 means a
lock-free `emit()` — whether reading `__adapters__.get()` or iterating the dict in
`_known_targets()` — **unconditionally** observes either the old complete dict or the
new complete dict, never a partially mutated one. This holds on every registration
(first or re-registration), not only on first registration. Documented assumption:
**all registration completes during import, before concurrent `emit()` traffic.**

### 3.6 Target hygiene [F-6]

Targets are opaque `Hashable`s owned by their domains, so collision avoidance is the
caller's responsibility. The docs and examples require a **package-namespaced target
type** — a package-owned `Enum` or frozen dataclass (e.g. mountainash-data's
`IbisDialectTarget`) — **never bare strings** like `"postgres"`, which two unrelated
packages could register on the same profile class and collide.

### 3.7 Optional ergonomic decorator (recommended, thin)

```python
def emit_adapter(profile_cls, target, *, overwrite=False):
    """Decorator: register the decorated fn as `profile_cls`'s adapter for `target`."""
    def _wrap(fn):
        profile_cls.register_adapter(target, fn, overwrite=overwrite)
        return fn
    return _wrap
```
A one-line convenience over the classmethod; same semantics. Exported from
`mountainash_settings.profiles`.

---

## 4. Interfaces & Isolation

- **`Profile.register_adapter`** — the only new public surface; pure class-state
  mutation with the documented copy-on-write + conflict contract. Understandable
  and testable without reading `emit()`.
- **`emit()`** — unchanged; consumes whatever `__adapters__` holds.
- Downstream contributes adapters; settings owns the mechanism. No new dependency
  direction (settings depends on nothing new).

---

## 5. Failure Modes & Error Handling

| Case | Result |
|---|---|
| `cls is Profile` (root registration) | `TypeError` — register on a concrete subclass [F-1] |
| `adapter` not callable | `TypeError` |
| `adapter` fails the two-positional trial-bind | `TypeError` (clear message; likely a 1-arg `__adapter__` mistake) [F-2] |
| `adapter` is a C callable (`signature` unavailable) | accepted after `callable()` check (cannot introspect) [F-2] |
| `target` re-registered with the **same** adapter object | no-op (idempotent) [F-3] |
| `target` re-registered with a **different** object, `overwrite=False` | `ValueError` |
| `target` unhashable | `TypeError` (pre-check for a clear message before the dict insert) |
| Registering on a class inheriting the shared default | fresh per-class dict created first; shared default untouched |
| Concurrent same-`(cls, target)` registration | serialized by the module RLock; one inserts, the other hits idempotent/conflict path [F-5] |

---

## 6. Testing

- Copy-on-write isolation: register on a profile that inherits the shared default
  (e.g. a test `Profile` subclass with no `__adapters__`); assert the sibling and
  `Profile.__adapters__` are **unchanged**.
- **Root rejection:** `Profile.register_adapter(...)` → `TypeError`; assert
  `Profile.__adapters__` untouched. [F-1]
- Idempotency: double-register same `(target, adapter)` → no error, one entry.
- Conflict: re-register different adapter → `ValueError`; with `overwrite=True` →
  replaced.
- Validation: non-callable → `TypeError`; 1-arg callable → `TypeError` (trial-bind);
  a 2-positional function and a `*args` callable → accepted; a builtin/C callable →
  accepted. [F-2]
- Identity caveat: registering a freshly-built `functools.partial`/bound method
  twice → `ValueError` (documents the identity contract); a module-level singleton
  → idempotent. [F-3]
- **Inheritance ordering:** parent-first (child sees parent's target) **and**
  child-first (child registers `t1`, then parent registers `t2`; assert child does
  **not** see `t2`) — locks in the documented §3.3 semantics. [F-4]
- Introspection: `registered_adapters()` returns a copy reflecting registered +
  inherited entries; mutating the returned dict does not affect the class. [F-7]
- End-to-end: register an adapter for a fresh `target`, then `emit(target, base=…)`
  routes through it and composes on `base` + `driver_key`; `emit(unknown_target)`
  still fails closed.
- Decorator form mirrors the classmethod.
- **Test isolation — via fresh per-test subclasses (record/restore fixture
  retired).** Tests define a **new local `Profile` subclass per test** (a fresh
  class has no own `__adapters__` and is garbage-collected after the test), so no
  test mutates a shared/real profile class and no record-and-restore fixture is
  needed. The "originally-absent vs originally-present-empty" restore concern only
  arises when mutating a long-lived class; if a future test must do that, add a
  small helper that snapshots `"__adapters__" in cls.__dict__` plus its contents
  and restores exactly. [F-7]
- Gate: settings' existing `hatch run test:test`, `mypy:check`, `ruff:check` green.

---

## 7. Rollout

Feature branch off settings `develop` → PR to `develop` (three-tier flow). Small,
additive, no behavior change to existing profiles. Lands **first** in the
three-package sequence; auth-client (docs) and mountainash-data (consumer) follow.

---

## 8. Downstream (context, not in this PR)

- **auth-client:** INTEGRATION.md note — "Emission targets are extensible: define
  your own `Hashable` target and `Profile.register_adapter(target, adapter)` to
  contribute an adapter; auth-client ships `TargetFamily.{HTTP,BOTO,PARAMIKO}`."
  Docs only; no code.
- **mountainash-data:** defines per-ibis-dialect targets and registers
  per-(auth-profile, dialect) adapters (which import the DB drivers and build
  `trino.auth.BasicAuthentication`, `google …Credentials`, etc.), then uses
  `auth_profile.emit(dialect_target, base=connection_profile.emit(dialect_target))`.
  Tracked in the mountainash-data migration spec.

---

## 9. Open Questions

None outstanding. (Home = settings; form = classmethod + thin decorator; conflict
policy = idempotent-or-raise by identity; root registration rejected; unregister =
out, fixture handles test isolation; targets must be package-namespaced.)

---

## 10. Adversarial review (Codex) — incorporated

A Codex design review (2026-06-27, fresh thread) confirmed the design is
directionally sound (no redesign) and that **pydantic v2 does not relocate
`__adapters__` out of `cls.__dict__`, so the `__dict__` copy-on-write check is
reliable**. All seven findings are resolved:

- **F-1 (major)** root-class registration would mutate the shared canonical dict →
  reject `cls is Profile` with `TypeError` (§3.2.0, §5).
- **F-2 (major)** brittle arity check / C callables → trial-bind two positional args;
  fall back to `callable()` for un-introspectable C callables (§3.2.1, §5).
- **F-3 (minor)** identity-based idempotence trips on `partial`/bound methods →
  documented; require module-level singleton callables (§3.2.3).
- **F-4 (major)** child-first registration severs live parent inheritance →
  documented as explicit order-sensitive semantics + both-ordering tests; consumers
  register on the exact (leaf) class; MRO-merge in `emit()` noted as the only
  escalation, out of scope (§3.3, §6).
- **F-5 (major)** unlocked read-check-write → module `RLock` over CoW+check+insert;
  `emit()` stays lock-free and consistent; import-time assumption documented (§3.5).
- **F-6 (minor)** bare-string target collisions → require package-namespaced target
  types (Enum/frozen dataclass) (§3.6).
- **F-7 (minor)** test-isolation/introspection gap → add read-only
  `registered_adapters()` + a record-and-restore fixture distinguishing
  absent-vs-empty (§3.4, §6).
