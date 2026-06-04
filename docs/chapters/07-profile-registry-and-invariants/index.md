---
title: Profile Registry and Invariants
description: The profile registry system covering the Registry class, name-keyed storage, decorator registration, duplicate prevention, lookup, descriptor invariants, and automated test generation.
generated_by: claude skill chapter-content-generator
date: 2026-06-03
version: 0.08
---

# Profile Registry and Invariants

## Summary

This chapter covers the profile registry that provides a centralized store for ProfileDescriptor instances. You will learn about the Registry class with its name-keyed store, decorator-based registration pattern, registry decorator factory for customizing registration, duplicate prevention, iteration and lookup by name, descriptor invariants that validate profile definitions, and the invariant test generator for automated testing.

## Concepts Covered

- Registry Class
- Name Keyed Store
- Decorator Registration
- Registry Decorator Factory
- Duplicate Prevention
- Registry Iteration
- Registry Lookup By Name
- Descriptor Invariants
- Invariant Test Generator

## Prerequisites

- Chapter 1: Pydantic and Configuration Foundations
- Chapter 6: Connection Profiles

---

<!-- concept:71 -->
<!-- concept:74 -->
<!-- concept:76 -->
## Why a Registry

When an application supports multiple connection backends -- PostgreSQL, MySQL, Redis, Snowflake, BigQuery -- each backend has its own `ProfileSpec` and `Profile` subclass. Something needs to collect these registrations, prevent naming collisions, and provide runtime lookup so that a configuration file specifying `backend: postgresql` can be resolved to the correct settings class. The Registry class fills this role.

Registries are domain-scoped. A database package has its own registry, a message broker package has another, and an API client package has a third. Each registry operates independently, with its own namespace and optional type constraints.

## Registry Class

The **Registry** class is a mutable, name-keyed store that maps profile names to their specs and settings classes. It maintains two parallel dictionaries:

- `_descriptors` -- maps name strings to `ProfileSpec` instances
- `_classes` -- maps name strings to `Profile` subclasses

The constructor accepts a name (used in error messages and test IDs) plus two optional type constraints:

```python
class Registry:
    def __init__(
        self,
        name: str,
        *,
        spec_type: type[ProfileSpec] | None = None,
        profile_type: type | None = None,
    ) -> None:
        self.name = name
        self._spec_type = spec_type
        self._profile_type = profile_type
        self._descriptors: dict[str, ProfileSpec] = {}
        self._classes: dict[str, type[Profile]] = {}
```

When `spec_type` is provided, every registered spec must be an instance of that type (or a subclass). When `profile_type` is provided, every registered class must be a subclass. These constraints catch accidental cross-domain registrations at registration time rather than at runtime lookup.

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
- **Lookup by name** -- `get_descriptor(name)` and `get_settings_class(name)` retrieve entries
- **Containment check** -- `name in registry` tests whether a name is registered

```python
<!-- concept:73 -->
# After registration:
assert "postgresql" in DATABASES_REGISTRY
assert len(DATABASES_REGISTRY) == 1

spec = DATABASES_REGISTRY.get_descriptor("postgresql")
cls = DATABASES_REGISTRY.get_settings_class("postgresql")
```

The `descriptors` property returns a shallow copy of the specs dictionary, providing a read-only view that prevents external mutation of the registry's internal state.

## Decorator Registration

**Decorator registration** is the primary mechanism for adding profiles to a registry. Instead of calling `registry.register(spec, cls)` imperatively, developers use the `@register` decorator on the class definition:

```python
register = DATABASES_REGISTRY.decorator()

@register
class PostgreSQLProfile(ConnectionProfile):
    __spec__ = POSTGRESQL_SPEC
```

The bare `@register` form (without arguments) is the canonical pattern as of version 26.5.0. The decorator reads `cls.__spec__` from the class body and calls `registry.register(spec, cls)` internally. This ensures that the spec and class are always in sync -- the spec declared on the class is exactly the spec registered in the registry.

The decorator returns the class unchanged, so the decorated class can be used normally after registration. The decoration has no effect on the class's behavior -- it only adds the class to the registry's lookup tables and sets `cls.__spec__` (for the deprecation-window mirror to `cls.__descriptor__`).

#### Diagram: Decorator Registration Flow

