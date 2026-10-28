---
title: Settings Parameters and Merge Strategies
description: The SettingsParameters dataclass covering structural/runtime field separation, custom hash semantics for caching, the create factory, and the per-field merge strategies.
generated_by: claude skill chapter-content-generator
date: 2026-06-03
version: 0.08
---

# Settings Parameters and Merge Strategies

`SettingsParameters` is the frozen dataclass that describes a settings request and keys the settings cache. It splits its fields into structural selectors, which define a private source context, and runtime `kwargs`, which stay invocation-local. It overrides hash and equality to cover only the structural fields, provides a `create()` factory that normalises caller input, and provides `merge()`, which combines two parameter sets with a per-field strategy: ordered file-list merge, last-wins scalars, a settings-class match check, and a shallow `kwargs` merge.

---

<!-- concept:27 -->
## The Parameter Abstraction Layer

Between the caller who says "give me database settings from this config file with debug=True" and the actual construction of a `MountainAshBaseSettings` instance, there is an important abstraction layer: the `SettingsParameters` class. This frozen dataclass captures everything needed to construct (or retrieve from cache) a settings instance. It separates the identity of a configuration -- which files, which class, which prefix -- from the source-form runtime inputs that may change on each access.

`SettingsParameters` drives structural context identity. Requests with different runtime inputs share pinned source state, while every retrieval receives a fresh owned instance after complete invocation validation.

<!-- concept:23 -->
## SettingsParameters Class

The `SettingsParameters` class is a frozen dataclass (immutable after construction) with six fields that together describe how to build a settings instance:

```python
@dataclass(frozen=True)
class SettingsParameters:
    config_files:   ConfigFilesInput = None   # str | UPath | Sequence[str | UPath] | None
    settings_class: type[MountainAshBaseSettings] | None = None
    env_prefix:     Optional[str] = None
    secrets_dir:    Optional[str] = None
    kwargs:         Optional[Dict[str, Any]] = field(default=None, repr=False)
    secret_store:   Optional["SecretReader"] = field(default=None, repr=False, compare=False, hash=False)
```

The frozen nature is significant. Because instances are immutable, they can safely be used as dictionary keys and cache lookup parameters. The `@dataclass(frozen=True)` decorator generates `__hash__` and `__eq__` methods by default, but `SettingsParameters` overrides both to implement its custom caching strategy. Its `kwargs` field is omitted from the generated representation, so ordinary diagnostics do not print runtime values; explicit access and serialization remain intentional, trusted operations.

The `kwargs` field carries field inputs only. `get_attribute_settings_kwargs()` keeps the keys that name a field of the settings class (or a validation alias path of a field) and drops the rest. It rejects, with a value-free `ValueError`, two kinds of control before any source opens:

- Every underscore-prefixed name (`_env_prefix`, `_env_file`, `_secrets_dir`, and any other name pydantic-settings accepts with a leading underscore). The rule is the leading underscore, not an enumerated list.
- The schema-control names `extra`, `arbitrary_types_allowed` and `validate_default`, unless the settings class declares a field of that name. Model configuration belongs on the class's `model_config`, not in a request.

`get_cache_runtime_kwargs()` applies the same rejection for cached retrieval, and additionally rejects the structural selectors and `reinitialise` when they appear inside `kwargs` (`config_files`, `settings_class`, `env_prefix`, `secrets_dir`, `secret_store`). It raises `ValueError("Cached retrieval does not accept source or schema controls")` and otherwise returns the supplied runtime inputs unchanged.

`config_files` accepts a single `str` or `UPath`, a sequence of either, or `None` (the `ConfigFilesInput` alias; `ConfigPath` is `str | UPath`). Source selection is by explicit parameters such as `env_prefix` and `secrets_dir`, never by underscore keys in `kwargs`.

<!-- concept:24 -->
<!-- concept:25 -->
## Structural Fields

**Structural fields** are the parameters that define a private source context. Identical structural fields select the same pinned source baseline; they do not return the same settings object.

The structural fields are:

| Field | Type | Purpose |
|-------|------|---------|
| `config_files` | `ConfigFilesInput` (a tuple of `str \| UPath` after `create()`) | Configuration files that define this settings identity; order is part of the identity |
| `settings_class` | `type[MountainAshBaseSettings] \| None` | The class to instantiate |
| `env_prefix` | `Optional[str]` | Environment variable prefix scope |
| `secrets_dir` | `Optional[str]` | Directory for pydantic-settings file-based secrets |
| `secret_store` | `Optional[SecretReader]` | Directly bound secret reader/writer, tested by object identity |

