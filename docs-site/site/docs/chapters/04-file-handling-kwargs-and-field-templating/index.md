---
title: File Handling, Kwargs, and Field Templating
description: How mountainash-settings loads configuration from files and kwargs, and how field values reference other fields via templates with resolution during post-init.
generated_by: claude skill chapter-content-generator
date: 2026-06-03
version: 0.08
---

# File Handling, Kwargs, and Field Templating

Configuration reaches a settings class through two input shapes: file paths and keyword arguments. `SettingsFileHandler` normalises, deduplicates and classifies file paths by extension into per-format buckets, `SettingsKwargsHandler` normalises keyword arguments into a plain dictionary, and `MountainAshBaseSettings` hands each bucket to the matching Pydantic settings source. Field values can also be declared as templates that reference other fields; the template helpers on `MountainAshBaseSettings` and the origin-aware derivation in `Profile` resolve them during `post_init()`.

---

## From Raw Input to Validated Fields

When a caller passes `config_files=["base.yaml", ".env", "overrides.toml"]` alongside keyword arguments like `debug=True`, each input follows its own path. File paths are categorized by extension and handed to the matching Pydantic settings source. Keyword arguments are accepted only as declared field inputs; source controls and schema controls are not routed anywhere, they are rejected before any source opens.

<!-- concept:32 -->
## FileHandler Class

The `SettingsFileHandler` class is a stateless utility (all methods are class methods or static methods) that manages the lifecycle of configuration file paths: normalization, classification, validation, deduplication, and format conversion.

The class provides six key operations:

- `separate_config_files()` -- the main entry point that takes a mixed file list and returns a `SettingsFiles` named tuple
- `identify_file_extension()` -- determines the type of a single file; raises `ValueError` for an unsupported extension
- `group_files_by_type()` -- groups a list of files into buckets by extension
- `validate_config_files_exist()` -- raises `FileNotFoundError` for missing files
- `deduplicate_files()` -- removes duplicates while preserving first-seen order
- `format_config_file_tuple()` / `format_config_file_list()` -- normalization helpers

The output container is the `SettingsFiles` named tuple, which provides typed access to each file category:

```python
ConfigPath = str | UPath
ConfigFilesInput = ConfigPath | Sequence[ConfigPath] | None

class SettingsFiles(NamedTuple):
    env_files:  tuple[ConfigPath, ...] = ()
    yaml_files: tuple[ConfigPath, ...] = ()
    toml_files: tuple[ConfigPath, ...] = ()
    json_files: tuple[ConfigPath, ...] = ()
```

Every category defaults to an empty tuple, never `None`. The handler accepts `ConfigFilesInput` -- a single path (`str` or `UPath`), a sequence of paths, or `None` -- and normalizes it consistently, so callers never need to pre-process their file paths. Any other input type raises `TypeError`.

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

`register_type()` extends classification only: after registering an extension, `identify()` and `group_files_by_type()` recognise it, but `separate_config_files()` retains only the `env`, `yaml`, `toml` and `json` buckets. A registered custom type is therefore not a fifth loadable source category. An extension the registry does not know raises `ValueError` from `identify_file_extension()`.

<!-- concept:34 -->
## File Categorization

**File categorization** is the process of sorting a mixed list of configuration files into their respective type buckets. The `separate_config_files()` method orchestrates this in three steps:

1. Normalize each input (expanding `~` home directory references) and deduplicate on the normalized path, keeping the first occurrence and its position
2. Group the remaining files by type using `group_files_by_type()`
3. Return a `SettingsFiles` named tuple with the four categories, each a tuple in first-seen order

```python
# Input: mixed file list
files = ["base.yaml", "secrets.env", "overrides.toml", "base.yaml"]

# Output: categorized and deduplicated
result = SettingsFileHandler.separate_config_files(files)
# SettingsFiles(env_files=('secrets.env',),
#               yaml_files=('base.yaml',),
#               toml_files=('overrides.toml',),
#               json_files=())
```

Entries supplied as strings stay normalized strings; entries supplied as `UPath` objects are kept as `UPath` objects. Empty categories are empty tuples.

After categorization, the `MountainAshBaseSettings` constructor validates that all referenced files exist on disk (or the target filesystem) by calling `validate_config_files_exist()` for each category. This fail-fast behavior catches configuration errors at construction time rather than at the point where a missing value is first accessed.