<iframe src="../../sims/decorator-registration-flow/main.html" width="100%" height="450px" scrolling="no"></iframe>
<details markdown="1">
<summary>Decorator Registration Flow</summary>
Type: workflow
**sim-id:** decorator-registration-flow<br/>
**Library:** vis-network<br/>
**Status:** Specified

A directed flow showing the `@register` decoration process: (1) Python evaluates class body (installs __spec__), (2) @register decorator invoked with the class, (3) decorator reads cls.__spec__, (4) type constraints validated (spec_type, profile_type), (5) duplicate check against _descriptors, (6) spec and class added to registry dictionaries, (7) class returned unchanged. Each step is clickable to show the data at that point. Error branches show what happens when type mismatch or duplicate is detected. Learning objective: Trace the registration lifecycle from class definition through decorator execution to registry storage (Bloom: Understand).
</details>

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

The factory also supports a deprecated with-argument form `@register(spec)` for backwards compatibility during the 26.5.x deprecation window. This form emits a `DeprecationWarning` and validates that the passed spec matches the class's `__spec__` if both are present. The disambiguation between the two forms is based on type: if the argument is a `type` (a class), it is the bare form; if it is a `ProfileSpec` instance, it is the deprecated with-argument form.

<!-- concept:75 -->
## Duplicate Prevention

**Duplicate prevention** ensures that no two profiles register under the same name in a single registry. The `register()` method checks `_descriptors` before adding a new entry:

```python
def register(self, spec: ProfileSpec, cls: type[Profile]) -> None:
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
```

The error message includes the fully qualified name of the class that already occupies the slot, making it easy to diagnose import-order conflicts where two modules both attempt to register under the same name. This is a common issue in plugin-style architectures where multiple packages contribute to the same registry.

Duplicate prevention applies per-registry. A name like `"postgresql"` can exist in both `DATABASES_REGISTRY` and `ANALYTICS_REGISTRY` without conflict, since they are separate Registry instances with independent namespaces.

!!! tip "Resolving duplicate registration errors"
    If you encounter a `ValueError` about duplicate registration, check whether the same module is being imported twice (common with relative vs absolute imports) or whether two specs accidentally share the same `name` field. The error message's module path helps identify the conflict source.

## Registry Iteration

**Registry iteration** is supported through the `descriptors` property and the `__len__` and `__contains__` dunder methods:

```python
# Check how many profiles are registered
print(len(DATABASES_REGISTRY))  # e.g., 5

# Iterate over all specs
for name, spec in DATABASES_REGISTRY.descriptors.items():
    print(f"{name}: {len(spec.parameters)} parameters")

# Check membership
if "postgresql" in DATABASES_REGISTRY:
    spec = DATABASES_REGISTRY.get_descriptor("postgresql")
```

The `descriptors` property returns a copy of the internal dictionary, which means iterating or modifying the returned dict does not affect the registry. The `__contains__` method checks `isinstance(name, str)` before lookup, ensuring that non-string values always return `False` rather than raising a `TypeError`.

<!-- concept:77 -->
## Registry Lookup By Name

**Registry lookup by name** is provided by two methods that mirror the two internal dictionaries:

- `get_descriptor(name)` -- returns the `ProfileSpec` for the given name
- `get_settings_class(name)` -- returns the `Profile` subclass for the given name

Both methods raise `KeyError` with a helpful message that lists all known names in the registry:

