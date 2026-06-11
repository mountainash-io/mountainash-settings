---
title: Caching, Settings Management, and App Settings
description: The caching layer with LRU cache, get_settings function, structural cache keys, runtime overrides via model_copy, SettingsManager, and the AppSettings convenience class.
generated_by: claude skill chapter-content-generator
date: 2026-06-03
version: 0.08
---

# Caching, Settings Management, and App Settings

## Summary

This chapter covers the caching layer that ensures settings instances are constructed once and reused efficiently, plus the AppSettings convenience class for application-level configuration. You will learn about the LRU cache decorator, the get_settings function and its internal implementation, structural cache keys derived from parameter hash/eq, runtime override application via model_copy, the SettingsManager dictionary store with named settings lookup, and the AppSettings class with its defaults, templates, and integration with the caching system.

---

## The Performance Problem

Constructing a settings instance is expensive. It involves reading configuration files from disk (or cloud storage), querying environment variables, resolving secret references from external vaults, running Pydantic's full validation pipeline, and expanding templates. In a web application handling thousands of requests per second, repeating this work for every request that needs database credentials or API configuration would create an unacceptable performance bottleneck.

The caching layer solves this by constructing each unique settings configuration exactly once and serving subsequent requests from an in-memory cache. The structural/runtime split (introduced in Chapter 3) makes this efficient: the cache key includes only structural parameters, while runtime overrides are applied as a lightweight copy-on-read operation.

<!-- concept:99 -->
<!-- concept:102 -->
## LRU Cache Decorator

The **LRU (Least Recently Used) cache decorator** from Python's `functools` module provides the caching mechanism. When applied to a function, `@lru_cache` stores the return value for each unique set of arguments and returns the cached value on subsequent calls with the same arguments.

mountainash-settings uses `@lru_cache(maxsize=None)` (unbounded cache) on two functions:

```python
from functools import lru_cache

@lru_cache(maxsize=None)
def get_settings_manager() -> SettingsManager:
    """Singleton SettingsManager instance."""
    return SettingsManager()

@lru_cache(maxsize=None)
def _get_settings(settings_parameters: SettingsParameters) -> MountainAshBaseSettings:
    """Cached settings construction based on structural parameters."""
    objSettingsManager = get_settings_manager()
    return objSettingsManager.get_or_create_settings(
        settings_parameters=settings_parameters
    )
```

The `maxsize=None` setting means the cache grows without bound. In practice, an application has a small, fixed number of unique structural configurations (one per settings class per config file set), so the cache stays small. The unbounded setting avoids the overhead of LRU eviction tracking for a cache that will never need eviction.

The `@lru_cache` decorator requires that function arguments are hashable. This is why `SettingsParameters` implements `__hash__` -- without it, the frozen dataclass could not serve as a cache key. The custom `__hash__` that excludes kwargs is what enables the structural/runtime split at the caching layer.

<!-- concept:100 -->
<!-- concept:101 -->
<!-- concept:106 -->
<!-- concept:108 -->
<!-- concept:109 -->
<!-- concept:110 -->
## Get Settings Function

The **`get_settings()` function** is the primary public API for retrieving settings instances. It accepts flexible inputs (settings class, config files, env prefix, and/or a pre-built `SettingsParameters`) and returns a validated settings instance from the cache:

```python
def get_settings(
    settings_parameters: Optional[SettingsParameters] = None,
    settings_class: Optional[Type[MountainAshBaseSettings]] = None,
    config_files: Optional[Union[UPath, str, List[UPath|str]]] = None,
    env_prefix: Optional[str] = None,
    **kwargs
) -> BaseSettings:
```

The function follows a two-step pattern:

1. **Build final parameters** -- merge the optional pre-built `settings_parameters` with any additional arguments
2. **Get cached + apply overrides** -- retrieve the cached base instance, then apply runtime overrides if kwargs are present

```python
<!-- concept:105 -->
<!-- concept:107 -->
# Simple usage -- just class and files
settings = get_settings(
    settings_class=DatabaseSettings,
    config_files="db.yaml"
)

<!-- concept:103 -->
# With runtime overrides
settings = get_settings(
    settings_class=DatabaseSettings,
    config_files="db.yaml",
    debug=True  # runtime override, doesn't bust cache
)
```

The function is also available as a class method on `MountainAshBaseSettings` via `cls.get_settings()`, providing a convenient calling convention:

```python
settings = DatabaseSettings.get_settings(config_files="db.yaml")
```

## Internal Get Settings

The **internal `_get_settings()` function** is the cached layer beneath the public `get_settings()`. It is decorated with `@lru_cache(maxsize=None)` and accepts only a `SettingsParameters` instance -- no loose kwargs, no class references, no file paths. All of that has been resolved into the parameters by the time this function is called.