#### Diagram: File Categorization Pipeline

<iframe src="../../sims/file-categorization-pipeline/main.html" width="100%" height="450px" scrolling="no"></iframe>
<details markdown="1">
<summary>File Categorization Pipeline</summary>
Type: workflow
**sim-id:** file-categorization-pipeline<br/>
**Library:** vis-network<br/>
**Status:** Specified

A directed flow showing mixed file inputs entering a pipeline of stages: normalization and first-seen deduplication, FileTypeRegistry.identify() dispatch, and group_files_by_type() bucketing. Output flows into four colored lanes (env=green, yaml=blue, toml=purple, json=orange). Clicking a file in the input list highlights its path through the pipeline. Dragging new file names into the input area runs them through the pipeline interactively. Shows how a mixed file list is categorized into typed buckets by the FileHandler.
</details>

<!-- concept:41 -->
## UPath Config Paths

Configuration file paths may be given as strings or as `UPath` objects (from `universal_pathlib`); both are valid `ConfigPath` values. The handler normalizes each entry with `UPath(item).expanduser()` for deduplication and type identification, but preserves the form it was given: a string entry comes back as a normalized string, and a `UPath` entry comes back as a `UPath` object, so any filesystem options carried by that object are retained rather than rebuilt from a URL.

```python
from upath import UPath

result = SettingsFileHandler.separate_config_files([UPath("conf/cfg.json"), "x/cfg.json"])
# SettingsFiles(env_files=(), yaml_files=(), toml_files=(),
#               json_files=(PosixUPath('conf/cfg.json'), 'x/cfg.json'))
```

The existence check in `validate_config_files_exist()` calls `UPath(item).exists()` on each entry, so it is evaluated against the filesystem the path names. This guarantee covers configuration-file paths only; it makes no claim about templated field values, which are plain strings.

<!-- concept:35 -->
<!-- concept:36 -->
## KwargsHandler Class

The `SettingsKwargsHandler` class normalizes keyword arguments into a consistent dictionary format. Like `SettingsFileHandler`, it is a stateless utility with class methods and static methods.

The primary method is `format_kwargs_dict()`, which accepts a mapping, an iterable of key-value pairs, or `None`, and always returns a fresh dictionary (`{}` for `None`):

```python
f = SettingsKwargsHandler.format_kwargs_dict
f(None)                       # {}
f({"debug": True})            # {'debug': True}
f((("b", 2), ("a", 1)))       # {'b': 2, 'a': 1}
f({"kwargs": {"a": 1}})       # {'a': 1}
```

If the input contains a nested `"kwargs"` key, the handler unwraps it, which handles kwargs that have been double-wrapped during parameter passing. The nested value must itself be a mapping with string keys. Input that cannot be converted to a dictionary, or a nested `kwargs` value that is not a string-keyed mapping, raises a value-free `TypeError("Invalid kwargs mapping")`; the offending value is never echoed.

`format_kwargs_tuple()` returns the same normalized items as a tuple of `(key, value)` pairs sorted by key, which gives a deterministic form. `merge_kwargs()` merges two normalized inputs with the second taking precedence.

## Kwargs Normalization

**Kwargs normalization** is the process by which `SettingsParameters.get_attribute_settings_kwargs()` turns the normalized kwargs of a direct construction into field inputs. It filters and rejects; it does not route kwargs to Pydantic internals or to `model_config`:

- **Field inputs** -- keys that match a declared field name (or a validation alias of a declared field) on the target settings class are accepted and passed to `BaseSettings.__init__` as field values.
- **Source controls** -- any key starting with an underscore (`_env_file`, `_env_prefix`, `_secrets_dir`, `_cli_*` and so on) raises `ValueError` value-free, before any source opens. Source selection is expressed through the public `config_files`, `env_prefix`, `secrets_dir` and `secret_store` parameters instead.
- **Schema controls** -- `extra`, `arbitrary_types_allowed` and `validate_default` raise `ValueError` unless the settings class declares a field of that name. Schema behaviour is configured on the class's `model_config`, never per call.
- **Anything else** that is not a declared field name is dropped from the field inputs.

