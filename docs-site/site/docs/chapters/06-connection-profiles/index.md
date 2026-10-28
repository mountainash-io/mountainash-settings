---
title: Connection Profiles
description: The connection profile system covering ProfileSpec, ParameterSpec, identity fields, type conventions, tiers, defaults, driver key mappings, secrets, transforms, validators, and dynamic field installation.
generated_by: claude skill chapter-content-generator
date: 2026-06-03
version: 0.08
---

# Connection Profiles

A connection profile is a reusable, typed set of settings for one external system, paired with the rules that turn those settings into driver keyword arguments. A profile is described by a `ProfileSpec` holding `ParameterSpec` entries and is realised as a `Profile` settings class, either from an explicit spec or from native Pydantic fields on the class itself. Parameters carry a name, Python type, tier, default, driver-key mapping, secret flag, transform and validator. `Profile.emit(target, base=...)` produces the kwargs for a driver. Authentication models are not part of this package; see [Authentication Boundary](../08-authentication-system/index.md).

---

## Why Profiles Exist

Applications that connect to external systems -- databases, message brokers, REST APIs, cloud services -- share a common pattern: they need a set of typed parameters (host, port, credentials, SSL settings) that translate into connection kwargs for a driver library. Without profiles, every team writes its own settings class for each backend, duplicating validation logic, default values, and the mapping between settings names and driver parameter names.

