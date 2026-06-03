---
title: MountainAsh Base Settings
description: The core MountainAshBaseSettings class covering model config, post-init lifecycle, source customization, validation invariants, source priority, and environment prefix overrides.
generated_by: claude skill chapter-content-generator
date: 2026-06-03
version: 0.08
---

# MountainAsh Base Settings

## Summary

This chapter covers the core MountainAshBaseSettings class that forms the heart of the framework. You will learn how it extends Pydantic BaseSettings with a custom model config, a post-init lifecycle for template resolution and secrets, source customization for controlling where configuration is loaded from, the validate_assignment invariant with its object setattr bypass, settings source priority ordering, environment prefix overrides, and config file parameter declarations.

## Concepts Covered

- MountainAshBaseSettings Class
- Settings Model Config
- Post Init Lifecycle
- Source Customization
- Validate Assignment Invariant
- Object Setattr Bypass
- Settings Source Priority
- Env Prefix Override
- Config Files Parameter

## Prerequisites

- Chapter 1: Pydantic and Configuration Foundations

---

## The Central Abstraction

The `MountainAshBaseSettings` class is the single most important type in the framework. Every settings class you define -- whether for database connections, API clients, application configuration, or connection profiles -- inherits from this class. It extends Pydantic's `BaseSettings` with five capabilities that standard `BaseSettings` does not provide: multi-format file loading, template expansion, secrets resolution, a structured caching layer, and a unified parameter interface.

Before construction even reaches Pydantic's `BaseSettings.__init__`, `MountainAshBaseSettings` performs extensive pre-processing: it creates a `SettingsParameters` object, separates config files by type, validates their existence, resolves secret references in kwargs, and configures the model's file sources. After construction completes, it records metadata for traceability and runs a post-init lifecycle hook.

## MountainAshBaseSettings Class

The class inherits directly from `pydantic_settings.BaseSettings` and declares a set of meta-fields prefixed with `SETTINGS_SOURCE_` that record the provenance of every configuration value. These meta-fields enable debugging and traceability -- you can inspect any settings instance to determine exactly which files, environment prefix, and kwargs were used to construct it.

The constructor signature accepts three positional-style parameters beyond the standard `**kwargs`:

- `config_files` -- a path, list of paths, or tuple of paths to configuration files
- `settings_parameters` -- an optional pre-built `SettingsParameters` instance to merge with
- `template_settings_parameters` -- optional parameters for template resolution

```python
from mountainash_settings import MountainAshBaseSettings
from pydantic import Field

class MyAppSettings(MountainAshBaseSettings):
    database_host: str = Field(default="localhost")
    database_port: int = Field(default=5432)
    debug: bool = Field(default=False)

# Instantiate with a config file and runtime overrides
settings = MyAppSettings(
    config_files=["config.yaml", ".env"],
    debug=True
)
```

The class also provides a `get_settings()` class method that integrates with the caching layer, and an `extract_settings_parameters()` instance method that reconstructs the `SettingsParameters` used to build the instance -- enabling round-trip parameter extraction for replication or debugging.

#### Diagram: MountainAshBaseSettings Construction Pipeline

<iframe src="../../sims/base-settings-pipeline/main.html" width="100%" height="550px" scrolling="no"></iframe>
<details markdown="1">
<summary>MountainAshBaseSettings Construction Pipeline</summary>
Type: workflow
**sim-id:** base-settings-pipeline<br/>
**Library:** vis-network<br/>
**Status:** Specified

A directed graph showing the construction pipeline: input (config_files, settings_parameters, kwargs) flows through SettingsParameters.create(), merge(), FileHandler.separate_config_files(), validate_config_files_exist(), resolve_references_in_dict(), super().__init__(), object.__setattr__ (meta-fields), resolve_references_in_model_tree(), and finally post_init(). Each node is clickable to show what happens at that stage. Edges are labeled with the data flowing between stages. Learning objective: Trace the complete construction pipeline of a MountainAshBaseSettings instance (Bloom: Analyze).
</details>

## Settings Model Config

The `model_config` attribute is declared as a `SettingsConfigDict` with four key settings that establish the behavioral contract for every settings class in the framework:

```python
model_config = SettingsConfigDict(
    extra="ignore",
    validate_default=False,
    arbitrary_types_allowed=True,
    validate_assignment=True,
)
```

Each setting serves a specific architectural purpose:

| Config Key | Value | Architectural Purpose |
|-----------|-------|----------------------|
| `extra` | `"ignore"` | Allows config files to contain fields not declared on the class without raising errors |
| `validate_default` | `False` | Avoids validating `Field(default=None)` declarations that serve as placeholders |
| `arbitrary_types_allowed` | `True` | Permits `UPath`, custom enums, and other non-standard types as field annotations |
| `validate_assignment` | `True` | Ensures type safety is maintained when fields are modified after construction |

The `extra="ignore"` setting is particularly important for forward compatibility. Configuration files often evolve faster than the code that reads them -- a shared YAML file might contain fields intended for multiple services. By ignoring extras rather than raising errors, mountainash-settings allows graceful degradation.

## Post Init Lifecycle

The **post-init lifecycle** is a hook method called `post_init()` that runs after all settings have been loaded, validated, and persisted to the instance. This hook is where template expansion occurs -- fields whose values depend on other fields are resolved here, after all source values have been established.

The base implementation of `post_init()` in `MountainAshBaseSettings` is intentionally empty. It serves as an extension point that subclasses override to implement their specific initialization logic. The `AppSettings` class, for example, uses `post_init()` to expand its `RUNDATETIME` field from a template that references `RUNDATE` and `RUNTIME`.

The lifecycle ordering is critical:

1. `SettingsParameters` are created and merged
2. Config files are separated and validated
3. Secret references in kwargs are resolved (first pass)
4. `BaseSettings.__init__` runs (loads env vars, files, applies kwargs)
5. Meta-fields are recorded via `object.__setattr__`
6. Secret references in the model tree are resolved (second pass)
7. `post_init()` runs -- templates expand here

This ordering guarantees that when `post_init()` executes, all field values from all sources are available for template interpolation. A template like `"{RUNDATE}T{RUNTIME}"` can safely reference both fields because they were populated in step 4.

## Source Customization

mountainash-settings customizes the Pydantic settings source chain by overriding `settings_customise_sources()`. This class method controls which configuration sources are consulted and in what order. The default implementation adds YAML, TOML, and JSON file sources that standard `BaseSettings` does not provide.

The customized source chain is:

1. **Init settings** -- values passed as kwargs to the constructor
2. **Environment settings** -- values from environment variables
3. **Dotenv settings** -- values from `.env` files
4. **YAML config** -- values from `.yaml` / `.yml` files
5. **TOML config** -- values from `.toml` files
6. **JSON config** -- values from `.json` files
7. **File secret settings** -- values from a secrets directory

```python
@classmethod
def settings_customise_sources(
    cls,
    settings_cls: Type[BaseSettings],
    init_settings: PydanticBaseSettingsSource,
    env_settings: PydanticBaseSettingsSource,
    dotenv_settings: PydanticBaseSettingsSource,
    file_secret_settings: PydanticBaseSettingsSource,
) -> Tuple[PydanticBaseSettingsSource, ...]:
    return (
        init_settings,
        env_settings,
        dotenv_settings,
        YamlConfigSettingsSource(settings_cls),
        TomlConfigSettingsSource(settings_cls),
        JsonConfigSettingsSource(settings_cls),
        file_secret_settings,
    )
```

Sources earlier in the tuple take precedence over later ones. This means explicitly passed kwargs always win, environment variables override file-based config, and file-based config overrides the secrets directory.

## Validate Assignment Invariant

The **validate_assignment invariant** is established by setting `validate_assignment=True` in the model config. This ensures that every field assignment after construction passes through Pydantic's full validation pipeline -- including type coercion, `SecretStr` wrapping, enum coercion, and any declared `AfterValidator` transforms.

Without this invariant, you could bypass type safety by assigning a raw string to a `SecretStr` field after construction:

```python
# With validate_assignment=True (mountainash-settings default):
settings.api_key = "raw-secret"
# Pydantic wraps it: settings.api_key is now SecretStr('**********')

# Without validate_assignment (hypothetical):
settings.api_key = "raw-secret"
# Field holds a plain str -- SecretStr contract is violated
```

This invariant is the reason why mountainash-settings can guarantee type safety throughout the entire lifecycle of a settings instance, not just at construction time. Any code that mutates settings -- whether the `update_settings_from_dict()` method, runtime overrides, or direct assignment -- benefits from the same validation pipeline that runs during `__init__`.

## Object Setattr Bypass

The **object setattr bypass** is a deliberate exception to the validate_assignment invariant. Meta-fields (those prefixed with `SETTINGS_SOURCE_`) are populated using `object.__setattr__()` rather than the normal `setattr()` mechanism. This bypasses Pydantic's validation pipeline entirely.

