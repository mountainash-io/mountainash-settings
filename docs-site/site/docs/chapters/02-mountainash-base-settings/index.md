---
title: MountainAsh base settings
description: The core MountainAshBaseSettings class covering model config, post-init lifecycle, source customization, validation invariants, source priority, and environment prefix overrides.
generated_by: claude skill chapter-content-generator
date: 2026-06-03
version: 0.08
---

# MountainAsh base settings

`MountainAshBaseSettings` is the base class for settings classes in this package. It extends Pydantic's `BaseSettings` so that a class can load values from `.env`, YAML, TOML and JSON files, environment variables and constructor arguments, with a fixed order of precedence. It validates every assignment, resolves secret references, and calls a `post_init()` hook once loading is finished.

---

## The central abstraction

Settings classes for database connections, API clients, application configuration and connection profiles all inherit from `MountainAshBaseSettings`. Compared with plain `BaseSettings`, it adds multi-format file loading, template expansion, secrets resolution, a caching layer and a unified parameter interface.

Construction runs in a set order. The class merges the parameters you give it, validates the config files, resolves secret references in the constructor arguments, and then lets Pydantic load values from every source. Afterwards it records which sources were used, resolves secret references in the loaded values, and runs `post_init()`.

<!-- concept:13 -->
<!-- concept:14 -->
## MountainAshBaseSettings class

Subclass it and declare fields as you would on any Pydantic settings class. The constructor takes three parameters in addition to the field values, and also accepts the selector keywords `env_prefix`, `secrets_dir` and `secret_store`:

- `config_files`: a path, list of paths, or tuple of paths to configuration files
- `settings_parameters`: an optional pre-built `SettingsParameters` instance to merge with
- `template_settings_parameters`: optional parameters for template resolution

```python
import tempfile
from pathlib import Path
from pydantic import Field
from mountainash_settings import MountainAshBaseSettings

class MyAppSettings(MountainAshBaseSettings):
    database_host: str = Field(default="localhost")
    database_port: int = Field(default=5432)
    debug: bool = Field(default=False)

with tempfile.TemporaryDirectory() as tmp:
    cfg = Path(tmp) / "config.yaml"
    cfg.write_text("database_host: db.internal\ndatabase_port: 5433\nunknown_key: ignored\n")

    settings = MyAppSettings(config_files=[str(cfg)], debug=True)
    print(settings.database_host, settings.database_port, settings.debug)
    # db.internal 5433 True
```

The YAML file supplies the host and port, the `debug=True` argument overrides the default, and the undeclared `unknown_key` is ignored.

The class also provides a `get_settings()` class method that integrates with the caching layer, and an `extract_settings_parameters()` instance method that returns the `SettingsParameters` needed to rebuild the instance, with `secret:` references left unresolved. When a selected secret store is a `SecretWriter`, `persist()` writes a local record through it, and `persist_key()` derives its default key; see the [secrets chapter](../05-secrets-resolution/index.md).

## Settings model config

Every settings class inherits a `model_config` with four settings:

| Config key | Value | Effect |
|-----------|-------|--------|
| `extra` | `"ignore"` | Config files can contain fields the class does not declare without raising errors |
| `validate_default` | `False` | `Field(default=None)` placeholders are not validated |
| `arbitrary_types_allowed` | `True` | `UPath`, custom enums and other non-standard types can be used as field annotations |
| `validate_assignment` | `True` | Fields are validated again when they are modified after construction |

The `extra="ignore"` setting matters for forward compatibility. Configuration files often change faster than the code that reads them, and a shared YAML file might contain fields meant for several services. Ignoring extras lets each service read only the fields it declares.

<!-- concept:15 -->
## Post-init lifecycle

`post_init()` is a hook that runs after all settings have been loaded and validated. Fields whose values depend on other fields are resolved here, after every source has contributed its values.

The base implementation does nothing. Subclasses override it to add their own initialization logic. The `AppSettings` class, for example, uses it to build its `RUNDATETIME` field from a template that references `RUNDATE` and `RUNTIME`. A user-defined class can do the same:

```python
from mountainash_settings import MountainAshBaseSettings

class ReportSettings(MountainAshBaseSettings):
    run_date: str = "2026-01-31"
    run_time: str = "0930"
    run_stamp: str = ""

    def post_init(self, **kwargs):
        super().post_init(**kwargs)
        self.run_stamp = f"{self.run_date}T{self.run_time}"

settings = ReportSettings(run_time="1015")
print(settings.run_stamp)
# 2026-01-31T1015
```

The order of construction is:

1. `SettingsParameters` are created and merged.
2. Config files are separated and validated.
3. Secret references in the constructor arguments are resolved (first pass).
4. Pydantic's `BaseSettings.__init__` runs, loading environment variables and files and applying the constructor arguments.
5. Value-free source facts and accepted input names are published.
6. Secret references in the loaded values are resolved (second pass).
7. `post_init()` runs, and templates expand here.

Secret references in the constructor arguments are therefore resolved before validation, and those loaded from files or the environment after it. When `post_init()` runs, the values from every source are already in place, so a template such as `"{RUNDATE}T{RUNTIME}"` can safely reference both fields.

<!-- concept:16 -->
## Source customization

The package overrides Pydantic's `settings_customise_sources()` class method to decide which sources are consulted and in what order. Compared with standard `BaseSettings`, it adds YAML, TOML and JSON file sources. The same source order is used for direct construction and for cached retrieval:

1. Init settings: values passed as kwargs to the constructor
2. Environment settings: values from environment variables
3. Dotenv settings: values from `.env` files, using the configured environment prefix
4. Unprefixed dotenv settings: the same `.env` files read again with no prefix
5. YAML config: values from `.yaml` and `.yml` files
6. TOML config: values from `.toml` files
7. JSON config: values from `.json` files
8. File secret settings: values from a secrets directory

Sources earlier in the list take precedence over later ones. Explicitly passed kwargs always win, environment variables override file-based config, and file-based config overrides the secrets directory. The YAML, TOML and JSON sources deep-merge, so nested mappings from several files of the same type merge key by key rather than the last file replacing whole sections.

Each construction uses its own file paths. The class-level `model_config` is shared between instances and construction never changes it.

<!-- concept:114 -->
## Cache-safe settings sources

`settings_customise_sources()` only governs direct construction. Cached retrieval through `get_settings()` does not invoke it: the cache builds the configured sources itself so that a customization hook is never run implicitly. Two things follow for classes that change the source chain:

- `settings_capture_sources(cls, sources)` is the cache-safe hook. The base implementation returns `sources` unchanged. A subclass overrides it to declare the source order the cache should use. A class that overrides `settings_customise_sources()` without also overriding `settings_capture_sources()` is rejected at cached retrieval with a `ValueError`.
- `CacheableSettingsSource` (exported from `mountainash_settings`) is the base class a custom source must extend to take part in cached retrieval. It requires `capture()`, which reads the source's structural values once, and a static `project()`, which returns terminal values for each materialization without performing I/O. Cached retrieval rejects custom sources that are not `CacheableSettingsSource` instances. The cache handles the built-in sources directly.

Direct construction is not affected by this restriction. For how structural contexts are captured and reused, see the [caching chapter](../09-caching-settings-management-and-app-settings/index.md).

<!-- concept:17 -->
## Validate assignment invariant

With `validate_assignment=True` in the model config, every field assignment after construction goes through Pydantic's full validation, including type coercion, `SecretStr` wrapping, enum coercion and any declared `AfterValidator` transforms.

```python
from pydantic import SecretStr
from mountainash_settings import MountainAshBaseSettings

class ApiSettings(MountainAshBaseSettings):
    api_key: SecretStr = SecretStr("unset")
    retries: int = 3

settings = ApiSettings()
settings.api_key = "raw-secret"
print(repr(settings.api_key))
# SecretStr('**********')

settings.retries = "5"
print(settings.retries, type(settings.retries).__name__)
# 5 int

settings.retries = "many"
# raises pydantic.ValidationError
```

Without validation on assignment, a raw string assigned to a `SecretStr` field would stay a plain `str`, and the masking would be lost. The same validation applies to every way of changing settings after construction, whether that is `update_settings_from_dict()`, runtime overrides or direct assignment.

<!-- concept:18 -->
## Object setattr bypass

There is one exception to the validate-assignment rule. The package's bookkeeping fields (`SETTINGS_SOURCE_*`, `SETTINGS_CLASS` and `SETTINGS_CLASS_NAME`) are set without validation and are not counted in `model_fields_set`, so your field validators never see them and they never look like user-supplied values.

!!! warning "Do not use the bypass on your own fields"
    Fields you declare should always be assigned normally so that validation runs. Using `object.__setattr__()` on a domain field would silently skip type checking.

<!-- concept:19 -->
## Settings source priority

When the same field is defined in several places, the highest-priority source wins:

1. Constructor kwargs (highest priority)
2. Environment variables
3. Dotenv files (`.env`, read with the configured prefix)
4. Unprefixed dotenv files (the same `.env` files read with no prefix)
5. YAML files
6. TOML files
7. JSON files
8. Secrets directory
9. Field defaults (lowest priority, used only as a fallback)

The closer a value is to the code that asks for it, the higher its priority. A `debug=True` kwarg wins over a YAML file that says `debug: false`, and an environment variable set by a deployment tool overrides what is checked into version control.