Cached retrieval applies a stricter check through `get_cache_runtime_kwargs()`: it raises `ValueError("Cached retrieval does not accept source or schema controls")` for structural names (`config_files`, `settings_class`, `env_prefix`, `secrets_dir`, `secret_store`, `reinitialise`), underscore-prefixed names, and undeclared schema controls.

!!! tip "Debugging kwargs"
    If a keyword argument does not populate a field, check that its name matches a declared field (or a validation alias) on the settings class: names that match nothing are dropped. If construction raises `ValueError` naming a kwarg, the name is a source or schema control; remove the underscore prefix, or move the setting to the corresponding public parameter or to `model_config`.

<!-- concept:22 -->
## Multi Format File Loading

**Multi-format file loading** is the mechanism that assigns categorized files to the correct Pydantic settings source. After the `FileHandler` produces a `SettingsFiles` tuple, the `MountainAshBaseSettings` constructor sends each category to its destination:

- **`.env` files** are converted to strings and passed as the `_env_file` argument of `BaseSettings.__init__`, where the `DotEnvSettingsSource` consumes them directly.
- **YAML, TOML and JSON files** are installed in a per-invocation source frame (a private `ContextVar`) for the duration of that one construction. `settings_customise_sources` reads the frame, but only when it belongs to the class currently under construction, and builds the corresponding `*ConfigSettingsSource` from those paths.

The shared class `model_config` is never mutated by construction. Because the frame is local to the invocation, overlapping, nested and failing constructions of the same or different settings classes cannot leak one invocation's file paths into another's.

This split exists because Pydantic handles `.env` files differently from structured config files: `.env` paths are an init argument, whereas the structured-file sources need paths supplied through the source customisation hook.

The result is that a single `config_files` parameter from the caller can contain any mix of file types, and each type is automatically routed to its native loading mechanism. A caller does not need to know which files are YAML versus TOML versus `.env` -- the handler figures it out from the file extensions.

<!-- concept:37 -->
<!-- concept:39 -->
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
    declared_fields = type(self).model_fields
    for _, field_name, _, _ in Formatter().parse(template_str):
        if field_name:
            if field_name in declared_fields:
                mapping[field_name] = getattr(self, field_name)
            else:
                raise AttributeError(
                    f"The object does not have an attribute "
                    f"named '{field_name}'"
                )
    return mapping
