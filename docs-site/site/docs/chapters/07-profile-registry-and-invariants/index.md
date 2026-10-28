---
title: Profile Registry and Invariants
description: The profile registry system covering the Registry class, name-keyed storage, decorator registration, duplicate prevention, lookup, spec invariants, and automated test generation.
generated_by: claude skill chapter-content-generator
date: 2026-06-03
version: 0.08
---

# Profile Registry and Invariants

The profile registry is the per-domain store that collects `ProfileSpec` instances and their `Profile` subclasses under unique names. It provides name-keyed storage, bare class-decorator registration, duplicate prevention, lookup by name, and a generator that turns every registered spec into a set of pytest invariant checks.

---

## Why a Registry

When an application supports multiple connection backends -- PostgreSQL, MySQL, Redis, Snowflake, BigQuery -- each backend has its own `ProfileSpec` and `Profile` subclass. Something needs to collect these registrations, prevent naming collisions, and provide runtime lookup so that a configuration file specifying `backend: postgresql` can be resolved to the correct settings class. The Registry class fills this role. A `Profile` subclass can come from either declaration path described in [Connection Profiles](../06-connection-profiles/index.md): an explicit `__spec__ = ProfileSpec(...)` or a native declaration whose spec is generated from its fields.

Registries are domain-scoped. A database package has its own registry, a message broker package has another, and an API client package has a third. Each registry operates independently, with its own namespace and optional type constraints.

<!-- concept:71 -->
## Registry Class

The **Registry** class is a mutable, name-keyed store that maps profile names to their specs and settings classes. It maintains two parallel dictionaries:

- `_specs` -- maps name strings to `ProfileSpec` instances
- `_classes` -- maps name strings to `Profile` subclasses

The constructor accepts a name (used in error messages and test IDs) plus two optional type constraints:

```python
class Registry(Generic[_SpecT, _ProfileT]):
    def __init__(
        self,
        name: str,
        *,
        spec_type: type[_SpecT] | None = None,
        profile_type: type[_ProfileT] | None = None,
    ) -> None:
        self.name = name
        self._spec_type = spec_type or ProfileSpec
        self._profile_type = profile_type or Profile
        self._specs: dict[str, _SpecT] = {}
        self._classes: dict[str, type[_ProfileT]] = {}
```

`Registry` is generic over the spec and profile types, so a typed registry gives type checkers precise return types from `get_spec()` and `get_settings_class()`. When `spec_type` is omitted it defaults to `ProfileSpec`, and when `profile_type` is omitted it defaults to `Profile`. Every registered spec must be an instance of `spec_type` (or a subclass), and every registered class must be a subclass of `profile_type`. A violation raises `TypeError` at registration time rather than at runtime lookup, and the registry is left unchanged.

```python
# Create a typed registry
DATABASES_REGISTRY = Registry(
    "databases",
    spec_type=BackendSpec,         # custom subclass of ProfileSpec
    profile_type=ConnectionProfile  # custom subclass of Profile
)
```

<!-- concept:72 -->
## Name Keyed Store

The **name-keyed store** is the core data structure: two dictionaries keyed by the `ProfileSpec.name` string. The name serves as the primary identifier for all lookup and registration operations.

The store supports three access patterns:

- **Registration** -- `register(spec, cls)` adds a new entry
- **Lookup by name** -- `get_spec(name)` and `get_settings_class(name)` retrieve entries
- **Containment check** -- `name in registry` tests whether a name is registered

```python
# After registration:
assert "postgresql" in DATABASES_REGISTRY
assert len(DATABASES_REGISTRY) == 1

spec = DATABASES_REGISTRY.get_spec("postgresql")
cls = DATABASES_REGISTRY.get_settings_class("postgresql")
```

The `specs` property returns a shallow copy of the specs dictionary, providing a view that prevents external mutation of the registry's internal state.

`register(spec, cls)` validates before it stores anything, in this order:

