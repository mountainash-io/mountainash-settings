---
title: MountainAsh Base Settings
description: The core MountainAshBaseSettings class covering model config, post-init lifecycle, source customization, validation invariants, source priority, and environment prefix overrides.
generated_by: claude skill chapter-content-generator
date: 2026-06-03
version: 0.08
---

# MountainAsh Base Settings

`MountainAshBaseSettings` is the base class for every settings class in the package. It extends Pydantic's `BaseSettings` with a custom model config, a post-init lifecycle for template resolution and secrets, a customized source chain, the `validate_assignment` invariant (with a deliberate `object.__setattr__` bypass for framework bookkeeping), a defined source priority, environment prefix overrides, and config file declarations.

---

## The Central Abstraction

The `MountainAshBaseSettings` class is the single most important type in the framework. Every settings class -- whether for database connections, API clients, application configuration, or connection profiles -- inherits from this class. It extends Pydantic's `BaseSettings` with five capabilities that standard `BaseSettings` does not provide: multi-format file loading, template expansion, secrets resolution, a structured caching layer, and a unified parameter interface.

Before construction reaches Pydantic's `BaseSettings.__init__`, `MountainAshBaseSettings` creates and merges a `SettingsParameters` object, separates and validates config files, privately captures accepted attribute inputs in source form, resolves secret references for live validation, and sets up this invocation's file sources. After construction completes, it records value-free source facts for diagnostics and runs a post-init lifecycle hook.

<!-- concept:13 -->
<!-- concept:14 -->
## MountainAshBaseSettings Class

The class declares `SETTINGS_SOURCE_` meta-fields that record value-free provenance such as files, environment prefix, secrets directory, and accepted input names. These fields support diagnostics without publishing a second tree of constructor values.

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

The class also provides a `get_settings()` class method that integrates with the caching layer, and an `extract_settings_parameters()` instance method that returns a fresh, source-form reconstruction handle for trusted code. It is not a general diagnostics export and performs no source or backend reads. When a selected secret store is a `SecretWriter`, `persist()` writes a local record through it, and `persist_key()` derives its default key; see the [secrets chapter](../05-secrets-resolution/index.md).

#### Diagram: MountainAshBaseSettings Construction Pipeline

<iframe src="../../sims/base-settings-pipeline/main.html" width="100%" height="550px" scrolling="no"></iframe>
<details markdown="1">
<summary>MountainAshBaseSettings Construction Pipeline</summary>
Type: workflow
**sim-id:** base-settings-pipeline<br/>
**Library:** vis-network<br/>
**Status:** Specified

A directed graph showing the construction pipeline: input (config_files, settings_parameters, kwargs) flows through `SettingsParameters.create()`, `merge()`, `FileHandler.separate_config_files()`, `validate_config_files_exist()`, private source-form capture, `resolve_references_in_dict()`, `super().__init__()`, value-free metadata publication, `resolve_references_in_model_tree()`, and finally `post_init()`. Each node is clickable to show what happens at that stage. Edges are labeled with the data flowing between stages. 
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

<!-- concept:15 -->
## Post Init Lifecycle

The **post-init lifecycle** is a hook method called `post_init()` that runs after all settings have been loaded, validated, and persisted to the instance. This hook is where template expansion occurs -- fields whose values depend on other fields are resolved here, after all source values have been established.

The base implementation of `post_init()` in `MountainAshBaseSettings` is intentionally empty. It serves as an extension point that subclasses override to implement their specific initialization logic. The `AppSettings` class, for example, uses `post_init()` to expand its `RUNDATETIME` field from a template that references `RUNDATE` and `RUNTIME`.

The lifecycle ordering is critical:

1. `SettingsParameters` are created and merged.
2. Config files are separated and validated.
3. Accepted attribute inputs are captured privately in source form.
4. Secret references in the validation kwargs are resolved (first pass).
5. `BaseSettings.__init__` runs (loads env vars, files, applies kwargs).
6. Value-free source facts and accepted input names are published; the reconstruction recipe remains private.
7. Secret references in the model tree are resolved (second pass).
8. `post_init()` runs — templates expand here.

This ordering keeps a backend reference out of public provenance while preserving it for controlled reconstruction. When `post_init()` executes, all live field values from all sources are available for template interpolation. A template like `"{RUNDATE}T{RUNTIME}"` can safely reference both fields because they were populated in step 5.


<!-- concept:16 -->
## Source Customization

mountainash-settings customizes the Pydantic settings source chain by overriding `settings_customise_sources()`. This class method controls which configuration sources are consulted and in what order. The default implementation adds YAML, TOML, and JSON file sources that standard `BaseSettings` does not provide.

The customized source chain (built by the shared `_cache_default_sources()` helper, so direct construction and cached retrieval use the same order) is:

1. **Init settings** -- values passed as kwargs to the constructor
2. **Environment settings** -- values from environment variables
3. **Dotenv settings** -- values from `.env` files, using the configured environment prefix
4. **Unprefixed dotenv settings** -- the same `.env` files read again with no prefix
5. **YAML config** -- values from `.yaml` / `.yml` files
6. **TOML config** -- values from `.toml` files
7. **JSON config** -- values from `.json` files
8. **File secret settings** -- values from a secrets directory

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
    # The shared helper returns the chain listed above:
    return (
        init_settings,
        env_settings,
        dotenv_settings,
        unprefixed_dotenv_settings,  # same env files, env_prefix=""
        YamlConfigSettingsSource(settings_cls, deep_merge=True),
        TomlConfigSettingsSource(settings_cls, deep_merge=True),
        JsonConfigSettingsSource(settings_cls, deep_merge=True),
        file_secret_settings,
    )
```

The snippet condenses `_cache_default_sources()`; the hook itself delegates to it. Sources earlier in the tuple take precedence over later ones. This means explicitly passed kwargs always win, environment variables override file-based config, and file-based config overrides the secrets directory. The YAML, TOML and JSON sources use `deep_merge=True`, so nested mappings from several files of the same type merge key by key rather than the last file replacing whole sections.

During direct construction, the YAML, TOML and JSON paths for that invocation travel through an invocation-local source frame, not through `model_config`. The class-level `model_config` is shared and is never mutated by construction.

<!-- concept:114 -->
## Cache-Safe Settings Sources

`settings_customise_sources()` only governs direct construction. Cached retrieval through `get_settings()` does not invoke it: the cache builds the configured sources itself so that a customization hook is never run implicitly. Two things follow for classes that change the source chain:

- **`settings_capture_sources(cls, sources)`** is the cache-safe hook. The base implementation returns `sources` unchanged; a subclass overrides it to declare the source order the cache should use. A class that overrides `settings_customise_sources()` without also overriding `settings_capture_sources()` is rejected at cached retrieval with a `ValueError`.
- **`CacheableSettingsSource`** (exported from `mountainash_settings`) is the base class a custom source must extend to take part in cached retrieval. It requires `capture()`, which reads the source's structural values once, and a static `project()`, which returns terminal values for each materialization without performing I/O. Custom sources that are not `CacheableSettingsSource` instances are rejected by cached retrieval; the built-in sources are handled by the cache directly.

Direct construction is unaffected by this restriction. For how structural contexts are captured and reused, see the [caching chapter](../09-caching-settings-management-and-app-settings/index.md).

<!-- concept:17 -->
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

<!-- concept:18 -->
## Object Setattr Bypass

The **object setattr bypass** is a deliberate exception to the validate_assignment invariant. Meta-fields (those prefixed with `SETTINGS_SOURCE_`) are populated using `object.__setattr__()` rather than the normal `setattr()` mechanism. This bypasses Pydantic's validation pipeline entirely.

```python
# These assignments bypass validation intentionally:
object.__setattr__(self, "SETTINGS_SOURCE_KWARG_NAMES", accepted_input_names)
object.__setattr__(self, "SETTINGS_CLASS", local_settings_params.settings_class)
object.__setattr__(self, "SETTINGS_CLASS_NAME", ...)
```

The bypass exists for two reasons. First, meta-fields contain framework bookkeeping (class references, file lists, and accepted input names) that is not user-facing configuration and should not pass through field validators designed for domain values. Second, the bypass skips `__pydantic_fields_set__` tracking, keeping this bookkeeping separate from domain-field assignment. The source-form reconstruction recipe is private and is never assigned to a public meta-field.

!!! warning "When to use object.__setattr__"
    The bypass pattern should only be used for framework-internal bookkeeping fields. User-facing configuration fields must always go through normal assignment to maintain the validate_assignment invariant. Misusing the bypass on domain fields would silently break type safety.

<!-- concept:19 -->
## Settings Source Priority

The **settings source priority** defines which configuration source wins when the same field is defined in multiple places. mountainash-settings follows a clear precedence hierarchy where more specific, more explicit sources override less specific ones:

1. **Constructor kwargs** (highest priority -- explicit always wins)
2. **Environment variables** (runtime environment)
3. **Dotenv files** (`.env`, read with the configured prefix -- environment-like but file-based)
4. **Unprefixed dotenv files** (the same `.env` files read with no prefix)
5. **YAML files** (structured config)
6. **TOML files** (structured config)
7. **JSON files** (structured config)
8. **Secrets directory** (lowest file priority)
9. **Field defaults** (lowest priority -- fallback only)

This ordering reflects a practical philosophy: the closer a value is to the code invoking it, the higher its priority. A developer passing `debug=True` as a kwarg should always win over a YAML file that says `debug: false`. An environment variable set by a deployment tool should override what is checked into version control.

#### Diagram: Source Priority Waterfall

<iframe src="../../sims/source-priority-waterfall/main.html" width="100%" height="500px" scrolling="no"></iframe>
<details markdown="1">
<summary>Source Priority Waterfall</summary>
Type: infographic
**sim-id:** source-priority-waterfall<br/>
**Library:** p5.js<br/>
**Status:** Specified

A vertical waterfall diagram showing the 9 priority levels from highest (top) to lowest (bottom). Each level is a colored horizontal bar with the source name. An interactive "value" token can be dragged to any level -- when released, the diagram shows which levels would be checked and which would be skipped based on the priority ordering. A field name dropdown lets the user select different fields to see which sources supply values for that field.
</details>

<!-- concept:20 -->
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

<!-- concept:21 -->
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

# UPath objects are accepted alongside strings
from upath import UPath
settings = MySettings(config_files=[
    UPath("./config/base.yaml"),
    UPath("./local.env")
])
```

