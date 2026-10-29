---
title: Connection profiles
description: The connection profile system covering ProfileSpec, ParameterSpec, identity fields, type conventions, tiers, defaults, driver key mappings, secrets, transforms, validators, and dynamic field installation.
generated_by: claude skill chapter-content-generator
date: 2026-06-03
version: 0.08
---

# Connection profiles

A connection profile is a reusable, typed set of settings for one external system, paired with the rules that turn those settings into driver keyword arguments. You declare a profile on a `Profile` settings class, either by writing a `ProfileSpec` made of `ParameterSpec` entries or by declaring native Pydantic fields with `ProfileField`. `Profile.emit(target, base=...)` returns the kwargs for a driver. Authentication models are not part of this package; see [Authentication boundary](../08-authentication-system/index.md).

---

## Why profiles exist

Applications that connect to databases, message brokers, REST APIs or cloud services need the same kind of settings for each: host, port, credentials, SSL options. Those settings then have to be renamed and reshaped into the keyword arguments a driver library expects. Without profiles, each team writes its own settings class per backend and repeats the validation, the defaults and the name mapping.

A profile separates what a backend needs (the `ProfileSpec`) from the settings class that holds the values (`Profile`). One declaration gives you a validated, cached settings class that can emit driver kwargs. You can write the `ProfileSpec` yourself and attach it as `__spec__`, or declare native fields on a `Profile` subclass and let the package generate the spec (see [Native profile declarations](#native-profile-declarations)).

<!-- concept:56 -->
<!-- concept:57 -->
<!-- concept:59 -->
<!-- concept:69 -->
## ProfileSpec class

`ProfileSpec` is a frozen, keyword-only dataclass that describes a connection profile. Written explicitly, it is the blueprint a `Profile` class turns into fields. Generated from native fields, it is a descriptive record of them. It has four fields:

| Field | Type | Meaning |
|-------|------|---------|
| `name` | `str` | Short lowercase identifier, such as `"postgresql"` |
| `provider_type` | any value except `None` | Domain classification of the system |
| `parameters` | `list[ParameterSpec]` | The settings the profile declares |
| `metadata` | `dict` | Optional domain information, empty by default |

All fields are passed by keyword. The spec cannot be reassigned after construction: assigning to an attribute raises `FrozenInstanceError`. It is not deeply immutable, because `parameters` and `metadata` are ordinary mutable containers, so treat them as read-only. Authentication is not declared on the spec. Credentials are ordinary parameters, typically with `secret=True`.

This spec and profile cover a PostgreSQL connection. The sections that follow explain each option it uses.

```python
from mountainash_settings import MISSING, ParameterSpec, Profile, ProfileSpec

def validate_port(v: int) -> int:
    if not (1 <= v <= 65535):
        raise ValueError(f"Port must be 1-65535, got {v}")
    return v

POSTGRESQL_SPEC = ProfileSpec(
    name="postgresql",
    provider_type="postgresql",
    parameters=[
        ParameterSpec(name="HOST", type=str, tier="core",
                      default="localhost", driver_key="host"),
        ParameterSpec(name="PORT", type=int, tier="core",
                      default=5432, driver_key="port", validator=validate_port),
        ParameterSpec(name="DATABASE", type=str, tier="core",
                      default=MISSING, driver_key="database"),
        ParameterSpec(name="PASSWORD", type=str, tier="core",
                      default=MISSING, driver_key="password", secret=True),
        ParameterSpec(name="SSL_MODE", type=str, tier="advanced",
                      default="prefer", driver_key="sslmode"),
        ParameterSpec(name="CONNECT_TIMEOUT_S", type=int, tier="advanced",
                      default=10, driver_key="connect_timeout_ms",
                      transform=lambda s: s * 1000),
    ],
    metadata={"default_port": 5432},
)

class PostgreSQLProfile(Profile):
    __spec__ = POSTGRESQL_SPEC

pg = PostgreSQLProfile(HOST="db.example.com", DATABASE="myapp",
                       PASSWORD="example-password")
print(pg.profile_name, pg.provider_type)
# postgresql postgresql
print(pg.emit())
# {'host': 'db.example.com', 'port': 5432, 'database': 'myapp',
#  'password': 'example-password', 'sslmode': 'prefer', 'connect_timeout_ms': 10000}
```

## Spec identity

The spec identity is the pair `name` and `provider_type`. The `name` is the lookup key in a registry. It must be non-empty, lowercase and unique within the registry, and by convention it matches the system's package name or common abbreviation.

Identity is checked differently on the two declaration paths. For an explicit `ProfileSpec`, the spec invariants (see [Profile registry and invariants](../07-profile-registry-and-invariants/index.md)) check the name and provider type once the spec is registered. For a native declaration, the class header is checked when the `class` statement runs: `name` and `provider_type` must be given together, `provider_type` must not be `None`, and `name` must be a non-empty lowercase string. Otherwise the class definition raises `TypeError`.

<!-- concept:58 -->
## Provider type field

The provider type is a domain-specific value that categorises the profile. For database profiles it might be an enum such as `DatabaseType.POSTGRESQL`. For API profiles it might be a string such as `"rest_api"`. It is exposed as `ProfileSpec.provider_type` and `Profile.provider_type`.

The name identifies a profile within a registry. The provider type records the category the profile belongs to. The `Registry` has no query API over provider types, so a domain that wants to group profiles by category does that in its own code. The only requirement the package makes is that the value is not `None`.

| Field | Purpose | Example values |
|-------|---------|----------------|
| `name` | Unique registry key | `"postgresql"`, `"mysql"`, `"redis"` |
| `provider_type` | Domain classification | `DatabaseType.POSTGRESQL`, `"rest_api"` |

<!-- concept:60 -->
<!-- concept:61 -->
<!-- concept:62 -->
<!-- concept:63 -->
<!-- concept:66 -->
## ParameterSpec class

`ParameterSpec` is a frozen, keyword-only dataclass that declares one settings field of a profile. It maps one-to-one to a Pydantic field on the settings class and carries both the field's input side (type, default, validator, secret flag) and its output side (driver key, transform).

| Field | Default | Meaning |
|-------|---------|---------|
| `name` | required | UPPERCASE settings field name |
| `type` | required | Annotation Pydantic validates against |
| `tier` | required | `"core"` or `"advanced"` |
| `default` | `MISSING` | Value when no source provides one |
| `description` | `""` | Field description |
| `driver_key` | `None` | Output keyword name: a string, a per-target `dict`, or `None` |
| `secret` | `False` | Store the value as `SecretStr` |
| `transform` | `None` | Callable applied to the value on emission |
| `validator` | `None` | Callable run after Pydantic's own validation |
| `template` | `None` | Template string the profile resolves into the field at initialisation |

The explicit `ParameterSpec` list is the data-driven way to build profiles. In the native path, the same entries are generated from the class's fields (see [Native profile declarations](#native-profile-declarations)).

## Parameter name convention

`ParameterSpec.name` values are UPPERCASE with underscores, such as `"HOST"`, `"SSL_CERT"` or `"DATABASE_NAME"`. This matches Python constant naming, the usual form of environment variable names and the meta-field naming in `MountainAshBaseSettings`.

The spec invariants reject a spec with a non-uppercase parameter name. Names must also be non-empty and unique within a spec. In a native declaration, a lowercase application field name raises `TypeError` at class creation.

## Parameter Python type

`ParameterSpec.type` is the annotation of the generated field. It accepts anything Pydantic can validate:

- Primitive types: `str`, `int`, `float`, `bool`
- Optional types: `str | None`, `Optional[int]`
- Enum types
- Generic containers: `List[str]`, `Dict[str, Any]`
- Pydantic models

With `secret=True`, the field is typed as `SecretStr` whatever `type` says. Declare `type=str` for a password and set `secret=True`.

## Parameter tier

The tier marks a parameter as `"core"` or `"advanced"`. Core parameters are needed for basic connectivity: host, port, database name, credentials. Advanced parameters tune behaviour and have sensible defaults: SSL mode, timeouts, pool size.

The tier is documentation metadata. It does not change runtime behaviour, but the invariants check that each parameter declares a valid one, and tooling can use it to show core parameters first.

## Parameter default value

`ParameterSpec.default` is the value the field takes when no configuration source supplies one. A parameter with `default=5432` becomes a field with that default. A parameter with no sensible default uses the `MISSING` sentinel and becomes a required field. A third value, `FACTORY_DEFAULT`, appears only in generated specs (see [FACTORY_DEFAULT](#factory_default)).

<!-- concept:64 -->
## MISSING sentinel

`MISSING` is a singleton that marks a parameter as having no default, so a configuration source must provide it. Constructing the profile without the value raises a `ValidationError`:

```python
try:
    PostgreSQLProfile(PASSWORD="example-password")   # DATABASE is MISSING
except ValueError as exc:
    print(type(exc).__name__)
# ValidationError
```

`MISSING` is falsy, so use `param.default is MISSING` rather than a truthiness test when checking for it.

<!-- concept:65 -->
## Driver key mapping

`ParameterSpec.driver_key` names the keyword argument a driver expects for a settings field. Settings fields are UPPERCASE (`HOST`, `SSL_CERT`) while drivers expect names like `host` or `sslcert`. The value takes one of three forms:

- A string maps the field to that key for every emission target.
- A `dict` maps it per target, such as `{"driver": "host", "url": "hostname"}`. A target with no entry skips the field.
- `None` leaves the field out of the output.

Use `None` for parameters that need more than a 1:1 rename. An adapter function handles those cases (see [Target-aware emission](#target-aware-emission)).

```python
print(pg.emit())
# 'sslmode' comes from SSL_MODE, 'database' from DATABASE, and so on.
# {'host': 'db.example.com', 'port': 5432, 'database': 'myapp',
#  'password': 'example-password', 'sslmode': 'prefer', 'connect_timeout_ms': 10000}
```

Fields whose value is `None` are omitted from the output.

## Secret parameter flag

`ParameterSpec.secret=True` makes the field a `SecretStr`. Pydantic wraps incoming values, `repr` masks them, and `emit()` unwraps them with `get_secret_value()` when it builds the kwargs.

```python
print(pg.PASSWORD)
# **********
print(pg.emit()["password"])
# example-password
```

Because the unwrapping happens at the output boundary, emitted kwargs contain plaintext credentials (see [Target-aware emission](#target-aware-emission)). In a native declaration the flag is derived: a field annotated with `SecretStr`, including inside `Annotated` or a union, projects to `secret=True`.

<!-- concept:67 -->
<!-- concept:68 -->
## Transform function

`ParameterSpec.transform` is an optional callable applied to the value on emission. It converts the settings-facing value into the form the driver expects. In the example above, `CONNECT_TIMEOUT_S=10` is emitted as `connect_timeout_ms=10000`.

Transforms run after `SecretStr` unwrapping and before the value goes into the output dict. Typical uses are unit conversions (seconds to milliseconds), type conversions (bool to dict) and format conversions (path string to SSL context).

## Validator function

`ParameterSpec.validator` is an optional callable that Pydantic runs after its own type coercion. It receives the typed value and returns it, or raises `ValueError` to reject it. In the example above, `validate_port` rejects ports outside 1-65535:

```python
try:
    PostgreSQLProfile(DATABASE="myapp", PASSWORD="example-password", PORT=70000)
except ValueError as exc:
    print(type(exc).__name__)
# ValidationError
```

## Profile class

`Profile` subclasses `MountainAshBaseSettings`, so a profile accepts keyword arguments, configuration files, environment variables and the rest of the base settings machinery. A subclass declares its profile one of two ways:

- Set `__spec__` in the class body (explicit path). The class gets a field for each `ParameterSpec`.
- Use a class header and native fields (generated path). The package builds `__spec__` from the fields once the class is complete.

Target-specific `__adapters__` shape the output of `emit(target)`.

A profile exposes `profile_name` (the spec's `name`) and `provider_type`, resolves template fields from the spec, and provides `emit(target, base=...)`.

<!-- concept:70 -->
## Dynamic field installation

For an explicit `__spec__`, the `Profile` class creates its fields when the `class` statement runs, not when an instance is created. After the class definition, each `ParameterSpec` is an ordinary Pydantic field:

```python
print(list(PostgreSQLProfile.model_fields)[-6:])
# ['HOST', 'PORT', 'DATABASE', 'PASSWORD', 'SSL_MODE', 'CONNECT_TIMEOUT_S']
print(PostgreSQLProfile.model_fields["PASSWORD"].annotation)
# <class 'pydantic.types.SecretStr'>
```

The field's annotation is `SecretStr` for secret parameters, and is wrapped with the validator for parameters that declare one. A `MISSING` default makes the field required. The parameter's driver key, tier, transform and template travel with the field and are used by `emit()`.

A parameter whose default is `FACTORY_DEFAULT` cannot be installed from an explicit spec. It raises `TypeError`. Native declarations do not use this path, because their fields already exist and the spec is derived from them.

<!-- concept:112 -->
## Native profile declarations

A native profile declaration describes the profile with ordinary Pydantic fields on a `Profile` subclass instead of a hand-written `ProfileSpec`. The package reads the fields and generates the spec, so the class is the single source of truth for validation, defaults and emission.

- Class header: `class X(Profile, name=..., provider_type=...)` supplies identity. Optional header options are `driver_keys="lower"` (default each field's driver key to its lowercase name), `spec_type` (a `ProfileSpec` subclass whose extra dataclass fields become accepted header options) and `metadata`. Unknown header options raise `TypeError`.
- `ProfileField`: a wrapper around Pydantic's `Field` that adds `driver_key`, `tier`, `transform` and `template`. Every other keyword (`ge`, `le`, `description`, `default_factory`, and so on) goes to Pydantic's `Field`. If you omit `driver_key`, the class convention applies: the lowercase name with `driver_keys="lower"`, otherwise no mapping. An explicit `driver_key=None` excludes the field, and a `dict` scopes the key per target. `tier` defaults to `"core"`.
- Projection: each uppercase application field becomes a `ParameterSpec`. Fields inherited from `MountainAshBaseSettings` are skipped and may not carry `ProfileField` options. A lowercase application field name, duplicate output keys, or more than one `ProfileField` marker on a field raises `TypeError`.

Here is the same PostgreSQL profile declared natively, created from keyword arguments and from a configuration file:

```python
import tempfile
from pathlib import Path
from pydantic import SecretStr
from mountainash_settings import Profile, ProfileField

class NativePG(Profile, name="postgresql", provider_type="postgresql",
               driver_keys="lower", metadata={"default_port": 5432}):
    HOST: str = "localhost"
    PORT: int = ProfileField(default=5432, ge=1, le=65535)
    DATABASE: str
    PASSWORD: SecretStr
    SSL_MODE: str = ProfileField(default="prefer", tier="advanced", driver_key="sslmode")
    LOCAL_NOTE: str | None = ProfileField(default=None, driver_key=None)

# From keyword arguments
pg = NativePG(DATABASE="myapp", PASSWORD="example-password")
print(pg.emit())
# {'host': 'localhost', 'port': 5432, 'database': 'myapp',
#  'password': 'example-password', 'sslmode': 'prefer'}

# From a configuration file, with a keyword override
with tempfile.TemporaryDirectory() as d:
    cfg = Path(d) / "pg.yaml"
    cfg.write_text("HOST: db.example.com\nDATABASE: reports\nPASSWORD: from-file\n")
    pg2 = NativePG(config_files=str(cfg), PORT=6432)
    print(pg2.emit())
# {'host': 'db.example.com', 'port': 6432, 'database': 'reports',
#  'password': 'from-file', 'sslmode': 'prefer'}

# The generated spec
spec = NativePG.__spec__
print(spec.name, spec.metadata)
# postgresql {'default_port': 5432}
print([(p.name, p.tier, p.driver_key, p.secret) for p in spec.parameters])
# [('HOST', 'core', 'host', False), ('PORT', 'core', 'port', False),
#  ('DATABASE', 'core', 'database', False), ('PASSWORD', 'core', 'password', True),
#  ('SSL_MODE', 'advanced', 'sslmode', False), ('LOCAL_NOTE', 'core', None, False)]
```

Compared with the explicit path, a native declaration needs no `ParameterSpec` list and uses Pydantic's own constraints, aliases and validators directly. The explicit `ProfileSpec` is plain data that you can build, inspect or register without writing a class body. The two cannot be mixed on one class: setting `__spec__` in the body of a class that has a native declaration raises `TypeError`. A generated `__spec__` describes the fields but cannot reconstruct factories, aliases or decorator validators, which stay on the class.

### FACTORY_DEFAULT

`FACTORY_DEFAULT` is a singleton, like `MISSING`. A generated spec records it as the default of a field declared with `default_factory`. It means the field has a default produced by a factory on the owning class, without storing the callable. Required fields project to `MISSING`, fields with a literal default project to that value, and factory fields project to `FACTORY_DEFAULT`.

```python
from pydantic import Field
from mountainash_settings import Profile

class P(Profile, name="p", provider_type="p"):
    A: int
    B: int = 3
    C: list[str] = Field(default_factory=list)

print({p.name: p.default for p in P.__spec__.parameters})
# {'A': MISSING, 'B': 3, 'C': FACTORY_DEFAULT}
```

It cannot be used in an explicit spec. Installing such a parameter raises `TypeError` and tells you to declare the factory on the class.

### Delayed types and model_rebuild

The spec is published only when the Pydantic model is complete. If a field annotation refers to a type that does not exist yet, the class stays incomplete: `__spec__` is `None` and instantiating it raises `TypeError`. Call `model_rebuild()` after defining the type to complete the model and publish the spec.

```python
class Late(Profile, name="late", provider_type="late"):
    X: "Later"

print(Late.__spec__)
# None
try:
    Late(X=1)
except TypeError as exc:
    print(exc)
# Late: incomplete profile; call model_rebuild() after defining referenced types

class Later(int): ...

Late.model_rebuild()
print(Late.__spec__.name, Late(X=Later(1)).X)
# late 1
```

A completed declaration is immutable, so further rebuilds keep the same spec. A class with no `name` (an intermediate base class) cannot be instantiated either. Declare `name` and `provider_type` on a concrete subclass.

<!-- concept:113 -->
## Target-aware emission

`Profile.emit(target, base=...)` turns a profile instance into the keyword arguments for one consumer, such as a driver, a URL builder or an SDK client. One profile can serve several consumers because both parts of emission are scoped by target:

1. A field's `driver_key` may be a `dict` mapping each target to its output key. A bare string applies to every target.
2. The class variable `__adapters__` maps a target to a callable `adapter(profile, kwargs) -> dict`. The adapter receives the profile and the already-merged kwargs and returns the final dict.

Targets are any hashable value. `base` supplies caller kwargs that the profile output is layered over, and profile values win on key collisions. `emit()` takes only a shallow copy of `base`, so an adapter that changes a nested container must copy it first.

```python
from pydantic import SecretStr
from mountainash_settings import Profile, ProfileField

def connection_options(profile, kwargs):
    return {**kwargs, "timeout": profile.TIMEOUT}

class Multi(Profile, name="multi", provider_type="multi"):
    HOST: str = ProfileField(driver_key={"driver": "host", "url": "hostname"})
    PASSWORD: SecretStr = ProfileField(driver_key={"driver": "password"})
    TIMEOUT: int = ProfileField(default=5, driver_key=None)
    __adapters__ = {"driver": connection_options}

m = Multi(HOST="db.example.com", PASSWORD="example-password")
base = {"app": "reports"}
print(m.emit("driver", base=base))
# {'app': 'reports', 'host': 'db.example.com', 'password': 'example-password', 'timeout': 5}
print(m.emit("url"))
# {'hostname': 'db.example.com'}
print(base)
# {'app': 'reports'}
```

### Fail-closed targeting

A profile is target-scoped when any field uses a `dict` driver key or the class defines `__adapters__`. On a target-scoped profile, `emit()` with no target raises `ValueError`, and so does a target the profile does not know. The known targets are the adapter keys plus every key of every `dict` driver key. An explicit `None` is accepted only if `None` is itself a known target. This stops a profile from silently emitting an empty or partial dict. A profile with only bare-string driver keys and no adapters is not target-scoped, and `emit()` with no argument returns the merged kwargs.

```python
for args in [(), ("other",), (None,)]:
    try:
        m.emit(*args)
    except ValueError as exc:
        print(exc)
# Multi is target-scoped; call emit(<target>).
# Multi has no emission for target 'other'; known: ['driver', 'url'].
# Multi has no emission for target None; known: ['driver', 'url'].
```

### Secrets at emission

`SecretStr` values are unwrapped while kwargs are built, before any `transform` runs, so the emitted dict and an adapter's input hold plaintext. Do not log emitted kwargs, include them in error messages or persist them. The instance still masks the value in `repr`. Authentication models and credential rendering for specific clients belong to the auth-client package. `emit()` with `base` and `__adapters__` is the integration point (see [Authentication boundary](../08-authentication-system/index.md)).