1. `spec` must be a `ProfileSpec` and an instance of the registry's `spec_type`; otherwise `TypeError` (`spec_type mismatch`).
2. `cls` must be a `Profile` subclass and a subclass of the registry's `profile_type`; otherwise `TypeError` (`profile_type mismatch`).
3. `cls` must be a completed profile. An intermediate native declaration (no `name`) or one whose field types are still unresolved raises `TypeError`; call `model_rebuild()` first.
4. A natively declared profile must be registered with its own published spec (`spec is cls.__spec__`); otherwise `TypeError`.
5. The name must be free; otherwise `ValueError` (see Duplicate Prevention).

After a successful registration `register()` also sets `cls.__spec__` to the registered spec.

<!-- concept:73 -->
## Decorator Registration

**Decorator registration** is the primary mechanism for adding profiles to a registry. Instead of calling `registry.register(spec, cls)` imperatively, developers use the `@register` decorator on the class definition:

```python
register = DATABASES_REGISTRY.decorator()

@register
class PostgreSQLProfile(ConnectionProfile):
    __spec__ = POSTGRESQL_SPEC
```

The bare `@register` form (without arguments) is the only decorator form. The decorator reads the class's own `__spec__` and calls `registry.register(spec, cls)` internally. This ensures that the spec and class are always in sync -- the spec declared on the class is exactly the spec registered in the registry.

The decorated class must be a `Profile` subclass with its own `__spec__`: either an explicit `ProfileSpec` set in the class body, or the spec generated for a completed native declaration. A spec inherited from a base class does not count, because the decorator looks only in the class's own namespace. The bare decorator returns the class unchanged and adds it to the registry's lookup tables. A native declaration registers the same way:

```python
register = REGISTRY.decorator()

@register
class NativePG(Profile, name="postgresql", provider_type="postgresql",
               driver_keys="lower"):
    HOST: str = "localhost"
    DATABASE: str
```

#### Diagram: Decorator Registration Flow

<iframe src="../../sims/decorator-registration-flow/main.html" width="100%" height="450px" scrolling="no"></iframe>
<details markdown="1">
<summary>Decorator Registration Flow</summary>
Type: workflow
**sim-id:** decorator-registration-flow<br/>
**Library:** vis-network<br/>
**Status:** Specified

A directed flow showing the `@register` decoration process: (1) Python evaluates class body (installs __spec__), (2) @register decorator invoked with the class, (3) decorator reads cls.__spec__, (4) type constraints validated (spec_type, profile_type), (5) completed-profile and generated-spec checks, (6) duplicate check against _specs, (7) spec and class added to registry dictionaries and cls.__spec__ set, (8) class returned unchanged. Each step is clickable to show the data at that point. Error branches show what happens when a missing own spec, type mismatch, incomplete profile or duplicate is detected.
</details>

<!-- concept:74 -->
## Registry Decorator Factory

The **registry decorator factory** is the `decorator()` method on Registry that returns the `@register` decorator bound to a specific registry instance. This factory pattern allows multiple registries to coexist, each with its own decorator:

```python
# Each registry produces its own decorator
db_register = DATABASES_REGISTRY.decorator()
mq_register = MESSAGE_QUEUE_REGISTRY.decorator()

@db_register
class PostgreSQLProfile(ConnectionProfile):
    __spec__ = POSTGRESQL_SPEC

@mq_register
class RabbitMQProfile(BrokerProfile):
    __spec__ = RABBITMQ_SPEC
```

There is no with-argument form. Calling the decorator with a `ProfileSpec` instance, as in `@register(spec)`, is rejected with `TypeError: Registration requires a Profile subclass`; the spec belongs in the class body as `__spec__` (or is generated from a native declaration).

<!-- concept:75 -->
## Duplicate Prevention

**Duplicate prevention** ensures that no two profiles register under the same name in a single registry. The `register()` method checks `_specs` before adding a new entry:

```python
def register(self, spec: ProfileSpec, cls: type[Profile]) -> None:
    # ... type and completeness checks first ...
    if spec.name in self._specs:
        existing = self._classes[spec.name]
        raise ValueError(
            f"Profile {spec.name!r} is already registered in {self.name} registry "
            f"by {existing.__module__}.{existing.__qualname__}"
        )
```

