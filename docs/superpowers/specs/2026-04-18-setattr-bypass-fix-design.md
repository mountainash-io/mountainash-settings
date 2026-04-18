# Setattr Bypass Fix — Restore Canonical Pydantic Assignment Semantics

**Date:** 2026-04-18
**Status:** Design — awaiting user review
**Related backlog:** `mountainash-central/01.principles/mountainash-data/f.backlog/setattr-bypass-limitation.md`
**Related prior spec:** `docs/superpowers/specs/2026-04-16-profiles-promotion-design.md`

## Problem

`MountainAshBaseSettings.update_settings_from_dict` uses raw `setattr(self, name, value)`
after pydantic's validation has already run. Because `MountainAshBaseSettings.model_config`
has `validate_assignment` disabled (commented out), these setattrs bypass the declared-type
contract:

- `SecretStr` fields end up holding plain `str` at runtime.
- Enum-typed fields hold raw strings rather than enum members.
- `AfterValidator` transforms that return normalized values are overwritten with the
  un-transformed raw input.

The bypass forces per-class `__setattr__` overrides (`PySparkMode` in `mountainash-data`)
and per-field defensive unwrap guards (`ConnectionProfile._default_driver_kwargs`).
As the descriptor/registry pattern is promoted to `mountainash-settings` for reuse by
`mountainash-utils-files`, `mountainash-utils-secrets`, and `mountainash-acrds-core`,
every new domain inherits the workaround burden.

## Root Cause Analysis

`MountainAshBaseSettings.__init__` at `src/mountainash_settings/settings/base_settings.py:83-110`
performs the following sequence:

1. `super().__init__(..., **valid_attribute_kwargs)` — full pydantic validation runs; fields are
   wrapped/coerced/transformed correctly.
2. `self.update_settings_from_dict(settings_dict=valid_attribute_kwargs)` —
   **the same kwargs** are raw-setattr'd back over the validated values, discarding
   the validation work.
3. Seven `setattr(self, "SETTINGS_*", ...)` calls for meta-field bookkeeping.

Pydantic v2's canonical contract is that `setattr` obeys declared types *only* when
`model_config["validate_assignment"] = True`. MountainAsh has this flag deliberately
off, and the `update_settings_from_dict` re-application amplifies the consequence:
every constructor call overwrites validated state with raw state.

### Callsite audit for `update_settings_from_dict`

Three live callsites in `mountainash-settings`:

| Callsite | Purpose | Status |
|---|---|---|
| `base_settings.py:98` (inside `__init__`) | Re-apply kwargs that `super().__init__` just applied with validation. | **Redundant.** Its only non-redundant side-effect is the `SETTINGS_SOURCE_KWARGS` stash at line 258. |
| `settings_manager.py:47` | Apply runtime override kwargs to `model_copy()` of a cached instance. | **Legitimate.** Runtime-override flow — exactly where setattr bypass silently corrupts types. |
| `settings_parameters.py:365` (`apply_runtime_overrides`) | Same `model_copy()` + override kwargs pattern. | **Legitimate.** Parallel flow to the above. |

## Goal

Restore canonical pydantic v2 assignment semantics so declared field types (enums,
`SecretStr`, `AfterValidator` transforms) are honoured on all post-construction
mutations — both direct `setattr` and `update_settings_from_dict`.

## Non-Goals (Out of Scope)

- Removing `PySparkMode.__setattr__` override in `mountainash-data`.
- Removing `ConnectionProfile._default_driver_kwargs` `SecretStr` unwrap guard.
- Removing adapter `str(enum_value)` defensive code.
- Any change to `ProfileDescriptor` / `ParameterSpec` / `DescriptorProfile` public API.

These are captured by a linked follow-up item (tracked separately in
`mountainash-data/f.backlog/`) once `mountainash-settings` is released and consumers bump.

## Design

Three coordinated changes, all within `mountainash-settings`.

### Change A — Enable canonical assignment validation

`src/mountainash_settings/settings/base_settings.py:16-23`

