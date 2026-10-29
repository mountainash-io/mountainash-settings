---
title: Profile registry and invariants
description: The profile registry system covering the Registry class, name-keyed storage, decorator registration, duplicate prevention, lookup, spec invariants, and automated test generation.
generated_by: claude skill chapter-content-generator
date: 2026-06-03
version: 0.08
---

# Profile registry and invariants

A `Registry` collects profiles under unique names for one domain. You register a profile with a class decorator, look it up by name at runtime, and get a ready-made set of pytest checks for every registered spec with `spec_invariants_for()`.

---

## Why a registry

An application that supports several backends, such as PostgreSQL, MySQL, Redis or Snowflake, has a `Profile` subclass for each. A config file that says `backend: postgresql` needs to be resolved to the right settings class, and two modules must not claim the same name. A `Registry` does both. A `Profile` subclass can come from either declaration path described in [Connection profiles](../06-connection-profiles/index.md): an explicit `__spec__ = ProfileSpec(...)` or a native declaration whose spec is generated from its fields.

Registries are scoped to a domain. A database package has its own registry, a message broker package has another, and each has its own namespace and optional type constraints.

<!-- concept:71 -->
## Registry class

`Registry` is a mutable store that maps profile names to their specs and settings classes. The constructor takes a name, used in error messages and test IDs, and two optional type constraints:

```python
from mountainash_settings import Registry

DATABASES = Registry("databases")
```

`Registry` is generic over the spec and profile types, so a typed registry gives type checkers precise return types from `get_spec()` and `get_settings_class()`. Without constraints it accepts any `ProfileSpec` and `Profile`. With `spec_type` and `profile_type`, every registered spec must be an instance of `spec_type` (or a subclass) and every registered class must be a subclass of `profile_type`. A violation raises `TypeError` at registration time rather than at lookup, and the registry is left unchanged.

```python
from dataclasses import dataclass
from mountainash_settings import ParameterSpec, Profile, ProfileSpec, Registry

@dataclass(frozen=True, kw_only=True)
class BackendSpec(ProfileSpec):
    default_port: int | None = None

class ConnectionProfile(Profile):
    pass

REGISTRY = Registry("databases", spec_type=BackendSpec,
                    profile_type=ConnectionProfile)
register = REGISTRY.decorator()

SPEC = BackendSpec(
    name="postgresql", provider_type="postgresql", default_port=5432,
    parameters=[ParameterSpec(name="HOST", type=str, tier="core",
                              default="localhost", driver_key="host")],
)

@register
class PostgresProfile(ConnectionProfile):
    __spec__ = SPEC

print(REGISTRY.get_spec("postgresql").default_port)  # 5432

try:
    @register
    class Plain(Profile, name="redis", provider_type="redis"):
        HOST: str = "x"
except TypeError as e:
    print(e)  # Registry 'databases': spec_type mismatch
```

<!-- concept:72 -->
## Name keyed store

Entries are keyed by the `ProfileSpec.name` string, which is the identifier for every registration and lookup. The registry supports three access patterns:

- Registration: `register(spec, cls)`, or the decorator described below
- Lookup by name: `get_spec(name)` and `get_settings_class(name)`
- Containment and size: `name in registry` and `len(registry)`

The examples in the rest of this chapter register native profiles in a registry like this:

```python
from mountainash_settings import Profile, ProfileField, Registry

DATABASES = Registry("databases")
register = DATABASES.decorator()

@register
class PostgresProfile(Profile, name="postgresql", provider_type="postgresql",
                      driver_keys="lower"):
    HOST: str = "localhost"
    PORT: int = ProfileField(default=5432, ge=1, le=65535)
    DATABASE: str = "app"

@register
class RedisProfile(Profile, name="redis", provider_type="redis",
                   driver_keys="lower"):
    HOST: str = "localhost"

print("postgresql" in DATABASES, len(DATABASES))  # True 2
cls = DATABASES.get_settings_class("postgresql")
spec = DATABASES.get_spec("postgresql")
print(cls.__name__, spec.provider_type)  # PostgresProfile postgresql
```

`register(spec, cls)` validates before it stores anything, in this order:

