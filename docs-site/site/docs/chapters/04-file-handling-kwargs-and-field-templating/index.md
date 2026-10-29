---
title: File handling, kwargs, and field templating
description: How mountainash-settings loads configuration from files and kwargs, and how field values reference other fields via templates with resolution during post-init.
generated_by: claude skill chapter-content-generator
date: 2026-06-03
version: 0.08
---

# File handling, kwargs, and field templating

Configuration reaches a settings class through two inputs: file paths (`config_files`) and keyword arguments. Files in `.env`, YAML, TOML and JSON formats can be mixed in one list, and each is loaded by its native source. A field can also be derived from a template that references other fields, such as `"{RUNDATE}T{RUNTIME}"`, when `post_init()` calls `init_setting_from_template()` or a `Profile` field declares `template=`.

---

## From raw input to validated fields

A caller can pass `config_files=["base.yaml", ".env", "overrides.toml"]` alongside keyword arguments like `debug=True`. File paths are sorted by extension and handed to the matching Pydantic settings source. Keyword arguments are accepted only as declared field inputs. Source controls and schema controls are rejected before any source opens.

```python
import tempfile
from pathlib import Path

from mountainash_settings import MountainAshBaseSettings


class ServiceSettings(MountainAshBaseSettings):
    RUNDATE: str = "20260603"
    RUNTIME: str = "143022"
    DEBUG: bool = False


with tempfile.TemporaryDirectory() as d:
    base = str(Path(d, "base.yaml"))
    secrets = str(Path(d, "secrets.env"))
    overrides = str(Path(d, "overrides.toml"))
    Path(base).write_text("RUNDATE: '20270101'\n")
    Path(secrets).write_text("DEBUG=true\n")
    Path(overrides).write_text("RUNTIME = '010203'\n")

    # Mixed formats, one duplicate entry, plus a keyword argument
    s = ServiceSettings(config_files=[base, secrets, overrides, base], RUNTIME="999999")
    print(s.RUNDATE, s.RUNTIME, s.DEBUG)
    # 20270101 999999 True
```

`RUNDATE` comes from the YAML file, `DEBUG` from the `.env` file, and `RUNTIME` from the keyword argument, which takes precedence over the TOML file. The duplicated `base.yaml` entry is loaded once.

<!-- concept:32 -->
## Config file handling

`config_files` accepts a single path, a list of paths, or `None`. Before loading, the paths are normalised (a leading `~` is expanded), deduplicated with the first occurrence kept, and sorted by format into `.env`, YAML, TOML and JSON groups, each in first-seen order.

Every referenced file must exist. A missing file raises `FileNotFoundError` when the settings object is constructed, so a configuration error shows up at construction time and not when a value is first read. A file whose extension is not recognised raises `ValueError`.

```python
with tempfile.TemporaryDirectory() as d:
    try:
        ServiceSettings(config_files=[str(Path(d, "missing.yaml"))])
    except FileNotFoundError:
        print("FileNotFoundError")

    try:
        ServiceSettings(config_files=[str(Path(d, "settings.ini"))])
    except ValueError:
        print("ValueError")
```

<!-- concept:33 -->
## File extension dispatch

The file type comes from the extension. For a regular file such as `config.yaml`, the extension is looked up directly. For a dotfile such as `.env`, which has a leading dot and no other dots, the name without the dot is used.

| Input path | Detection | Resolved type |
|-----------|-----------|---------------|
| `config.yaml` | Extension `.yaml` | YAML |
| `settings.yml` | Extension `.yml` | YAML |
| `app.toml` | Extension `.toml` | TOML |
| `data.json` | Extension `.json` | JSON |
| `.env` | Dotfile `env` | ENV |
| `.env.local` | Extension `.local` | Unknown |

`.env.local` is not recognised because it has more than one dot, so it raises `ValueError`. Rename it, for example to `local.env`, to load it.

<!-- concept:34 -->
## File categorization

Categorization sorts the mixed `config_files` list into its format groups, so a caller does not need to know which files are YAML, TOML, JSON or `.env`. Duplicates are removed on the normalised path, and the first occurrence keeps its position. Entries given as strings stay strings, and entries given as `UPath` objects stay `UPath` objects.

