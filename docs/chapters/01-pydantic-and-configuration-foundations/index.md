---
title: Pydantic and Configuration Foundations
description: Prerequisite concepts underpinning the mountainash-settings framework, including Pydantic models, configuration file formats, environment variables, decorators, unions, and secret types.
generated_by: claude skill chapter-content-generator
date: 2026-06-03
version: 0.08
---

# Pydantic and Configuration Foundations

## Summary

This chapter introduces the prerequisite concepts that underpin the mountainash-settings framework. You will learn about Pydantic's BaseModel and BaseSettings classes, field validators, model configuration, the four supported configuration file formats (YAML, TOML, JSON, .env), environment variables, Python decorators, discriminated unions, and the SecretStr type. These foundational concepts are essential for understanding how mountainash-settings extends Pydantic to provide a typed, multi-source configuration system.

## Concepts Covered

- Pydantic BaseModel
- Pydantic BaseSettings
- Field Validators
- Model Config
- YAML File Format
- TOML File Format
- JSON File Format
- Env File Format
- Environment Variables
- Python Decorators
- Discriminated Unions
- SecretStr Type

## Prerequisites

None -- this is the foundational chapter.

---

<!-- concept:4 -->
## Why Configuration Matters

Every non-trivial application needs external configuration: database URLs, API keys, feature flags, file paths, and timeouts that change between development, staging, and production. Hard-coding these values into source files creates fragile systems that resist change. The mountainash-settings framework solves this problem by providing a typed, validated, multi-source configuration layer built on top of Pydantic. Before diving into the framework itself, you need a solid understanding of the building blocks it depends on.

This chapter covers twelve foundational concepts grouped into three themes: Pydantic's data modelling primitives, the configuration file formats that carry settings values, and several Python language features that the framework uses internally.

<!-- concept:1 -->
<!-- concept:2 -->
## Pydantic BaseModel

Pydantic is a Python library for data validation using type annotations. At its core is the **BaseModel** class, which acts as both a data container and a validation engine. When you define a class that inherits from `BaseModel`, each annotated attribute becomes a validated field. Pydantic parses incoming data, coerces compatible types, and raises detailed errors when values do not match the declared types.

A `BaseModel` subclass provides several capabilities that mountainash-settings relies on heavily:

- **Type coercion** -- string `"42"` becomes integer `42` when the field expects `int`
- **Default values** -- fields can declare defaults that apply when no value is supplied
- **Serialization** -- instances can export to dictionaries and JSON via `model_dump()`
- **Immutability control** -- models can be configured as frozen to prevent mutation after construction
- **Nested models** -- fields can reference other `BaseModel` subclasses, creating validated trees

```python
from pydantic import BaseModel

class DatabaseConfig(BaseModel):
    host: str
    port: int = 5432
    ssl_enabled: bool = True

# Pydantic validates and coerces on construction
config = DatabaseConfig(host="db.example.com", port="5432")
assert config.port == 5432  # coerced from str to int
```

The example above demonstrates the basic pattern: declare a class with annotated fields, instantiate it with data, and Pydantic handles validation. This pattern is the foundation upon which every mountainash-settings class is built.

## Pydantic BaseSettings

While `BaseModel` validates data you pass directly, **Pydantic BaseSettings** extends this pattern to load values from external sources automatically. The `BaseSettings` class (from the `pydantic-settings` package) inherits all of `BaseModel`'s validation capabilities but adds a source priority chain that checks environment variables, `.env` files, and secrets directories before falling back to defaults.

| Feature | BaseModel | BaseSettings |
|---------|-----------|--------------|
| Type validation | Yes | Yes |
| Default values | Yes | Yes |
| Environment variable loading | No | Yes |
| `.env` file support | No | Yes |
| Secrets directory support | No | Yes |
| Source priority chain | No | Yes |

The key architectural insight is that `BaseSettings` separates the _declaration_ of what configuration an application needs from the _mechanism_ by which values are supplied. A single class definition works whether values come from environment variables in a container orchestrator, from a `.env` file on a developer's laptop, or from a secrets volume in a Kubernetes pod.

```python
from pydantic_settings import BaseSettings

class AppConfig(BaseSettings):
    database_url: str
    debug: bool = False

<!-- concept:9 -->
# Values loaded from environment variables automatically
# export DATABASE_URL="postgresql://localhost/mydb"
config = AppConfig()
```

mountainash-settings extends `BaseSettings` further by adding YAML, TOML, and JSON file sources, template expansion, and a caching layer -- topics covered in subsequent chapters.

<!-- concept:3 -->
## Field Validators

Pydantic provides **field validators** that run custom logic during the parsing and validation pipeline. Validators can transform values (coercion), enforce business rules (constraints), or compute derived fields. The mountainash-settings framework uses validators extensively -- for example, the profile system wires `AfterValidator` functions declared in `ParameterSpec` into dynamically installed fields.

