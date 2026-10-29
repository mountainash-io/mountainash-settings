---
title: Caching, settings management and app settings
description: Cached settings retrieval with structural source contexts, isolated complete-invocation materialization, SettingsManager, and the AppSettings convenience class.
generated_by: claude skill chapter-content-generator
date: 2026-06-03
version: 0.08
---

# Caching, settings management and app settings

`get_settings()` reads your configuration sources once per source context and returns a fresh, independently owned settings object on every call. `SettingsManager` owns those contexts, and `AppSettings` is a ready-made base class for common application fields such as debug flag, run date and run time.

---

## Cached retrieval

`get_settings()` and `MountainAshBaseSettings.get_settings()` pick a source context from the request's structural selectors. Every call builds a new settings object from that context. Runtime keyword arguments and returned instances never become shared baseline state.

The examples below use one settings class and one YAML file:

```python
import pathlib, tempfile
from pydantic import Field
from mountainash_settings import (
    MountainAshBaseSettings, SettingsManager, SettingsParameters, get_settings,
)

class DatabaseSettings(MountainAshBaseSettings):
    host: str = "localhost"
    port: int = 5432
    tags: list[str] = Field(default_factory=list)

tmp = pathlib.Path(tempfile.mkdtemp())
(tmp / "db.yaml").write_text("host: db.internal\nport: 6543\n")
cfg = str(tmp / "db.yaml")
```

<!-- concept:99 -->
<!-- concept:102 -->
<!-- concept:105 -->
## Manager factory and direct retrieval

`get_settings_manager()` returns the process-wide `SettingsManager`. The manager is not a cache of settings results. It owns the source contexts and does not expose a dictionary of settings objects.

Use `get_settings()` for ordinary retrieval. `SettingsManager.get_or_create_settings()` is the direct manager entry point. `get_settings_object()` builds a result only from a context that is already initialized and fails if there is none. Both accept the keyword-only argument `reinitialise=False`.

```python
manager = SettingsManager()
params = SettingsParameters.create(settings_class=DatabaseSettings, config_files=cfg)

print(manager.is_initialised(params))       # False
settings = manager.get_or_create_settings(params)
print(settings.host, manager.is_initialised(params))   # db.internal True
```

`is_initialised(params)` reports whether the context for those parameters has captured its sources. It does not say whether a particular result object exists, because results are not retained. It returns `False` for an argument that is not a `SettingsParameters` and for parameters that cannot form a structural key.

Each `SettingsManager()` has its own contexts, so tests that need isolation create a fresh manager instead of clearing a shared cache.

<!-- concept:100 -->
<!-- concept:101 -->
<!-- concept:106 -->
## The get_settings function

`get_settings()` accepts a settings class, config files, an environment prefix and runtime keyword arguments, and returns a validated instance that the caller owns:

```python
a = get_settings(settings_class=DatabaseSettings, config_files=cfg)
b = get_settings(settings_class=DatabaseSettings, config_files=cfg)
print(a.host, a.port, a is b)      # db.internal 6543 False

a.tags.append("mutated")
print(b.tags)                       # []
print(get_settings(settings_class=DatabaseSettings, config_files=cfg).tags)   # []
```

Each call returns a different object, and mutating one has no effect on the next call or on the cached context.

Five structural selectors choose the context: `config_files`, `settings_class`, `env_prefix`, `secrets_dir`, and the identity of the bound `secret_store`. Runtime keyword arguments and `reinitialise` are not part of the identity.

The first retrieval for a context reads the selected sources in normal precedence and keeps independent copies of the source-form and baseline-resolved values. Later retrievals for the same context use those copies even if a source file changes or is deleted:

```python
(tmp / "db.yaml").write_text("host: changed\n")
print(get_settings(settings_class=DatabaseSettings, config_files=cfg).host)   # db.internal
```

A different context that is first initialized later reads the sources as they are at that time. A `SettingsManager()` created after the edit above sees `changed`.

Each retrieval validates the cached source values together with that call's runtime kwargs, so validators and default factories run on every call.

Source references are resolved before final validation. An explicit runtime `secret:` reference is resolved once per invocation, even when its text equals a baseline reference, and it never replaces baseline state.

## Structural context identity