The config_files parameter accepts strings and `UPath` objects, and preserves the form it was given (see [UPath Config Paths](../04-file-handling-kwargs-and-field-templating/index.md#upath-config-paths)). Path normalisation calls `expanduser()`, so it is documented for local paths only.

When multiple files are provided, they are processed according to the source priority chain. Priority between files of different types is determined by the source type (env > dotenv > yaml > toml > json). Within the same type, files are grouped without being reordered, and because structured sources deep-merge, a later-listed file overrides the leaf values of an earlier-listed one while keys defined only in earlier files are retained.

#### Diagram: Config Files Processing Flow

<iframe src="../../sims/config-files-processing/main.html" width="100%" height="450px" scrolling="no"></iframe>
<details markdown="1">
<summary>Config Files Processing Flow</summary>
Type: workflow
**sim-id:** config-files-processing<br/>
**Library:** vis-network<br/>
**Status:** Specified

A directed graph showing how a list of mixed config files flows through the processing pipeline: input list enters FileHandler.separate_config_files(), which dispatches to FileTypeRegistry.identify() for each file, groups them into SettingsFiles(env_files, yaml_files, toml_files, json_files), validates existence, and then hands the groups to the settings sources for this invocation: the env files go to the `_env_file` init parameter, and the YAML, TOML and JSON files go through the invocation-local source frame (the class `model_config` is not modified). Clicking on a file type node shows example file content.
</details>

## Meta-Field Traceability

After construction completes, the instance carries value-free source facts that help diagnose configuration setup:

- `SETTINGS_CLASS` — the Python class used for construction
- `SETTINGS_CLASS_NAME` — the class name as a string
- `SETTINGS_SOURCE_ENV_FILES` — which `.env` files were loaded
- `SETTINGS_SOURCE_ENV_PREFIX` — the environment variable prefix applied
- `SETTINGS_SOURCE_YAML_FILES` — which YAML files were loaded
- `SETTINGS_SOURCE_TOML_FILES` — which TOML files were loaded
- `SETTINGS_SOURCE_JSON_FILES` — which JSON files were loaded
- `SETTINGS_SOURCE_KWARG_NAMES` — accepted attribute-input names, in deterministic order
- `SETTINGS_SOURCE_SECRETS_DIR` — the secrets directory path

`SETTINGS_SOURCE_KWARGS` no longer exists and has no replacement raw-value
field. The bound `secret_store` is never a public `SETTINGS_SOURCE_*` field —
it lives on a private attribute so it never appears in `model_dump()`, `repr()`
or provenance diagnostics. Source facts may appear in normal diagnostics because they contain no
constructor value tree. Domain fields remain intentional model data: use
`SecretStr` for Pydantic's normal masking, and do not treat `model_dump()` as
an arbitrary-secret redactor. Code that deliberately needs reconstruction can
call `extract_settings_parameters()` in a trusted context.

#### Diagram: MountainAshBaseSettings Class Structure

<iframe src="../../sims/base-settings-class-structure/main.html" width="100%" height="500px" scrolling="no"></iframe>
<details markdown="1">
<summary>MountainAshBaseSettings Class Structure</summary>
Type: diagram
**sim-id:** base-settings-class-structure<br/>
**Library:** vis-network<br/>
**Status:** Specified

A UML-style class diagram showing MountainAshBaseSettings inheriting from BaseSettings. The class box is divided into three sections: meta-fields (SETTINGS_SOURCE_*), constructor parameters, and methods (post_init, get_settings, extract_settings_parameters, init_setting_from_template, format_template_from_settings, update_settings_from_dict, settings_customise_sources, __hash__). Hovering over each method shows its docstring. Clicking on the inheritance arrow shows which methods are inherited vs overridden.
</details>
