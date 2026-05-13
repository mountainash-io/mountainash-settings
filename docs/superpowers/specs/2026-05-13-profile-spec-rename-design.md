# Profile / ProfileSpec rename and structural cleanup

**Date:** 2026-05-13
**Status:** Design draft — pending review
**Target version:** mountainash-settings 26.5.0 (rename + deprecation), 26.6.0 (removal)

## Summary

Rename the `ProfileDescriptor` / `DescriptorProfile` pair to `ProfileSpec` / `Profile`, propagate the rename through every adjacent identifier (the `__descriptor__` class attribute, the `descriptor_invariants_for` helper, and `*_DESCRIPTOR` constants in consumer code), tighten the `Registry` API with type constraints, and consolidate two duplicated MRO walks into a shared helper. Ship through one deprecation cycle so downstream consumers (mountainash-data and any other package that builds on top of `mountainash_settings.profiles`) can migrate without coordinated big-bang releases.

## Background

The `mountainash_settings.profiles` subpackage exposes a declarative settings system: a frozen dataclass describes the shape (`ProfileDescriptor`), and a `MountainAshBaseSettings` subclass picks up that shape at class-creation time (`DescriptorProfile`). Several downstream packages, most prominently `mountainash-data`, build typed connection profiles on top of this system.

Six issues were identified. Five are in scope; the sixth is deferred:

1. **Name inversion.** `ProfileDescriptor` (data) and `DescriptorProfile` (class) use the same two words in reversed order. A reader cannot tell which is which without already knowing. Downstream extensions (`BackendDescriptor` ↔ `ConnectionProfile`) inherit the same confusion.
2. **`__descriptor__` body redundancy.** Concrete classes declare `__spec__` (currently `__descriptor__`) in their body *and* receive the same value through the `@register(spec)` decorator. Two declarations, no drift detection — copy-paste errors silently bind the wrong spec.
3. **`*AuthSettings` class-name convention (deferred).** Concrete consumer classes such as `PostgreSQLAuthSettings` describe full connection profiles, not just authentication. The `Auth` suffix is misleading. Deferred to a separate refactor because it touches user-facing class names that callers may import directly.
4. **`_Missing` private import.** `mountainash-data` imports the private `_Missing` class from `mountainash_settings.profiles.descriptor`. The sentinel class needs a public surface, or callers need to stop importing it directly.
5. **No type coupling between extension hierarchies.** `BackendDescriptor` and `ConnectionProfile` are connected only by convention. A consumer can register a `BackendDescriptor` against a plain `DescriptorProfile` subclass with no error; `to_driver_kwargs()` and `to_connection_string()` then silently fail to exist.
6. **Duplicated MRO walks.** `DescriptorProfile.post_init()` and `ConnectionProfile.to_driver_kwargs()` independently implement the same "find a class-level dunder by walking `__mro__`" pattern. Drift risk on pydantic upgrades.

This design addresses issues 1, 2, 4, 5, and 6. Issue 3 is referenced here for traceability but is not implemented as part of this work.

## Goals

- Pick names that distinguish data from class without sharing vocabulary.
- Enforce type coupling between specs and profile classes at the Registry boundary.
- Eliminate the body-vs-decorator redundancy without breaking field installation ordering.
- Provide a reusable migration path so any downstream consumer can adopt the new names independently, on its own release schedule.
- Remove all duplicated MRO-walk code paths.

## Non-goals

- Renaming `ConnectionProfile`, `ParameterSpec`, or `Registry`. These are already correctly named.
- Renaming any consumer-level concrete class (e.g. `PostgreSQLAuthSettings`). The naming of those classes is a separate concern.
- Changing pydantic field installation semantics, secrets resolution, caching, or any other runtime behaviour.
- Changing the runtime behaviour of `to_driver_kwargs()`, `to_connection_string()`, or `auth_to_driver_kwargs()`.

## Design overview

### New public API surface