The example in [From raw input to validated fields](#from-raw-input-to-validated-fields) shows this: `base.yaml` appears twice in the list and is loaded once, and the three formats are each routed to their own source.

<!-- concept:41 -->
## UPath config paths

Configuration file paths may be strings or `UPath` objects (from `universal_pathlib`). Both are valid `config_files` entries. A `UPath` entry is kept as a `UPath`, so any filesystem options it carries are retained.

```python
from upath import UPath

with tempfile.TemporaryDirectory() as d:
    path = Path(d, "cfg.json")
    path.write_text('{"RUNDATE": "20280101"}')

    print(ServiceSettings(config_files=UPath(str(path))).RUNDATE)
    # 20280101
```

!!! warning "Remote config paths are not supported"
    Only local config paths work. A remote path such as `s3://bucket/cfg.json` or `memory:///cfg.json` raises `NotImplementedError` when the settings object is constructed, so keep configuration files on the local filesystem.

This applies to configuration file paths only. Templated field values are plain strings, so a template such as `"s3://{BUCKET}/{ENVIRONMENT}/{DATASET}.parquet"` works normally.

<!-- concept:35 -->
<!-- concept:36 -->
## Keyword arguments

Keyword arguments passed to a settings class are matched against its declared fields. A key that matches a declared field name, or a validation alias of one, is accepted as that field's value. Anything else is dealt with as follows:

- Source controls: any key starting with an underscore (`_env_file`, `_env_prefix`, `_secrets_dir`, `_cli_*` and so on) raises `ValueError` before any source opens. Source selection goes through the public `config_files`, `env_prefix`, `secrets_dir` and `secret_store` parameters instead.
- Schema controls: `extra`, `arbitrary_types_allowed` and `validate_default` raise `ValueError` unless the settings class declares a field of that name. Schema behaviour is configured on the class's `model_config`, never per call.
- Anything else that is not a declared field name is dropped.

```python
# A kwarg that matches no declared field is dropped
print(ServiceSettings(DEBUG=True, nothing=1).DEBUG)
# True

# Source and schema controls are rejected
for bad in ({"_env_file": "x.env"}, {"extra": "allow"}):
    try:
        ServiceSettings(**bad)
    except ValueError as e:
        print(e)
# Unsupported source control kwarg: '_env_file'
# Unsupported schema control kwarg: 'extra'. Configure this on the settings class's model_config instead.
```

The error messages name the offending key and never echo its value. Retrieval through the settings cache (`get_settings`) applies the same rules, and also refuses `reinitialise` or any source selector supplied as a runtime field rather than through its own parameter.

!!! tip "Debugging kwargs"
    If a keyword argument does not populate a field, check that its name matches a declared field (or a validation alias) on the settings class. Names that match nothing are dropped. If construction raises `ValueError` naming a kwarg, the name is a source or schema control. Remove the underscore prefix, or move the setting to the corresponding public parameter or to `model_config`.

<!-- concept:22 -->
## Multi format file loading

Each format reaches its Pydantic settings source by a different route:

- `.env` files are passed to Pydantic's dotenv source.
- YAML, TOML and JSON files are supplied to the matching Pydantic config source for that one construction only.

The class's `model_config` is never modified, and file paths cannot leak from one construction into another, even when constructions overlap, nest or fail. Two settings instances built with different `config_files` stay independent.

<!-- concept:37 -->
<!-- concept:39 -->
## Template syntax

Templates use Python's standard `str.format()` placeholders. A template is a string containing one or more `{FIELD_NAME}` placeholders, each replaced with the current value of the named field on the same settings instance.

`init_setting_from_template()` resolves a template and `format_template_from_settings()` formats one on demand. The usual place to call `init_setting_from_template()` is `post_init()`:

```python
from typing import Optional

from mountainash_settings import MountainAshBaseSettings


class PipelineSettings(MountainAshBaseSettings):
    RUNDATE: str = "20260603"
    RUNTIME: str = "143022"
    RUNDATETIME: Optional[str] = None
    OUTPUT_DIR: Optional[str] = None

    def post_init(self, **kwargs):
        super().post_init(**kwargs)
        self.RUNDATETIME = self.init_setting_from_template(
            "{RUNDATE}T{RUNTIME}", self.RUNDATETIME
        )
        self.OUTPUT_DIR = self.init_setting_from_template(
            "output/{RUNDATETIME}", self.OUTPUT_DIR
        )


s = PipelineSettings()
print(s.RUNDATETIME)
# 20260603T143022
print(s.OUTPUT_DIR)
# output/20260603T143022
```

Only declared fields can be referenced. Private attributes, methods and dunder attributes are never available to a template. A template that names anything else raises `AttributeError` immediately, so a typo fails at once and does not produce a wrong value:

```python
for template in ("{MISSING}", "{__class__}", "{model_dump}"):
    try:
        s.format_template_from_settings(template)
    except AttributeError as e:
        print(e)
# The object does not have an attribute named 'MISSING'
# The object does not have an attribute named '__class__'
# The object does not have an attribute named 'model_dump'
```

<!-- concept:38 -->
## Field name placeholder

A field name placeholder is a single `{FIELD_NAME}` reference inside a template. The name must match a declared field exactly, including case. A template can hold several placeholders mixed with literal text:

- `"{RUNDATE}"` resolves to the field value directly.
- `"{RUNDATE}T{RUNTIME}"` has two placeholders and a literal `T`.
- `"s3://{BUCKET}/{ENVIRONMENT}/{DATASET}.parquet"` has three placeholders and path separators.

A placeholder reads the field's value at resolution time. If a source (environment variable, config file or kwarg) set the field, the template uses that value. Otherwise it uses the field's default.

## Template resolution

`init_setting_from_template()` takes the template, the field's current value and an optional `reinitialise` flag. If the current value is not `None` and `reinitialise` is false, the current value is returned unchanged and the template is not evaluated. Otherwise the template is formatted with the current field values.

An explicitly provided value therefore always wins over a template. In the example above, passing `RUNDATETIME` directly leaves the template unused for that field:

```python
print(PipelineSettings(RUNDATETIME="2026-01-01T00:00:00").OUTPUT_DIR)
# output/2026-01-01T00:00:00
```

`format_template_from_settings()` always resolves the template, whatever the current value. Use it to build a formatted string on demand:

```python
print(s.format_template_from_settings("s3://bucket/{RUNDATE}/data.parquet"))
# s3://bucket/20260603/data.parquet
```

<!-- concept:40 -->
## Post init template expansion

Templates are resolved in `post_init()`, which runs after all configuration sources have loaded and before the instance is returned. That ordering means a template sees values from files, environment variables and kwargs, not only defaults. `PipelineSettings` above shows the pattern: call `super().post_init(**kwargs)`, then assign each templated field.

A `Profile` automates this. A `ParameterSpec` that declares a `template` is resolved for you, with no `post_init()` override:

```python
from mountainash_settings import ParameterSpec, Profile, ProfileSpec


class ApiProfile(Profile):
    __spec__ = ProfileSpec(
        name="api", provider_type="api",
        parameters=[
            ParameterSpec(name="HOST", type=str, tier="core"),
            ParameterSpec(name="URL", type=str, tier="core", default="",
                          template="https://{HOST}/api"),
        ],
    )


print(ApiProfile(HOST="example.com").URL)
# https://example.com/api
print(ApiProfile(HOST="a.b", URL="https://override.example/").URL)
# https://override.example/
```

The same templating is available on `ProfileField(template=...)` for profiles declared with native Pydantic fields.

<!-- concept:42 -->
## Template priority rules

Template priority rules decide when a template is evaluated and when an explicit value stands.

For a hand-written `post_init()` that calls `init_setting_from_template()`, the rule is a check on the current value:

1. If the current value is not `None` and `reinitialise` is not true, the current value is kept.
2. Otherwise the template is evaluated.

`Profile` uses a stricter rule based on where a value came from, not on what it is. A comparison of values cannot tell "the caller passed the same value as the default" from "no value was supplied", and getting that wrong silently overwrites an explicit choice.

1. Initial construction: every templated field that was not explicitly supplied to this call is derived, even if its value happens to equal the default, `None` or `""`.
2. `reinitialise=True`: only fields that were previously derived from a template are recomputed, excluding any supplied explicitly to this call through `get_settings(reinitialise=True)` or `SettingsManager`.

A template such as `OUTPUT_PATH = "s3://{BUCKET}/{RUNDATE}/output.parquet"` provides a derived value, but a caller who passes `OUTPUT_PATH="/local/override/path"` gets that exact value, including on a later `reinitialise=True` call made through the cache.

The derived value is assigned through the model's normal validated assignment, so type coercion, field validators and `SecretStr` wrapping apply as they would to an explicit value.

Values loaded from config files also take precedence over templates, because every source has been applied by the time `post_init()` runs.

!!! warning "Direct `post_init(reinitialise=True)` is not override-protected"
    The "explicit in this call" exclusion applies only on the cache route. Calling `post_init(reinitialise=True)` directly on an instance you built yourself cannot tell a field you just set from one that still holds an old derived value. It re-derives every field that was ever template-derived on that instance, so an override you set by hand is overwritten.

<!-- concept:43 -->
## Nested template resolution

A template can reference a field that is itself template-derived. In `PipelineSettings`, `OUTPUT_DIR` uses `{RUNDATETIME}`, and `RUNDATETIME` is resolved on the line before it.

The order within `post_init()` is the subclass author's responsibility. Resolve templates in dependency order, so that a field referenced by another template is resolved first.

Resolution is a single ordered pass with ordinary `str.format()`. There is no recursive expansion and no cycle detection. A template that references a field not yet resolved reads that field's current value at that moment:

```python
class Pair(MountainAshBaseSettings):
    A: Optional[str] = None
    B: Optional[str] = None

    def post_init(self, **kwargs):
        super().post_init(**kwargs)
        self.A = self.init_setting_from_template("a-{B}", self.A)
        self.B = self.init_setting_from_template("b-{A}", self.B)


p = Pair()
print(p.A, p.B)
# a-None b-a-None
```

Two fields that refer to each other do not raise an error. The result depends on the order in which they are resolved.
