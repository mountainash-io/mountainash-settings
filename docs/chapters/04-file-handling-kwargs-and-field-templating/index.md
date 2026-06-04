---
title: File Handling, Kwargs, and Field Templating
description: How mountainash-settings loads configuration from files and kwargs, and how field values reference other fields via templates with resolution during post-init.
generated_by: claude skill chapter-content-generator
date: 2026-06-03
version: 0.08
---

# File Handling, Kwargs, and Field Templating

## Summary

This chapter covers how mountainash-settings loads configuration from files and keyword arguments, and how field values can reference other fields via templates. You will learn about the FileHandler class with its extension-based dispatch and file categorization, the KwargsHandler for normalizing keyword arguments, multi-format file loading that ties everything together, and the template system including syntax, field name placeholders, resolution during post-init, UPath path derivation, priority rules, and nested template resolution.

## Concepts Covered

- FileHandler Class
- File Extension Dispatch
- File Categorization
- KwargsHandler Class
- Kwargs Normalization
- Multi Format File Loading
- Template Syntax
- Field Name Placeholder
- Template Resolution
- Post Init Template Expansion
- UPath Path Derivation
- Template Priority Rules
- Nested Template Resolution

## Prerequisites

- Chapter 2: MountainAsh Base Settings
- Chapter 3: Settings Parameters and Merge Strategies

---

<!-- concept:38 -->
## From Raw Input to Validated Fields

When a caller passes `config_files=["base.yaml", ".env", "overrides.toml"]` alongside keyword arguments like `debug=True`, the framework must route each input to the correct processing pipeline. File paths need to be categorized by extension and handed to the matching Pydantic settings source. Keyword arguments need to be separated into Pydantic-internal parameters, model config overrides, and user-facing attribute values. This chapter covers the two handler classes that perform this routing, the multi-format loading mechanism that ties them together, and the template system that derives field values from other fields.

<!-- concept:32 -->
<!-- concept:35 -->
## FileHandler Class

The `SettingsFileHandler` class is a stateless utility (all methods are class methods or static methods) that manages the lifecycle of configuration file paths: normalization, classification, validation, deduplication, and format conversion.

The class provides six key operations:

- `separate_config_files()` -- the main entry point that takes a mixed file list and returns a `SettingsFiles` named tuple
- `identify_file_extension()` -- determines the type of a single file
- `group_files_by_type()` -- groups a list of files into buckets by extension
- `validate_config_files_exist()` -- raises `FileNotFoundError` for missing files
- `deduplicate_files()` -- removes duplicates while preserving order
- `format_config_file_tuple()` / `format_config_file_list()` -- normalization helpers

The output container is the `SettingsFiles` named tuple, which provides typed access to each file category:

```python
class SettingsFiles(NamedTuple):
    env_files:  Optional[List[Union[UPath, str]]] = None
    yaml_files: Optional[List[Union[UPath, str]]] = None
    toml_files: Optional[List[Union[UPath, str]]] = None
    json_files: Optional[List[Union[UPath, str]]] = None
```

The handler accepts flexible input types (single path, list, tuple, or None) and normalizes them consistently. This design means callers never need to pre-process their file paths -- the handler accommodates whatever shape the data arrives in.

<!-- concept:33 -->
## File Extension Dispatch

**File extension dispatch** is the mechanism by which the handler determines what type of configuration a file contains. The `FileTypeRegistry` class maintains a mapping from file extensions to logical file types:

```python
class FileTypeRegistry:
    _registry = {
        'env':  FileType.ENV,
        'yaml': FileType.YAML,
        'yml':  FileType.YAML,
        'toml': FileType.TOML,
        'json': FileType.JSON
    }
```

The `identify()` method handles two distinct cases. For regular files with extensions (like `config.yaml`), it strips the leading dot from the suffix and looks up the extension in the registry. For dotfiles (like `.env`), it detects that the filename starts with a dot and contains no other dots, then uses the name minus the leading dot as the lookup key.

| Input Path | Detection Method | Resolved Type |
|-----------|-----------------|---------------|
| `config.yaml` | Extension: `.yaml` | YAML |
| `settings.yml` | Extension: `.yml` | YAML |
| `app.toml` | Extension: `.toml` | TOML |
| `data.json` | Extension: `.json` | JSON |
| `.env` | Dotfile: `env` | ENV |
| `.env.local` | Extension: `.local` | Unknown |

