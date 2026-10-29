---
title: Pydantic and configuration foundations
description: Prerequisite concepts underpinning the mountainash-settings framework, including Pydantic models, configuration file formats, environment variables, decorators, unions, and secret types.
generated_by: claude skill chapter-content-generator
date: 2026-06-03
version: 0.08
---

# Pydantic and configuration foundations

mountainash-settings is a typed, multi-source configuration layer built on Pydantic. The Pydantic and configuration-format concepts it relies on are described here.

---

<!-- concept:4 -->
## Why configuration matters

Every non-trivial application needs external configuration: database URLs, API keys, feature flags, file paths, and timeouts that change between development, staging, and production. Hard-coding these values into source files makes systems fragile and hard to change. mountainash-settings loads them from files and the environment into typed, validated settings classes. It is built from a small set of Pydantic primitives and the configuration file formats that carry the values.

<!-- concept:1 -->
<!-- concept:2 -->
## Pydantic BaseModel

Pydantic is a Python library for data validation using type annotations. At its core is the `BaseModel` class, which holds data and validates it. When you define a class that inherits from `BaseModel`, each annotated attribute becomes a validated field. Pydantic parses incoming data, coerces compatible types, and raises detailed errors when values do not match the declared types.

A `BaseModel` subclass gives you:

- Type coercion: the string `"42"` becomes the integer `42` when the field expects `int`.
- Default values that apply when no value is supplied.
- Export to dictionaries and JSON with `model_dump()`.
- Optional immutability, by configuring the model as frozen.
- Nested models: a field can be another `BaseModel` subclass.

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

Declare a class with annotated fields, instantiate it with data, and Pydantic validates it. Every mountainash-settings class follows this pattern.

## Pydantic BaseSettings

`BaseModel` validates data you pass directly. `BaseSettings`, from the `pydantic-settings` package, keeps that validation and also loads values from external sources. Its priority chain checks environment variables, `.env` files, and secrets directories before falling back to defaults.

| Feature | BaseModel | BaseSettings |
|---------|-----------|--------------|
| Type validation | Yes | Yes |
| Default values | Yes | Yes |
| Environment variable loading | No | Yes |
| `.env` file support | No | Yes |
| Secrets directory support | No | Yes |
| Source priority chain | No | Yes |

`BaseSettings` separates the declaration of what configuration an application needs from the way values are supplied. The same class works whether values come from environment variables in a container, a `.env` file on a laptop, or a secrets volume in Kubernetes.

```python
from pydantic_settings import BaseSettings

class AppConfig(BaseSettings):
    database_url: str
    debug: bool = False

# export DATABASE_URL="postgresql://localhost/mydb"
config = AppConfig()
print(config)  # database_url='postgresql://localhost/mydb' debug=False
```

`MountainAshBaseSettings` extends `BaseSettings` with YAML, TOML, and JSON file sources, template expansion, and a caching layer, described in the following chapters. A subclass reads files through the `config_files` argument:

```python
from mountainash_settings import MountainAshBaseSettings

class ServiceSettings(MountainAshBaseSettings):
    database_url: str = "sqlite:///local.db"
    debug: bool = False

settings = ServiceSettings(config_files="config.yaml")
```

<!-- concept:3 -->
## Field validators

Pydantic **field validators** run custom logic while a value is parsed. They can transform values, enforce rules, or reject bad input. The `validator` option on a profile's `ParameterSpec` is applied as an `AfterValidator` on the generated field.

There are three main kinds:

- `@field_validator` is a class method that validates one or more named fields.
- `BeforeValidator` runs before Pydantic's own type coercion.
- `AfterValidator` runs after Pydantic has validated and coerced the value.

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

Validators work the same way on a settings class:

```python
from pydantic import field_validator
from mountainash_settings import MountainAshBaseSettings

class ApiSettings(MountainAshBaseSettings):
    port: int = 8080

    @field_validator("port")
    @classmethod
    def port_in_range(cls, v: int) -> int:
        if not (1 <= v <= 65535):
            raise ValueError("port must be between 1 and 65535")
        return v

settings = ApiSettings()
settings.port = 70000  # raises a validation error
```

!!! note "Validators and validate_assignment"
    `MountainAshBaseSettings` sets `validate_assignment=True`, so validators also run when you assign to an attribute after construction, not only in `__init__`. `SecretStr` wrapping, enum coercion, and `AfterValidator` transforms run on every assignment.

## Model config

Every Pydantic model can customize its behavior through the `model_config` attribute, a typed dictionary (`SettingsConfigDict` for settings classes). It controls whether extra fields are ignored or forbidden, whether assignment triggers revalidation, and whether arbitrary types are allowed as field annotations.

