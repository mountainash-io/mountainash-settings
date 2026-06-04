---
title: Connection Profiles
description: The connection profile system covering ProfileSpec, ParameterSpec, identity fields, type conventions, tiers, defaults, driver key mappings, secrets, transforms, validators, and dynamic field installation.
generated_by: claude skill chapter-content-generator
date: 2026-06-03
version: 0.08
---

# Connection Profiles

## Summary

This chapter introduces the connection profile system that allows reusable, typed connection configurations to be defined declaratively. You will learn about the ProfileDescriptor class with its identity and provider type fields, the ParameterSpec class for defining typed parameters with name conventions, Python types, tiers, default values, the MISSING sentinel, driver key mappings, secret flags, transform functions, and validator functions. The chapter concludes with DescriptorProfile and its dynamic Pydantic field installation mechanism.

## Concepts Covered

- ProfileDescriptor Class
- Descriptor Identity
- Provider Type Field
- ParameterSpec Class
- Parameter Name Convention
- Parameter Python Type
- Parameter Tier
- Parameter Default Value
- MISSING Sentinel
- Driver Key Mapping
- Secret Parameter Flag
- Transform Function
- Validator Function
- DescriptorProfile Class
- Dynamic Field Installation

## Prerequisites

- Chapter 1: Pydantic and Configuration Foundations
- Chapter 2: MountainAsh Base Settings

---

## Why Profiles Exist

Applications that connect to external systems -- databases, message brokers, REST APIs, cloud services -- share a common pattern: they need a set of typed parameters (host, port, credentials, SSL settings) that translate into connection kwargs for a driver library. Without profiles, every team writes its own settings class for each backend, duplicating validation logic, default values, and the mapping between settings names and driver parameter names.

The profile system solves this by separating _what_ a backend needs (declared in a `ProfileSpec`) from _how_ that translates into a Pydantic settings class (implemented by the `Profile` base class). A single spec declaration produces a fully validated, cached, template-aware settings class with zero boilerplate.

<!-- concept:56 -->
<!-- concept:57 -->
<!-- concept:59 -->
<!-- concept:69 -->
## ProfileDescriptor Class

The **ProfileDescriptor** (now canonically named `ProfileSpec` as of version 26.5.0) is a frozen dataclass that captures the complete specification of a connection profile. It is the declarative blueprint from which a `Profile` settings class generates its Pydantic fields.

```python
@dataclass(frozen=True, kw_only=True)
class ProfileSpec:
    name: str
    provider_type: Any
    parameters: list[ParameterSpec]
    auth_modes: list[type]
    metadata: dict[str, Any] = field(default_factory=dict)
```

The spec is immutable after construction (`frozen=True`), which means it can safely be shared across threads, cached, and used as a registry key. The `kw_only=True` constraint ensures that all fields must be passed as keyword arguments during construction, improving readability at the call site.

A complete spec declares the profile's identity (`name`, `provider_type`), its parameters (as a list of `ParameterSpec` instances), the authentication modes it supports (`auth_modes`), and optional metadata for domain-specific information:

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
        ParameterSpec(name="SSL_MODE", type=str, tier="advanced",
                      default="prefer", driver_key="sslmode"),
    ],
    auth_modes=[PasswordAuth, CertificateAuth],
    metadata={"default_port": 5432, "url_scheme": "postgresql"},
)
```

## Descriptor Identity

The **descriptor identity** consists of two fields that uniquely identify what system a profile connects to:

- `name` -- a short, lowercase string identifier (e.g., `"postgresql"`, `"redis"`, `"snowflake"`)
- The combination of name and provider_type establishes the profile's identity within a registry

The `name` field is the primary lookup key in the registry system. It must be unique within a given registry, lowercase, and non-empty (the invariant system enforces these constraints). Conventionally, names match the system's package name or common abbreviation.

<!-- concept:58 -->
<!-- concept:70 -->
## Provider Type Field

The **provider type field** is a domain-specific value that categorizes the profile within its domain. For database profiles, this might be an enum like `DatabaseType.POSTGRESQL`. For API profiles, it might be a string like `"rest_api"` or an enum member.

The provider type serves as a secondary classification beyond the name. While the name uniquely identifies a profile within a registry, the provider type groups related profiles by category. This enables queries like "give me all PostgreSQL-compatible profiles" or "show me all REST API backends."

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
    driver_key: str | None = None
    secret: bool = False
    transform: Callable[[Any], Any] | None = None
    validator: Callable[[Any], Any] | None = None
    template: str | None = None
```