The registry is extensible via `register_type()`, allowing applications to add support for custom file extensions without modifying the handler itself.

<!-- concept:34 -->
## File Categorization

**File categorization** is the process of sorting a mixed list of configuration files into their respective type buckets. The `separate_config_files()` method orchestrates this in four steps:

1. Normalize the input to a list of `UPath` objects (expanding `~` home directory references)
2. Group files by type using `group_files_by_type()`
3. Deduplicate each group while preserving order
4. Return a `SettingsFiles` named tuple with the four categories

```python
# Input: mixed file list
files = ["base.yaml", "secrets.env", "overrides.toml", "base.yaml"]

# Output: categorized and deduplicated
result = SettingsFileHandler.separate_config_files(files)
<!-- concept:41 -->
# result.yaml_files == [UPath("base.yaml")]  (deduplicated)
# result.env_files  == [UPath("secrets.env")]
# result.toml_files == [UPath("overrides.toml")]
# result.json_files == None
```

After categorization, the `MountainAshBaseSettings` constructor validates that all referenced files exist on disk (or the target filesystem) by calling `validate_config_files_exist()` for each category. This fail-fast behavior catches configuration errors at construction time rather than at the point where a missing value is first accessed.

#### Diagram: File Categorization Pipeline

<iframe src="../../sims/file-categorization-pipeline/main.html" width="100%" height="450px" scrolling="no"></iframe>
<details markdown="1">
<summary>File Categorization Pipeline</summary>
Type: workflow
**sim-id:** file-categorization-pipeline<br/>
**Library:** vis-network<br/>
**Status:** Specified

A directed flow showing mixed file inputs entering a pipeline of four stages: UPath normalization, FileTypeRegistry.identify() dispatch, group_files_by_type() bucketing, and deduplicate_files() cleanup. Output flows into four colored lanes (env=green, yaml=blue, toml=purple, json=orange). Clicking a file in the input list highlights its path through the pipeline. Dragging new file names into the input area runs them through the pipeline interactively. Learning objective: Trace how a mixed file list is categorized into typed buckets by the FileHandler (Bloom: Apply).
</details>

<!-- concept:36 -->
## KwargsHandler Class

The `SettingsKwargsHandler` class normalizes keyword arguments into a consistent dictionary format. Like `SettingsFileHandler`, it is a stateless utility with class methods and static methods.

The primary method is `format_kwargs_dict()`, which accepts three input shapes -- `None`, a dictionary, or a tuple of key-value pairs -- and normalizes them:

```python
@classmethod
def format_kwargs_dict(cls,
                       p_kwargs: None | Dict[str,Any] | Tuple[Any,Any] = None
                       ) -> Optional[Dict[str,Any]]:
    if p_kwargs is None:
        return None
    if isinstance(p_kwargs, dict):
        p_kwargs = p_kwargs.get("kwargs", p_kwargs)
        return p_kwargs
    if isinstance(p_kwargs, tuple):
        p_kwargs = dict(p_kwargs)
        p_kwargs = p_kwargs.get("kwargs", p_kwargs)
        return p_kwargs
    raise ValueError(f"Invalid p_kwargs: {p_kwargs}")
```

A subtle detail is the `p_kwargs.get("kwargs", p_kwargs)` pattern. If the input dictionary itself contains a nested `"kwargs"` key, the handler unwraps it. This handles the case where kwargs have been double-wrapped during parameter passing -- a defensive measure against a common serialization artifact.

## Kwargs Normalization

**Kwargs normalization** is the broader process by which the `SettingsParameters` class separates a flat dictionary of keyword arguments into three routing destinations:

- **Pydantic model config kwargs** -- keys in `_reserved_pydantic_modelconfig_kwargs` (e.g., `extra`, `arbitrary_types_allowed`)
- **Pydantic settings kwargs** -- keys in `_reserved_pydantic_kwargs` (e.g., `_env_prefix`, `_env_file`, `_secrets_dir`)
- **Attribute settings kwargs** -- everything else that matches a field name on the target settings class

