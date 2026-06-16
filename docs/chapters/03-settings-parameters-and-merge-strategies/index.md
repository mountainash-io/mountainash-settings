---
title: Settings Parameters and Merge Strategies
description: The SettingsParameters dataclass covering structural/runtime field separation, custom hash semantics for caching, the create factory, and the three merge strategies.
generated_by: claude skill chapter-content-generator
date: 2026-06-03
version: 0.08
---

# Settings Parameters and Merge Strategies

## Summary

This chapter introduces the SettingsParameters class that controls how settings instances are constructed and cached. You will learn about the structural/runtime field split, custom hash and equality semantics for cache key generation, the parameter create factory, and the merge framework with its three strategies: file list union, scalar last-wins, and dict deep-merge.

---

<!-- concept:27 -->
## The Parameter Abstraction Layer

Between the caller who says "give me database settings from this config file with debug=True" and the actual construction of a `MountainAshBaseSettings` instance, there is an important abstraction layer: the `SettingsParameters` class. This frozen dataclass captures everything needed to construct (or retrieve from cache) a settings instance. It separates the identity of a configuration -- which files, which class, which prefix -- from the transient overrides that might change on each access.

Understanding `SettingsParameters` is essential because it drives the caching strategy. Two requests for the same structural configuration but different runtime overrides share a single cached base instance, with overrides applied as a thin copy-on-read layer.

<!-- concept:23 -->
## SettingsParameters Class

The `SettingsParameters` class is a frozen dataclass (immutable after construction) with six fields that together describe how to build a settings instance:

```python
@dataclass(frozen=True)
class SettingsParameters:
    config_files:     Optional[List[str|UPath]|Tuple[str|UPath]] = None
    settings_class:   Optional[Type[BaseSettings]] = None
    env_prefix:       Optional[str] = None
    secrets_dir:      Optional[str] = None
    kwargs:           Optional[Dict[str, Any]] = None
    secrets_provider: Optional[str] = None
```

The frozen nature is significant. Because instances are immutable, they can safely be used as dictionary keys and cache lookup parameters. The `@dataclass(frozen=True)` decorator generates `__hash__` and `__eq__` methods by default, but `SettingsParameters` overrides both to implement its custom caching strategy.

The class also declares two reserved kwarg lists that it uses to separate Pydantic-internal parameters from user-facing attribute kwargs:

- `_reserved_pydantic_kwargs` -- parameters like `_env_prefix`, `_env_file`, `_secrets_dir` that Pydantic BaseSettings accepts in its `__init__`
- `_reserved_pydantic_modelconfig_kwargs` -- parameters like `extra`, `arbitrary_types_allowed` that modify the model config at construction time

This separation ensures that when a caller passes `_env_ignore_empty=True` alongside `database_host="localhost"`, the framework routes each parameter to its correct destination.

#### Diagram: SettingsParameters Field Classification

<iframe src="../../sims/settings-params-fields/main.html" width="100%" height="450px" scrolling="no"></iframe>
<details markdown="1">
<summary>SettingsParameters Field Classification</summary>
Type: diagram
**sim-id:** settings-params-fields<br/>
**Library:** vis-network<br/>
**Status:** Specified

A partition diagram showing the six SettingsParameters fields divided into two groups: structural (config_files, settings_class, env_prefix, secrets_dir, secrets_provider) and runtime (kwargs). Within kwargs, a secondary partition shows the three kwarg categories: pydantic_modelconfig_kwargs, pydantic_settings_kwargs, and attribute_settings_kwargs. Clicking on each field shows its type annotation and role. A toggle button switches between "cache identity view" (highlighting structural) and "override view" (highlighting runtime). Learning objective: Classify SettingsParameters fields by their role in caching vs runtime behavior (Bloom: Analyze).
</details>

<!-- concept:24 -->
<!-- concept:25 -->
## Structural Fields

**Structural fields** are the parameters that define the core identity of a configuration. They determine which cached settings instance will be retrieved -- if two `SettingsParameters` have identical structural fields, they reference the same cached object regardless of differences in their runtime fields.

The structural fields are:

| Field | Type | Purpose |
|-------|------|---------|
| `config_files` | `Optional[Tuple[str\|UPath]]` | Configuration files that define this settings identity |
| `settings_class` | `Optional[Type[BaseSettings]]` | The class to instantiate |
| `env_prefix` | `Optional[str]` | Environment variable prefix scope |
| `secrets_dir` | `Optional[str]` | Directory for pydantic-settings file-based secrets |
| `secrets_provider` | `Optional[str]` | Registered secrets resolver name |

These five fields answer the question: "What configuration am I loading?" Two sets of parameters that load the same files, for the same class, with the same prefix and secrets setup represent the same logical configuration, even if one requests `debug=True` as a runtime override and the other does not.

## Runtime Fields

**Runtime fields** are parameters that modify the output of a settings lookup without affecting which cached instance is used as the base. Currently, the single runtime field is `kwargs` -- a dictionary of key-value overrides that are applied as a copy-on-read layer on top of the cached base instance.

The architectural significance of this split is performance. Consider an application that requests the same database settings fifty times per second, each time with a different `request_id` kwarg for tracing. Without the structural/runtime split, each request would create and validate a new settings instance from scratch. With the split, a single validated instance is cached and reused, with only the lightweight `request_id` override applied as a `model_copy()`.

```python
# These two produce the same cached base instance:
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
        self.secrets_provider,
        # Deliberately exclude: self.kwargs
    ])
    return hash(hashable_attrs)
```

The `__eq__` method mirrors this logic exactly -- two `SettingsParameters` are equal if and only if their structural fields match. This contract enables the `lru_cache` decorator (which uses `__hash__` for lookup and `__eq__` for collision resolution) to correctly identify cache hits even when kwargs differ.

The `config_files` field requires special handling because lists are not hashable. The implementation converts them to a sorted tuple of strings via `SettingsFileHandler.format_config_file_tuple()` before hashing. This normalization also ensures that `["a.yaml", "b.yaml"]` and `["b.yaml", "a.yaml"]` hash to the same value -- file order within the same priority level does not affect identity.

## Parameter Create Factory

The `create()` class method is the canonical way to construct a `SettingsParameters` instance. It normalizes inputs before passing them to the frozen dataclass constructor, handling the flexible input types that callers use:

```python
@classmethod
def create(cls,
           config_files: Optional[str|UPath|List|Tuple] = None,
           settings_class: Optional[Type[BaseSettings]] = None,
           env_prefix: Optional[str] = None,
           secrets_dir: Optional[str] = None,
           secrets_provider: Optional[str] = None,
           **kwargs: Any
           ) -> 'SettingsParameters':

    resolved_config_files = SettingsFileHandler.format_config_file_tuple(
        config_files
    )
    resolved_kwargs = SettingsKwargsHandler.format_kwargs_dict(kwargs) \
        if kwargs else None

    return cls(
        config_files=resolved_config_files,
        settings_class=settings_class,
        env_prefix=env_prefix,
        secrets_dir=secrets_dir,
        secrets_provider=secrets_provider,
        kwargs=resolved_kwargs
    )
```

The factory performs two normalizations. First, it converts `config_files` from any accepted input format (single string, UPath, list, tuple) into a canonical tuple. Second, it extracts `**kwargs` from the caller's keyword arguments and wraps them into the `kwargs` dict field. This design allows callers to pass configuration values naturally:

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

#### Diagram: Merge Framework Strategy Router

<iframe src="../../sims/merge-framework-router/main.html" width="100%" height="500px" scrolling="no"></iframe>
<details markdown="1">
<summary>Merge Framework Strategy Router</summary>
Type: workflow
**sim-id:** merge-framework-router<br/>
**Library:** vis-network<br/>
**Status:** Specified

A directed graph showing two SettingsParameters inputs flowing into a central "merge()" router node. From the router, five arrows lead to strategy nodes: "File List Union" (for config_files), "Validate Match" (for settings_class), "Scalar Last Wins" (for env_prefix, secrets_dir, secrets_provider), and "Dict Deep Merge" (for kwargs). Each strategy node is clickable to show a before/after example. A toggle switches between prioritise_base=False and prioritise_base=True to show how precedence changes. Learning objective: Select the appropriate merge strategy for each field type when combining SettingsParameters (Bloom: Apply).
</details>

