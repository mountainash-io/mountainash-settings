---
title: Settings parameters and merge strategies
description: The SettingsParameters dataclass covering structural/runtime field separation, custom hash semantics for caching, the create factory, and the per-field merge strategies.
generated_by: claude skill chapter-content-generator
date: 2026-06-03
version: 0.08
---

# Settings parameters and merge strategies

`SettingsParameters` is the frozen dataclass that describes a settings request. It separates structural selectors, which decide which source context a request uses, from runtime `kwargs`, which apply to a single call. Equality and hashing cover only the structural fields. `SettingsParameters.create()` normalises caller input, and `SettingsParameters.merge()` combines two parameter sets with a rule for each field.

---

<!-- concept:27 -->
## The parameter abstraction layer

A caller asks for database settings from a config file with `debug=True`. Between that request and the `MountainAshBaseSettings` instance sits `SettingsParameters`. It records which files, which class and which prefix identify the configuration, and it carries the runtime inputs that may change on every call.

Requests that differ only in runtime inputs share the same pinned source state. Each retrieval still returns a fresh instance that is validated for that call.

<!-- concept:23 -->
## SettingsParameters class

`SettingsParameters` is immutable after construction and has six fields:

| Field | Type | Role |
|-------|------|------|
| `config_files` | `str`, `UPath`, a sequence of either, or `None` | Configuration files to load |
| `settings_class` | `type[MountainAshBaseSettings]` or `None` | The class to instantiate |
| `env_prefix` | `str` or `None` | Environment variable prefix |
| `secrets_dir` | `str` or `None` | Directory for file-based secrets |
| `kwargs` | `dict` or `None` | Runtime field inputs |
| `secret_store` | secret reader or `None` | Directly bound secret reader/writer |

Because instances are immutable they can be used as dictionary keys. The `kwargs` field is left out of the generated representation, so printing a `SettingsParameters` does not show runtime values.

`kwargs` carries field inputs only. Settings retrieval keeps the keys that name a field of the settings class (or a validation alias path of a field) and drops the rest. Before any source opens, it rejects two kinds of control with a `ValueError` that does not echo the value:

- Any name with a leading underscore, such as `_env_prefix`, `_env_file` or `_secrets_dir`. The rule is the leading underscore, not a fixed list.
- The schema-control names `extra`, `arbitrary_types_allowed` and `validate_default`, unless the settings class declares a field of that name. Model configuration belongs on the class's `model_config`, not in a request.

Cached retrieval applies the same rejection. Select sources with the explicit `config_files`, `settings_class`, `env_prefix`, `secrets_dir` and `secret_store` parameters. A selector name placed inside `kwargs` is not a runtime field: it fails with an error before any source opens (a `TypeError` for a duplicated selector, or `ValueError("Cached retrieval does not accept source or schema controls")` for `reinitialise` or underscore and schema-control names).

<!-- concept:24 -->
<!-- concept:25 -->
## Structural fields

Structural fields define a private source context. Identical structural fields select the same pinned source baseline. They do not return the same settings object.

The structural fields are `config_files`, `settings_class`, `env_prefix`, `secrets_dir` and `secret_store`. The `secret_store` is compared by object identity. File order inside `config_files` is part of the identity.

Two parameter sets that load the same files for the same class, with the same prefix and the same bound `secret_store` object, describe the same configuration, even if one of them passes `debug=True` as a runtime override.

## Runtime fields

`kwargs` is the only runtime field. It carries inputs for one invocation and does not affect structural identity. Cached retrieval validates the complete candidate for each call and returns an independently owned result.

```python
from mountainash_settings import SettingsParameters

a = SettingsParameters.create(config_files=["db.yaml"], request_id="abc-123")
b = SettingsParameters.create(config_files=["db.yaml"], request_id="def-456")
print(a == b, hash(a) == hash(b))   # True True
```

<!-- concept:26 -->
## Custom hash and eq

Equality and hashing consider only the structural fields and deliberately exclude `kwargs`. The same selectors form the settings manager's private context key, so requests that differ only in kwargs select the same captured source context.

Lists are not hashable, so `config_files` is normalised to a tuple first. The normalisation expands `~`, removes duplicates and keeps first-seen order. It does not sort. Later files take precedence over earlier ones for structured sources, so `["a.yaml", "b.yaml"]` and `["b.yaml", "a.yaml"]` are different requests with different precedence. They compare unequal and select different source contexts:

```python
from mountainash_settings import SettingsParameters

ab = SettingsParameters.create(config_files=["a.yaml", "b.yaml"])
ba = SettingsParameters.create(config_files=["b.yaml", "a.yaml"])
print(ab == ba)   # False
```

## Parameter create factory

`SettingsParameters.create()` is the standard way to build an instance. It accepts a single string or `UPath`, a list, a tuple or `None` for `config_files`, and turns whatever it receives into a tuple. `None` becomes `()`. Every extra keyword argument is collected into `kwargs`, and absent kwargs become `{}`, not `None`.

```python
from mountainash_settings import SettingsParameters

params = SettingsParameters.create(
    config_files="config.yaml",
    env_prefix="APP_",
    database_host="localhost",
    debug=True,
)
print(params.config_files)   # ('config.yaml',)
print(params.env_prefix)     # APP_
print(params.kwargs)         # {'database_host': 'localhost', 'debug': True}

empty = SettingsParameters.create()
print(empty.config_files, empty.kwargs)   # () {}
```

<!-- concept:28 -->
## Merge framework

`SettingsParameters.merge(base, other=None, prioritise_base=False)` combines two parameter sets into one. It supports layered configuration, where a base set (for example a global default) is merged with a caller-specific set. Each field has its own strategy, described in the sections below.