```python
from mountainash_settings import (
    ProfileSpec,           # was ProfileDescriptor
    Profile,               # was DescriptorProfile
    ParameterSpec,         # unchanged
    Registry,              # unchanged name; new constructor kwargs
    MISSING,               # unchanged sentinel instance
    Missing,               # NEW — public class for type annotations
    spec_invariants_for,   # was descriptor_invariants_for
    lookup_class_var,      # NEW — public MRO-walking helper
)
```

### New class attribute

```python
class MyProfile(Profile):
    __spec__ = MY_SPEC      # was __descriptor__
```

### New Registry constructor

```python
Registry(
    name: str,
    *,
    spec_type: type[ProfileSpec] = ProfileSpec,
    profile_type: type[Profile] = Profile,
)
```

`Registry.register()` validates that the descriptor is an instance of `spec_type` and the decorated class subclasses `profile_type`. Misuse raises `TypeError` at decoration time. Default values give existing callers unchanged behaviour.

### New `@register` form

```python
# Old (deprecated)
@register(MY_SPEC)
class MyProfile(Profile):
    __descriptor__ = MY_SPEC

# New
@register
class MyProfile(Profile):
    __spec__ = MY_SPEC
```

The argument-free `@register` reads `cls.__dict__["__spec__"]` and registers under `cls.__spec__.name`. Spec is named exactly once. The old form `@register(spec)` continues to work during deprecation and additionally validates that `spec` and `cls.__spec__` (if both present) agree — a drift-catch that the previous "belt-and-braces" assignment lacked.

### Shared MRO-walk helper (public)

```python
def lookup_class_var(cls: type, name: str) -> t.Any | None:
    """Walk cls.__mro__ and return the first __dict__ value for `name`."""
```

Exported as `mountainash_settings.lookup_class_var` (and from `mountainash_settings.profiles`). Used internally for `__spec__` lookup (with old-name fallback) and `__adapter__` lookup. Documented as a public, supported helper from 26.5.0 onwards so downstream consumers can adopt it without taking a private-dependency risk. The old-name fallback issues a `DeprecationWarning` when only `__descriptor__` is present.

## Upstream changes — `mountainash-settings`

### File-by-file

**`src/mountainash_settings/profiles/spec.py`** (new file; replaces `descriptor.py` as the canonical location).
- `ProfileSpec` class (frozen dataclass) — verbatim port of `ProfileDescriptor` with the new name.
- `Missing` class — verbatim port of `_Missing` with the new public name.
- `MISSING` sentinel instance — unchanged.
- `ParameterSpec` — unchanged.
- `__all__` exports `ProfileSpec`, `Missing`, `MISSING`, `ParameterSpec`.

**`src/mountainash_settings/profiles/descriptor.py`** (kept as a compatibility shim).
- Module-level `__getattr__` (PEP 562) intercepts `ProfileDescriptor` and `_Missing` lookups (the two symbols this module owned).
- Each emits `DeprecationWarning` naming the new symbol and the removal version, then returns the new object.
- `BackendDescriptor` is intentionally **not** aliased here — it is a `mountainash-data` symbol, not a `mountainash-settings` one. Its compatibility shim lives in `mountainash-data`'s own `descriptor.py` (see "Optional: keep your own old names available" in the migration guide).

**`src/mountainash_settings/profiles/profile.py`**.
- `Profile` class — verbatim port of `DescriptorProfile` with the new name.
- `__pydantic_init_subclass__` reads `cls.__dict__.get("__spec__")` first, falls back to `cls.__dict__.get("__descriptor__")` with a `DeprecationWarning` when only the old attribute is present.
- If both `__spec__` and `__descriptor__` are declared and disagree → `TypeError` with both values in the message.
- `post_init()` uses the new public `lookup_class_var()` helper instead of an inline MRO loop.
- The `_default_kwargs()` and `_auth_kwargs()` methods are unchanged.