`SettingsParameters` hashing and equality use the five structural selectors and ignore runtime keyword arguments:

```python
p1 = SettingsParameters.create(settings_class=DatabaseSettings, config_files=[cfg], host="override-a")
p2 = SettingsParameters.create(settings_class=DatabaseSettings, config_files=[cfg], host="override-b")

print(hash(p1) == hash(p2), p1 == p2)    # True True
```

Equal selectors share captured source state, never an object returned to an earlier caller. Runtime fields stay local to the invocation, and every result graph is isolated from other callers.

<!-- concept:103 -->
<!-- concept:104 -->
## Runtime materialization

Runtime values are combined with the cached source values and validated as one invocation, so nothing a caller changes on its result reaches another caller or the cached context.

A runtime override therefore applies to a single call:

```python
c = get_settings(settings_class=DatabaseSettings, config_files=cfg, host="override")
d = get_settings(settings_class=DatabaseSettings, config_files=cfg)
print(c.host, d.host)    # override db.internal
```

`reinitialise=True` is keyword-only operation control. It is not an application field, a source reload, a refresh request, or a structural selector. Profile template derivation uses this same route (see [Template priority rules](../04-file-handling-kwargs-and-field-templating/index.md#template-priority-rules)). Refreshing a context from changed providers is not part of `reinitialise`.

`extract_settings_parameters()` on a live instance rebuilds a `SettingsParameters` from it. The result carries the structural selectors, including the bound `secret_store`, and an independent copy of the accepted constructor and update inputs in source form. A `secret:` reference stays a reference. The method does not reread files, environment variables or secret backends, and it raises `TypeError` when the source inputs cannot be copied faithfully.

```python
params = a.extract_settings_parameters()
print(type(params).__name__)    # SettingsParameters
```

## Cacheable custom sources

Source capture is described in [Cache-safe settings sources](../02-mountainash-base-settings/index.md#cache-safe-settings-sources).

A custom source used with cached retrieval subclasses `CacheableSettingsSource`. `capture()` reads external state once per context. `project()` is a static method that turns the captured snapshot into candidate values for each call and must not do I/O. The class also needs the ordinary `PydanticBaseSettingsSource` methods for direct construction.

```python
from typing import Any
from mountainash_settings import CacheableSettingsSource

calls = {"capture": 0}

class InventorySource(CacheableSettingsSource):
    def get_field_value(self, field, field_name):
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        return self.project(self.capture(), self.current_state, self.settings_sources_data)

    def capture(self) -> dict[str, Any]:
        calls["capture"] += 1            # the external read happens here
        return {"ITEM_COUNT": 3}

    @staticmethod
    def project(snapshot, current_state, sources_data) -> dict[str, Any]:
        return {"ITEM_COUNT": snapshot["ITEM_COUNT"]}

class InventorySettings(MountainAshBaseSettings):
    ITEM_COUNT: int = 0

    @classmethod
    def settings_capture_sources(cls, sources):
        return sources + (InventorySource(cls),)

print(get_settings(settings_class=InventorySettings).ITEM_COUNT)   # 3
print(get_settings(settings_class=InventorySettings).ITEM_COUNT)   # 3
print(calls["capture"])                                            # 1
```

`settings_capture_sources` receives the configured ordered source tuple and returns the tuple to use for cached retrieval. It is independent of the `settings_customise_sources` hook used by direct construction. A class that overrides `settings_customise_sources` must adapt it through `settings_capture_sources`, or cached retrieval rejects it before any source is read. Direct construction keeps its existing behaviour.

Cached retrieval requires a `MountainAshBaseSettings` subclass. A plain Pydantic `BaseSettings` subclass is rejected before source reads, with or without a custom constructor. Direct construction of such a class still works.

<!-- concept:107 -->
## AppSettings class

`AppSettings` is a subclass of `MountainAshBaseSettings` that declares fields most applications need: `LOCALE_TIMEZONE`, `DEBUG`, `RUNDATE`, `RUNTIME` and `RUNDATETIME`. Subclass it to add your own fields. The run date and time fields come with it, and so does template expansion for `RUNDATETIME`. Import it from `mountainash_settings.settings.app`.

```python
from pydantic import Field
from mountainash_settings.settings.app import AppSettings

class MyAppSettings(AppSettings):
    API_BASE_URL: str = Field(default="https://api.example.com")
    MAX_RETRIES: int = Field(default=3)

settings = MyAppSettings.get_settings(DEBUG=True)
print(settings.DEBUG, settings.LOCALE_TIMEZONE)      # True UTC
print(settings.API_BASE_URL, settings.MAX_RETRIES)   # https://api.example.com 3
print(settings.RUNDATE, settings.RUNTIME, settings.RUNDATETIME)
# 20261029 121937 20261029T121937   (your values will differ)
```

`MyAppSettings(MAX_RETRIES=5)` constructs directly without the cache. `MyAppSettings.get_settings()` follows the same fresh-result contract as `get_settings()`: source inputs are pinned per context, and runtime fields and mutable state stay local to the call.

<!-- concept:108 -->
## App settings defaults

| Field | Default | Source |
|-------|---------|--------|
| `LOCALE_TIMEZONE` | `"UTC"` | Static default |
| `DEBUG` | `False` | Static default |
| `RUNDATE` | Local date as `YYYYMMDD` | Default factory fed by the captured run instant |
| `RUNTIME` | Local time as `HHMMSS` | Default factory fed by the captured run instant |
| `RUNDATETIME` | `None` (template-derived) | Resolved during `post_init()` |

`RUNDATE` and `RUNTIME` are not computed at import. Both are Pydantic default factories that read one local-time instant captured when initialization starts, so they always come from the same instant. `LOCALE_TIMEZONE` does not convert them. Normal source precedence applies: configuration files, environment variables and explicit field inputs override the generated defaults, and overriding one component keeps the generated value for the other.

The class variable `RUN_TIMESTAMP_SCOPE` sets how long the captured instant lives. It is not a settings field or an invocation override.

- `"context"` (the default): direct construction captures a fresh instant on each call. Cached retrieval captures once per manager-owned context, and later retrievals of that context, including `reinitialise=True`, keep it. Separate contexts and managers capture independently.
- `"process"`: one instant is shared across process-scoped `AppSettings` classes, contexts and managers. Capture happens on the first process-scoped construction or context initialization. A new process, including a forked child, captures its own instant on first use.

```python
from typing import ClassVar, Literal
from mountainash_settings.settings.app import AppSettings

class ReportingSettings(AppSettings):
    RUN_TIMESTAMP_SCOPE: ClassVar[Literal["context", "process"]] = "process"
```

Declare the scope on the class before it is initialized. Changing it on an already initialized class or context is unsupported, and an invalid value raises `ValueError`.

<!-- concept:109 -->
## App settings templates

`AppSettingsTemplates` is a companion settings class that holds the template used for `RUNDATETIME`. Its default is `"{RUNDATE}T{RUNTIME}"`, which produces strings such as `20260603T143022`. Because the template is its own settings class, configuration can override it when an application needs a different datetime format.

```python
from mountainash_settings.settings.app import AppSettings, AppSettingsTemplates

print(AppSettingsTemplates().RUNDATETIME_TEMPLATE)    # {RUNDATE}T{RUNTIME}

print(AppSettings(RUNDATE="20260101", RUNTIME="093000").RUNDATETIME)   # 20260101T093000
print(AppSettings(RUNDATETIME="custom").RUNDATETIME)                   # custom
```

An explicit `RUNDATETIME` is kept as given. When it is unset, `post_init()` fills it from the template.

<!-- concept:110 -->
## App settings integration

Direct construction skips the cache, and `get_settings()` uses it:

```python
direct = AppSettings(DEBUG=True)                # uncached
cached = AppSettings.get_settings()             # cached source context, fresh result
```

A subclass that adds fields needing template expansion overrides `post_init()` and calls `super().post_init(...)` first, as `MyAppSettings` could do. Profile template derivation uses the same cached route.

## Retrieval flow

1. The caller invokes `get_settings()` or `cls.get_settings()` with selectors and optional runtime fields.
2. The request is normalized into a `SettingsParameters`.
3. The five structural selectors pick a source context.
4. On first access, that context captures the ordered source inputs and baseline-resolved references.
5. On every access, the manager combines those inputs with the current runtime fields and validates the complete invocation.
6. The manager returns one independently owned result.