There are three main validator types:

- **`@field_validator`** -- a class method that validates one or more named fields
- **`BeforeValidator`** -- runs before Pydantic's own type coercion
- **`AfterValidator`** -- runs after Pydantic has validated and coerced the value

```python
from pydantic import BaseModel, field_validator

class PortConfig(BaseModel):
    port: int

    @field_validator("port")
    @classmethod
    def port_in_range(cls, v: int) -> int:
        if not (1 <= v <= 65535):
            raise ValueError("port must be between 1 and 65535")
        return v
```

!!! note "Validators and validate_assignment"
    When a model sets `validate_assignment=True` in its configuration (as mountainash-settings does), validators also run on attribute assignment after construction -- not just during `__init__`. This means `SecretStr` wrapping, enum coercion, and `AfterValidator` transforms all execute on every `setattr`, providing ongoing type safety.

## Model Config

Every Pydantic model can customize its behavior through the **model_config** attribute, which is a typed dictionary (`SettingsConfigDict` for settings classes). Model configuration controls aspects like whether extra fields are ignored or forbidden, whether assignment triggers revalidation, and whether arbitrary types are permitted as field annotations.

The mountainash-settings base class declares its model configuration as follows:

- `extra="ignore"` -- silently discards unrecognized fields rather than raising errors
- `validate_default=False` -- skips validation of default values for performance
- `arbitrary_types_allowed=True` -- permits non-Pydantic types like `UPath` as field annotations
- `validate_assignment=True` -- revalidates fields when they are assigned after construction

These four settings establish the contract for every settings class in the framework: be permissive about input (ignore extras), be strict about types (validate on assignment), and support the full range of Python types that configuration values might need.

| Config Key | Value | Purpose |
|-----------|-------|---------|
| `extra` | `"ignore"` | Silently drop unrecognized fields |
| `validate_default` | `False` | Skip validation of declared defaults |
| `arbitrary_types_allowed` | `True` | Allow non-Pydantic types (e.g. `UPath`) |
| `validate_assignment` | `True` | Revalidate on post-construction `setattr` |

<!-- concept:5 -->
<!-- concept:6 -->
<!-- concept:7 -->
<!-- concept:8 -->
## Configuration File Formats

mountainash-settings supports four file formats for externalizing configuration values. Each format has distinct strengths, and a single settings class can load from multiple formats simultaneously. Understanding the characteristics of each format helps you choose the right one for each use case.

### YAML File Format