The `SettingsParameters` class provides three getter methods that implement this separation:

```python
def get_pydantic_modelconfig_kwargs(self) -> Dict[str, Any]:
    # Returns only model config overrides

def get_pydantic_settings_kwargs(self) -> Dict[str, Any]:
    # Returns only Pydantic BaseSettings init parameters

def get_attribute_settings_kwargs(self, settings_class=None) -> Dict[str, Any]:
    # Returns only user-facing field values
```

This three-way split ensures each parameter reaches its correct destination during construction. The model config kwargs update `self.model_config` before `BaseSettings.__init__` runs. The Pydantic settings kwargs are passed as named arguments to `super().__init__()`. The attribute kwargs are passed as `**valid_attribute_kwargs` to populate the instance's declared fields.

!!! tip "Debugging kwargs routing"
    If a keyword argument silently fails to populate a field, check whether it matches a key in `_reserved_pydantic_kwargs`. If so, it is being routed to Pydantic's internal machinery rather than to a field setter. Prefix it with an underscore to explicitly target the Pydantic parameter, or remove the prefix to target the field.

<!-- concept:22 -->
## Multi Format File Loading

**Multi-format file loading** is the mechanism that assigns categorized files to the correct Pydantic settings source. After the `FileHandler` produces a `SettingsFiles` tuple, the `MountainAshBaseSettings` constructor assigns each category to its destination:

```python
# YAML, TOML, JSON go through model_config
self.model_config["yaml_file"] = obj_config_files.yaml_files or None
self.model_config["toml_file"] = obj_config_files.toml_files or None
self.model_config["json_file"] = obj_config_files.json_files or None

# ENV files go through BaseSettings._env_file parameter
super().__init__(_env_file=obj_config_files.env_files, ...)
```

This split exists because Pydantic handles `.env` files differently from structured config files. The `.env` file is passed as an init parameter that the `DotEnvSettingsSource` consumes directly. Structured files (YAML, TOML, JSON) are declared on `model_config` where the corresponding `*ConfigSettingsSource` classes read them.

The result is that a single `config_files` parameter from the caller can contain any mix of file types, and each type is automatically routed to its native loading mechanism. A caller does not need to know which files are YAML versus TOML versus `.env` -- the handler figures it out from the file extensions.

<!-- concept:37 -->
<!-- concept:39 -->
<!-- concept:42 -->
<!-- concept:43 -->
## Template Syntax

The mountainash-settings **template syntax** uses Python's standard `str.format()` placeholders to reference other fields on the same settings instance. A template is a string containing one or more `{FIELD_NAME}` placeholders that will be replaced with the current value of the named field.

```python
# Template syntax uses curly braces around field names
template = "{RUNDATE}T{RUNTIME}"
# If RUNDATE="20260603" and RUNTIME="143022"
# Resolves to: "20260603T143022"
```

The syntax leverages Python's built-in `string.Formatter` class for parsing. The `_build_template_mapping()` method iterates over the parsed fields and builds a mapping dictionary by reading the current value of each referenced field from the settings instance:

```python
def _build_template_mapping(self, template_str: str) -> Dict[str, Any]:
    mapping = {}
    for _, field_name, _, _ in Formatter().parse(template_str):
        if field_name:
            if hasattr(self, field_name):
                mapping[field_name] = getattr(self, field_name)
            else:
                raise AttributeError(
                    f"The object does not have an attribute "
                    f"named '{field_name}'"
                )
    return mapping
```

If a template references a field that does not exist on the instance, an `AttributeError` is raised immediately -- templates fail fast rather than producing silently incorrect values.

## Field Name Placeholder

A **field name placeholder** is a single `{FIELD_NAME}` reference within a template string. The placeholder name must match an attribute name on the settings instance exactly (case-sensitive). Multiple placeholders can appear in a single template, and they can be interspersed with literal text:

- `"{RUNDATE}"` -- single placeholder, resolves to the field value directly
- `"{RUNDATE}T{RUNTIME}"` -- two placeholders with a literal `T` separator
- `"s3://{BUCKET}/{ENVIRONMENT}/{DATASET}.parquet"` -- three placeholders with path separators