```python
model_config = SettingsConfigDict(
    extra="ignore",
    validate_default=False,
    arbitrary_types_allowed=True,
    validate_assignment=True,   # was commented out
)
```

**Effect:** every `setattr(instance, name, value)` runs the field's full validator
pipeline — enum coercion, `SecretStr` wrapping, `AfterValidator` transforms.
This is pydantic v2's documented canonical behaviour.

### Change B — Remove redundant re-application in `__init__`

`src/mountainash_settings/settings/base_settings.py:83-110`

**Before:**

```python
super().__init__(..., **valid_attribute_kwargs)             # validated
...
self.update_settings_from_dict(settings_dict=valid_attribute_kwargs)  # overwrites raw
setattr(self, "SETTINGS_CLASS", ...)
...  # six more setattrs
```

**After:**

```python
super().__init__(..., **valid_attribute_kwargs)             # validated
...
# Bookkeeping only — no re-application of already-validated kwargs.
# object.__setattr__ documents intent: bypass validation for
# harness meta-fields that are not user config.
object.__setattr__(self, "SETTINGS_SOURCE_KWARGS", valid_attribute_kwargs)
object.__setattr__(self, "SETTINGS_CLASS", ...)
...  # six more object.__setattr__ calls
```

**Rationale for `object.__setattr__` on the seven meta-field writes:**
With `validate_assignment=True`, every plain `setattr` validates. The meta-fields
(`SETTINGS_CLASS`, `SETTINGS_CLASS_NAME`, `SETTINGS_SOURCE_ENV_PREFIX`,
`SETTINGS_SOURCE_ENV_FILES`, `SETTINGS_SOURCE_YAML_FILES`, `SETTINGS_SOURCE_TOML_FILES`,
`SETTINGS_SOURCE_JSON_FILES`, `SETTINGS_SOURCE_SECRETS_DIR`) are permissively typed and
carry bookkeeping semantics, not user configuration. Explicit `object.__setattr__`
documents intentional bypass and avoids needless validation on a hot path.

### Change C — Leave `update_settings_from_dict` as-is

With `validate_assignment=True`, the method's existing `setattr` loop validates
automatically. Callsites 2 and 3 (runtime-override flows) correctly coerce enums,
wrap `SecretStr`, and apply transforms with zero code change. This is the systemic
payoff of going root-canonical: the runtime-override path becomes correct for free.

## Risk Surface

### Category 1 — Internal setattrs in `MountainAshBaseSettings.__init__`

Seven writes converted to `object.__setattr__` by Change B → exempt by construction.

### Category 2 — Downstream `setattr` in subclasses / callers

Every plain `setattr` on a `MountainAshBaseSettings` instance now validates:

- **Type-compatible value written** → validation passes, transforms fire,
  behaviour becomes more correct. Intended outcome.
- **Type-incompatible value written** → `ValidationError` raises. That's a latent
  bug the bypass was previously masking.

**Audit scope within `mountainash-settings`:** grep for `setattr` / `__setattr__`
in `src/` and `tests/`. Confirm each site either (a) targets a meta-field now
using `object.__setattr__` via Change B, or (b) writes a type-compatible value.

`DescriptorProfile.post_init` at `src/mountainash_settings/profiles/profile.py:147`
already uses `object.__setattr__` — unchanged, correct.

### Category 3 — Existing test failures

`tests/test_base_settings_coverage.py` has `update_settings_from_dict` tests
(lines 312-367, 541, 608). Expected outcomes after Changes A+B:

- Tests writing type-compatible values → pass, possibly with adjusted assertion
  shape (e.g. `SecretStr` vs raw `str`).
- Tests writing type-incompatible values → raise `ValidationError`.

Per the user's global test-integrity rule, each failure is triaged explicitly:
either the test asserted the broken contract (rewrite to the validated contract)
or the implementation has a genuine bug (fix the implementation). **No test is
skipped, disabled, or silently modified.** Decisions escalate to the user.

### Category 4 — `DescriptorProfile` subclasses