```

Only declared model fields can be referenced: private attributes (such as the raw reconstruction kwargs), methods and dunder attributes are never renderable. If a template references a name that is not a declared field, an `AttributeError` is raised immediately -- templates fail fast rather than producing silently incorrect values.

<!-- concept:38 -->
## Field Name Placeholder

A **field name placeholder** is a single `{FIELD_NAME}` reference within a template string. The placeholder name must match a declared field name on the settings class exactly (case-sensitive). Multiple placeholders can appear in a single template, and they can be interspersed with literal text:

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

The `Profile` class uses an automated version: it iterates over all `ParameterSpec` entries that declare a `template` attribute and calls `init_setting_from_template()` for each one, applying templates only when the field was not explicitly supplied to that call (see [Template Priority Rules](#template-priority-rules) below for the exact, origin-aware eligibility rule). Fields it derives are recorded in the private `_profile_derived_field_names` set so that a later `reinitialise=True` pass knows which fields it may recompute.

#### Diagram: Template Expansion Timeline

<iframe src="../../sims/template-expansion-timeline/main.html" width="100%" height="450px" scrolling="no"></iframe>
<details markdown="1">
<summary>Template Expansion Timeline</summary>
Type: microsim
**sim-id:** template-expansion-timeline<br/>
**Library:** vis-timeline<br/>
**Status:** Specified

A horizontal timeline showing the construction lifecycle with seven labeled stages. Template-related events are highlighted: placeholder fields receive their values from config sources at stage 4, template expansion occurs at stage 7 (post_init). Users can click each stage to see the state of a sample settings instance at that point -- showing which fields have values and which are still placeholders. A "Step Through" button advances through the stages one at a time. Shows the state of field values at each stage of the construction lifecycle.
</details>

<!-- concept:42 -->
## Template Priority Rules

**Template priority rules** determine when a template is evaluated versus when an explicitly provided value takes precedence.

For the low-level `init_setting_from_template()` helper (used directly in a hand-written `post_init()`, as in the examples above), the rule is a simple current-value check:

1. If `current_value` is not `None` and `reinitialise` is not `True`: **keep the current value** (a no-op).
2. Otherwise (no current value, or `reinitialise=True`): **evaluate the template**.

`Profile` uses a stricter, origin-aware rule rather than comparing values, because a value-based check cannot distinguish "the caller explicitly passed the same value as the default" from "no value was supplied" -- and misclassifying the former silently overwrites an explicit choice:

1. **Initial construction:** every declared template field not explicitly supplied to *this* call is eligible for derivation, regardless of whether its value happens to equal the declared default, `None`, or `""`.
2. **`reinitialise=True`:** only fields `Profile` previously recorded as template-derived are eligible, excluding any explicitly supplied to *this* call through the cache/fork route (`get_settings(reinitialise=True)` / `SettingsManager`).

A template for `OUTPUT_PATH = "s3://{BUCKET}/{RUNDATE}/output.parquet"` provides a sensible derived value, but a caller who passes `OUTPUT_PATH="/local/override/path"` gets exactly what they asked for, including on a later `reinitialise=True` call made through the cache/fork route.

!!! warning "Direct `post_init(reinitialise=True)` is not override-protected"
    The "explicit this call" exclusion is populated only by the cache/fork route. A raw call to `post_init(reinitialise=True)` on a manually constructed instance cannot distinguish a field the caller just set from a field that still holds an old derived value, so it re-derives every field the instance has ever template-derived from current attribute state. Overriding a derived field and then calling `post_init(reinitialise=True)` directly overwrites the override (covered by `test_direct_reinitialise_known_limitation_overwrites_a_fresh_manual_override`).

`Profile.post_init()` computes eligibility from field-name sets, never field values:

```python
explicit_at_entry = frozenset(self.__pydantic_fields_set__)
previously_derived = self._settings_carried_field_names | self._profile_derived_field_names
explicit_this_call = self._settings_runtime_field_names

if reinitialise:
    eligible = param.name in previously_derived and param.name not in explicit_this_call
else:
    eligible = param.name not in previously_derived and param.name not in explicit_at_entry
```

`_settings_carried_field_names` is populated by the cache/fork route; `_profile_derived_field_names` accumulates the fields `Profile` has derived on this instance, which covers direct (non-cached) construction. After each pass the newly derived names are added to `_profile_derived_field_names`.

The eligible result is assigned through the model's normal validated `setattr` path -- coercion, field validators, and `SecretStr` wrapping all apply exactly as they would to an equivalent explicit value.

This means that runtime fields (kwargs) are the primary mechanism for user-provided overrides. Structural fields loaded from config files also take precedence over templates, because by the time `post_init()` runs, all source values have already been populated.

<!-- concept:43 -->
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

The ordering within `post_init()` is the responsibility of the subclass author. Templates must be resolved in dependency order -- a field that references another template-derived field must come after that field's resolution. Resolution is a single ordered pass using ordinary `str.format()`: there is no recursive expansion and no cycle detection. A template that references a field not yet resolved reads that field's current value at that moment. In a mutually referencing pair, `A = "a-{B}"` resolved before `B = "b-{A}"` yields `A == "a-None"` and `B == "b-a-None"`, not an error, so dependency order matters.

#### Diagram: Nested Template Resolution Graph

<iframe src="../../sims/nested-template-graph/main.html" width="100%" height="450px" scrolling="no"></iframe>
<details markdown="1">
<summary>Nested Template Resolution Graph</summary>
Type: graph-model
**sim-id:** nested-template-graph<br/>
**Library:** vis-network<br/>
**Status:** Specified

A directed acyclic graph showing fields as nodes and template references as edges. Source fields (RUNDATE, RUNTIME) are at the top, first-level derived fields (RUNDATETIME) in the middle, and second-level derived fields (OUTPUT_DIR) at the bottom. Clicking a node shows its template string and current resolved value. Hovering over an edge shows which placeholder in the template references which field. A "Resolve" button animates the resolution in topological order. A "Change RUNDATE" slider lets users modify the source value and see how all derived fields update. Shows how template dependency chains resolve in declaration order.
</details>