<!-- concept:29 -->
## File List Union Strategy

For the `config_files` field, the merge framework uses a **union strategy**: files from both `base` and `other` are combined and deduplicated. The result is the sorted union of both file sets, ensuring that all configuration sources from both parameter sets are loaded.

```python
# File List Union example:
base_params = SettingsParameters.create(config_files=["base.yaml", "shared.env"])
other_params = SettingsParameters.create(config_files=["override.yaml", "shared.env"])

merged = SettingsParameters.merge(base_params, other_params)
# merged.config_files == ("base.yaml", "override.yaml", "shared.env")
# Note: shared.env appears once (deduplicated), all files are sorted
```

This strategy reflects the philosophy that configuration files are additive -- you never want to silently drop a file that was explicitly requested. If both a base layer and an override layer reference the same file, it still appears only once in the result (deduplication prevents double-loading).

The `prioritise_base=True` variant changes this behavior: instead of unioning, it takes `base.config_files` if non-None, otherwise falls back to `other.config_files`. This is useful when a higher-priority layer wants to declare a complete, exclusive file set.

<!-- concept:30 -->
## Scalar Last Wins Strategy

For scalar fields (`env_prefix`, `secrets_dir`, `secrets_provider`), the merge framework uses a **last-wins strategy**: the `other` value takes precedence if it is non-None, otherwise the `base` value is retained.

```python
# Scalar Last Wins example:
base_params = SettingsParameters.create(env_prefix="APP_")
other_params = SettingsParameters.create(env_prefix="MYAPP_")

merged = SettingsParameters.merge(base_params, other_params)
# merged.env_prefix == "MYAPP_" (other wins)

# With prioritise_base=True:
merged = SettingsParameters.merge(base_params, other_params, prioritise_base=True)
# merged.env_prefix == "APP_" (base wins)
```

The `settings_class` field receives special treatment: if both `base` and `other` declare a `settings_class` and they differ, the merge raises a `ValueError`. Two parameter sets targeting different classes cannot be meaningfully merged -- this is a conflict that requires human resolution.

<!-- concept:31 -->
## Dict Deep Merge Strategy

For the `kwargs` dictionary, the merge framework uses Python's dict union operator (`|`), which performs a shallow merge where `other` values override `base` values for keys that appear in both:

```python
# Dict Deep Merge example:
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
```

This strategy enables layered overrides. A base parameter set might define sensible defaults for all fields, while a caller-specific parameter set overrides only the fields it cares about. Fields not mentioned in `other` are preserved from `base`.

When `prioritise_base=True`, the kwargs from `base` are used if non-None, with no merging from `other`. This all-or-nothing behavior prevents partial overwrites when the base layer needs complete control.

## Merge Strategy Selection Logic

Choosing the correct merge strategy is not arbitrary -- each field type has semantics that dictate how it should be combined. Understanding why each strategy was chosen helps you predict merge behavior in complex multi-layer configurations.

**Config files use union** because files are additive resources. A base layer that says "load base.yaml" and an override layer that says "load override.yaml" both contribute configuration. Dropping either file would lose data. The union preserves all requested files while deduplicating to prevent double-loading.

**Scalars use last-wins** because scalars are mutually exclusive values. An env_prefix can only be one string at a time -- there is no meaningful way to "combine" `"APP_"` and `"MYAPP_"`. The most recently specified value represents the caller's intent.

**Settings class uses validate-match** because merging parameters for different classes would produce nonsensical results. A `DatabaseSettings` parameter set cannot be meaningfully merged with an `ApiSettings` parameter set -- the field sets are incompatible. Rather than silently producing an invalid result, the merge raises an error.

**Kwargs use dict merge** because keyword arguments are a partial specification. A base layer might define `{host: "localhost", port: 5432}` while an override layer specifies `{port: 5433, debug: True}`. The dict merge preserves `host` from base, applies the `port` override from other, and adds the new `debug` key -- exactly the layered override semantics that callers expect.