```python
# These assignments bypass validation intentionally:
object.__setattr__(self, "SETTINGS_SOURCE_KWARGS", valid_attribute_kwargs)
object.__setattr__(self, "SETTINGS_CLASS", local_settings_params.settings_class)
object.__setattr__(self, "SETTINGS_CLASS_NAME", ...)
```

The bypass exists for two reasons. First, meta-fields contain internal bookkeeping data (class references, file lists) that is not user-facing configuration and should not pass through field validators designed for domain values. Second, the bypass also skips `__pydantic_fields_set__` tracking, which means meta-fields do not appear in `model_dump(exclude_unset=True)` -- they are infrastructure, not model state.

!!! warning "When to use object.__setattr__"
    The bypass pattern should only be used for framework-internal bookkeeping fields. User-facing configuration fields must always go through normal assignment to maintain the validate_assignment invariant. Misusing the bypass on domain fields would silently break type safety.

## Settings Source Priority

The **settings source priority** defines which configuration source wins when the same field is defined in multiple places. mountainash-settings follows a clear precedence hierarchy where more specific, more explicit sources override less specific ones:

1. **Constructor kwargs** (highest priority -- explicit always wins)
2. **Environment variables** (runtime environment)
3. **Dotenv files** (`.env` -- environment-like but file-based)
4. **YAML files** (structured config)
5. **TOML files** (structured config)
6. **JSON files** (structured config)
7. **Secrets directory** (lowest file priority)
8. **Field defaults** (lowest priority -- fallback only)

This ordering reflects a practical philosophy: the closer a value is to the code invoking it, the higher its priority. A developer passing `debug=True` as a kwarg should always win over a YAML file that says `debug: false`. An environment variable set by a deployment tool should override what is checked into version control.

#### Diagram: Source Priority Waterfall

<iframe src="../../sims/source-priority-waterfall/main.html" width="100%" height="500px" scrolling="no"></iframe>
<details markdown="1">
<summary>Source Priority Waterfall</summary>
Type: infographic
**sim-id:** source-priority-waterfall<br/>
**Library:** p5.js<br/>
**Status:** Specified

A vertical waterfall diagram showing the 8 priority levels from highest (top) to lowest (bottom). Each level is a colored horizontal bar with the source name. An interactive "value" token can be dragged to any level -- when released, the diagram shows which levels would be checked and which would be skipped based on the priority ordering. A field name dropdown lets the user select different fields to see which sources supply values for that field. Learning objective: Predict which configuration source will supply a field's value given multiple conflicting definitions (Bloom: Apply).
</details>

## Env Prefix Override

The **env prefix override** allows each settings class to scope its environment variable lookups to a specific prefix string. Without a prefix, a field named `host` reads the environment variable `HOST`. With a prefix of `DB_`, it reads `DB_HOST` instead.

This mechanism solves a common problem in microservice architectures where multiple components share an environment (a Docker Compose file, a Kubernetes pod, a systemd unit). By assigning each settings class a unique prefix, collisions between `DATABASE_HOST`, `CACHE_HOST`, and `API_HOST` are avoided without requiring field names to be globally unique.

The prefix is specified via the `env_prefix` parameter on `SettingsParameters`:

```python
from mountainash_settings import MountainAshBaseSettings, SettingsParameters

class CacheSettings(MountainAshBaseSettings):
    host: str = "localhost"
    port: int = 6379

# Reads CACHE_HOST and CACHE_PORT from environment
params = SettingsParameters.create(
    settings_class=CacheSettings,
    env_prefix="CACHE_"
)
settings = CacheSettings(settings_parameters=params)
```

The prefix is passed through to Pydantic's `_env_prefix` init parameter, which handles the actual environment variable lookup logic.

## Config Files Parameter

The **config files parameter** is the primary mechanism for declaring which configuration files a settings instance should load. It accepts a flexible set of input types -- a single path string, a `UPath` object, a list of paths, or a tuple of paths -- and processes them through the `FileHandler` to separate, validate, and categorize them by extension.

```python
# Single file
settings = MySettings(config_files="config.yaml")

# Multiple files in different formats
settings = MySettings(config_files=[
    "base.yaml",
    "overrides.toml",
    ".env"
])

# Using UPath for cloud-compatible paths
from upath import UPath
settings = MySettings(config_files=[
    UPath("s3://my-bucket/config.yaml"),
    UPath("./local.env")
])
```