Each `ParameterSpec` maps one-to-one to a Pydantic field on the generated settings class. The spec contains both the field's type information (for Pydantic) and its output mapping (for the driver kwargs). This dual role is what makes the profile system powerful -- a single declaration handles both input validation and output transformation.

<!-- concept:65 -->
#### Diagram: ParameterSpec Field Mapping

<iframe src="../../sims/parameter-spec-mapping/main.html" width="100%" height="500px" scrolling="no"></iframe>
<details markdown="1">
<summary>ParameterSpec Field Mapping</summary>
Type: diagram
**sim-id:** parameter-spec-mapping<br/>
**Library:** vis-network<br/>
**Status:** Specified

A two-column diagram showing the mapping from ParameterSpec attributes (left column) to their effects on the generated Pydantic field and driver kwargs (right column). Lines connect each ParameterSpec attribute to its downstream effects: name -> field name, type -> annotation, default -> FieldInfo default, secret -> SecretStr wrapping, driver_key -> output kwargs key, validator -> AfterValidator, transform -> kwargs emit transform. Clicking each attribute shows a code example. A toggle switches between "input view" (how config values enter) and "output view" (how kwargs are emitted). Learning objective: Map each ParameterSpec attribute to its effect on the settings class and driver kwargs (Bloom: Analyze).
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

If no default is appropriate (the parameter is required), the special `MISSING` sentinel is used instead.

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

## Driver Key Mapping

The **driver key mapping** (`ParameterSpec.driver_key`) defines how a settings field name translates to the keyword argument name expected by the underlying driver library. Settings fields use UPPERCASE names (`HOST`, `SSL_CERT`), but driver libraries expect lowercase or camelCase names (`host`, `sslcert`):

```python
ParameterSpec(name="SSL_CERT", type=str, tier="advanced",
              default=None, driver_key="sslcert")
# Settings field: SSL_CERT = "/path/to/cert.pem"
# Driver kwarg:   sslcert="/path/to/cert.pem"
```

When `driver_key` is `None`, the parameter does not participate in the default kwargs output. This is appropriate for parameters that require domain-specific transformation logic rather than a simple 1:1 mapping -- an adapter function handles those cases.

The `Profile._default_kwargs()` method uses the driver key mapping to produce the output dictionary:

```python
def _default_kwargs(self) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for param in self.__spec__.parameters:
        if param.driver_key is None:
            continue
        val = getattr(self, param.name, None)
        if val is None:
            continue
        if isinstance(val, SecretStr):
            val = val.get_secret_value()
        if param.transform is not None:
            val = param.transform(val)
        out[param.driver_key] = val
    return out
```

## Secret Parameter Flag

The **secret parameter flag** (`ParameterSpec.secret`) controls whether the generated field is typed as `SecretStr`. When `secret=True`:

1. The field annotation is changed from `param.type` to `SecretStr` during dynamic field installation
2. Values are automatically wrapped by Pydantic's `SecretStr` validator on input
3. The `_default_kwargs()` method automatically unwraps via `.get_secret_value()` on output

This flag provides a single declaration point for secret handling. The developer declares `secret=True` and the framework handles all the plumbing -- wrapping, protection from accidental exposure, and unwrapping at the output boundary.

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

Transforms run inside `_default_kwargs()` after `SecretStr` unwrapping but before the value is placed in the output dictionary. They are appropriate for type conversions (bool to dict), unit conversions (seconds to milliseconds), or format conversions (path string to SSL context object).

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

## DescriptorProfile Class

The **DescriptorProfile** (now canonically named `Profile` as of version 26.5.0) is a base class that inherits from `MountainAshBaseSettings` and uses `__pydantic_init_subclass__` to install fields from a `ProfileSpec`. When you subclass `Profile` and declare `__spec__`, the base class automatically generates Pydantic fields for each `ParameterSpec` in the spec, plus an `auth` field typed as a discriminated union of the spec's auth modes.