```python
@lru_cache(maxsize=None)
def _get_settings(settings_parameters: SettingsParameters) -> MountainAshBaseSettings:
    objSettingsManager = get_settings_manager()
    settings = objSettingsManager.get_or_create_settings(
        settings_parameters=settings_parameters
    )
    return settings
```

The separation between `get_settings()` (public, flexible) and `_get_settings()` (internal, cached) serves a critical purpose. The public function handles parameter merging and runtime override application -- operations that should NOT be cached because they vary per call. The internal function handles only the expensive construction work -- which SHOULD be cached.

This layering means that calling `get_settings(config_files="db.yaml", debug=True)` and `get_settings(config_files="db.yaml", debug=False)` both hit the same cache entry in `_get_settings()` (because `debug` is a runtime kwarg excluded from the hash), and then each gets its own override applied cheaply.

#### Diagram: Caching Layer Architecture

<iframe src="../../sims/caching-layer-arch/main.html" width="100%" height="500px" scrolling="no"></iframe>
<details markdown="1">
<summary>Caching Layer Architecture</summary>
Type: diagram
**sim-id:** caching-layer-arch<br/>
**Library:** vis-network<br/>
**Status:** Specified

A layered architecture diagram showing three tiers: (1) Public API layer (get_settings, cls.get_settings) at the top, (2) Parameter resolution layer (SettingsParameters.create, merge) in the middle, (3) Cached construction layer (_get_settings with @lru_cache, SettingsManager) at the bottom. Arrows show how a call flows down through the layers. The cache boundary is drawn as a dashed line between layers 2 and 3. Clicking on each layer shows the operations performed at that level. A "Cache Hit" indicator lights up green when a call would hit cache. Learning objective: Identify which operations are cached vs per-call in the settings retrieval pipeline (Bloom: Analyze).
</details>

## Structural Cache Key

The **structural cache key** is the hash value produced by `SettingsParameters.__hash__()` that `@lru_cache` uses for cache lookup. As established in Chapter 3, this hash includes only structural fields (config_files, settings_class, env_prefix, secrets_dir, secrets_provider) and excludes runtime kwargs.

The key insight is that two `SettingsParameters` instances with different kwargs but identical structural fields produce the same hash:

```python
params_a = SettingsParameters.create(
    settings_class=DbSettings,
    config_files=["db.yaml"],
    host="override-a"  # runtime kwarg
)
params_b = SettingsParameters.create(
    settings_class=DbSettings,
    config_files=["db.yaml"],
    host="override-b"  # different runtime kwarg
)

# Same structural cache key
assert hash(params_a) == hash(params_b)
assert params_a == params_b  # __eq__ also structural-only
```

This means the `@lru_cache` on `_get_settings()` returns the same cached instance for both calls. The runtime differences are then applied in the layer above via `apply_runtime_overrides()`.

## Runtime Override Application

**Runtime override application** is the process of taking a cached base settings instance and applying per-call kwargs to produce a customized copy. The `apply_runtime_overrides()` method on `SettingsParameters` implements this:

```python
def apply_runtime_overrides(self, cached_settings: BaseSettings) -> BaseSettings:
    if self.kwargs:
        settings_copy = cached_settings.model_copy()
        override_kwargs = self.get_attribute_settings_kwargs()
        if override_kwargs:
            if self.secrets_provider:
                resolver = get_secrets_resolver(self.secrets_provider)
                override_kwargs = resolve_references_in_dict(
                    override_kwargs, resolver
                )
            settings_copy.update_settings_from_dict(
                settings_dict=override_kwargs
            )
        return settings_copy
    return cached_settings
```

When kwargs are present, the method creates a shallow copy of the cached instance, resolves any secret references in the override kwargs, and applies them via `update_settings_from_dict()`. When no kwargs are present, it returns the cached instance directly (zero-copy fast path).

This design ensures the cached instance is never mutated. Multiple concurrent callers can safely access the same cached base instance because overrides are always applied to a fresh copy.

<!-- concept:104 -->
## Model Copy For Overrides

The **`model_copy()` method** (from Pydantic) creates a shallow copy of a settings instance. This is the mechanism that enables safe runtime overrides without mutating the cache:

```python
# Pydantic's model_copy creates a new instance with the same field values
settings_copy = cached_settings.model_copy()

# Modifications to the copy do not affect the original
settings_copy.update_settings_from_dict({"debug": True})
assert cached_settings.debug == False  # original unchanged
```

The shallow copy is efficient -- it does not recursively deep-copy nested objects or re-run validation on existing values. It simply creates a new Python object with references to the same field values. The subsequent `update_settings_from_dict()` then mutates only the override fields on the copy.