The profile system solves this by separating _what_ a backend needs (described by a `ProfileSpec`) from _how_ that translates into a Pydantic settings class (implemented by the `Profile` base class). A single declaration produces a validated, cached, template-aware settings class with zero boilerplate. A profile can be declared in two ways: by writing the `ProfileSpec` explicitly and attaching it as `__spec__`, or by declaring native Pydantic fields on a `Profile` subclass and letting the package generate the spec (see [Native Profile Declarations](#native-profile-declarations)).

<!-- concept:56 -->
<!-- concept:57 -->
<!-- concept:59 -->
<!-- concept:69 -->
## ProfileSpec Class

**ProfileSpec** is a frozen dataclass specifying a connection profile. It is the blueprint from which a `Profile` settings class installs its Pydantic fields when the spec is written explicitly, and the descriptive record the package generates when the profile is declared with native fields. The former descriptor alias is removed in 0.1.0.

```python
@dataclass(frozen=True, kw_only=True)
class ProfileSpec:
    name: str
    provider_type: Any
    parameters: list[ParameterSpec]
    metadata: dict[str, Any] = field(default_factory=dict)
```

The spec cannot be reassigned after construction (`frozen=True`; assigning to an attribute raises `FrozenInstanceError`). Frozen is not deeply immutable: `parameters` and `metadata` are ordinary mutable containers, so treat them as read-only after construction. The `kw_only=True` constraint ensures that all fields must be passed as keyword arguments during construction, improving readability at the call site.

A complete spec declares the profile's identity (`name`, `provider_type`), its parameters (as a list of `ParameterSpec` instances), and optional metadata for domain-specific information. Authentication is not declared on the spec; credentials are ordinary parameters (typically `secret=True`) and authentication models belong to the separate auth-client package (see [Authentication Boundary](../08-authentication-system/index.md)):

```python
POSTGRESQL_SPEC = ProfileSpec(
    name="postgresql",
    provider_type=DatabaseType.POSTGRESQL,
    parameters=[
        ParameterSpec(name="HOST", type=str, tier="core",
                      default="localhost", driver_key="host"),
        ParameterSpec(name="PORT", type=int, tier="core",
                      default=5432, driver_key="port"),
        ParameterSpec(name="DATABASE", type=str, tier="core",
                      default=MISSING, driver_key="database"),
        ParameterSpec(name="PASSWORD", type=str, tier="core",
                      default=MISSING, driver_key="password", secret=True),
        ParameterSpec(name="SSL_MODE", type=str, tier="advanced",
                      default="prefer", driver_key="sslmode"),
    ],
    metadata={"default_port": 5432, "url_scheme": "postgresql"},
)
```

## Spec Identity

The **spec identity** consists of two fields that identify what system a profile connects to:

- `name` -- a short, lowercase string identifier (e.g., `"postgresql"`, `"redis"`, `"snowflake"`)
- `provider_type` -- a domain-specific classification of the system (see below)

The `name` field is the primary lookup key in the registry system. It must be unique within a given registry, lowercase, and non-empty. Conventionally, names match the system's package name or common abbreviation.

Identity is enforced differently on the two declaration paths. For an explicit `ProfileSpec`, the spec invariants (see [Profile Registry and Invariants](../07-profile-registry-and-invariants/index.md)) check the name and provider type once the spec is registered. For a generated declaration, the class header is checked when the class statement runs: `name` and `provider_type` must be given together, `provider_type` must not be `None`, and `name` must be a non-empty lowercase string; otherwise the class definition raises `TypeError`.

<!-- concept:58 -->
## Provider Type Field

The **provider type field** is a domain-specific value that categorizes the profile within its domain. For database profiles, this might be an enum like `DatabaseType.POSTGRESQL`. For API profiles, it might be a string like `"rest_api"` or an enum member.

The provider type is domain metadata: a secondary classification beyond the name. While the name uniquely identifies a profile within a registry, the provider type records the category the profile belongs to and is exposed as `ProfileSpec.provider_type` and `Profile.provider_type`. The `Registry` has no query API over provider types; a domain that wants to group profiles by category does so in its own code. The only package-level requirement is that it is not `None`.

| Field | Purpose | Example Values |
|-------|---------|----------------|
| `name` | Unique registry key | `"postgresql"`, `"mysql"`, `"redis"` |
| `provider_type` | Domain classification | `DatabaseType.POSTGRESQL`, `"rest_api"` |

<!-- concept:60 -->
<!-- concept:61 -->
<!-- concept:62 -->
<!-- concept:63 -->
<!-- concept:66 -->
## ParameterSpec Class

The **ParameterSpec** class is a frozen dataclass that declares a single settings field within a profile. It captures everything needed to generate a Pydantic `FieldInfo`, wire up validation, configure secret handling, and map the field to a driver keyword argument:

```python
@dataclass(frozen=True, kw_only=True)
class ParameterSpec:
    name: str
    type: Any
    tier: Literal["core", "advanced"]
    default: Any = MISSING
    description: str = ""
    driver_key: str | dict[Hashable, str] | None = field(default=None, hash=False)  # excluded from the hash so dict-scoped specs stay hashable
    secret: bool = False
    transform: Callable[[Any], Any] | None = None
    validator: Callable[[Any], Any] | None = None
    template: str | None = None
```

Each `ParameterSpec` maps one-to-one to a Pydantic field on the settings class. The spec contains both the field's type information (for Pydantic) and its output mapping (for the driver kwargs). This dual role is what makes the profile system powerful -- a single declaration handles both input validation and output transformation. In the explicit-spec path the `ParameterSpec` list is the declaration and is the data-driven way to build profiles; in the native path the same `ParameterSpec` entries are generated from the class's fields (see [Native Profile Declarations](#native-profile-declarations)).

#### Diagram: ParameterSpec Field Mapping

<iframe src="../../sims/parameter-spec-mapping/main.html" width="100%" height="500px" scrolling="no"></iframe>
<details markdown="1">
<summary>ParameterSpec Field Mapping</summary>
Type: diagram
**sim-id:** parameter-spec-mapping<br/>
**Library:** vis-network<br/>
**Status:** Specified

A two-column diagram showing the mapping from ParameterSpec attributes (left column) to their effects on the generated Pydantic field and driver kwargs (right column). Lines connect each ParameterSpec attribute to its downstream effects: name -> field name, type -> annotation, default -> FieldInfo default, secret -> SecretStr wrapping, driver_key -> output kwargs key, validator -> AfterValidator, transform -> kwargs emit transform. Clicking each attribute shows a code example. A toggle switches between "input view" (how config values enter) and "output view" (how kwargs are emitted).
</details>

## Parameter Name Convention

The **parameter name convention** requires that all `ParameterSpec.name` values use UPPERCASE with underscores (e.g., `"HOST"`, `"SSL_CERT"`, `"DATABASE_NAME"`). This convention aligns with:

- Python constant naming conventions
- Environment variable naming conventions (which are traditionally uppercase)
- The existing MountainAshBaseSettings meta-field naming pattern

The invariant system enforces this convention: any spec with a non-uppercase parameter name will fail the `test_parameter_names_uppercase` invariant check. Names must also be non-empty and unique within a single spec (no two parameters share the same name).

## Parameter Python Type

The **parameter Python type** (`ParameterSpec.type`) declares the Pydantic annotation for the generated field. It accepts any type that Pydantic can validate against:

- Primitive types: `str`, `int`, `float`, `bool`
- Optional types: `str | None`, `Optional[int]`
- Enum types: `SSLMode`, `AuthMethod`
- Complex types: `List[str]`, `Dict[str, Any]`
- Pydantic models: nested `BaseModel` subclasses

When `secret=True`, the type is automatically wrapped as `SecretStr` during field installation, regardless of what `type` declares. This means you declare `type=str` for a password field and set `secret=True` -- the framework handles the `SecretStr` wrapping.

## Parameter Tier

The **parameter tier** classifies each parameter as either `"core"` or `"advanced"`:

- **Core** parameters are essential for basic connectivity (host, port, database name, credentials)
- **Advanced** parameters tune behavior but have sensible defaults (SSL mode, connection timeout, pool size)

The tier serves documentation and audit purposes. It does not affect runtime behavior directly, but the invariant system validates that every parameter declares a valid tier. Tooling can use tiers to generate progressive documentation -- showing core parameters first, then revealing advanced parameters on demand.

## Parameter Default Value

The **parameter default value** (`ParameterSpec.default`) specifies what value the field receives when no configuration source provides it. When a default is set, the generated Pydantic `FieldInfo` uses `Field(default=value)`:

```python
ParameterSpec(name="PORT", type=int, tier="core", default=5432)
# Generates: PORT: int = Field(default=5432)
```

If no default is appropriate (the parameter is required), the special `MISSING` sentinel is used instead. A third value, `FACTORY_DEFAULT`, appears only in generated specs (see [FACTORY_DEFAULT](#factory_default)).

<!-- concept:64 -->
## MISSING Sentinel

The **MISSING sentinel** is a singleton object that indicates a parameter has no default value -- it must be explicitly provided by some configuration source. When `ParameterSpec.default` is `MISSING`, the generated field uses `Field(default=...)` (Pydantic's ellipsis marker for required fields):

```python
class Missing:
    _instance: ClassVar[Missing | None] = None

    def __new__(cls) -> Missing:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "MISSING"

    def __bool__(self) -> bool:
        return False

MISSING: Missing = Missing()
```

The singleton pattern ensures that identity checks (`param.default is MISSING`) work correctly. The `__bool__` returning `False` means `MISSING` is falsy, which is useful in conditional expressions but requires care -- use `is MISSING` for explicit sentinel checks rather than truthiness tests.

```python
# Required parameter -- must be provided
ParameterSpec(name="DATABASE", type=str, tier="core", default=MISSING)
# Generates: DATABASE: str = Field(default=...)

# Optional parameter -- has a default
ParameterSpec(name="PORT", type=int, tier="core", default=5432)
# Generates: PORT: int = Field(default=5432)
```

<!-- concept:65 -->
## Driver Key Mapping

The **driver key mapping** (`ParameterSpec.driver_key`) defines how a settings field name translates to the keyword argument name expected by the underlying driver library. Settings fields use UPPERCASE names (`HOST`, `SSL_CERT`), but driver libraries expect lowercase or camelCase names (`host`, `sslcert`). A bare string maps the field for every emission target, a `dict` maps it per target (`{"driver": "host", "url": "hostname"}`; a target with no entry skips the field), and `None` leaves the field out of the default output:

```python
ParameterSpec(name="SSL_CERT", type=str, tier="advanced",
              default=None, driver_key="sslcert")
# Settings field: SSL_CERT = "/path/to/cert.pem"
# Driver kwarg:   sslcert="/path/to/cert.pem"
```

When `driver_key` is `None`, the parameter does not participate in the default kwargs output. This is appropriate for parameters that require domain-specific transformation logic rather than a simple 1:1 mapping -- an adapter function handles those cases.

The `Profile._default_kwargs(target)` method uses the driver key mapping to produce the output dictionary for a target. `emit()` builds on it (see [Target-Aware Emission](#target-aware-emission)):

```python
def _default_kwargs(self, target: Hashable = None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for param in self.__spec__.parameters:
        key = self._resolve_driver_key(param.driver_key, target)
        if key is None:
            continue
        val = getattr(self, param.name, None)
        if val is None:
            continue
        if isinstance(val, SecretStr):
            val = val.get_secret_value()
        if param.transform is not None:
            val = param.transform(val)
        out[key] = val
    return out
```

## Secret Parameter Flag

The **secret parameter flag** (`ParameterSpec.secret`) controls whether the generated field is typed as `SecretStr`. When `secret=True`:

1. The field annotation is changed from `param.type` to `SecretStr` during dynamic field installation
2. Values are automatically wrapped by Pydantic's `SecretStr` validator on input
3. The `_default_kwargs()` method (and therefore `emit()`) unwraps via `.get_secret_value()` on output

This flag provides a single declaration point for secret handling. The developer declares `secret=True` and the framework handles the plumbing -- wrapping, masking in `repr` output, and unwrapping at the output boundary. Because the unwrapping happens at that boundary, emitted kwargs contain plaintext credentials (see [Target-Aware Emission](#target-aware-emission)). In generated declarations the flag is derived: a field annotated with `SecretStr` (including inside `Annotated` or a union) projects to `secret=True`.

<!-- concept:67 -->
<!-- concept:68 -->
## Transform Function

The **transform function** (`ParameterSpec.transform`) is an optional callable applied to the field value when emitting driver kwargs. It converts the settings-facing value into the format the driver expects:

```python
ParameterSpec(
    name="SSL_ENABLED",
    type=bool,
    tier="advanced",
    default=True,
    driver_key="ssl",
    transform=lambda v: {"ssl": True} if v else None
)
```

Transforms run inside `_default_kwargs()` (and so inside `emit()`) after `SecretStr` unwrapping but before the value is placed in the output dictionary. They are appropriate for type conversions (bool to dict), unit conversions (seconds to milliseconds), or format conversions (path string to SSL context object).

## Validator Function

The **validator function** (`ParameterSpec.validator`) is an optional callable that Pydantic invokes during field validation via `AfterValidator`. It receives the already-typed value and can either return it (valid) or raise a `ValueError`:

```python
def validate_port(v: int) -> int:
    if not (1 <= v <= 65535):
        raise ValueError(f"Port must be 1-65535, got {v}")
    return v

ParameterSpec(
    name="PORT", type=int, tier="core",
    default=5432, driver_key="port",
    validator=validate_port
)
```

During dynamic field installation, when a validator is present, the type annotation is wrapped with `Annotated[type, AfterValidator(validator)]`. This means the validator runs after Pydantic's built-in type coercion but before the value is stored on the instance.

## Profile Class

**Profile** inherits from `MountainAshBaseSettings`. A subclass either sets a class-body `__spec__` (explicit path), in which case `__pydantic_init_subclass__` installs a field for each `ParameterSpec`, or uses a class header and native fields (generated path), in which case the package publishes `__spec__` from the fields once the class is complete. Target-specific `__adapters__` compose the merged base and driver-key kwargs when `emit(target)` is called; the singular adapter hook is removed in 0.1.0.

```python
from mountainash_settings import Profile

class PostgreSQLProfile(Profile):
    __spec__ = POSTGRESQL_SPEC

# PostgreSQLProfile now has fields: HOST, PORT, DATABASE, PASSWORD, SSL_MODE
# All fields are validated, typed, and cacheable
settings = PostgreSQLProfile(
    HOST="db.example.com",
    DATABASE="myapp",
    PASSWORD="example-password",
)
print(settings.profile_name, settings.provider_type)
# postgresql DatabaseType.POSTGRESQL
```

The `Profile` class also provides:

- `profile_name` property that returns `__spec__.name`
- `provider_type` property that returns `__spec__.provider_type`
- A `post_init()` override that resolves template fields from the spec
- `_default_kwargs(target)` that produces the 1:1 driver keyword argument dictionary
- `emit(target, base=...)` that produces the final kwargs for a target

<!-- concept:70 -->
## Dynamic Field Installation

**Dynamic field installation** is the mechanism by which `Profile.__pydantic_init_subclass__()` translates the `ParameterSpec` declarations of an explicit `__spec__` into live Pydantic fields. This happens at class definition time (when the `class` statement executes), not at instance creation time. Generated declarations do not use this path: their fields already exist as native Pydantic fields, and the spec is derived from them afterwards.

The installation process for each parameter:

1. Reject `FACTORY_DEFAULT` (`TypeError`): it describes a native factory and cannot be installed from an explicit spec
2. Determine the annotation: `SecretStr` if `param.secret`, else `param.type`
3. Wrap with `AfterValidator` if `param.validator` is set
4. Create a `FieldInfo` with the annotation, default (`...` for `MISSING`) and description, and attach the parameter's emission options (`driver_key`, `tier`, `transform`, `template`) as field metadata
5. Add to `cls.model_fields[param.name]` and `cls.__annotations__[param.name]`

After all parameters are installed, `cls.model_rebuild(force=True)` is called to regenerate Pydantic's internal validation machinery.

```python
@classmethod
def __pydantic_init_subclass__(cls, **kwargs):
    super().__pydantic_init_subclass__(**kwargs)
    if cls._profile_declaration is not None:
        _complete_generated_profile(cls)
        return
    spec = _resolve_spec(cls)
    if spec is None:
        return

    new_fields: dict[str, tuple[Any, FieldInfo]] = {}

    for param in spec.parameters:
        if param.default is FACTORY_DEFAULT:
            raise TypeError(...)
        ptype = SecretStr if param.secret else param.type
        if param.validator is not None:
            ptype = Annotated[ptype, AfterValidator(param.validator)]
        if param.default is MISSING:
            info = FieldInfo(annotation=ptype, default=...,
                             description=param.description)
        else:
            info = FieldInfo(annotation=ptype, default=param.default,
                             description=param.description)
        info.metadata.append(_ProfileOptions(...))
        new_fields[param.name] = (ptype, info)

    for name, (annotation, info) in new_fields.items():
        cls.model_fields[name] = info
        cls.__annotations__[name] = annotation

    cls.model_rebuild(force=True)
```

#### Diagram: Dynamic Field Installation Sequence

<iframe src="../../sims/dynamic-field-install/main.html" width="100%" height="550px" scrolling="no"></iframe>
<details markdown="1">
<summary>Dynamic Field Installation Sequence</summary>
Type: microsim
**sim-id:** dynamic-field-install<br/>
**Library:** p5.js<br/>
**Status:** Specified

An animated sequence showing a ProfileSpec with four parameters being installed onto a blank Profile subclass. Each step shows: (1) the ParameterSpec being processed, (2) the annotation being constructed (with SecretStr/AfterValidator wrapping shown conditionally), (3) the FieldInfo being created, (4) the field being added to model_fields. After all parameters, model_rebuild() runs. Users can click each ParameterSpec to see how its attributes (secret, validator, default) affect the generated field.
</details>

<!-- concept:112 -->
## Native Profile Declarations

A **native profile declaration** describes the profile with ordinary Pydantic fields on a `Profile` subclass instead of a hand-written `ProfileSpec`. The package reads the fields and generates the spec, so the class is the single source of truth for validation, defaults and emission. Three pieces take part:

- **Class header** (`_declaration.py`): `class X(Profile, name=..., provider_type=...)` supplies identity. Optional header options are `driver_keys="lower"` (default every field's driver key to its lowercase name), `spec_type` (a `ProfileSpec` subclass, whose extra dataclass fields become accepted header options) and `metadata` (or those extra fields). Unknown header options raise `TypeError`. Identity is validated at class creation (see Spec Identity).
- **`ProfileField`** (`fields.py`): a wrapper around Pydantic's `Field` that adds `driver_key`, `tier`, `transform` and `template`. Every other keyword (`ge`, `le`, `description`, `default_factory`, ...) goes to Pydantic's `Field`. Omitting `driver_key` follows the class convention (`driver_keys="lower"` gives the lowercase name, otherwise no mapping); an explicit `driver_key=None` excludes the field; a `dict` scopes the key per target. `tier` defaults to `"core"`.
- **Projection** (`_projection.py`): each uppercase application field becomes a `ParameterSpec`. Framework fields inherited from `MountainAshBaseSettings` are skipped (and may not carry `ProfileField` options). A lowercase application field name, duplicate output keys, or more than one `ProfileField` marker on a field raises `TypeError`.

```python
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

spec = NativePG.__spec__
print(spec.name, spec.metadata)
# postgresql {'default_port': 5432}
print([(p.name, p.driver_key) for p in spec.parameters])
# [('HOST', 'host'), ('PORT', 'port'), ('DATABASE', 'database'),
#  ('PASSWORD', 'password'), ('SSL_MODE', 'sslmode'), ('LOCAL_NOTE', None)]
print(NativePG(DATABASE="myapp", PASSWORD="example-password").emit())
# {'host': 'localhost', 'port': 5432, 'database': 'myapp', 'password': 'example-password', 'sslmode': 'prefer'}
```

Compared with the explicit path: a native declaration needs no `ParameterSpec` list and gets Pydantic's own constraints, aliases and validators directly, whereas the explicit `ProfileSpec` is plain data that can be built, inspected or registered without writing a class body. The two cannot be mixed on one class: setting `__spec__` in the body of a class that has a generated declaration raises `TypeError`. A generated `__spec__` is a descriptive record of the fields; it cannot reconstruct factories, aliases or decorator validators, which stay on the owning class.

### FACTORY_DEFAULT

`FACTORY_DEFAULT` (a singleton, like `MISSING`) is the `ParameterSpec.default` recorded in a generated spec for a field declared with a `default_factory`. It says "this field has a default, produced by a factory on the owning class" without attempting to store the callable. The projection yields `MISSING` for required fields, the literal default for fields with one, and `FACTORY_DEFAULT` for factory fields. It cannot be used in an explicit spec: installing a parameter whose default is `FACTORY_DEFAULT` raises `TypeError`, directing you to declare the factory on the class.

### Delayed types and model_rebuild

The spec is published only when the Pydantic model is complete. If a field annotation refers to a type that is not yet defined, the class stays incomplete: `__spec__` is `None` and instantiating it raises `TypeError` ("incomplete profile; call model_rebuild() after defining referenced types"). Calling `Profile.model_rebuild()` once the type exists completes the model and publishes the spec; a completed declaration is immutable, so further rebuilds keep the same spec. A declaration with no `name` (an intermediate base class) cannot be instantiated either; declare `name` and `provider_type` on a concrete subclass.

<!-- concept:113 -->
## Target-Aware Emission

**`Profile.emit(target, base=...)`** turns a profile instance into the keyword arguments for one consumer (a driver, a URL builder, an SDK client). A profile can serve several consumers at once because both parts of emission are scoped by target:

1. Each field's `driver_key` may be a `dict` mapping a target to the output key for that target (a bare string applies to every target).
2. The plural class variable `__adapters__` maps a target to a two-argument callable `adapter(profile, kwargs) -> dict` that receives the profile and the already-merged kwargs and returns the final dict. The singular adapter hook is removed.

Targets are any hashable value. `base` supplies caller kwargs that the profile output is layered over (profile values win on key collisions); `emit()` takes only a shallow copy, so an adapter that changes a nested container must copy it first.

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

**Fail-closed targeting.** A profile is target-scoped when any field uses a `dict` driver key or the class defines any `__adapters__`. On a target-scoped profile, `emit()` with no target raises `ValueError`, and so does an explicit target the profile does not know (the known targets are the adapter keys plus every key of every `dict` driver key). An explicit `None` is accepted only if `None` is itself a known target. This prevents silently emitting an empty or partial dict. A profile with only bare-string driver keys and no adapters is not target-scoped, and `emit()` with no argument returns the merged kwargs.

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

**Secrets at emission.** `SecretStr` values are unwrapped with `.get_secret_value()` while kwargs are built, before any `transform` runs, so the emitted dict (and an adapter's input) holds plaintext. Emitted kwargs may expose credentials: do not log them, include them in error messages or persist them. The instance itself still masks the value (`repr` shows `SecretStr('**********')`). Authentication models and credential rendering for specific clients belong to the auth-client package; `emit()` with `base` and `__adapters__` is the integration point (see [Authentication Boundary](../08-authentication-system/index.md)).