```python
from mountainash_settings import Profile, ProfileSpec

class PostgreSQLProfile(Profile):
    __spec__ = POSTGRESQL_SPEC

# PostgreSQLProfile now has fields: HOST, PORT, DATABASE, SSL_MODE, auth
# All fields are validated, typed, and cacheable
settings = PostgreSQLProfile(
    config_files=["db.yaml"],
    HOST="db.example.com",
    DATABASE="myapp"
)
```

The `Profile` class also provides:

- `profile_name` / `backend` properties that return `__spec__.name`
- `provider_type` property that returns `__spec__.provider_type`
- A `post_init()` override that resolves template fields from the spec
- `_default_kwargs()` that produces the driver keyword argument dictionary

## Dynamic Field Installation

**Dynamic field installation** is the mechanism by which `Profile.__pydantic_init_subclass__()` translates `ParameterSpec` declarations into live Pydantic fields. This happens at class definition time (when the `class` statement executes), not at instance creation time.

The installation process for each parameter:

1. Determine the annotation: `SecretStr` if `param.secret`, else `param.type`
2. Wrap with `AfterValidator` if `param.validator` is set
3. Create a `FieldInfo` with the annotation, default, and description
4. Add to `cls.model_fields[param.name]` and `cls.__annotations__[param.name]`

After all parameters are installed, the auth field is added as a discriminated union, and `cls.model_rebuild(force=True)` is called to regenerate Pydantic's internal validation machinery.

```python
@classmethod
def __pydantic_init_subclass__(cls, **kwargs):
    super().__pydantic_init_subclass__(**kwargs)
    spec = _resolve_spec(cls)
    if spec is None:
        return

    new_fields: dict[str, tuple[Any, FieldInfo]] = {}

    for param in spec.parameters:
        ptype = SecretStr if param.secret else param.type
        if param.validator is not None:
            ptype = Annotated[ptype, AfterValidator(param.validator)]
        if param.default is MISSING:
            info = FieldInfo(annotation=ptype, default=...)
        else:
            info = FieldInfo(annotation=ptype, default=param.default)
        new_fields[param.name] = (ptype, info)

    # Install auth union field
    if spec.auth_modes:
        auth_union = Union[tuple(spec.auth_modes)]
        auth_info = FieldInfo(annotation=auth_union, default=...,
                              discriminator="kind")
        new_fields["auth"] = (auth_union, auth_info)

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

An animated sequence showing a ProfileSpec with four parameters being installed onto a blank Profile subclass. Each step shows: (1) the ParameterSpec being processed, (2) the annotation being constructed (with SecretStr/AfterValidator wrapping shown conditionally), (3) the FieldInfo being created, (4) the field being added to model_fields. After all parameters, the auth union field is installed, and model_rebuild() runs. Users can click each ParameterSpec to see how its attributes (secret, validator, default) affect the generated field. Learning objective: Trace how each ParameterSpec attribute influences the dynamically installed Pydantic field (Bloom: Analyze).
</details>

## Key Takeaways

- **ProfileSpec** (formerly ProfileDescriptor) is a frozen dataclass that declaratively specifies everything a connection profile needs -- parameters, auth modes, identity, and metadata.
- **Descriptor Identity** consists of a lowercase `name` (registry key) and a `provider_type` (domain classification) that together identify the target system.
- **ParameterSpec** declares a single field with type, tier, default, driver key mapping, secret flag, transform, and validator -- all in one frozen dataclass.
- **Parameter Name Convention** requires UPPERCASE_WITH_UNDERSCORES, aligning with environment variable conventions and enforced by invariant checks.
- **MISSING Sentinel** is a singleton that indicates required fields with no default, generating `Field(default=...)` in the installed Pydantic field.
- **Driver Key Mapping** translates between settings-facing names (UPPERCASE) and driver-facing names (lowercase/camelCase) in the `_default_kwargs()` output.
- **Secret Parameter Flag** provides one-declaration secret handling: `SecretStr` wrapping on input, masked in logs, auto-unwrapped on kwargs output.
- **Dynamic Field Installation** happens at class definition time via `__pydantic_init_subclass__`, translating specs into validated Pydantic fields with zero boilerplate.