`MountainAshBaseSettings` ships with these defaults, which subclasses inherit:

| Config key | Value | Effect |
|-----------|-------|---------|
| `extra` | `"ignore"` | Silently drop unrecognized fields |
| `validate_default` | `False` | Declared defaults are not validated |
| `arbitrary_types_allowed` | `True` | Allow non-Pydantic types as annotations |
| `validate_assignment` | `True` | Revalidate on assignment after construction |

The effect is that unknown keys in a file are dropped and values are checked when assigned:

```python
import tempfile
from pathlib import Path
from mountainash_settings import MountainAshBaseSettings

class DatabaseSettings(MountainAshBaseSettings):
    host: str = "localhost"
    port: int = 5432

with tempfile.TemporaryDirectory() as d:
    path = Path(d) / "config.yaml"
    path.write_text("host: db.example.com\nunknown_key: ignored\n")
    settings = DatabaseSettings(config_files=str(path))
    print(settings.host, settings.port)  # db.example.com 5432

settings.port = "7000"           # coerced to the integer 7000
settings.port = "not-a-number"   # raises a validation error
```

<!-- concept:5 -->
<!-- concept:6 -->
<!-- concept:7 -->
<!-- concept:8 -->
## Configuration file formats

mountainash-settings reads configuration from four file formats, and a single settings class can load from several at once.

### YAML

YAML uses indentation to represent structure. It is widely used for application configuration because it is readable and supports nesting, comments, and multi-line strings.

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

YAML files use the `.yaml` or `.yml` extension. mountainash-settings treats both the same.

### TOML

TOML is designed for configuration files and is the format of `pyproject.toml`. It distinguishes integers, floats, dates, and strings syntactically, which reduces type ambiguity.

```toml
# config.toml
[database]
host = "db.example.com"
port = 5432
ssl_enabled = true
```

### JSON

JSON has strict syntax and no comments, so it is less pleasant to edit by hand than YAML or TOML. It is common in API responses, cloud service configuration, and tool output, and mountainash-settings can load it directly.

```json
{
  "database": {
    "host": "db.example.com",
    "port": 5432,
    "ssl_enabled": true
  }
}
```

### Env files