1. `spec` must be a `ProfileSpec` and an instance of the registry's `spec_type`; otherwise `TypeError` (`spec_type mismatch`).
2. `cls` must be a `Profile` subclass and a subclass of the registry's `profile_type`; otherwise `TypeError` (`profile_type mismatch`).
3. `cls` must be a completed profile. An intermediate native declaration (no `name`) or one whose field types are still unresolved raises `TypeError`; call `model_rebuild()` first.
4. A natively declared profile must be registered with its own published spec (`spec is cls.__spec__`); otherwise `TypeError`.
5. The name must be free; otherwise `ValueError` (see [Duplicate prevention](#duplicate-prevention)).

After a successful registration `register()` also sets `cls.__spec__` to the registered spec.

<!-- concept:73 -->
## Decorator registration

Decorator registration is the usual way to add a profile. Instead of calling `registry.register(spec, cls)`, apply the `@register` decorator, obtained from `registry.decorator()`, to the class definition, as the examples above do. The explicit-spec path looks like this:

```python
from mountainash_settings import ParameterSpec, Profile, ProfileSpec, Registry

DATABASES = Registry("databases")
register = DATABASES.decorator()

POSTGRESQL_SPEC = ProfileSpec(
    name="postgresql",
    provider_type="postgresql",
    parameters=[ParameterSpec(name="HOST", type=str, tier="core",
                              default="localhost", driver_key="host")],
)

@register
class PostgreSQLProfile(Profile):
    __spec__ = POSTGRESQL_SPEC

print(DATABASES.get_settings_class("postgresql").__name__)  # PostgreSQLProfile
print(DATABASES.get_spec("postgresql") is POSTGRESQL_SPEC)  # True
```

The bare `@register` form, without arguments, is the only decorator form. The decorator reads the class's own `__spec__` and registers that spec with that class, so the spec on the class is always the spec in the registry.

The decorated class must be a `Profile` subclass with its own `__spec__`: either an explicit `ProfileSpec` set in the class body, or the spec generated for a completed native declaration. A spec inherited from a base class does not count. The decorator returns the class unchanged.

<!-- concept:74 -->
## Registry decorator factory

`decorator()` returns a `@register` decorator bound to one registry, so several registries can coexist, each with its own decorator:

```python
from mountainash_settings import Profile, Registry

DATABASES = Registry("databases")
BROKERS = Registry("brokers")
db_register = DATABASES.decorator()
mq_register = BROKERS.decorator()

@db_register
class PostgresProfile(Profile, name="postgresql", provider_type="postgresql"):
    HOST: str = "localhost"

@mq_register
class RabbitMQProfile(Profile, name="rabbitmq", provider_type="rabbitmq"):
    HOST: str = "localhost"

print(list(DATABASES.specs), list(BROKERS.specs))  # ['postgresql'] ['rabbitmq']
```

There is no with-argument form. Calling the decorator with a `ProfileSpec` instance, as in `@register(spec)`, raises `TypeError: Registration requires a Profile subclass`. The spec belongs in the class body as `__spec__`, or is generated from a native declaration.

<!-- concept:75 -->
## Duplicate prevention

No two profiles can register under the same name in one registry. A second registration raises `ValueError` that names the class already holding the name:

```python
try:
    @register
    class Other(Profile, name="postgresql", provider_type="postgresql"):
        HOST: str = "x"
except ValueError as e:
    print(e)
# Profile 'postgresql' is already registered in databases registry by __main__.PostgresProfile
```

The message includes the fully qualified name of the existing class, which makes import-order conflicts easy to diagnose. This is common in plugin-style setups where several packages contribute to one registry.

The check is per registry. A name like `"postgresql"` can exist in both a `databases` registry and an `analytics` registry, because they are separate `Registry` instances.

!!! tip "Resolving duplicate registration errors"
    If you get a `ValueError` about duplicate registration, check whether the same module is imported twice (common with relative and absolute imports) or whether two specs share the same `name`. The module path in the message points to the first registrant.

<!-- concept:76 -->
## Registry iteration

`len()`, `in` and the `specs` property cover inspection of a registry:

```python
print(len(DATABASES))                      # 2
for name, spec in DATABASES.specs.items():
    print(name, len(spec.parameters))      # postgresql 3, then redis 1
if "postgresql" in DATABASES:
    spec = DATABASES.get_spec("postgresql")
```

`specs` returns a copy of the registry's specs, so changing the returned dictionary does not affect the registry. `in` returns `False` for non-string values instead of raising.

<!-- concept:77 -->
## Registry lookup by name

Two methods look up an entry by name:

- `get_spec(name)` returns the `ProfileSpec`
- `get_settings_class(name)` returns the `Profile` subclass

Both raise `KeyError` for an unknown name, and the message lists the names that are registered:

```python
try:
    DATABASES.get_spec("postgresq")
except KeyError as e:
    print(e)
# "No profile registered under 'postgresq' in databases registry. Known: postgresql, redis"
```

The known-names hint makes a typo such as `"postgresq"` easy to spot in applications with many profiles.

<!-- concept:78 -->
## Spec invariants

Spec invariants are rules every registered `ProfileSpec` must satisfy. They cover naming conventions, uniqueness and structure:

| Invariant | Rule | Failure meaning |
|-----------|------|----------------|
| `test_name_matches_registry_key` | `spec.name == registry_key` | Spec name and registry key are out of sync |
| `test_name_lowercase_nonempty` | `spec.name` is lowercase and non-empty | Naming convention violated |
| `test_parameter_names_unique` | No duplicate names in `spec.parameters` | Ambiguous field definitions |
| `test_parameter_names_uppercase` | All parameter names are UPPERCASE and non-empty | Naming convention violated |
| `test_driver_keys_unique` | No duplicate output key within any one target: bare-string `driver_key` values must be unique and must not collide with any target's key; dict `driver_key` values must be unique per target | Ambiguous driver kwargs |
| `test_parameter_tiers_valid` | All tiers are `"core"` or `"advanced"` | Invalid tier classification |
| `test_provider_type_not_none` | `spec.provider_type` is not None | Missing domain classification |

A bare-string `driver_key` applies to every emission target and a dict `driver_key` applies per named target, so uniqueness is checked per target after resolving both forms. The same key under two different targets is not a collision. Two parameters that map to the same key for one target are.

These checks catch specification errors at test time: a typo in a parameter name, a duplicated driver key or a missing provider type each fail with a descriptive message. Authentication is not part of the spec (see [Authentication boundary](../08-authentication-system/index.md)), so there is no invariant for it.

<!-- concept:79 -->
## Invariant test generator

`spec_invariants_for(registry)` returns a pytest test class with every invariant above, parameterized over every spec in the registry. Assign it to a `Test...` name in a test module and pytest collects it:

```python
# tests/test_profile_invariants.py
from mountainash_settings import spec_invariants_for
from my_package.settings import MY_REGISTRY   # importing registers the profiles

TestMyInvariants = spec_invariants_for(MY_REGISTRY)
```

The class is named `TestSpecInvariants_<registry name>`, so pytest output shows which registry is running. For a registry holding one profile, it contains these tests, each run once per registered profile:

```text
test_driver_keys_unique
test_name_lowercase_nonempty
test_name_matches_registry_key
test_parameter_names_unique
test_parameter_names_uppercase
test_parameter_tiers_valid
test_provider_type_not_none
```

Adding a new backend needs no new test code. Profiles registered before the call are covered automatically.

The generator reads the registry's specs once, when `spec_invariants_for()` is called. Profiles registered after that are not covered, so call it after the modules that register profiles have been imported. The returned class carries the `unit` pytest mark, and `pytest` is imported only when you call the function, so `mountainash_settings` stays importable where pytest is not installed.

## Putting it all together

1. Define a `ProfileSpec` with an identity (`name`, `provider_type`) and parameters, or declare the profile natively and let the spec be generated.
2. Create a `Profile` subclass with `__spec__ = YOUR_SPEC` (explicit path) or a `name=`/`provider_type=` class header (native path).
3. Register it with `@register`.
4. Add `TestInvariants = spec_invariants_for(REGISTRY)` to your test suite, after the registering modules are imported.
5. Look the class up at runtime with `REGISTRY.get_settings_class("name")`.

Failures surface early. A misspelled name raises `KeyError` with the known names. A type constraint violation, a missing own `__spec__` or an incomplete profile raises `TypeError` at registration. A duplicate name raises `ValueError` with the conflicting class's location.
