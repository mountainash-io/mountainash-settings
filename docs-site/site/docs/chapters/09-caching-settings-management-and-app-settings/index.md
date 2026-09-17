---
title: Caching, Settings Management, and App Settings
description: The caching layer with LRU cache, get_settings function, structural cache keys, source-form runtime-overlay handoff, SettingsManager, and the AppSettings convenience class.
generated_by: claude skill chapter-content-generator
date: 2026-06-03
version: 0.08
---

# Caching, Settings Management, and App Settings

## Summary

This chapter covers the caching layer that ensures settings instances are constructed once and reused efficiently, plus the AppSettings convenience class for application-level configuration. You will learn about the LRU cache decorator, the get_settings function and its internal implementation, structural cache keys derived from parameter hash/eq, source-form runtime-overlay handoff, the SettingsManager dictionary store with named settings lookup, and the AppSettings class with its defaults, templates, and integration with the caching system.

---

## The Performance Problem

Constructing a settings instance is expensive. It involves reading configuration files from disk (or cloud storage), querying environment variables, resolving secret references from external vaults, running Pydantic's full validation pipeline, and expanding templates. In a web application handling thousands of requests per second, repeating this work for every request that needs database credentials or API configuration would create an unacceptable performance bottleneck.

The caching layer reuses settings instances by structural identity. Runtime kwargs are excluded from that identity but still enter cold construction. MAS-SEC-001 protects reconstruction provenance; MAS-SEC-002 must fix cold contamination and shallow-copy sharing.

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

1. **Build final parameters** -- merge the optional pre-built `settings_parameters` with any additional arguments.
2. **Get cached + apply overlay** -- retrieve the cached instance and pass original runtime inputs to the private reconstruction lifecycle through a shallow copy.

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

The public function merges parameters and applies an additional runtime overlay. The internal cached function still receives the full parameter object, including kwargs, and cold construction retains those inputs. Removing kwargs from equality/hash alone does not exclude them from retained state.

Calls with different `debug` values share a structural entry and each public call applies its overlay, but later source-only retrieval can expose the first caller's override. This is the open MAS-SEC-002 defect.

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

The `@lru_cache` on `_get_settings()` returns the same cached instance for both structural keys. Runtime inputs are then applied through `apply_runtime_overrides()`. This is not yet an isolation guarantee: the cold construction retains its runtime inputs, and later overlays use shallow copies.

## Runtime Override Application

**Runtime override application** hands original accepted inputs to the private `_apply_settings_inputs()` lifecycle. MAS-SEC-001 owns the reconstruction recipe before reference resolution; it does not fix cache ownership.

```python
settings_copy = cached_settings.model_copy()
settings_copy._apply_settings_inputs(source_inputs)
```

The private lifecycle owns the source-form patch before resolving references for live validation and assignment. On a cache hit, the public overlay resolves runtime references through the selected backend. On a cold call, runtime inputs also participate in the cached construction and can remain in the cached state. No-input calls return the cached instance directly.

Cold-call contamination and shared nested state remain open under MAS-SEC-002. Do not use this cache as a caller-isolation boundary until that milestone is implemented.

<!-- concept:104 -->
## Model Copy For Overrides

Pydantic's `model_copy()` creates a shallow outer copy, not independently owned nested settings state. The private reconstruction lifecycle owns supported source-form recipes, but that narrower guarantee does not isolate all live fields, extras or private state.

```python
# The cached baseline remains unchanged.
settings_copy = cached_settings.model_copy()
settings_copy._apply_settings_inputs({"debug": True})
assert cached_settings.debug is False
```

The shallow copy avoids re-running construction. Assignment validates supplied fields individually, not an atomic complete invocation. Nested mutable values can still be shared, and no-input calls expose the cached object.

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

An interactive simulation of structural cache hits and misses. Display class and file selectors for entries, cold construction including runtime inputs, and the shallow-copy branch for overlays. Do not portray that copy as nested-state isolation. Learning objective: predict cache hits from structural parameters and distinguish caching from the pending MAS-SEC-002 ownership guarantee.
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

`SettingsManager.get_settings_object()` shallow-copies on runtime kwargs and calls `update_settings_from_dict()`. This preserves supported source-form reconstruction through `_apply_settings_inputs()`, but does not select the backend used by the public overlay route or independently own all live state. MAS-SEC-002 must unify these routes.

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

`AppSettings.get_settings()` uses the same cache routes and therefore shares their current cold-input retention and shallow-overlay limitations.

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

1. Caller invokes `get_settings()` or `cls.get_settings()` with flexible arguments.
2. A `SettingsParameters` is built via `create()` and optionally `merge()`.
3. Structural parameters are passed to `_get_settings()` (the `@lru_cache`-decorated function).
4. `lru_cache` computes `hash(settings_parameters)` -- only structural fields contribute.
5. **Cache hit**: the cached `MountainAshBaseSettings` instance supplies the baseline.
6. **Cache miss**: `SettingsManager.get_or_create_settings()` constructs that baseline.
7. Back in the public layer, `apply_runtime_overrides()` checks for accepted kwargs.
8. **No kwargs**: return the cached instance directly (zero-copy).
9. **Has kwargs**: shallow-copy and hand original source-form inputs to `_apply_settings_inputs()` before public-route reference resolution and assignment.

Expensive source loading is reused, but cold runtime inputs can remain cached and nested live state can remain shared. Provenance ownership is narrower than the cache isolation planned in MAS-SEC-002.

## Key Takeaways

- **LRU Cache Decorator** with `maxsize=None` provides unbounded caching for both the SettingsManager singleton and individual settings instances.
- **Get Settings Function** is the public API that handles parameter building, cache lookup, and source-form runtime-overlay handoff in one call.
- **Internal Get Settings** is the `@lru_cache`-decorated layer that ensures expensive baseline construction happens once per structural configuration.
- **Structural Cache Key** is the hash of structural parameters only, enabling cache sharing across calls with different runtime kwargs.
- **Runtime Override Application** applies kwargs through the private source-form lifecycle; it does not yet guarantee caller/cache isolation.
- **Model Copy For Overrides** copies the outer model only; nested mutable state may remain shared.
- **SettingsManager Class** maintains the dictionary cache and handles class resolution via `importlib` for lazy construction.
- **AppSettings Class** provides pre-configured application fields (timezone, debug, date/time) with template expansion, serving as a ready-to-use base for application settings.