```python
import os
import tempfile
from pathlib import Path
from mountainash_settings import MountainAshBaseSettings

class ServiceSettings(MountainAshBaseSettings):
    host: str = "localhost"
    port: int = 6379

with tempfile.TemporaryDirectory() as tmp:
    cfg = Path(tmp) / "service.yaml"
    cfg.write_text("host: from-yaml\nport: 1111\n")
    cfgs = [str(cfg)]

    print(ServiceSettings(config_files=cfgs).host)
    # from-yaml
    os.environ["host"] = "from-env"
    print(ServiceSettings(config_files=cfgs).host)
    # from-env
    print(ServiceSettings(config_files=cfgs, host="from-kwarg").host)
    # from-kwarg
```

<!-- concept:20 -->
## Env prefix override

An environment prefix scopes a settings class's environment variable lookups. Without a prefix, a field named `host` reads the environment variable `host`. With a prefix of `CACHE_`, it reads `CACHE_host` instead. Environment lookups are case-sensitive and use the field name exactly as declared, so a field named `HOST` reads `HOST`.

Prefixes help when several components share an environment such as a Docker Compose file, a Kubernetes pod or a systemd unit. Giving each settings class its own prefix avoids collisions between variables for different components without requiring field names to be globally unique.

Set the prefix with the `env_prefix` parameter on `SettingsParameters`:

```python
import os
from mountainash_settings import MountainAshBaseSettings, SettingsParameters

class CacheSettings(MountainAshBaseSettings):
    host: str = "localhost"
    port: int = 6379

os.environ["CACHE_host"] = "cache.internal"
os.environ["CACHE_port"] = "6380"

params = SettingsParameters.create(settings_class=CacheSettings, env_prefix="CACHE_")
settings = CacheSettings(settings_parameters=params)
print(settings.host, settings.port)
# cache.internal 6380
print(settings.SETTINGS_SOURCE_ENV_PREFIX)
# CACHE_
```

<!-- concept:21 -->
## Config files parameter

The `config_files` parameter declares which configuration files an instance loads. It accepts a single path string, a `UPath` object, a list of paths, or a tuple of paths. The package sorts the paths by extension and checks that each file exists.

```python
import tempfile
from pathlib import Path
from upath import UPath
from mountainash_settings import MountainAshBaseSettings

class PipelineSettings(MountainAshBaseSettings):
    name: str = "default"
    mode: str = "dev"

with tempfile.TemporaryDirectory() as tmp:
    base = Path(tmp) / "base.yaml"
    base.write_text("name: base\nmode: staging\n")
    overrides = UPath(tmp) / "overrides.toml"
    overrides.write_text('mode = "prod"\n')

    s = PipelineSettings(config_files=[str(base), overrides])
    print(s.name, s.mode)
    # base staging
```

Strings and `UPath` objects can be mixed, and each keeps the form it was given (see [UPath config paths](../04-file-handling-kwargs-and-field-templating/index.md#upath-config-paths)). Path normalisation calls `expanduser()`, so config paths are documented for local paths only. Remote paths are not supported and raise `NotImplementedError`.

When several files are given, the source priority above decides between file types: dotenv, then YAML, then TOML, then JSON. In the example, `mode` comes from the YAML file because YAML outranks TOML, while `name` comes from the only file that sets it. Within one type, files are kept in the order given. Because structured sources deep-merge, a later-listed file overrides the leaf values of an earlier-listed one, and keys defined only in earlier files are retained.

## Meta-field traceability

After construction, the instance carries value-free source facts that help diagnose configuration setup:

- `SETTINGS_CLASS`: the Python class used for construction
- `SETTINGS_CLASS_NAME`: the class name as a string
- `SETTINGS_SOURCE_ENV_FILES`: which `.env` files were loaded
- `SETTINGS_SOURCE_ENV_PREFIX`: the environment variable prefix applied
- `SETTINGS_SOURCE_YAML_FILES`: which YAML files were loaded
- `SETTINGS_SOURCE_TOML_FILES`: which TOML files were loaded
- `SETTINGS_SOURCE_JSON_FILES`: which JSON files were loaded
- `SETTINGS_SOURCE_KWARG_NAMES`: names of the accepted attribute inputs, in deterministic order
- `SETTINGS_SOURCE_SECRETS_DIR`: the secrets directory path

None of these fields holds a constructor value, so they are safe to include in normal diagnostics. The bound `secret_store` is not exposed as a public field and does not appear in `model_dump()`, `repr()` or the source facts.

Domain fields remain ordinary model data. Use `SecretStr` for Pydantic's normal masking, and do not treat `model_dump()` as a redactor for arbitrary secrets. Code that deliberately needs reconstruction can call `extract_settings_parameters()` in a trusted context.