```python
def get_descriptor(self, name: str) -> ProfileSpec:
    try:
        return self._descriptors[name]
    except KeyError:
        known = ", ".join(sorted(self._descriptors)) or "<none>"
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

An interactive diagram showing a Registry instance with its two parallel dictionaries (_descriptors and _classes). Three sample profiles are registered (postgresql, mysql, redis). Clicking a profile name in either dictionary highlights the matching entry in the other dictionary and shows the spec details / class information in a side panel. The type constraint badges (spec_type, profile_type) are shown at the top with hover explanations. A search box allows filtering registered entries. Learning objective: Navigate the Registry's dual-dictionary structure and understand how specs and classes are co-indexed (Bloom: Understand).
</details>

<!-- concept:78 -->
<!-- concept:79 -->
## Descriptor Invariants

**Descriptor invariants** are a set of validation rules that every registered `ProfileSpec` must satisfy. They encode the naming conventions, uniqueness constraints, and structural requirements that the profile system relies on:

| Invariant | Rule | Failure Meaning |
|-----------|------|----------------|
| `test_name_matches_registry_key` | `spec.name == registry_key` | Spec name and registry key are out of sync |
| `test_name_lowercase_nonempty` | `spec.name` is lowercase and non-empty | Naming convention violated |
| `test_parameter_names_unique` | No duplicate names in `spec.parameters` | Ambiguous field definitions |
| `test_parameter_names_uppercase` | All parameter names are UPPERCASE and non-empty | Naming convention violated |
| `test_driver_keys_unique` | No duplicate `driver_key` values | Ambiguous driver kwargs |
| `test_parameter_tiers_valid` | All tiers are `"core"` or `"advanced"` | Invalid tier classification |
| `test_auth_modes_nonempty` | `spec.auth_modes` has at least one entry | Missing authentication declaration |
| `test_provider_type_not_none` | `spec.provider_type` is not None | Missing domain classification |

These invariants catch specification errors at test time, well before they could cause runtime failures. A typo in a parameter name, a forgotten auth mode declaration, or a missing provider type all produce clear test failures with descriptive messages.

## Invariant Test Generator

The **invariant test generator** is the `spec_invariants_for()` function that takes a Registry instance and returns a pytest class parameterized over every registered spec. This function is the primary integration point between the invariant system and a project's test suite:

```python
from mountainash_settings.profiles import spec_invariants_for
from my_package.settings import MY_REGISTRY

TestMyInvariants = spec_invariants_for(MY_REGISTRY)
```

This single line generates one test per invariant per registered spec. If the registry contains five profiles and there are eight invariants, the generated class produces forty parameterized test cases.

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

The class is dynamically renamed to `TestSpecInvariants_<registry_name>` so that pytest output clearly identifies which registry's invariants are running. New profile registrations automatically get full invariant coverage -- there is no need to write individual tests for each new backend.

#### Diagram: Invariant Test Coverage Matrix

<iframe src="../../sims/invariant-test-matrix/main.html" width="100%" height="450px" scrolling="no"></iframe>
<details markdown="1">
<summary>Invariant Test Coverage Matrix</summary>
Type: chart
**sim-id:** invariant-test-matrix<br/>
**Library:** Chart.js<br/>
**Status:** Specified

A heatmap-style matrix with invariant names as rows and registered profile names as columns. Each cell is green (pass), red (fail), or gray (not yet run). Clicking a cell shows the test assertion that passed or the error message that failed. Hovering over a row header shows the invariant's rule description. A "Run All" button animates the matrix filling in cell by cell. Users can add a "broken" spec via a form to see how invariant failures appear. Learning objective: Evaluate the completeness of invariant coverage across all registered profiles in a registry (Bloom: Evaluate).
</details>

## Putting It All Together

The registry and invariant systems work together to create a reliable, discoverable ecosystem of connection profiles. The full workflow from profile creation to validated deployment is:

1. **Define a ProfileSpec** with parameters, auth modes, and identity
2. **Create a Profile subclass** with `__spec__ = YOUR_SPEC`
3. **Register with `@register`** on the class definition
4. **Add `TestInvariants = spec_invariants_for(REGISTRY)`** to your test suite
5. **Look up at runtime** via `REGISTRY.get_settings_class("name")`

Each step in this workflow is supported by the framework with clear error messages and fail-fast behavior. Misspelled names produce `KeyError` with a list of known alternatives. Type constraint violations produce `TypeError` at registration time. Duplicate names produce `ValueError` with the conflicting class's location.

The test seam methods (`_snapshot_for_tests` and `_reset_for_tests`) allow test suites to register temporary profiles without permanently polluting the global registry, supporting isolated test scenarios.

## Key Takeaways

- **Registry Class** provides a mutable, name-keyed store with optional type constraints for both specs and profile classes.
- **Name Keyed Store** maintains two parallel dictionaries (specs and classes) indexed by the profile name string.
- **Decorator Registration** uses bare `@register` to read `cls.__spec__` and add the class to the registry in a single declaration.
- **Registry Decorator Factory** returns a bound decorator, enabling multiple independent registries with their own `@register` decorators.
- **Duplicate Prevention** raises `ValueError` with the conflicting class's module path when a name collision occurs.
- **Registry Iteration** provides read-only access via the `descriptors` property, `__len__`, and `__contains__`.
- **Registry Lookup By Name** raises `KeyError` with a list of known names when a lookup fails, aiding quick diagnosis of typos.
- **Invariant Test Generator** produces parameterized pytest classes that automatically cover every registered spec, ensuring new profiles get full validation for free.