The config_files parameter supports the `UPath` universal path type, which means configuration files can reside on local filesystems, S3 buckets, GCS, Azure Blob Storage, or any filesystem that `fsspec` supports. This is a significant capability for cloud-native applications that store configuration in object storage.

When multiple files are provided, they are processed according to the source priority chain. A value defined in an earlier-listed YAML file does not necessarily win over a later-listed one -- instead, the priority is determined by the source type (env > dotenv > yaml > toml > json). Within the same source type, files are loaded in the order provided.

#### Diagram: Config Files Processing Flow

<iframe src="../../sims/config-files-processing/main.html" width="100%" height="450px" scrolling="no"></iframe>
<details markdown="1">
<summary>Config Files Processing Flow</summary>
Type: workflow
**sim-id:** config-files-processing<br/>
**Library:** vis-network<br/>
**Status:** Specified

A directed graph showing how a list of mixed config files flows through the processing pipeline: input list enters FileHandler.separate_config_files(), which dispatches to FileTypeRegistry.identify() for each file, groups them into SettingsFiles(env_files, yaml_files, toml_files, json_files), validates existence, and then assigns each group to the appropriate model_config key or BaseSettings init parameter. Clicking on a file type node shows example file content. Learning objective: Trace how mixed configuration file inputs are categorized and routed to the correct Pydantic settings source (Bloom: Analyze).
</details>

## Meta-Field Traceability

After construction completes, the instance carries a full record of how it was built. These meta-fields are invaluable for debugging configuration issues in production:

- `SETTINGS_CLASS` -- the Python class used for construction
- `SETTINGS_CLASS_NAME` -- the class name as a string
- `SETTINGS_SOURCE_ENV_FILES` -- which `.env` files were loaded
- `SETTINGS_SOURCE_ENV_PREFIX` -- the environment variable prefix applied
- `SETTINGS_SOURCE_YAML_FILES` -- which YAML files were loaded
- `SETTINGS_SOURCE_TOML_FILES` -- which TOML files were loaded
- `SETTINGS_SOURCE_JSON_FILES` -- which JSON files were loaded
- `SETTINGS_SOURCE_KWARGS` -- the attribute kwargs that were applied
- `SETTINGS_SOURCE_SECRETS_DIR` -- the secrets directory path
- `SETTINGS_SOURCE_SECRETS_PROVIDER` -- the registered secrets provider name

Because these fields are set via `object.__setattr__`, they do not appear in `model_fields_set` and are excluded from `model_dump(exclude_unset=True)`. This means serializing a settings instance for API responses or logs produces only the domain fields, while the meta-fields remain accessible for infrastructure tooling.

#### Diagram: MountainAshBaseSettings Class Structure

<iframe src="../../sims/base-settings-class-structure/main.html" width="100%" height="500px" scrolling="no"></iframe>
<details markdown="1">
<summary>MountainAshBaseSettings Class Structure</summary>
Type: diagram
**sim-id:** base-settings-class-structure<br/>
**Library:** vis-network<br/>
**Status:** Specified

A UML-style class diagram showing MountainAshBaseSettings inheriting from BaseSettings. The class box is divided into three sections: meta-fields (SETTINGS_SOURCE_*), constructor parameters, and methods (post_init, get_settings, extract_settings_parameters, init_setting_from_template, format_template_from_settings, update_settings_from_dict, settings_customise_sources, __hash__). Hovering over each method shows its docstring. Clicking on the inheritance arrow shows which methods are inherited vs overridden. Learning objective: Identify the structural components and extension points of MountainAshBaseSettings (Bloom: Understand).
</details>

## Key Takeaways

- **MountainAshBaseSettings** is the framework's central class, extending Pydantic BaseSettings with file loading, templates, secrets, and caching.
- **Settings Model Config** establishes `validate_assignment=True` and `extra="ignore"` as the behavioral contract for all settings classes.
- **Post Init Lifecycle** provides a hook after all sources are loaded, enabling template expansion that safely references other fields.
- **Source Customization** adds YAML, TOML, and JSON sources to the standard BaseSettings source chain.
- **Validate Assignment Invariant** guarantees type safety on every field mutation, not just at construction.
- **Object Setattr Bypass** is reserved exclusively for internal meta-fields that should not trigger validation or appear in model dumps.
- **Settings Source Priority** follows a clear hierarchy: explicit kwargs beat environment variables, which beat file-based config, which beats defaults.
- **Env Prefix Override** scopes environment variable lookups to prevent collisions between multiple settings classes in shared environments.
