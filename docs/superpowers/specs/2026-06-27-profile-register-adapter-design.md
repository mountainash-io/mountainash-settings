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

1. **Validate `adapter`** is callable; reject with `TypeError` otherwise. Best-effort
   arity check via `inspect.signature` — must accept ≥2 positional params (or
   `*args`); reject clearly if it cannot (catches a 1-arg legacy `__adapter__`
   passed by mistake).
2. **Copy-on-write the class dict:** if `"__adapters__" not in cls.__dict__`, set
   `cls.__adapters__ = dict(cls.__adapters__)` — snapshot inherited entries into a
   fresh per-`cls` dict. This is the core safety step (§1 hazard).
3. **Idempotent / conflict rules:**
   - `target` absent → insert.
   - `target` present and maps to the **same `adapter` object** → no-op (safe under
     module re-import).
   - `target` present mapping to a **different** adapter → raise `ValueError` unless
     `overwrite=True`.
4. **Insert** `cls.__adapters__[target] = adapter`.

No change to `emit()`: it already reads `type(self).__adapters__.get(target)`
(profile.py:297) and treats `_is_targeted()` / `_known_targets()` off the same
dict, so a registered target immediately participates in fail-closed semantics
(unknown target → raises; registered target → served).

### 3.3 Inheritance semantics

Registration on `cls` affects `cls` and any subclass that does not shadow
`__adapters__` with its own literal — consistent with how `emit()` resolves
`type(self).__adapters__`. Registering on a base (e.g. `PasswordAuthProfile`)
propagates to its subclasses; a subclass that needs a different adapter for the
same target registers its own (triggering its own copy-on-write).

### 3.4 Optional ergonomic decorator (recommended, thin)

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
| `adapter` not callable | `TypeError` |
| `adapter` cannot accept 2 positional args | `TypeError` (clear message; likely a 1-arg `__adapter__` mistake) |
| `target` re-registered with identical adapter | no-op (idempotent) |
| `target` re-registered with different adapter, `overwrite=False` | `ValueError` |
| `target` unhashable | `TypeError` (from the dict insert; pre-check for a clearer message) |
| Registering on a class inheriting the shared default | fresh per-class dict created first; shared default untouched |

---

## 6. Testing

- Copy-on-write isolation: register on a profile that inherits the shared default
  (e.g. a test `Profile` subclass with no `__adapters__`); assert the sibling and
  `Profile.__adapters__` are **unchanged**.
- Idempotency: double-register same `(target, adapter)` → no error, one entry.
- Conflict: re-register different adapter → `ValueError`; with `overwrite=True` →
  replaced.
- Validation: non-callable and 1-arg callable → `TypeError`.
- End-to-end: register an adapter for a fresh `target`, then `emit(target, base=…)`
  routes through it and composes on `base` + `driver_key`; `emit(unknown_target)`
  still fails closed.
- Decorator form mirrors the classmethod.
- **Test isolation fixture:** a fixture that snapshots `cls.__dict__["__adapters__"]`
  (and its absence) before a test and restores after, so registration tests don't
  leak class state across the suite.
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
policy = idempotent-or-raise; unregister = out, fixture handles test isolation.)
</content>