!!! tip "When model_copy is and is not used"
    `model_copy()` is invoked only when runtime kwargs are present. If you call `get_settings(settings_class=X, config_files="y.yaml")` without any overrides, the cached instance is returned directly -- no copy overhead. This makes the zero-override path (the common case for most production code) as fast as a dictionary lookup.

## SettingsManager Class

The **SettingsManager** class maintains a dictionary cache of settings instances keyed by `SettingsParameters`. It provides the `get_or_create_settings()` method that either returns an existing cached instance or constructs a new one:

```python
class SettingsManager:
    def __init__(self) -> None:
        self.settings_object_cache: Dict[Any, MountainAshBaseSettings] = {}

    def get_or_create_settings(
        self, settings_parameters: SettingsParameters
    ) -> MountainAshBaseSettings:
        if self.is_initialised(settings_parameters):
            return self.get_settings_object(settings_parameters)
        else:
            # Import and instantiate the settings class
            settings_class_ref = getattr(
                import_module(settings_parameters.settings_class.__module__),
                settings_parameters.settings_class.__name__
            )
            obj_settings = settings_class_ref(
                settings_parameters=settings_parameters
            )
            self.settings_object_cache[settings_parameters] = obj_settings
            return obj_settings
```

The SettingsManager is itself cached as a singleton via `@lru_cache(maxsize=None)` on `get_settings_manager()`. This ensures all settings lookups share the same manager instance and its cache.

The manager uses `importlib.import_module()` to resolve the settings class by its module path and name. This indirection supports scenarios where the settings class is defined in a module that has not yet been imported at the time the parameters are constructed.

#### Diagram: SettingsManager Cache Lookup

<iframe src="../../sims/settings-manager-lookup/main.html" width="100%" height="450px" scrolling="no"></iframe>
<details markdown="1">
<summary>SettingsManager Cache Lookup</summary>
Type: microsim
**sim-id:** settings-manager-lookup<br/>
**Library:** p5.js<br/>
**Status:** Specified

An interactive simulation of the SettingsManager cache. A hash table visualization shows cached entries (each entry shows settings_class name and config_files). Users can "send" lookup requests with different SettingsParameters -- on cache hit, the entry lights up green; on cache miss, a construction animation plays and a new entry is added. A "with kwargs" checkbox adds runtime overrides to the request, showing the model_copy branch. A hit-rate counter and timing comparison (cached vs uncached) are displayed. Learning objective: Predict whether a given settings request will be a cache hit or miss based on its structural parameters (Bloom: Apply).
</details>

## Named Settings Lookup

**Named settings lookup** is the pattern where a settings instance is retrieved by a string name from a registry-backed store. This combines the SettingsManager's caching with the Registry's name-keyed lookup to provide a high-level API:

```python
# Conceptual usage:
settings = get_settings(
    settings_class=DATABASES_REGISTRY.get_settings_class("postgresql"),
    config_files="db.yaml"
)
```

The named lookup pattern is particularly useful in applications that determine the backend at runtime (from a configuration file or environment variable). The registry resolves the name to a class, and the caching layer handles efficient construction.

The `SettingsManager.get_settings_object()` method also supports override application: when kwargs are present in the parameters, it creates a `model_copy()` and applies overrides, mirroring the behavior of `apply_runtime_overrides()`:

```python
def get_settings_object(self, settings_parameters):
    obj_settings = self.settings_object_cache.get(settings_parameters)
    override_kwargs = settings_parameters.get_attribute_settings_kwargs()
    if override_kwargs:
        obj_settings = obj_settings.model_copy()
        obj_settings.update_settings_from_dict(settings_dict=override_kwargs)
    return obj_settings
```

## AppSettings Class

The **AppSettings** class is a convenience subclass of `MountainAshBaseSettings` that provides common application-level fields pre-configured with sensible defaults. It demonstrates the framework's template system in practice and serves as a starting point for application configuration:

```python
class AppSettings(MountainAshBaseSettings):
    LOCALE_TIMEZONE: str = Field(default="UTC")
    DEBUG: bool = Field(default=False)
    RUNDATE: str = Field(default=datetime.now().strftime("%Y%m%d"))
    RUNTIME: str = Field(default=datetime.now().strftime("%H%M%S"))
    RUNDATETIME: str = Field(default=None)
```

The class provides five pre-declared fields that most applications need: timezone, debug flag, run date, run time, and a combined datetime stamp. Subclasses extend these with application-specific fields while inheriting the template expansion logic.

## App Settings Defaults

**App settings defaults** are the pre-configured values that `AppSettings` provides out of the box:

| Field | Default | Source |
|-------|---------|--------|
| `LOCALE_TIMEZONE` | `"UTC"` | Static default |
| `DEBUG` | `False` | Static default |
| `RUNDATE` | Current date as `YYYYMMDD` | Computed at class definition time |
| `RUNTIME` | Current time as `HHMMSS` | Computed at class definition time |
| `RUNDATETIME` | `None` (template-derived) | Resolved during `post_init()` |