`DescriptorProfile.__pydantic_init_subclass__` at `profile.py:42-90` already wires
`AfterValidator` from `ParameterSpec.validator`. With `validate_assignment=True`,
those validators fire on assignment too — exactly what the backlog item wanted.
No code change required in this file. This is where the systemic payoff lands
across the four target domains.

## Testing Strategy

### New tests (added to `tests/test_base_settings_coverage.py`)

A new class `TestCanonicalAssignmentSemantics` covering:

1. **SecretStr round-trip on assignment.** Construct a settings class with a
   `SecretStr` field. `setattr` a raw string. Assert stored value is
   `isinstance(..., SecretStr)` and `.get_secret_value()` returns the raw string.

2. **Enum coercion on assignment.** Settings class with a `StrEnum` field.
   `setattr` the raw string value. Assert stored value `is` the enum member
   (identity, not equality — `PySparkMode`'s workaround was specifically about
   identity).

3. **`AfterValidator` transform on assignment.** Settings class with
   `Annotated[str, AfterValidator(str.upper)]`. `setattr` a lowercase string.
   Assert stored value is uppercased.

4. **`update_settings_from_dict` validates.** Same three primitives above, routed
   through `update_settings_from_dict`. Confirms `SettingsManager` and
   `apply_runtime_overrides` flows are fixed.

5. **`DescriptorProfile` integration.** Minimal `DescriptorProfile` subclass with
   `ParameterSpec(secret=True)`, `ParameterSpec(type=SomeStrEnum)`, and
   `ParameterSpec(validator=lambda s: s.upper())`. Assert correct behaviour on
   both construction and post-construction `setattr`.

6. **Meta-field bookkeeping bypass.** Assert `SETTINGS_SOURCE_KWARGS` and the
   other six meta-fields still write as dicts/lists via `object.__setattr__`
   in `__init__` and are not coerced (guards against someone "tidying up" by
   removing the bypass).

### Regression guard

```python
def test_validate_assignment_is_enabled():
    """Regression guard — canonical assignment validation must stay on."""
    assert MountainAshBaseSettings.model_config.get("validate_assignment") is True
```

### Existing tests

Run `hatch run test:test` after Changes A+B; triage each failure per Category 3
above.

## Implementation Order

One commit per step for clean bisect:

1. Add new tests from `TestCanonicalAssignmentSemantics` as `xfail` / skipped
   (proves contract pre-change).
2. **Change A:** flip `validate_assignment=True`.
3. **Change B:** convert seven `__init__` meta-field writes to `object.__setattr__`;
   remove redundant `update_settings_from_dict(valid_attribute_kwargs)` call;
   lift `SETTINGS_SOURCE_KWARGS` stash inline.
4. Flip new tests to passing (remove `xfail`). Triage existing-test failures.
5. Add regression guard test.

## Release Notes Entry

> **Behaviour change:** `MountainAshBaseSettings` now validates on assignment
> (`validate_assignment=True`). Values written via `setattr` after construction —
> including via `update_settings_from_dict`, `SettingsManager` runtime overrides,
> and subclass custom setters — now run the declared field validator pipeline.
> `SecretStr` fields wrap raw strings automatically; enum fields coerce raw
> values to enum members; `AfterValidator` transforms apply on assignment as
> well as construction. Subclasses that previously relied on `setattr` bypassing
> validation must switch to `object.__setattr__` for intentional bypass, or fix
> the declared type. CalVer micro bump recommended.

## Follow-up (Tracked Separately)

After `mountainash-settings` is released and consumers bump:

- Remove `PySparkMode.__setattr__` override in `mountainash-data`.
- Remove `ConnectionProfile._default_driver_kwargs` `SecretStr` unwrap guard
  (keep the transform-at-emit step; drop only the defensive unwrap).
- Audit adapter `str(enum_value)` defensive code; simplify where enum instances
  are now guaranteed.
- Close `mountainash-central/01.principles/mountainash-data/f.backlog/setattr-bypass-limitation.md`.