Placeholders reference the _current_ field value at resolution time. This means that if a field has been set by any source (env var, config file, kwargs), the template uses that value. If the field retains its default, the template uses the default. This interaction with the source priority chain is governed by the template priority rules discussed below.

## Template Resolution

**Template resolution** is the process of replacing placeholders with field values to produce a concrete string. The `init_setting_from_template()` method performs this resolution with an important guard: if the target field already has a non-None value and `reinitialise` is False, the existing value is preserved:

```python
def init_setting_from_template(self, template_str, current_value=None,
                                reinitialise=False):
    if current_value is not None and reinitialise is False:
        return current_value

    mapping = self._build_template_mapping(template_str)
    return template_str.format(**mapping)
```

This guard implements a critical design principle: explicitly provided values always take precedence over template-derived values. If a caller passes `RUNDATETIME="2026-01-01T00:00:00"` as a kwarg, the template `"{RUNDATE}T{RUNTIME}"` is never evaluated for that field.

The companion method `format_template_from_settings()` always resolves the template, regardless of the current value. This method is used when the caller wants a formatted string on demand, not as part of the initialization lifecycle.

<!-- concept:40 -->
## Post Init Template Expansion

**Post-init template expansion** is the mechanism by which templates are resolved during the `post_init()` lifecycle hook. This timing is critical: templates must be expanded after all configuration sources have been loaded but before the settings instance is returned to the caller.

The `AppSettings` class demonstrates this pattern:

```python
def post_init(self, template_settings_parameters=None,
              reinitialise=False):
    super().post_init(reinitialise=reinitialise)
    app_settings_templates = self._init_template_object(
        template_settings_parameters
    )
    self.RUNDATETIME = self.init_setting_from_template(
        template_str=app_settings_templates.RUNDATETIME_TEMPLATE,
        current_value=self.RUNDATETIME,
        reinitialise=reinitialise
    )
```

The `Profile` class uses an automated version: it iterates over all `ParameterSpec` entries that declare a `template` attribute and calls `init_setting_from_template()` for each one, applying templates only when the field still holds its default value.

#### Diagram: Template Expansion Timeline

<iframe src="../../sims/template-expansion-timeline/main.html" width="100%" height="450px" scrolling="no"></iframe>
<details markdown="1">
<summary>Template Expansion Timeline</summary>
Type: microsim
**sim-id:** template-expansion-timeline<br/>
**Library:** vis-timeline<br/>
**Status:** Specified

A horizontal timeline showing the construction lifecycle with seven labeled stages. Template-related events are highlighted: placeholder fields receive their values from config sources at stage 4, template expansion occurs at stage 7 (post_init). Users can click each stage to see the state of a sample settings instance at that point -- showing which fields have values and which are still placeholders. A "Step Through" button advances through the stages one at a time. Learning objective: Predict the state of field values at each stage of the construction lifecycle (Bloom: Apply).
</details>

## UPath Path Derivation

The template system supports **UPath path derivation**, which means template-resolved values can be used as file system paths via the `UPath` (universal path) type. When a template resolves to a string like `"s3://my-bucket/data/20260603/output.parquet"`, the result can be assigned to a `UPath` field and used for file operations on any supported filesystem.

This capability is particularly powerful for data pipeline configurations where output paths incorporate runtime parameters:

```python
class PipelineSettings(MountainAshBaseSettings):
    BUCKET: str = Field(default="my-bucket")
    RUNDATE: str = Field(default="20260603")
    OUTPUT_PATH: Optional[str] = Field(default=None)

    def post_init(self, **kwargs):
        super().post_init(**kwargs)
        self.OUTPUT_PATH = self.init_setting_from_template(
            template_str="s3://{BUCKET}/data/{RUNDATE}/output.parquet",
            current_value=self.OUTPUT_PATH
        )
```

Because mountainash-settings uses `UPath` (from the `universal_pathlib` package) rather than `pathlib.Path`, these derived paths work transparently with S3, GCS, Azure Blob Storage, HDFS, and any other filesystem supported by `fsspec`.

## Template Priority Rules

**Template priority rules** determine when a template is evaluated versus when an explicitly provided value takes precedence. The rules follow a simple hierarchy:

1. If the field has an explicit value from kwargs, environment variable, or config file: **keep the explicit value**
2. If the field has its declared default (or None): **evaluate the template**
3. If `reinitialise=True` is passed: **always evaluate the template**, overriding any existing value