YAML (YAML Ain't Markup Language) is a human-readable data serialization format that uses indentation to represent structure. It is the most common format for application configuration due to its readability and support for complex nested structures, comments, and multi-line strings.

```yaml
# config.yaml
database:
  host: db.example.com
  port: 5432
  ssl_enabled: true
features:
  - user_management
  - audit_logging
```

YAML files use the `.yaml` or `.yml` extension. mountainash-settings recognizes both extensions and treats them identically through its file type registry.

### TOML File Format

TOML (Tom's Obvious, Minimal Language) is designed specifically for configuration files. It maps unambiguously to a hash table and is the format used by `pyproject.toml` in the Python ecosystem. TOML distinguishes between integers, floats, dates, and strings syntactically, reducing type ambiguity.

```toml
# config.toml
[database]
host = "db.example.com"
port = 5432
ssl_enabled = true
```

### JSON File Format

JSON (JavaScript Object Notation) is the lingua franca of data interchange. While less human-friendly than YAML or TOML due to its strict syntax requirements and lack of comments, JSON is ubiquitous in API responses, cloud service configurations, and tooling output. mountainash-settings supports JSON configuration for interoperability with systems that produce JSON output.

```json
{
  "database": {
    "host": "db.example.com",
    "port": 5432,
    "ssl_enabled": true
  }
}
```

### Env File Format

The `.env` format is a simple key-value format where each line contains a variable assignment. It originated in the twelve-factor app methodology and is widely used with Docker, CI/CD systems, and local development tools. Unlike the hierarchical formats above, `.env` files are flat -- nested structures require a delimiter convention (like double underscores).

```
# .env
DATABASE_URL=postgresql://localhost/mydb
DEBUG=true
API_KEY=sk-abc123
```

#### Diagram: Configuration Format Comparison

<iframe src="../../sims/config-format-comparison/main.html" width="100%" height="500px" scrolling="no"></iframe>
<details markdown="1">
<summary>Configuration Format Comparison</summary>
Type: chart
**sim-id:** config-format-comparison<br/>
**Library:** Chart.js<br/>
**Status:** Specified

A radar chart comparing the four configuration formats across five dimensions: human readability, nesting support, type safety, ecosystem adoption, and comment support. Each format is a colored polygon on the radar. Hovering over a vertex shows the specific score and a brief explanation. Clicking a format name in the legend toggles its visibility. Learning objective: Compare and evaluate configuration file formats for different use cases (Bloom: Evaluate).
</details>

## Environment Variables

**Environment variables** are key-value pairs maintained by the operating system process. They represent the most portable configuration mechanism because every operating system, container runtime, and cloud platform supports them natively. Pydantic BaseSettings reads environment variables by matching field names (case-insensitively by default) to variable names.

mountainash-settings adds an important extension: the **env prefix override**, which allows multiple settings classes to coexist by scoping their environment variable lookups. For example, a database settings class with prefix `DB_` would read `DB_HOST` and `DB_PORT` rather than `HOST` and `PORT`, preventing collisions with other settings.

Environment variables have two notable limitations that the file-based formats address:

- They are flat key-value pairs with no native nesting
- All values are strings, requiring the consumer to handle type conversion

Pydantic and mountainash-settings handle both limitations: nested models use a configurable delimiter (e.g. `__`), and Pydantic's type coercion converts string values to their declared Python types.

<!-- concept:10 -->
## Python Decorators

A **Python decorator** is a callable that wraps another callable, modifying or extending its behavior without changing its source code. Decorators use the `@` syntax and are applied at definition time. mountainash-settings uses decorators in two important contexts: the `@lru_cache` decorator for settings caching, and the registry `@register` decorator for profile registration.

```python
# The @decorator syntax is syntactic sugar
@my_decorator
def my_function():
    pass

# It is equivalent to:
def my_function():
    pass
my_function = my_decorator(my_function)
```

Decorator factories are decorators that accept arguments and return the actual decorator. This pattern appears in the registry system, where `Registry.decorator()` returns a `@register` decorator bound to a specific registry instance. The factory pattern allows a single decorator implementation to serve multiple registries.

- **Simple decorators** wrap a function or class directly
- **Decorator factories** accept configuration arguments and return a decorator
- **Class decorators** wrap entire classes, not just functions

<!-- concept:11 -->
## Discriminated Unions

A **discriminated union** (also called a tagged union) is a type that can be one of several variants, where each variant carries a literal tag field that identifies which variant is active. In Pydantic, discriminated unions use `Annotated[Union[A, B, C], Field(discriminator="kind")]` to enable efficient parsing -- Pydantic reads the discriminator field first to determine which variant to validate against, avoiding trial-and-error parsing.

mountainash-settings uses discriminated unions in the authentication system, where each auth mode (password, token, OAuth2, certificate, etc.) shares a common `kind` literal that Pydantic uses for dispatch.

```python
from typing import Literal, Union, Annotated
from pydantic import BaseModel, Field

class PasswordAuth(BaseModel):
    kind: Literal["password"] = "password"
    username: str
    password: str

class TokenAuth(BaseModel):
    kind: Literal["token"] = "token"
    token: str

AuthType = Annotated[
    Union[PasswordAuth, TokenAuth],
    Field(discriminator="kind")
]
```

The discriminator approach is more efficient than standard union validation because Pydantic does not need to attempt parsing against each variant sequentially. It reads the `kind` field, selects the matching variant, and validates only against that variant.

#### Diagram: Discriminated Union Dispatch

<iframe src="../../sims/discriminated-union-dispatch/main.html" width="100%" height="450px" scrolling="no"></iframe>
<details markdown="1">
<summary>Discriminated Union Dispatch</summary>
Type: workflow
**sim-id:** discriminated-union-dispatch<br/>
**Library:** vis-network<br/>
**Status:** Specified

A directed graph showing how Pydantic processes a discriminated union. The input data node flows to a "Read discriminator field" decision node, which branches to each variant type (PasswordAuth, TokenAuth, etc.). Clicking a variant highlights the validation path and shows the fields that would be validated. Hovering over the decision node shows the discriminator key name. Learning objective: Trace the discriminated union dispatch mechanism used by the auth system (Bloom: Understand).
</details>

<!-- concept:12 -->
## SecretStr Type

The **SecretStr** type from Pydantic is a string wrapper that prevents accidental exposure of sensitive values. When you print a `SecretStr` instance or serialize it with `model_dump()`, the value is masked as `'**********'` rather than showing the actual content. To access the real value, you must explicitly call `.get_secret_value()`.

```python
from pydantic import BaseModel, SecretStr

class Credentials(BaseModel):
    api_key: SecretStr

creds = Credentials(api_key="sk-abc123")
print(creds.api_key)                    # SecretStr('**********')
print(creds.api_key.get_secret_value()) # sk-abc123
```

mountainash-settings uses `SecretStr` in two key contexts. First, the secrets resolution system works with `SecretStr` fields during its model tree pass, unwrapping the secret value to check for reference prefixes like `secret:` and then re-wrapping the resolved value. Second, the profile system's `ParameterSpec` has a `secret` flag -- when set to `True`, the field's type is automatically wrapped as `SecretStr`, and the `_default_kwargs()` method unwraps it via `.get_secret_value()` when emitting driver kwargs.

This design ensures that secrets are protected by default throughout the settings lifecycle. Log statements, debug output, and serialization all see masked values unless the consumer explicitly opts in to reading the raw secret.

#### Diagram: SecretStr Lifecycle

<iframe src="../../sims/secretstr-lifecycle/main.html" width="100%" height="400px" scrolling="no"></iframe>
<details markdown="1">
<summary>SecretStr Lifecycle</summary>
Type: workflow
**sim-id:** secretstr-lifecycle<br/>
**Library:** vis-network<br/>
**Status:** Specified

A linear workflow showing the lifecycle of a secret value: raw string input enters Pydantic, is wrapped as SecretStr during validation, is masked in print/dump operations, and is explicitly unwrapped via get_secret_value() at the consumption boundary. Each node is clickable to show the string representation at that stage. A toggle button switches between "safe" view (masked) and "debug" view (showing actual values). Learning objective: Explain how SecretStr protects sensitive configuration values throughout the settings lifecycle (Bloom: Understand).
</details>

## Bringing It All Together

These twelve concepts form the vocabulary and the toolbox that mountainash-settings builds upon. The framework extends `BaseSettings` (not `BaseModel`) to inherit environment variable loading, adds file handler classes that leverage the four file formats, uses `model_config` to enforce `validate_assignment=True` across all settings, wires field validators through `ParameterSpec`, employs decorators for both caching and registration, dispatches auth modes via discriminated unions, and protects sensitive values with `SecretStr`.

The following table maps each foundation concept to where it appears in the mountainash-settings architecture:

| Foundation Concept | Framework Usage |
|-------------------|-----------------|
| Pydantic BaseModel | Base class for SettingsParameters, ProfileSpec, ParameterSpec |
| Pydantic BaseSettings | Parent of MountainAshBaseSettings |
| Field Validators | Wired via ParameterSpec.validator in dynamic field installation |
| Model Config | Declared on MountainAshBaseSettings with validate_assignment=True |
| YAML / TOML / JSON / .env | Loaded via FileHandler and pydantic-settings sources |
| Environment Variables | Read by BaseSettings; scoped via env_prefix override |
| Python Decorators | @lru_cache for caching, @register for profile registration |
| Discriminated Unions | Auth system's AuthType union with kind discriminator |
| SecretStr Type | Secrets resolution, ParameterSpec.secret flag |

#### Diagram: Foundation Concept Dependency Map

<iframe src="../../sims/foundation-dependency-map/main.html" width="100%" height="550px" scrolling="no"></iframe>
<details markdown="1">
<summary>Foundation Concept Dependency Map</summary>
Type: graph-model
**sim-id:** foundation-dependency-map<br/>
**Library:** vis-network<br/>
**Status:** Specified

An interactive directed graph showing the 12 foundation concepts as nodes, with edges indicating dependencies (e.g., BaseSettings depends on BaseModel; SecretStr depends on BaseModel). Nodes are colored by theme: blue for Pydantic primitives, green for file formats, orange for Python features. Clicking a node highlights its dependents (downstream concepts) and prerequisites (upstream concepts). Dragging nodes rearranges the layout. Learning objective: Analyze the dependency relationships among foundation concepts to understand the framework's architectural prerequisites (Bloom: Analyze).
</details>

## Key Takeaways

- **Pydantic BaseModel** provides type validation, coercion, serialization, and nested model support that every mountainash-settings class inherits.
- **Pydantic BaseSettings** extends BaseModel with automatic loading from environment variables, `.env` files, and secrets directories, establishing the multi-source pattern.
- **Field validators** enforce custom constraints and transformations during both construction and assignment, maintaining type safety throughout the settings lifecycle.
- **Model Config** controls framework-wide behavior -- mountainash-settings uses `validate_assignment=True` and `extra="ignore"` as its baseline contract.
- **Four file formats** (YAML, TOML, JSON, .env) cover different use cases from human-readable nested config to flat environment-style key-value pairs.
- **Environment variables** provide the most portable configuration mechanism; mountainash-settings scopes them with configurable prefixes to prevent collisions.
- **Python decorators** enable both the `@lru_cache` caching strategy and the `@register` pattern for profile registration without modifying the decorated class.
- **Discriminated unions** allow efficient, tag-based dispatch in the authentication system, avoiding trial-and-error type parsing.