By default `other` wins over `base`. With `prioritise_base=True`, `base` wins instead. Use it when a higher-level parameter set should not be overridden by a lower-level one.

<!-- concept:29 -->
## Ordered file list merge

For `config_files`, the merged tuple holds the files of `base` first, in their original order, followed by the files of `other` that `base` did not already contain. Nothing is sorted. Because later files take precedence for structured sources, this order decides which file wins a conflicting key.

```python
from mountainash_settings import SettingsParameters

base = SettingsParameters.create(config_files=["base.yaml", "shared.env"])
other = SettingsParameters.create(config_files=["override.yaml", "shared.env"])

print(SettingsParameters.merge(base, other).config_files)
# ('base.yaml', 'shared.env', 'override.yaml')
print(SettingsParameters.merge(base, other, prioritise_base=True).config_files)
# ('base.yaml', 'shared.env')
```

Files are additive, so a requested file is never silently dropped. A file listed by both layers appears once, at the position where `base` first listed it, so it does not move to the end of the precedence order.

With `prioritise_base=True` there is no merging. The result takes `base.config_files` if it is non-empty and otherwise falls back to `other.config_files`. A higher-priority layer can use this to declare a complete, exclusive file set.

<!-- concept:30 -->
## Scalar last wins strategy

Two different rules apply, and they are not interchangeable.

For the string scalars `env_prefix` and `secrets_dir`, the merge uses truthiness. The `other` value wins if it is non-empty, otherwise the `base` value is kept. An empty string or `None` in `other` does not clear a `base` value.

For `secret_store`, the merge tests `is None`, never truthiness. The `other` store wins if it is not `None`, otherwise the `base` store is kept. A store object that happens to be falsey still counts as bound.

With `prioritise_base=True` each rule is applied with the roles swapped. `base` wins when its value is truthy (or, for `secret_store`, not `None`).

```python
from mountainash_settings import MountainAshBaseSettings, SettingsParameters

base = SettingsParameters.create(env_prefix="APP_")
other = SettingsParameters.create(env_prefix="MYAPP_")
print(SettingsParameters.merge(base, other).env_prefix)                        # MYAPP_
print(SettingsParameters.merge(base, other, prioritise_base=True).env_prefix)  # APP_

# An empty string in other does not clear the base value
empty = SettingsParameters.create(env_prefix="")
print(SettingsParameters.merge(base, empty).env_prefix)                        # APP_
```

`settings_class` is checked rather than overridden. If both sets declare a class and the classes differ, the merge raises a `ValueError`. Parameter sets for different classes cannot be merged meaningfully, so the conflict is left for the caller to resolve:

```python
class DbSettings(MountainAshBaseSettings):
    host: str = "localhost"

class ApiSettings(MountainAshBaseSettings):
    url: str = ""

try:
    SettingsParameters.merge(
        SettingsParameters.create(settings_class=DbSettings),
        SettingsParameters.create(settings_class=ApiSettings),
    )
except ValueError as e:
    print(e)
# Settings class must match for merging. base: <class '__main__.DbSettings'> != other: <class '__main__.ApiSettings'>
```

<!-- concept:31 -->
## Shallow kwargs merge

`kwargs` are merged with the dict union operator (`|`). The merge is shallow: `other` values replace `base` values for keys present in both, and nothing is merged recursively. A nested dict from `other` replaces the `base` nested dict as a whole.

```python
from mountainash_settings import SettingsParameters

base = SettingsParameters.create(database_host="base-host", debug=False)
other = SettingsParameters.create(debug=True, timeout=30)
print(SettingsParameters.merge(base, other).kwargs)
# {'database_host': 'base-host', 'debug': True, 'timeout': 30}

# Nested values are replaced, not merged
b = SettingsParameters.create(nested={"a": 1, "b": 2})
o = SettingsParameters.create(nested={"a": 9})
print(SettingsParameters.merge(b, o).kwargs)
# {'nested': {'a': 9}}
```

A base set can define defaults for every field while a caller-specific set overrides only what it needs. Keys absent from `other` are kept from `base`.

With `prioritise_base=True` the kwargs of `base` are used as they are if non-empty, otherwise those of `other`, with no merging. This prevents partial overwrites when the base layer needs complete control:

```python
print(SettingsParameters.merge(base, other, prioritise_base=True).kwargs)
# {'database_host': 'base-host', 'debug': False}
```

## Merge strategy selection logic

Each strategy follows from what the field means.

- Config files are additive resources. If one layer loads `base.yaml` and another loads `override.yaml`, both contribute, so the merge keeps both in base-then-other order and removes duplicates.
- Scalars are mutually exclusive. An `env_prefix` is one string, and `"APP_"` and `"MYAPP_"` cannot be combined, so the most recent non-empty value wins. `secret_store` follows the same direction with an `is None` test.
- A `DatabaseSettings` parameter set cannot be merged with an `ApiSettings` one because their field sets are incompatible, so a class mismatch raises an error instead of producing an invalid result.
- Kwargs are a partial specification. With `{host: "localhost", port: 5432}` in base and `{port: 5433, debug: True}` in other, the result keeps `host`, takes the new `port` and adds `debug`. Top-level keys are the unit of override.

## Putting it together: structural contexts and runtime materialization

Together these give cached retrieval its shape: the five structural selectors pick a source context that reads its sources once, and every call validates its own runtime kwargs into a fresh instance. `reinitialise` does not reload sources. Validation errors on fields resolved from a `secret:` reference never echo the secret value. Chapter 9 covers [cached retrieval](../09-caching-settings-management-and-app-settings/index.md) in full.