These five fields answer the question: "What configuration am I loading?" Two sets of parameters that load the same files, for the same class, with the same prefix and the same bound `secret_store` object represent the same logical configuration, even if one requests `debug=True` as a runtime override and the other does not.

## Runtime Fields

**Runtime fields** do not affect structural identity. `kwargs` carries
invocation-local source-form inputs. Cached retrieval resolves selected source
references before final validation, resolves explicit runtime references once
per invocation, and validates the complete candidate before returning an
independently owned result.

```python
params_a = SettingsParameters.create(
    settings_class=DbSettings,
    config_files=["db.yaml"],
    request_id="abc-123"    # runtime override
)
params_b = SettingsParameters.create(
    settings_class=DbSettings,
    config_files=["db.yaml"],
    request_id="def-456"    # different runtime override
)

# params_a and params_b hash to the same value
assert hash(params_a) == hash(params_b)
```

<!-- concept:26 -->
## Custom Hash And Eq

The `SettingsParameters` class overrides both `__hash__` and `__eq__` to implement the structural/runtime split at the Python object protocol level. The custom implementations consider only structural fields, deliberately excluding `kwargs`:

```python
def __hash__(self):
    hashable_config_files = SettingsFileHandler.format_config_file_tuple(
        self.config_files
    )
    hashable_attrs = tuple([
        hashable_config_files,
        self.settings_class,
        self.env_prefix,
        self.secrets_dir,
        id(self.secret_store) if self.secret_store is not None else None,
        # Deliberately exclude: self.kwargs
    ])
    return hash(hashable_attrs)
```

The `__eq__` method mirrors this logic exactly -- two `SettingsParameters` are equal if and only if their structural fields match. The same structural selectors also form the `SettingsManager`'s private context key (`_StructuralKey`), so requests that differ only in kwargs select the same captured source context.

The `config_files` field requires special handling because lists are not hashable. The implementation converts them to a tuple via `SettingsFileHandler.format_config_file_tuple()` before hashing. That normalisation expands `~`, removes duplicates and keeps first-seen order; it does not sort. File order is therefore part of the structural key: later files take precedence over earlier ones for structured sources, so `["a.yaml", "b.yaml"]` and `["b.yaml", "a.yaml"]` are different requests with different precedence. They compare unequal and select different source contexts:

```python
ab = SettingsParameters.create(config_files=["a.yaml", "b.yaml"])
ba = SettingsParameters.create(config_files=["b.yaml", "a.yaml"])
print(ab == ba)   # False
```

## Parameter Create Factory

The `create()` class method is the canonical way to construct a `SettingsParameters` instance. It normalizes inputs before passing them to the frozen dataclass constructor, handling the flexible input types that callers use:

```python
@classmethod
def create(cls,
           config_files: Optional[str|UPath|List|Tuple] = None,
           settings_class: Optional[Type[BaseSettings]] = None,
           env_prefix: Optional[str] = None,
           secrets_dir: Optional[str] = None,
           secret_store: Optional["SecretReader"] = None,
           **kwargs: Any
           ) -> 'SettingsParameters':

    resolved_config_files = SettingsFileHandler.format_config_file_tuple(
        config_files
    )
    resolved_kwargs = SettingsKwargsHandler.format_kwargs_dict(kwargs)

    return cls(
        config_files=resolved_config_files,
        settings_class=settings_class,
        env_prefix=env_prefix,
        secrets_dir=secrets_dir,
        secret_store=secret_store,
        kwargs=resolved_kwargs
    )
```

The factory performs two normalizations. First, it converts `config_files` from any accepted input format (single string, UPath, list, tuple, or `None`) into a canonical tuple; `None` becomes the empty tuple `()`. Second, it extracts `**kwargs` from the caller's keyword arguments and wraps them into a fresh `kwargs` dict; absent kwargs become `{}`, not `None`. This design allows callers to pass configuration values naturally:

```python
# Natural calling convention -- kwargs are captured automatically
params = SettingsParameters.create(
    settings_class=MySettings,
    config_files="config.yaml",
    database_host="localhost",
    debug=True
)
# params.kwargs == {"database_host": "localhost", "debug": True}
```

<!-- concept:28 -->
## Merge Framework

The **merge framework** is implemented by the `SettingsParameters.merge()` class method. It combines two `SettingsParameters` instances -- a `base` and an `other` -- into a single merged result. This operation is fundamental to the framework's layered configuration pattern, where a base set of parameters (perhaps from a global default) is merged with a caller-specific set.

The merge applies a different strategy to each field type, reflecting the semantics of that field:

```python
@classmethod
def merge(cls,
          base: 'SettingsParameters',
          other: Optional['SettingsParameters'] = None,
          prioritise_base: bool = False
          ) -> 'SettingsParameters':
```

The `prioritise_base` flag inverts the default precedence. Normally, `other` values win over `base` values (last-writer-wins). When `prioritise_base=True`, `base` values win -- useful when a higher-level parameter set should not be overridden by a lower-level one.

<!-- concept:29 -->
## Ordered File List Merge

For the `config_files` field, the merge framework uses an **ordered, deduplicated merge**: the files of `base` come first in their original order, followed by the files of `other` that `base` did not already contain. Nothing is sorted. Because later files take precedence for structured sources, the order of the merged tuple decides which file wins a conflicting key.

```python
# Ordered file list merge example:
base_params = SettingsParameters.create(config_files=["base.yaml", "shared.env"])
other_params = SettingsParameters.create(config_files=["override.yaml", "shared.env"])

merged = SettingsParameters.merge(base_params, other_params)
print(merged.config_files)
# ('base.yaml', 'shared.env', 'override.yaml')
# shared.env appears once, at the position where base first listed it
```

This strategy reflects the philosophy that configuration files are additive -- you never want to silently drop a file that was explicitly requested. If both a base layer and an override layer reference the same file, it still appears only once in the result (deduplication prevents double-loading), but it keeps its earlier position, so a file shared between layers does not move to the end of the precedence order. The implementation is `SettingsFileHandler.merge_config_files()`, which concatenates the two normalised tuples and normalises again.

The `prioritise_base=True` variant changes this behavior: instead of merging, it takes `base.config_files` if non-empty, otherwise falls back to `other.config_files`. For the example above it yields `('base.yaml', 'shared.env')`. This is useful when a higher-priority layer wants to declare a complete, exclusive file set.

<!-- concept:30 -->
## Scalar Last Wins Strategy

Two different rules apply, and they are not interchangeable.

For the string scalars `env_prefix` and `secrets_dir`, the merge uses **truthiness**: the `other` value takes precedence if it is non-empty, otherwise the `base` value is retained (`other.value or base.value`). An empty string or `None` in `other` therefore does not clear a `base` value.

For `secret_store`, the merge tests **`is None`**, never truthiness: the `other` store takes precedence if it is not `None`, otherwise the `base` store is retained. A store object that happens to be falsey still counts as bound.

```python
# Scalar Last Wins example:
base_params = SettingsParameters.create(env_prefix="APP_")
other_params = SettingsParameters.create(env_prefix="MYAPP_")

merged = SettingsParameters.merge(base_params, other_params)
# merged.env_prefix == "MYAPP_" (other wins)

# With prioritise_base=True:
merged = SettingsParameters.merge(base_params, other_params, prioritise_base=True)
# merged.env_prefix == "APP_" (base wins)

# An empty string in other does not clear the base value:
merged = SettingsParameters.merge(
    SettingsParameters.create(env_prefix="APP_"),
    SettingsParameters.create(env_prefix=""),
)
# merged.env_prefix == "APP_"
```

With `prioritise_base=True` each rule is applied with the roles swapped: `base` wins when its value is truthy (or, for `secret_store`, not `None`).

The `settings_class` field receives special treatment: if both `base` and `other` declare a `settings_class` and they differ, the merge raises a `ValueError`. Two parameter sets targeting different classes cannot be meaningfully merged -- this is a conflict that requires human resolution.

<!-- concept:31 -->
## Shallow Kwargs Merge

For the `kwargs` dictionary, the merge framework uses Python's dict union operator (`|`), which performs a **shallow** merge: `other` values replace `base` values for keys that appear in both. Despite the heading, nothing is merged recursively. A nested dict supplied by `other` replaces the `base` nested dict as a whole.