The `RUNDATE` and `RUNTIME` fields use `datetime.now().strftime()` as their defaults. This means the value is computed once when the class is first defined (imported), not on each instantiation. For per-instance timestamps, callers should override these via kwargs or environment variables.

## App Settings Templates

The **AppSettingsTemplates** class is a companion settings class that holds the template strings used by `AppSettings.post_init()`:

```python
class AppSettingsTemplates(MountainAshBaseSettings):
    RUNDATETIME_TEMPLATE: str = Field(default="{RUNDATE}T{RUNTIME}")
```

The template `"{RUNDATE}T{RUNTIME}"` combines the date and time fields into an ISO 8601-style datetime string (e.g., `"20260603T143022"`). The separation of templates into their own settings class allows the template format to be overridden via configuration files -- an application that needs a different datetime format can provide an alternative template.

The `AppSettings.post_init()` method loads the template object and applies it:

```python
def post_init(self, template_settings_parameters=None, reinitialise=False):
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

## App Settings Integration

**App settings integration** refers to how `AppSettings` connects with the caching layer and serves as a foundation for application-specific settings classes. The integration follows the standard pattern:

```python
# Direct instantiation (uncached)
settings = AppSettings(config_files="app.yaml", DEBUG=True)

# Cached instantiation via get_settings
settings = AppSettings.get_settings(config_files="app.yaml")

# Subclassing for application-specific fields
class MyAppSettings(AppSettings):
    API_BASE_URL: str = Field(default="https://api.example.com")
    MAX_RETRIES: int = Field(default=3)

    def post_init(self, **kwargs):
        super().post_init(**kwargs)
        # Custom template expansion for app-specific fields
```

The `get_settings()` class method ensures that `AppSettings` instances participate in the caching system. Multiple calls with the same config files return the same cached instance (or a lightweight copy if kwargs differ).

#### Diagram: AppSettings Inheritance and Integration

<iframe src="../../sims/app-settings-integration/main.html" width="100%" height="500px" scrolling="no"></iframe>
<details markdown="1">
<summary>AppSettings Inheritance and Integration</summary>
Type: diagram
**sim-id:** app-settings-integration<br/>
**Library:** vis-network<br/>
**Status:** Specified

A class hierarchy diagram showing the inheritance chain: BaseSettings -> MountainAshBaseSettings -> AppSettings -> MyAppSettings. Each class box shows its declared fields and methods. Arrows show inheritance. A separate lane shows AppSettingsTemplates and how post_init() bridges between AppSettings and its templates. The caching layer is shown as a cloud annotation connected to get_settings(). Clicking each class shows its fields and the override pattern. Learning objective: Design an application settings class that integrates with caching, templates, and the inheritance hierarchy (Bloom: Create).
</details>

## The Complete Caching Picture

Bringing all the caching concepts together, the complete flow for a settings retrieval is:

1. Caller invokes `get_settings()` or `cls.get_settings()` with flexible arguments
2. A `SettingsParameters` is built via `create()` and optionally `merge()`
3. The parameters are passed to `_get_settings()` (the `@lru_cache`-decorated function)
4. `lru_cache` computes `hash(settings_parameters)` -- only structural fields contribute
5. **Cache hit**: the cached `MountainAshBaseSettings` instance is returned immediately
6. **Cache miss**: `SettingsManager.get_or_create_settings()` constructs a new instance
7. Back in the public layer, `apply_runtime_overrides()` checks for kwargs
8. **No kwargs**: return the cached instance directly (zero-copy)
9. **Has kwargs**: `model_copy()` + `update_settings_from_dict()` on the copy

The result is that the expensive work (file I/O, secret resolution, validation) happens at most once per unique structural configuration, while runtime overrides are a lightweight dictionary update on a shallow copy.

## Key Takeaways

- **LRU Cache Decorator** with `maxsize=None` provides unbounded caching for both the SettingsManager singleton and individual settings instances.
- **Get Settings Function** is the public API that handles parameter building, cache lookup, and runtime override application in one call.
- **Internal Get Settings** is the `@lru_cache`-decorated layer that ensures expensive construction happens at most once per structural configuration.
- **Structural Cache Key** is the hash of structural parameters only, enabling cache sharing across calls with different runtime kwargs.
- **Runtime Override Application** creates a `model_copy()` only when kwargs are present, applying overrides without mutating the cached base.
- **Model Copy For Overrides** ensures thread-safe access to cached instances by never mutating the original.
- **SettingsManager Class** maintains the dictionary cache and handles class resolution via `importlib` for lazy construction.
- **AppSettings Class** provides pre-configured application fields (timezone, debug, date/time) with template expansion, serving as a ready-to-use base for application settings.