The `.env` format has one variable assignment per line. It comes from the twelve-factor app methodology and is common with Docker, CI systems, and local development. Unlike the formats above, `.env` files are flat. Pydantic `BaseSettings` can express nesting with a delimiter such as double underscores, but `MountainAshBaseSettings` sets no `env_nested_delimiter`, so nested-delimiter parsing is off by default (see [Environment variables](#environment-variables)).

```
# .env
database_url=postgresql://localhost/mydb
debug=true
api_key=sk-abc123
```

With `MountainAshBaseSettings`, `.env` keys must match field names exactly, including case.

<!-- concept:9 -->
## Environment variables

**Environment variables** are the most portable configuration mechanism, supported by every operating system, container runtime, and cloud platform. Pydantic `BaseSettings` matches field names to variable names, case-insensitively by default. `MountainAshBaseSettings` is case-sensitive, so variable names must match field names exactly.

mountainash-settings also supports an **env prefix**, which scopes a settings class's lookups so several classes can share one environment. With prefix `DB_`, a field named `port` reads `DB_port` rather than `port`:

```python
import os
from mountainash_settings import MountainAshBaseSettings, SettingsParameters

class DatabaseSettings(MountainAshBaseSettings):
    host: str = "localhost"
    port: int = 5432

params = SettingsParameters.create(settings_class=DatabaseSettings, env_prefix="DB_")

os.environ["DB_PORT"] = "6543"
print(DatabaseSettings(settings_parameters=params).port)  # 5432: DB_PORT does not match

os.environ["DB_port"] = "6543"
print(DatabaseSettings(settings_parameters=params).port)  # 6543, converted to int
```

Environment variables have two limitations that the file formats address:

- They are flat key-value pairs with no native nesting.
- All values are strings, so they depend on type coercion.

Pydantic converts the strings to the declared Python types. `BaseSettings` can also split nested model values on a delimiter such as `__`, but `MountainAshBaseSettings` sets no `env_nested_delimiter`, so that is off by default. Setting `env_nested_delimiter` in the class `model_config` enables it for both direct construction and cached retrieval.

<!-- concept:10 -->
## Python decorators

A **Python decorator** is a callable that wraps another callable, extending its behavior without changing its source. The `@` syntax applies it at definition time. mountainash-settings uses a decorator for profile registration: `Registry.decorator()` returns a decorator that registers a profile class. Settings caching does not use a decorator.

```python
def my_decorator(func):
    return func

# The @ syntax is shorthand
@my_decorator
def my_function():
    pass

# for this:
def my_function():
    pass
my_function = my_decorator(my_function)
```

A decorator factory takes arguments and returns the actual decorator. `Registry.decorator()` works this way: the decorator it returns is bound to that registry, so one implementation serves many registries. The same pattern in plain Python:

```python
def register_in(registry: dict):
    def register(cls):
        registry[cls.__name__] = cls
        return cls
    return register

PLUGINS: dict = {}

@register_in(PLUGINS)
class CsvLoader:
    pass

print(PLUGINS)  # {'CsvLoader': <class '__main__.CsvLoader'>}
```

<!-- concept:11 -->
## Discriminated unions

A **discriminated union** (also called a tagged union) is a type that can be one of several variants, each carrying a literal tag field that identifies it. In Pydantic it is written `Annotated[Union[A, B, C], Field(discriminator="kind")]`. Pydantic reads the discriminator first and validates only against the matching variant.

Discriminated unions are a general Pydantic feature, and mountainash-settings defines none of its own. They are useful in your own settings models whenever one field can take several shapes, such as a storage location that is either local or remote.

```python
from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field

class LocalStorage(BaseModel):
    kind: Literal["local"] = "local"
    path: str

class S3Storage(BaseModel):
    kind: Literal["s3"] = "s3"
    bucket: str
    region: str = "us-east-1"

StorageType = Annotated[
    Union[LocalStorage, S3Storage],
    Field(discriminator="kind"),
]

class Config(BaseModel):
    storage: StorageType

cfg = Config.model_validate({"storage": {"kind": "s3", "bucket": "data"}})
print(type(cfg.storage).__name__)  # S3Storage
```

<!-- concept:12 -->
## SecretStr

Pydantic's `SecretStr` wraps a string to prevent accidental exposure. Printing it or serializing it with `model_dump()` shows a mask instead of the value. To read the real value, call `.get_secret_value()`.

```python
from pydantic import BaseModel, SecretStr

class Credentials(BaseModel):
    api_key: SecretStr

creds = Credentials(api_key="sk-abc123")
print(creds.api_key)                     # **********
print(creds.api_key.get_secret_value())  # sk-abc123
print(creds.model_dump())                # {'api_key': SecretStr('**********')}
```

The same applies on a settings class, including after assignment:

```python
from pydantic import SecretStr
from mountainash_settings import MountainAshBaseSettings

class ApiSettings(MountainAshBaseSettings):
    api_key: SecretStr = SecretStr("sk-abc123")

settings = ApiSettings()
settings.api_key = "sk-rotated"   # a plain str is wrapped as SecretStr
print(settings.api_key)           # **********
```

mountainash-settings works with `SecretStr` in two places. Secret resolution can replace a `secret:` reference in a `SecretStr` field with the stored value. A profile `ParameterSpec` with `secret=True` declares its field as `SecretStr`.

`SecretStr` masks the value in `print`, `repr` and `model_dump()` output for the fields declared with that type. It is not general redaction: a `secret:` reference can resolve into a field declared as plain `str`, and that field is not masked. Declare credential fields as `SecretStr` and see the secrets resolution chapter for the resolution rules.

## Where each concept appears

`MountainAshBaseSettings` extends `BaseSettings` rather than `BaseModel`, so it inherits environment variable loading. It adds file sources for the formats above, sets `validate_assignment=True`, and protects declared secret fields with `SecretStr`.

| Foundation concept | Role in mountainash-settings |
|-------------------|-----------------|
| Pydantic BaseModel | Base of `MountainAshBaseSettings` (via `BaseSettings`) and of nested settings models. `SettingsParameters`, `ProfileSpec` and `ParameterSpec` are frozen dataclasses, not models. |
| Pydantic BaseSettings | Parent of `MountainAshBaseSettings` |
| Field validators | `ParameterSpec.validator` is applied when a profile's fields are generated; your own `@field_validator` methods work as usual |
| Model config | Declared on `MountainAshBaseSettings` with `validate_assignment=True` |
| YAML, TOML, JSON, .env | Loaded through `config_files` |
| Environment variables | Read by `BaseSettings`; scoped with `env_prefix` |
| Python decorators | `Registry.decorator()` registers profile classes |
| Discriminated unions | Available in your own models; not used by the package |
| SecretStr | Target of `secret:` reference resolution; used for `ParameterSpec.secret` fields |