```python
# Shallow kwargs merge example:
base_params = SettingsParameters.create(
    settings_class=MySettings,
    database_host="base-host",
    debug=False
)
other_params = SettingsParameters.create(
    settings_class=MySettings,
    debug=True,
    timeout=30
)

merged = SettingsParameters.merge(base_params, other_params)
# merged.kwargs == {
#     "database_host": "base-host",  # from base (not in other)
#     "debug": True,                  # from other (overrides base)
#     "timeout": 30                   # from other (not in base)
# }

# Nested values are replaced, not merged:
b = SettingsParameters.create(nested={"a": 1, "b": 2})
o = SettingsParameters.create(nested={"a": 9})
SettingsParameters.merge(b, o).kwargs   # {'nested': {'a': 9}}
```

This strategy enables layered overrides. A base parameter set might define sensible defaults for all fields, while a caller-specific parameter set overrides only the fields it cares about. Fields not mentioned in `other` are preserved from `base`.

When `prioritise_base=True`, the kwargs from `base` are used if non-empty (otherwise those of `other`), with no merging. This all-or-nothing behavior prevents partial overwrites when the base layer needs complete control.

## Merge Strategy Selection Logic

Each field type has semantics that dictate how it is combined, which determines merge behavior in multi-layer configurations.

**Config files use an ordered merge** because files are additive resources. A base layer that says "load base.yaml" and an override layer that says "load override.yaml" both contribute configuration. Dropping either file would lose data. The merge preserves all requested files in base-then-other order while deduplicating to prevent double-loading.

**Scalars use last-wins** because scalars are mutually exclusive values. An env_prefix can only be one string at a time -- there is no meaningful way to "combine" `"APP_"` and `"MYAPP_"`. The most recently specified non-empty value represents the caller's intent; `secret_store` uses the same direction with an `is None` test.

**Settings class uses validate-match** because merging parameters for different classes would produce nonsensical results. A `DatabaseSettings` parameter set cannot be meaningfully merged with an `ApiSettings` parameter set -- the field sets are incompatible. Rather than silently producing an invalid result, the merge raises an error.

**Kwargs use a shallow dict merge** because keyword arguments are a partial specification. A base layer might define `{host: "localhost", port: 5432}` while an override layer specifies `{port: 5433, debug: True}`. The dict merge preserves `host` from base, applies the `port` override from other, and adds the new `debug` key. Top-level keys are the unit of override.

## Putting It Together: Structural Contexts and Runtime Materialization

The structural/runtime split, custom hash, create factory, and merge framework
identify a private source context rather than a retained settings instance.
The complete cached flow is:

1. Caller invokes `get_settings(settings_class=X, config_files=["a.yaml"], debug=True)`.
2. `get_settings` creates or merges a `SettingsParameters`.
3. The five structural selectors identify a private context: config files,
   settings class, environment prefix, secrets directory, and bound
   secret store.
4. The context captures selected source inputs once, resolves source
   references before final validation, and retains separate owned source-form
   and resolved baseline trees.
5. Every request combines that baseline with its current runtime fields and
   validates the complete invocation.
6. Every request receives a fresh owned result. Runtime values, including
   explicit runtime secret references, do not become shared baseline state.

Absent source fields remain absent from the retained candidate, so Pydantic
evaluates defaults and default factories per materialization with the normal
class validation policy. A runtime `secret:` reference resolves once for its
invocation even if its source text equals a baseline reference. Pure source
projection output is terminal candidate data; it is not recursively treated
as another reference.

`reinitialise` is a keyword-only cached-retrieval control, not structural
identity, source reload, or refresh. Profile origin-aware eligibility and
validated template derivation (MAS-SEC-005), invocation-local
direct-constructor source framing (MAS-SEC-004), and common error
handling (MAS-SEC-006), which sanitises validation errors on fields resolved from a reference, are
all delivered; context/provider lifecycle refresh remains separate, later
work.

| Component | Role in Cached Retrieval |
|-----------|--------------------------|
| Structural fields | Select the private source context |
| Runtime fields | Invocation-local complete-validation inputs |
| Custom hash/eq | Normalize the five structural selectors |
| Create/merge | Build a caller's structural and runtime input set |
| Result ownership | Isolate every returned object graph |