**`src/mountainash_settings/profiles/registry.py`**.
- `Registry.__init__` accepts keyword-only `spec_type: type[ProfileSpec] = ProfileSpec` and `profile_type: type[Profile] = Profile`. Stored on the instance.
- `Registry.register(spec, cls)` validates `isinstance(spec, self._spec_type)` and `issubclass(cls, self._profile_type)`. `TypeError` on mismatch.
- `Registry.register()` sets `cls.__spec__` to the registered spec **and also mirrors it to `cls.__descriptor__`** during the 26.5.x deprecation window. Both attributes point at the same object. Any downstream code that still reads `cls.__descriptor__` or `instance.__descriptor__` keeps working until 26.6.0 — the documented removal point. The mirror is dropped in 26.6.0.
- `Registry.decorator()` returns a decorator that accepts either:
  - Zero arguments (the class) — reads `cls.__spec__`, validates, registers. New canonical form.
  - One argument (the spec) — same as before, also validates against `cls.__spec__` if declared. Emits `DeprecationWarning`.

**`src/mountainash_settings/profiles/invariants.py`**.
- `spec_invariants_for(registry)` — verbatim port of `descriptor_invariants_for` with renamed parametrize IDs (`descriptor` → `spec`).
- Generated test class name: `TestSpecInvariants_<registry_name>` (was `TestDescriptorInvariants_<registry_name>`).

**`src/mountainash_settings/profiles/lookup.py`** (new helper module, public).
- `lookup_class_var(cls, name)` — single MRO walk used by `Profile` for `__spec__`, `__descriptor__` fallback, and `__adapter__`. Re-exported from `mountainash_settings.profiles` and `mountainash_settings` top-level. Documented as supported public API from 26.5.0 onwards.

**`src/mountainash_settings/profiles/__init__.py`**.
- Re-exports the new public symbols.
- Module-level `__getattr__` adds deprecated aliases for `ProfileDescriptor`, `DescriptorProfile`, `descriptor_invariants_for`. Each emits `DeprecationWarning` with the new name and removal version, then returns the new object.

**`src/mountainash_settings/__init__.py`**.
- Re-exports new symbols at top level.
- Module-level `__getattr__` for top-level deprecated aliases.

### Deprecation mechanics

**Module-level (PEP 562 `__getattr__`).** Single function per module:

```python
_DEPRECATED = {
    "ProfileDescriptor":         ("ProfileSpec", ProfileSpec),
    "DescriptorProfile":         ("Profile", Profile),
    "descriptor_invariants_for": ("spec_invariants_for", spec_invariants_for),
}

def __getattr__(name: str) -> t.Any:
    if name in _DEPRECATED:
        new_name, obj = _DEPRECATED[name]
        warnings.warn(
            f"{name!r} is renamed to {new_name!r} in mountainash-settings 26.5.0. "
            f"The old name will be removed in 26.6.0.",
            DeprecationWarning, stacklevel=2,
        )
        return obj
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

**Class attribute `__descriptor__`.** The deprecation contract has two sides — *reading* code that still uses the old attribute name, and *writing* code that still declares it.

*Reading side (preservation of old attribute on migrated classes).* `Registry.register()` sets `cls.__spec__` to the registered spec and additionally sets `cls.__descriptor__` to the same object. This means a class that has been fully migrated to the new form — `__spec__ = MY_SPEC` in the body and the bare `@register` decorator — still exposes `cls.__descriptor__` and `instance.__descriptor__` for any downstream consumer that hasn't yet migrated its *reads*. Both names resolve to the same object. The mirror lives only during 26.5.x; removed in 26.6.0.

*Writing side (classes that still declare `__descriptor__` in the body).* `Profile.__pydantic_init_subclass__` reads:

```python
spec = cls.__dict__.get("__spec__")
old = cls.__dict__.get("__descriptor__")
if spec is None and old is not None:
    warnings.warn(
        f"{cls.__name__} declares '__descriptor__' (deprecated). "
        f"Rename to '__spec__' before mountainash-settings 26.6.0.",
        DeprecationWarning, stacklevel=2,
    )
    spec = old
elif spec is not None and old is not None and spec is not old:
    raise TypeError(
        f"{cls.__name__} declares both '__spec__' and '__descriptor__' "
        f"with conflicting values: {spec!r} vs {old!r}"
    )