These rules ensure that templates behave as intelligent defaults. A template for `OUTPUT_PATH = "s3://{BUCKET}/{RUNDATE}/output.parquet"` provides a sensible derived value, but a caller who passes `OUTPUT_PATH="/local/override/path"` gets exactly what they asked for.

The `Profile` class enforces this by comparing the current field value against the `ParameterSpec.default`:

```python
# Only apply template when value matches the declared default
param_default = param.default if param.default is not MISSING else None
if current not in (param_default, None, ""):
    continue  # skip -- explicit value takes precedence
```

This means that runtime fields (kwargs) are the primary mechanism for user-provided overrides. Structural fields loaded from config files also take precedence over templates, because by the time `post_init()` runs, all source values have already been populated.

## Nested Template Resolution

**Nested template resolution** refers to the ability of templates to reference fields that are themselves template-derived. Because `post_init()` resolves templates in the order they are declared, a template can safely reference a field that was resolved by a preceding template in the same `post_init()` call.

```python
class PipelineSettings(MountainAshBaseSettings):
    RUNDATE: str = "20260603"
    RUNTIME: str = "143022"
    RUNDATETIME: Optional[str] = None     # template: "{RUNDATE}T{RUNTIME}"
    OUTPUT_DIR: Optional[str] = None      # template: "output/{RUNDATETIME}"

    def post_init(self, **kwargs):
        super().post_init(**kwargs)
        # First: resolve RUNDATETIME from RUNDATE and RUNTIME
        self.RUNDATETIME = self.init_setting_from_template(
            "{RUNDATE}T{RUNTIME}", self.RUNDATETIME
        )
        # Second: resolve OUTPUT_DIR from (now resolved) RUNDATETIME
        self.OUTPUT_DIR = self.init_setting_from_template(
            "output/{RUNDATETIME}", self.OUTPUT_DIR
        )
```

The ordering within `post_init()` is the responsibility of the subclass author. Templates must be resolved in dependency order -- a field that references another template-derived field must come after that field's resolution. Circular references (A references B which references A) would cause infinite recursion; the framework does not detect these at declaration time, so the subclass author must avoid them.

#### Diagram: Nested Template Resolution Graph

<iframe src="../../sims/nested-template-graph/main.html" width="100%" height="450px" scrolling="no"></iframe>
<details markdown="1">
<summary>Nested Template Resolution Graph</summary>
Type: graph-model
**sim-id:** nested-template-graph<br/>
**Library:** vis-network<br/>
**Status:** Specified

A directed acyclic graph showing fields as nodes and template references as edges. Source fields (RUNDATE, RUNTIME) are at the top, first-level derived fields (RUNDATETIME) in the middle, and second-level derived fields (OUTPUT_DIR) at the bottom. Clicking a node shows its template string and current resolved value. Hovering over an edge shows which placeholder in the template references which field. A "Resolve" button animates the resolution in topological order. A "Change RUNDATE" slider lets users modify the source value and see how all derived fields update. Learning objective: Design template dependency chains that resolve correctly without circular references (Bloom: Create).
</details>

## Key Takeaways

- **FileHandler Class** is a stateless utility that normalizes, categorizes, validates, and deduplicates configuration file paths into typed buckets.
- **File Extension Dispatch** uses a pluggable registry to identify file types from extensions, with special handling for dotfiles like `.env`.
- **File Categorization** produces a `SettingsFiles` named tuple that routes each file category to its correct Pydantic settings source.
- **KwargsHandler Class** normalizes keyword arguments from dictionaries or tuples into a consistent dictionary format, unwrapping nested "kwargs" keys.
- **Kwargs Normalization** separates kwargs into three routing destinations: model config overrides, Pydantic settings parameters, and user-facing field values.
- **Multi Format File Loading** assigns env files to `_env_file` and structured files to `model_config`, enabling transparent mixed-format loading from a single parameter.
- **Template Syntax** uses Python's `str.format()` with `{FIELD_NAME}` placeholders that reference other fields on the same settings instance.
- **Template Priority Rules** ensure explicit values from kwargs, env vars, or config files always take precedence over template-derived values.