#### Diagram: Merge Strategy Decision Tree

<iframe src="../../sims/merge-strategy-decision/main.html" width="100%" height="450px" scrolling="no"></iframe>
<details markdown="1">
<summary>Merge Strategy Decision Tree</summary>
Type: workflow
**sim-id:** merge-strategy-decision<br/>
**Library:** vis-network<br/>
**Status:** Specified

A decision tree showing how the merge method selects a strategy for each field. The root node asks "Which field?" and branches to five leaf strategies: config_files -> File List Union, settings_class -> Validate Match, env_prefix/secrets_dir/secrets_provider -> Scalar Last Wins, kwargs -> Dict Merge. Each leaf shows the rationale. A "prioritise_base" toggle at the top flips the precedence direction for applicable strategies. Clicking a leaf shows before/after examples with real values. Learning objective: Select and justify the appropriate merge strategy for each SettingsParameters field type (Bloom: Evaluate).
</details>

## Putting It Together: The Caching Flow

The structural/runtime split, custom hash, create factory, and merge framework all serve a single purpose: efficient settings caching. The complete flow works as follows:

1. Caller invokes `get_settings(settings_class=X, config_files=["a.yaml"], debug=True)`
2. The `get_settings` function creates a `SettingsParameters` via `create()`
3. The parameters are passed to `_get_settings()`, which is decorated with `@lru_cache`
4. `lru_cache` calls `__hash__` -- only structural fields contribute
5. Cache hit: the existing `MountainAshBaseSettings` instance is returned
6. `apply_runtime_overrides()` creates a `model_copy()` and applies `debug=True`
7. Caller receives a fresh copy with the override, while the cache retains the original

This flow means that the expensive work -- parsing config files, loading environment variables, running validators -- happens exactly once per unique structural configuration. Runtime overrides are applied as a lightweight copy operation.

| Component | Role in Caching |
|-----------|----------------|
| Structural Fields | Define cache key identity |
| Runtime Fields | Applied as post-cache overlay |
| Custom Hash/Eq | Enable lru_cache lookup |
| Create Factory | Normalizes inputs for consistent hashing |
| Merge Framework | Combines layered parameter sets before cache lookup |

#### Diagram: Caching Flow with Structural/Runtime Split

<iframe src="../../sims/caching-split-flow/main.html" width="100%" height="500px" scrolling="no"></iframe>
<details markdown="1">
<summary>Caching Flow with Structural/Runtime Split</summary>
Type: microsim
**sim-id:** caching-split-flow<br/>
**Library:** p5.js<br/>
**Status:** Specified

An animated simulation showing multiple settings requests arriving (represented as colored packets with structural + runtime data). Structural data is used to look up the cache (shown as a hash table). On cache hit, the cached instance is cloned and runtime overrides are applied (shown as a thin overlay layer). On cache miss, full construction occurs. A counter shows cache hit rate. Users can click "Send Request" to generate new requests with varying structural/runtime combinations. Learning objective: Evaluate how the structural/runtime split improves cache efficiency in high-throughput settings access patterns (Bloom: Evaluate).
</details>

## Key Takeaways

- **SettingsParameters** is a frozen dataclass that captures everything needed to construct or retrieve a settings instance from cache.
- **Structural fields** (config_files, settings_class, env_prefix, secrets_dir, secrets_provider) define the cache key identity -- same structure means same cached instance.
- **Runtime fields** (kwargs) are applied as a copy-on-read overlay and do not affect cache identity, enabling efficient reuse.
- **Custom Hash and Eq** deliberately exclude runtime fields, allowing `lru_cache` to share base instances across callers with different overrides.
- **Parameter Create Factory** normalizes flexible input types into a canonical frozen form suitable for hashing and caching.
- **File List Union Strategy** combines config file lists from both parameter sets, deduplicating but never dropping explicitly requested files.
- **Scalar Last Wins Strategy** gives precedence to the later (more specific) parameter set for env_prefix, secrets_dir, and secrets_provider.
- **Dict Deep Merge Strategy** merges kwargs dictionaries with later values overriding earlier ones for shared keys, preserving non-conflicting keys from both.