```

This handles the case where a class body still uses the old name. The reading-side mirror above runs after this (when `@register` fires) and unconditionally mirrors `__spec__` to `__descriptor__`, so any successful registration leaves both attributes available regardless of which name the body used.

**Decorator form `@register(spec)`.** When `Registry.decorator()` is called with one argument:

```python
warnings.warn(
    "@register(spec) is deprecated. Use '@register' (no argument); "
    "the spec will be read from the class's __spec__ attribute.",
    DeprecationWarning, stacklevel=2,
)
```

The old form still works and additionally validates against `cls.__spec__` if declared.

### Removal (26.6.0)

- Module-level `__getattr__` shims removed.
- `descriptor.py` compatibility shim file removed.
- `__pydantic_init_subclass__` no longer reads `__descriptor__`.
- `Registry.register()` no longer mirrors `__spec__` to `__descriptor__`. Only `__spec__` is set on migrated classes.
- `Registry.decorator()` only accepts the argument-free form.
- All deprecation tests deleted; new-form tests retained.

## Migration guide for downstream consumers

This section is reusable by any package that builds on `mountainash_settings.profiles`. It applies to `mountainash-data` and any other consumer.

### Prerequisites

- Upgrade to `mountainash-settings >= 26.5.0`.
- Run your test suite with `pytest -W default::DeprecationWarning` to see which deprecated names your code uses.

### Step-by-step

1. **Rename type aliases.** If you subclass `ProfileDescriptor` to add domain-specific metadata (e.g. `BackendDescriptor` in mountainash-data), rename your subclass to use the `Spec` vocabulary (e.g. `BackendSpec`). The parent class import changes:

    ```python
    # Before
    from mountainash_settings.profiles import ProfileDescriptor
    class BackendDescriptor(ProfileDescriptor): ...

    # After
    from mountainash_settings.profiles import ProfileSpec
    class BackendSpec(ProfileSpec): ...
    ```

2. **Switch `_Missing` import to public `Missing` (if used).** If your code imports `_Missing` from `mountainash_settings.profiles.descriptor` for type annotations, switch to the public `Missing`:

    ```python
    # Before
    from mountainash_settings.profiles.descriptor import _Missing

    # After
    from mountainash_settings.profiles import Missing
    ```

3. **Rename your `*_DESCRIPTOR` constants to `*_SPEC`.** Mechanical search-and-replace in every file that declares a profile spec:

    ```python
    # Before
    POSTGRESQL_DESCRIPTOR = BackendDescriptor(...)

    # After
    POSTGRESQL_SPEC = BackendSpec(...)
    ```

4. **Rename the class attribute on every concrete profile.** Change `__descriptor__` to `__spec__` everywhere it appears in a class body:

    ```python
    # Before
    class PostgreSQLAuthSettings(ConnectionProfile):
        __descriptor__ = POSTGRESQL_DESCRIPTOR

    # After
    class PostgreSQLAuthSettings(ConnectionProfile):
        __spec__ = POSTGRESQL_SPEC
    ```

5. **Switch to argument-free `@register`.** Remove the spec argument from every decorator call. The spec is now read from the class body — naming it once:

    ```python
    # Before
    @register(POSTGRESQL_DESCRIPTOR)
    class PostgreSQLAuthSettings(ConnectionProfile):
        __descriptor__ = POSTGRESQL_DESCRIPTOR

    # After
    @register
    class PostgreSQLAuthSettings(ConnectionProfile):
        __spec__ = POSTGRESQL_SPEC
    ```

6. **Tighten your `Registry` with type constraints.** If you have a domain-specific spec subclass and profile subclass, pass them to `Registry` so the registry validates registrations:

    ```python
    # Before
    DATABASES_REGISTRY = Registry("databases")

    # After
    DATABASES_REGISTRY = Registry(
        "databases",
        spec_type=BackendSpec,
        profile_type=ConnectionProfile,
    )
    ```

7. **Rename `descriptor_invariants_for` to `spec_invariants_for`.** Mechanical rename of the import and the call:

    ```python
    # Before
    from mountainash_settings import descriptor_invariants_for
    TestInvariants = descriptor_invariants_for(MY_REGISTRY)

    # After
    from mountainash_settings import spec_invariants_for
    TestInvariants = spec_invariants_for(MY_REGISTRY)
    ```

    The generated test class name changes accordingly. Update any test selection patterns that referenced `TestDescriptorInvariants_*`.

8. **Replace local MRO walks (if any).** If your package implements its own version of "walk `__mro__` to find a class-level dunder" (the way `ConnectionProfile.to_driver_kwargs()` originally did for `__adapter__`), import the public helper from `mountainash_settings`:

    ```python
    # Before — local MRO walk
    adapter = type(self).__dict__.get("__adapter__")
    if adapter is None:
        for base in type(self).__mro__[1:]:
            candidate = base.__dict__.get("__adapter__")
            if candidate is not None:
                adapter = candidate
                break

    # After — public helper (supported API from 26.5.0)
    from mountainash_settings import lookup_class_var
    adapter = lookup_class_var(type(self), "__adapter__")
    ```

9. **Verify migration is complete.** Re-run your tests with deprecation warnings escalated to errors:

    ```bash
    pytest -W error::DeprecationWarning
    ```

    Any remaining use of an old name will fail the run, pointing you to the file and line. This is the migration completion check.

10. **Bump your `mountainash-settings` lower bound.** In `pyproject.toml`:

    ```toml
    [project]
    dependencies = [
        "mountainash-settings>=26.5.0",
    ]
    ```

11. **Plan removal upgrade.** Before `mountainash-settings 26.6.0` releases, your package should already be on the new names. The deprecation cycle is one release; after 26.6.0 the old names raise `AttributeError` / `ImportError`.

### Optional: keep your own old names available

If your package itself has been exporting names that referenced the old vocabulary — for example, `mountainash-data` historically re-exported `BackendDescriptor` and `_Missing` from its `descriptor.py` — apply the same PEP 562 `__getattr__` pattern in your package's module so your own consumers get a deprecation cycle too. The recipe is identical:

```python
# my_package/descriptor.py
from .new_names import BackendSpec, Missing