The error message includes the fully qualified name of the class that already occupies the slot, making it easy to diagnose import-order conflicts where two modules both attempt to register under the same name. This is a common issue in plugin-style architectures where multiple packages contribute to the same registry.

Duplicate prevention applies per-registry. A name like `"postgresql"` can exist in both `DATABASES_REGISTRY` and `ANALYTICS_REGISTRY` without conflict, since they are separate Registry instances with independent namespaces.

!!! tip "Resolving duplicate registration errors"
    If you encounter a `ValueError` about duplicate registration, check whether the same module is being imported twice (common with relative vs absolute imports) or whether two specs accidentally share the same `name` field. The error message's module path helps identify the conflict source.

<!-- concept:76 -->
## Registry Iteration

**Registry iteration** is supported through the `specs` property and the `__len__` and `__contains__` dunder methods:

```python
# Check how many profiles are registered
print(len(DATABASES_REGISTRY))  # e.g., 5

# Iterate over all specs
for name, spec in DATABASES_REGISTRY.specs.items():
    print(f"{name}: {len(spec.parameters)} parameters")

# Check membership
if "postgresql" in DATABASES_REGISTRY:
    spec = DATABASES_REGISTRY.get_spec("postgresql")
```

The `specs` property returns a copy of the internal dictionary, which means iterating or modifying the returned dict does not affect the registry. The `__contains__` method checks `isinstance(name, str)` before lookup, ensuring that non-string values always return `False` rather than raising a `TypeError`.

<!-- concept:77 -->
## Registry Lookup By Name

**Registry lookup by name** is provided by two methods that mirror the two internal dictionaries:

- `get_spec(name)` -- returns the `ProfileSpec` for the given name
- `get_settings_class(name)` -- returns the `Profile` subclass for the given name

Both methods raise `KeyError` with a helpful message that lists all known names in the registry:

```python
def get_spec(self, name: str) -> ProfileSpec:
    try:
        return self._specs[name]
    except KeyError:
        known = ", ".join(sorted(self._specs)) or "<none>"
        raise KeyError(
            f"No profile registered under {name!r} in {self.name} "
            f"registry. Known: {known}"
        ) from None
```

The `from None` suppression ensures a clean error message without the confusing "during handling of the above exception, another exception occurred" chain. The known-names hint is especially valuable in applications with many registered profiles, where a typo in the name (e.g., `"postgresq"` instead of `"postgresql"`) can be immediately identified.

#### Diagram: Registry Internal Structure

<iframe src="../../sims/registry-structure/main.html" width="100%" height="500px" scrolling="no"></iframe>
<details markdown="1">
<summary>Registry Internal Structure</summary>
Type: diagram
**sim-id:** registry-structure<br/>
**Library:** vis-network<br/>
**Status:** Specified

An interactive diagram showing a Registry instance with its two parallel dictionaries (_specs and _classes). Three sample profiles are registered (postgresql, mysql, redis). Clicking a profile name in either dictionary highlights the matching entry in the other dictionary and shows the spec details / class information in a side panel. The type constraint badges (spec_type, profile_type) are shown at the top with hover explanations. A search box allows filtering registered entries.
</details>

<!-- concept:78 -->
## Spec Invariants

**Spec invariants** are a set of validation rules that every registered `ProfileSpec` must satisfy. They encode the naming conventions, uniqueness constraints, and structural requirements that the profile system relies on:

| Invariant | Rule | Failure Meaning |
|-----------|------|----------------|
| `test_name_matches_registry_key` | `spec.name == registry_key` | Spec name and registry key are out of sync |
| `test_name_lowercase_nonempty` | `spec.name` is lowercase and non-empty | Naming convention violated |
| `test_parameter_names_unique` | No duplicate names in `spec.parameters` | Ambiguous field definitions |
| `test_parameter_names_uppercase` | All parameter names are UPPERCASE and non-empty | Naming convention violated |
| `test_driver_keys_unique` | No duplicate output key within any one target: bare-string `driver_key` values must be unique and must not collide with any target's key; dict `driver_key` values must be unique per target | Ambiguous driver kwargs |
| `test_parameter_tiers_valid` | All tiers are `"core"` or `"advanced"` | Invalid tier classification |
| `test_provider_type_not_none` | `spec.provider_type` is not None | Missing domain classification |

