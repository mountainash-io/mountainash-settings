# The ProfileSpec Pattern: Why and When

The quickstart shows `Profile` + `ProfileSpec` used to define a connection profile. This guide explains the design rationale — what you gain over a plain `MountainAshBaseSettings` subclass, and when the extra structure is worth it.

## The plain subclass approach

When you need settings for a single connection type, a direct subclass is the simplest thing that works:

```python
from pydantic import Field, SecretStr
from mountainash_settings import MountainAshBaseSettings

class PostgreSQLSettings(MountainAshBaseSettings):
    HOST: str = Field(default=...)
    PORT: int = Field(default=5432)
    DATABASE: str = Field(default=...)
    USERNAME: str = Field(default=...)
    PASSWORD: SecretStr = Field(default=...)
```

This is fine for one profile in one application. The friction starts when you have many.

## What the ProfileSpec pattern adds

### 1. The spec is inspectable data, not just code

A `ProfileSpec` is a frozen dataclass — it's a value you can pass around, iterate over, and query programmatically, independently of any settings instance. Each `ParameterSpec` carries metadata that a plain pydantic field cannot express:

| `ParameterSpec` attribute | What it holds |
|---|---|
| `driver_key` | The kwarg name the underlying driver expects (e.g. `"dbname"` not `"DATABASE"`) |
| `tier` | `"core"` or `"advanced"` — audit-style severity for documentation and schema generation |
| `secret` | Whether to wrap as `SecretStr` and unwrap at the kwargs boundary |
| `transform` | A callable applied to the value when emitting driver kwargs |
| `validator` | A pydantic-compatible field-level validator |
| `template` | A `{FIELD_NAME}` template string for auto-derived fields |

None of these exist in a plain pydantic `FieldInfo`. With a direct subclass you can define all the behaviour, but it is scattered across field annotations, validators, and `post_init()` methods with no single place to introspect it.

With a spec, you can query the shape of a profile without constructing an instance:

```python
for spec in POSTGRESQL_SPEC.parameters:
    if spec.secret:
        print(f"  {spec.name} is a secret (driver key: {spec.driver_key})")
```

### 2. Field installation happens once, not per subclass

With a direct subclass, every profile you write re-declares its fields. Twelve database profiles means twelve copies of `HOST`, `PORT`, `DATABASE`, each with slightly different types or defaults — and it's easy for them to drift.

`Profile.__pydantic_init_subclass__` reads the `__spec__` at class-creation time and installs pydantic fields automatically. The spec is the single source of truth. If `POSTGRESQL_SPEC` says `PORT` defaults to `5432`, every subclass pointing at it gets that default — you cannot accidentally override it in the wrong place.

```python
# The spec is declared once
POSTGRESQL_SPEC = ProfileSpec(
    name="postgresql",
    provider_type="postgresql",
    parameters=[
        ParameterSpec(name="HOST",     type=str, tier="core", driver_key="host"),
        ParameterSpec(name="PORT",     type=int, tier="core", driver_key="port", default=5432),
        ParameterSpec(name="DATABASE", type=str, tier="core", driver_key="dbname"),
    ],
    auth_modes=[NoAuth, PasswordAuth],
)

# The class declares nothing — fields come from the spec
class PostgreSQLSettings(Profile):
    __spec__ = POSTGRESQL_SPEC
```

### 3. The auth union is assembled automatically

A connection profile typically accepts more than one auth mode, and the valid modes are part of the profile's definition — not every auth mode makes sense for every backend.

With a direct subclass you would define this yourself:

```python
# Manual discriminated union — boilerplate per class
class PostgreSQLSettings(MountainAshBaseSettings):
    auth: Union[NoAuth, PasswordAuth] = Field(discriminator="kind")
```

The spec declares `auth_modes=[NoAuth, PasswordAuth]`, and `Profile` assembles the discriminated union field automatically. Add a new valid auth mode to the spec; all subclasses pick it up. Remove one; it is rejected at validation time for every profile pointing at that spec.

### 4. The `_default_kwargs()` method handles the naming mismatch

Settings field names follow Python conventions (uppercase, SETTINGS_STYLE). Driver kwargs follow the driver's conventions (usually lowercase, sometimes camelCase). Without help, you write a mapping manually for every profile:

```python
# Manual mapping — repeated in every settings class
def to_driver_kwargs(self) -> dict:
    return {
        "host": self.HOST,
        "port": self.PORT,
        "dbname": self.DATABASE,
        "password": self.PASSWORD.get_secret_value(),
    }
```

`Profile._default_kwargs()` generates this mapping from `ParameterSpec.driver_key` automatically. It also handles:

- **SecretStr unwrapping** — `spec.secret=True` fields are unwrapped via `.get_secret_value()` before emission
- **None skipping** — optional fields that were not set are omitted from the output dict
- **Transform application** — if `spec.transform` is set, it is called on the value before the kwarg is written

```python
settings = PostgreSQLSettings(HOST="db.example.com", DATABASE="myapp", auth=NoAuth())
settings._default_kwargs()
# {"host": "db.example.com", "port": 5432, "dbname": "myapp"}
# PORT used its default; PASSWORD was None so it was skipped
```

### 5. A Registry enables dynamic lookup by name

When the connection type is determined at runtime (e.g. read from a config file, dispatched from a string), a plain subclass gives you nothing to look up against. You end up maintaining your own `dict[str, type]` manually.

`Registry` is that dict, with duplicate protection and descriptive `KeyError` messages:

```python
DATABASES = Registry("databases")
register = DATABASES.decorator()

@register
class PostgreSQLSettings(Profile): ...

@register
class RedshiftSettings(Profile): ...

# Runtime dispatch from a string — no manual mapping needed
backend = config["backend"]                          # e.g. "postgresql"
spec = DATABASES.get_descriptor(backend)
cls = DATABASES.get_settings_class(backend)
settings = cls(HOST=..., DATABASE=..., auth=...)
```

This pattern is the foundation for packages like `mountainash-data` that let callers configure any supported backend from a config file.

### 6. Every new registration gets invariant tests for free

With direct subclasses, testing that every profile satisfies the same structural rules requires either duplication (one test per class) or a manually maintained parametrised test.

`spec_invariants_for(REGISTRY)` returns a pytest class parametrised over every spec in the registry. Add a new profile; it is automatically covered. The invariants check things that are easy to get wrong — parameter names in the wrong case, duplicate `driver_key` values, empty `auth_modes`, missing `provider_type`.

```python
# tests/unit/test_database_profiles.py

from mountainash_settings import spec_invariants_for
from my_package.db.settings import DATABASES

TestDatabaseInvariants = spec_invariants_for(DATABASES)
# That's it. Every spec in DATABASES is now tested.
```

## When to use each approach

| Situation | Use |
|---|---|
| One-off settings class for your own application | Plain `MountainAshBaseSettings` subclass |
| Several connection types in the same domain that must be lookable by name | `ProfileSpec` + `Registry` |
| You need to emit driver kwargs with field renaming, SecretStr unwrapping, or value transforms | `Profile` (`_default_kwargs()`) |
| You want to introspect profile structure programmatically (schema generation, documentation, audit) | `ProfileSpec` — it's just data |
| You're building a library where downstream code registers profiles you don't control | `Registry` + `spec_invariants_for()` |
| The valid auth modes differ between backends | `ProfileSpec.auth_modes` discriminated union assembly |

## What you give up

The pattern is not free. Compared to a plain subclass:

- **More indirection** — fields are installed at class-creation time via `__pydantic_init_subclass__`, which is invisible to a reader who just looks at the class body. IDE "go to definition" on a field like `HOST` will not lead anywhere useful — the field comes from `__spec__`, not the class body.
- **Dynamic field installation is pydantic-version-sensitive** — it mutates `model_fields` and calls `model_rebuild(force=True)`, which is not officially documented by pydantic and may need adjustment on major pydantic upgrades.
- **Slightly more ceremony to set up** — you need a `ProfileSpec`, at least one `ParameterSpec` per field, a `Registry`, and a `Profile` subclass, before you have a working settings class.

For a single application-specific settings class, none of this is worth it. For a library or any code where you manage more than two or three similar profiles, the structural guarantees pay for themselves quickly.

## Extending emission

`emit()` targets are any `Hashable`, so other domains can add their own. The
sanctioned mechanism is the **inline** per-target adapter map declared on the
profile class:

```python
class PasswordAuthProfile(Profile):
    __spec__ = ...
    __adapters__ = {MyTarget.POSTGRES: _postgres}


def _postgres(auth, base):
    return {**base, "user": auth.USERNAME,
            "password": auth.PASSWORD.get_secret_value()}
```

Each adapter has the 2-arg compose signature `(profile, merged) -> dict`;
`instance.emit(target, base=...)` routes through the entry for `target`. Use a
package-namespaced target type (an `Enum` / frozen dataclass), never bare
strings.

A consumer that needs to extend emission for a profile it does not own builds a
**consumer-owned** dispatch table (`(provider_type, auth_class) -> fn`) and reads
the credential's data directly, rather than mutating a class it imports — see
`mountainash-auth-client/a.architecture/credentials-are-rendered-by-the-consumer.md`.