_DEPRECATED = {
    "BackendDescriptor": ("BackendSpec", BackendSpec),
    "_Missing":          ("Missing", Missing),
}

def __getattr__(name):
    if name in _DEPRECATED:
        new_name, obj = _DEPRECATED[name]
        warnings.warn(
            f"{name!r} is renamed to {new_name!r}. "
            f"Update imports before <your-removal-version>.",
            DeprecationWarning, stacklevel=2,
        )
        return obj
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

## Example migration: `mountainash-data`

This section illustrates the migration guide above against the concrete shape of `mountainash-data`. The same pattern applies to any other consumer.

### Files changed

- `src/mountainash_data/core/settings/descriptor.py` — `BackendDescriptor` → `BackendSpec`, `_Missing` import replaced with public `Missing`. `__getattr__` shim added for the old names (since `mountainash-data` itself may have downstream consumers).
- `src/mountainash_data/core/settings/profile.py` — local MRO walk in `to_driver_kwargs()` replaced with a `lookup_class_var()` call imported from `mountainash_settings`.
- `src/mountainash_data/core/settings/registry.py` — `DATABASES_REGISTRY` constructed with `spec_type=BackendSpec, profile_type=ConnectionProfile`.
- `src/mountainash_data/core/settings/*.py` (21 backend files) — mechanical sweep: import renames, constant renames (`*_DESCRIPTOR` → `*_SPEC`), `@register(SPEC)` → `@register`, `__descriptor__` → `__spec__`.
- `src/mountainash_data/core/settings/__init__.py` — exports updated; deprecation `__getattr__` for any re-exported old names.
- `tests/**/*` — references updated; `descriptor_invariants_for` → `spec_invariants_for`.
- `CLAUDE.md` — internal documentation updated.

### Out-of-scope consumer code

`core/connection.py`, `backends/ibis/backend.py`, `backends/iceberg/connection.py`, `backends/iceberg/catalogs/rest.py` import `SettingsParameters`, `MountainAshBaseSettings`, and the various `*AuthSettings` classes — none of which are renamed. They are unaffected by this refactor.

### Adapter files

`adapters/*.py` call `_default_kwargs()` and `_auth_kwargs()` on a `ConnectionProfile` instance, neither of which is renamed. Adapters are unaffected.