A bare-string `driver_key` applies to every emission target and a dict `driver_key` applies per named target, so uniqueness is checked per target after resolving both forms. The same key under two different targets is not a collision. Two parameters that map to the same key for one target are.

These invariants catch specification errors at test time, well before they could cause runtime failures. A typo in a parameter name, a duplicated driver key, or a missing provider type all produce clear test failures with descriptive messages. Authentication is not part of the spec (see [Authentication Boundary](../08-authentication-system/index.md)), so there is no invariant for it.

<!-- concept:79 -->
## Invariant Test Generator

The **invariant test generator** is the `spec_invariants_for()` function that takes a Registry instance and returns a pytest class parameterized over every registered spec. This function is the primary integration point between the invariant system and a project's test suite:

```python
from mountainash_settings.profiles import spec_invariants_for
from my_package.settings import MY_REGISTRY

TestMyInvariants = spec_invariants_for(MY_REGISTRY)
```

This single line generates one test per invariant per registered spec. If the registry contains five profiles and there are seven invariants, the generated class produces thirty-five parameterized test cases.

The generator reads `registry.specs` once, when `spec_invariants_for()` is called. Profiles registered after that call are not covered by the returned class, so call it after the modules that register profiles have been imported. The returned class is also marked `pytest.mark.unit` and imports `pytest` lazily, so `mountainash_settings` stays importable where pytest is not installed.

The generator uses `pytest.mark.parametrize` to create test cases named by the profile:

```python
@pytest.mark.parametrize("name,spec", entries, ids=ids)
class TestSpecInvariants:
    def test_name_matches_registry_key(self, name, spec):
        assert spec.name == name

    def test_parameter_names_unique(self, name, spec):
        names = [p.name for p in spec.parameters]
        assert len(names) == len(set(names))
    # ... remaining invariants
```

The class is dynamically renamed to `TestSpecInvariants_<registry_name>` so that pytest output clearly identifies which registry's invariants are running. Profiles registered before the call automatically get full invariant coverage -- there is no need to write individual tests for each new backend.

#### Diagram: Invariant Test Coverage Matrix

<iframe src="../../sims/invariant-test-matrix/main.html" width="100%" height="450px" scrolling="no"></iframe>
<details markdown="1">
<summary>Invariant Test Coverage Matrix</summary>
Type: chart
**sim-id:** invariant-test-matrix<br/>
**Library:** Chart.js<br/>
**Status:** Specified

A heatmap-style matrix with invariant names as rows and registered profile names as columns. Each cell is green (pass), red (fail), or gray (not yet run). Clicking a cell shows the test assertion that passed or the error message that failed. Hovering over a row header shows the invariant's rule description. A "Run All" button animates the matrix filling in cell by cell. Users can add a "broken" spec via a form to see how invariant failures appear.
</details>

## Putting It All Together

The registry and invariant systems work together to create a reliable, discoverable ecosystem of connection profiles. The full workflow from profile creation to validated deployment is:

1. **Define a ProfileSpec** with an identity (`name`, `provider_type`) and parameters, or declare the profile natively and let the spec be generated
2. **Create a Profile subclass** with `__spec__ = YOUR_SPEC` (explicit path) or a `name=`/`provider_type=` class header (native path)
3. **Register with `@register`** on the class definition
4. **Add `TestInvariants = spec_invariants_for(REGISTRY)`** to your test suite, after the registering modules are imported
5. **Look up at runtime** via `REGISTRY.get_settings_class("name")`

Each step in this workflow is supported by the framework with clear error messages and fail-fast behavior. Misspelled names produce `KeyError` with a list of known alternatives. Type constraint violations, a missing own `__spec__` and incomplete profiles produce `TypeError` at registration time. Duplicate names produce `ValueError` with the conflicting class's location.

The test seam methods (`_snapshot_for_tests` and `_reset_for_tests`) allow test suites to register temporary profiles without permanently polluting the global registry, supporting isolated test scenarios.