### CI verification

After the migration PR merges, `mountainash-data`'s CI configuration flips to `pytest -W error::DeprecationWarning` so future contributions cannot reintroduce the deprecated names.

## Testing strategy

### `mountainash-settings`

Three new concerns, each with its own test module or section.

**Deprecation paths** — new `tests/unit/profiles/test_deprecation.py`:

- `from mountainash_settings.profiles import ProfileDescriptor` emits `DeprecationWarning` and returns `ProfileSpec`.
- `from mountainash_settings.profiles import DescriptorProfile` emits `DeprecationWarning` and returns `Profile`.
- `from mountainash_settings.profiles import descriptor_invariants_for` emits `DeprecationWarning` and returns `spec_invariants_for`.
- `from mountainash_settings.profiles.descriptor import _Missing` emits `DeprecationWarning` and returns `Missing`.
- A class declaring only `__descriptor__` (no `__spec__`) emits `DeprecationWarning` at class creation; fields install correctly from the old attribute.
- A class declaring both `__spec__` and `__descriptor__` with the same value installs correctly (no warning).
- A class declaring both `__spec__` and `__descriptor__` with different values raises `TypeError`.
- `Registry.decorator()(spec)` (old one-argument form) emits `DeprecationWarning`, registers correctly, and additionally raises if `spec` disagrees with `cls.__spec__`.
- **A class registered via the new bare `@register` form with only `__spec__` declared still exposes `cls.__descriptor__` after registration.** Specifically: `cls.__descriptor__ is cls.__spec__` and `instance.__descriptor__ is cls.__spec__`. This protects downstream code that still *reads* the old attribute name during the deprecation window. (This test deletes in 26.6.0 when the mirror is removed.)

**Registry constraints** — additions to `tests/unit/profiles/test_registry.py`:

- `Registry("name", spec_type=CustomSpec)` accepts `CustomSpec` instances via `register()`.
- `Registry("name", spec_type=CustomSpec)` raises `TypeError` when passed a plain `ProfileSpec` instance, with both types named in the message.
- `Registry("name", profile_type=CustomProfile)` accepts `CustomProfile` subclasses.
- `Registry("name", profile_type=CustomProfile)` raises `TypeError` for a non-subclass.
- Default `Registry("name")` (no constraints) keeps all existing tests passing.

**Argument-free `@register`** — additions to `test_registry.py`:

- `@register` (no args) reads `cls.__spec__` and registers under `cls.__spec__.name`.
- `@register` raises `TypeError` when `cls.__spec__` is missing.
- `@register` raises `TypeError` when `cls.__spec__` is the wrong type for the registry.

**Public lookup helper** — new `tests/unit/profiles/test_lookup.py`:

- `lookup_class_var(cls, name)` returns the value from `cls.__dict__` when present.
- `lookup_class_var(cls, name)` walks `__mro__` when the attribute is on a base class.
- `lookup_class_var(cls, name)` returns `None` when the attribute is absent everywhere in the MRO.
- `lookup_class_var` is importable from both `mountainash_settings` and `mountainash_settings.profiles` and resolves to the same function object.

**Regression checks** — additions to existing tests:

- `SettingsParameters.__hash__` returns identical values for equivalent configurations under both old and new names (the alias is the same class object).
- `model_dump()` output is byte-identical before and after the rename for any given settings instance.
- `isinstance(instance, ProfileDescriptor)` returns `True` during deprecation (the alias is the same class, not a subclass).

### Downstream consumers

The migration guide's verification step (`pytest -W error::DeprecationWarning`) is the canonical completion check for any downstream consumer. Consumers may add explicit tests for their own deprecation shims if they re-export renamed symbols.

For `mountainash-data` specifically: every backend test continues to pass under the new names; `spec_invariants_for(DATABASES_REGISTRY)` continues to parametrise over every registered backend; the full suite runs with `-W error::DeprecationWarning` after the migration PR.

## Release sequencing

### Version targets

- **`mountainash-settings 26.5.0`** — rename + deprecation aliases. Minor bump. Old names emit `DeprecationWarning` but resolve correctly.
- **Downstream consumer next release** — each consumer migrates to new names on its own schedule, bumps `mountainash-settings>=26.5.0`.
- **`mountainash-settings 26.6.0`** — removes deprecation aliases. Breaking for any consumer still on old names; the prior release's deprecation warnings were the contract.

### `mountainash-settings 26.5.0` PR scope

Single PR, single review cycle. Branch off `develop`, target `develop`.

1. Add `spec.py`; port `ProfileSpec` and `Missing` from `descriptor.py`.
2. Update `profile.py` — class rename, `__spec__` attribute, MRO fallback for `__descriptor__`.
3. Add `lookup.py` — public `lookup_class_var()` helper.
4. Update `registry.py` — constructor constraints, argument-free decorator form, drift catch on old form.
5. Rename `descriptor_invariants_for` → `spec_invariants_for` in `invariants.py`.
6. Convert `descriptor.py` to a compatibility shim with `__getattr__`.
7. Update `profiles/__init__.py` and top-level `__init__.py` exports and `__getattr__` shims.
8. Add `tests/unit/profiles/test_deprecation.py`; update existing tests.
9. Update docs (`docs/quickstart.md`, `docs/advanced-usage.md`, `docs/profile-descriptor-pattern.md` → `docs/profile-spec-pattern.md`, `README.md`).
10. Add release notes (in PR description and, if the repo adopts one, a `CHANGELOG.md` entry) naming new symbols, old symbols, and the 26.6.0 removal commitment. The `mountainash-settings` repo currently has no `CHANGELOG.md`; release notes are generated by the GitHub Actions release workflow. Either is acceptable as long as the removal commitment is in writing.

### Package profile refresh (separate work)

The `docs/package-profile/` profile records the codebase shape at a given commit. After the rename PR merges, run the `hiivmind-documentation-profile:package-documentation-profile` skill in `incremental-refresh` mode to update the profile. Out of scope for the rename PR itself.

## Risks and mitigations

**Conflicting `__spec__` / `__descriptor__` declarations.** A class could end up declaring both attributes with different values (e.g. a partial migration). Mitigation: the fallback path in `Profile.__pydantic_init_subclass__` raises `TypeError` rather than silently picking one, with both values in the error message. The `Registry.register()` mirror runs after this check, so a class that conflicts will never reach the mirroring step.

**Mirror-induced shadowing across inheritance.** During deprecation, `Registry.register()` mirrors `__spec__` to `__descriptor__` on the registered class. If a user defines a subclass of a registered class without re-registering it, the subclass inherits both attributes. This is intentional and matches the existing inheritance semantics for `__spec__`; documented for transparency. The 26.6.0 removal eliminates this surface entirely.

**External consumers we have not audited.** Packages beyond `mountainash-data` may depend on `mountainash-settings.profiles` symbols. Mitigation: the deprecation cycle gives them time. The deprecation message names both the new symbol and the removal version. The 26.6.0 release should be preceded by an audit of the `mountainash-io` org for any remaining old-name usage.

**Pydantic-version sensitivity.** Dynamic field installation via `__pydantic_init_subclass__` + `model_fields` mutation + `model_rebuild(force=True)` is not officially documented by pydantic. The rename does not change this surface, but it touches the methods that use it. Mitigation: existing tests cover the field-installation contract; deprecation tests cover the new fallback path.

**Stacklevel correctness in warnings.** `stacklevel=2` works for direct `from module import name` but may not point at the right line for re-exports through multiple `__getattr__` layers. Mitigation: deprecation tests assert that warnings include the new-name suggestion in the message, which is a more reliable signal than line number.

## Out of scope

- Renaming `ConnectionProfile`, `ParameterSpec`, `Registry`.
- Renaming concrete `*AuthSettings` classes in `mountainash-data` or any other consumer.
- Updating downstream packages other than `mountainash-data`. Each is owned by its maintainers; this spec provides them the migration guide.
- Refreshing the `docs/package-profile/` profile — separate task using the package-documentation-profile skill.

## Open questions

None. All clarifying questions were resolved during brainstorming.
