---
title: Caching, Settings Management, and App Settings
description: Cached settings retrieval with structural source contexts, isolated complete-invocation materialization, SettingsManager, and the AppSettings convenience class.
generated_by: claude skill chapter-content-generator
date: 2026-06-03
version: 0.08
---

# Caching, Settings Management, and App Settings

## Summary

This chapter covers cached settings retrieval, structural context identity, fresh owned result materialization, and the AppSettings convenience class.

---

## Cached retrieval

`get_settings()` and `MountainAshBaseSettings.get_settings()` select a private source context by structural identity. Every call materializes a fresh, independently owned settings object from that context; neither runtime kwargs nor a returned instance become shared baseline state.

<!-- concept:99 -->
<!-- concept:102 -->
## Manager factory and direct retrieval

`get_settings_manager()` remains a process-wide singleton manager factory. It is not a retained-settings-result cache. The manager owns private structural contexts rather than a public dictionary of settings objects.

Use public `get_settings()` for ordinary retrieval. `SettingsManager.get_or_create_settings()` is the direct manager entry point; `get_settings_object()` materializes only an already initialized context and fails if it is absent. Both direct manager routes accept keyword-only `reinitialise=False`.

```python
manager = SettingsManager()
settings = manager.get_or_create_settings(
    SettingsParameters.create(
        settings_class=DatabaseSettings,
        config_files="db.yaml",
    ),
    reinitialise=False,
)
```

Tests needing isolation use a fresh manager owner; they do not clear a production cache.

<!-- concept:100 -->
<!-- concept:101 -->
<!-- concept:106 -->
<!-- concept:108 -->
<!-- concept:109 -->
<!-- concept:110 -->
## Get Settings Function

The public `get_settings()` function accepts flexible inputs and returns a validated, independently owned instance:

```python
settings = get_settings(
    settings_class=DatabaseSettings,
    config_files="db.yaml",
    debug=True,
)
```

`SettingsParameters` merge normalizes the requested selectors and invocation
fields. Its five structural selectors are `config_files`, `settings_class`,
`env_prefix`, `secrets_dir`, and `secrets_provider`. Runtime kwargs and
`reinitialise` are not structural identity.

The first retrieval captures selected sources in normal precedence and
retains independently owned source-form and baseline-resolved trees. Later
same-context retrievals use those pinned inputs even if a source changes or
is deleted. A different context first initialized later may observe its
current sources.

Each retrieval combines the retained baseline with its current runtime fields
and validates the complete invocation. This preserves multi-field policies
and ensures validators receive raw invocation inputs rather than already
transformed prior output. Missing source fields remain absent so Pydantic
evaluates defaults and default factories per materialization under the
class's ordinary policy.

Source references are resolved before final validation. An explicit runtime
`secret:` reference resolves once per invocation—even if its text equals a
baseline reference—and never replaces baseline state. Pure source projector
output is terminal candidate data, not recursively resolved reference text.

#### Diagram: Caching Layer Architecture

<iframe src="../../sims/caching-layer-arch/main.html" width="100%" height="500px" scrolling="no"></iframe>
<details markdown="1">
<summary>Caching Layer Architecture</summary>
Type: diagram
**sim-id:** caching-layer-arch<br/>
**Library:** vis-network<br/>
**Status:** Specified

The planned diagram represents public and direct-manager entry points selecting one structural context, ordered source capture, and fresh owned materialization for every caller. It must not portray `_get_settings`, an instance LRU, a raw manager dictionary, or a shallow overlay. The textbook-refresh tooling remains unavailable, so the specified simulation has not been regenerated.
</details>

## Structural Context Identity

`SettingsParameters.__hash__()` and equality use the five structural selectors
and exclude runtime kwargs:

```python
params_a = SettingsParameters.create(
    settings_class=DbSettings,
    config_files=["db.yaml"],
    host="override-a",
)
params_b = SettingsParameters.create(
    settings_class=DbSettings,
    config_files=["db.yaml"],
    host="override-b",
)

assert hash(params_a) == hash(params_b)
assert params_a == params_b
```

Equal selectors reuse captured source state, not an object returned to the
first caller. Runtime fields remain invocation-local and every complete
result graph is isolated from other callers.

## Runtime Materialization

Runtime values are combined with the retained baseline and validated as one
complete invocation. They are not applied as a post-cache shallow overlay.
Mutable fields, extras, private state, validator-created values, and
non-field state are owned before return, so a caller cannot mutate another
caller or the retained context.

`reinitialise=True` is keyword-only operation control. It is not an
application field, source reload, refresh request, structural selector, or
lifecycle rotation mechanism. Profile origin/template behavior remains the
MAS-SEC-005 joint integration; direct-constructor source framing remains
MAS-SEC-004, shared secret-validation errors remain MAS-SEC-006, and
provider/context refresh remains separate lifecycle work.

## Cacheable Custom Sources

Cached custom sources must opt into the package-root
`CacheableSettingsSource` protocol:
Implement the source's ordinary `PydanticBaseSettingsSource` methods as needed
for direct construction as well; capture/project is the additional explicit
cached-retrieval capability.


```python
from mountainash_settings import CacheableSettingsSource

class InventorySource(CacheableSettingsSource):
    def capture(self) -> dict:
        """Capture external state once."""

    @staticmethod
    def project(snapshot, current_state, sources_data) -> dict:
        """Purely project terminal candidate values without external I/O."""
```

The cache-only settings-class hook receives and returns the configured ordered
source tuple:

```python
@classmethod
def settings_capture_sources(cls, sources):
    return sources
```

It is independent of direct construction's `settings_customise_sources` hook.
A class that overrides the legacy hook must explicitly adapt it through
`settings_capture_sources`; otherwise cached retrieval rejects it before
source reads. Direct construction keeps its existing custom-source semantics.

Standard plain `BaseSettings` subclasses inheriting `BaseSettings.__init__`
remain supported. Plain subclasses with custom constructors are rejected
before source reads by cached retrieval; direct construction remains
unchanged. `MountainAshBaseSettings` provides the supported cached
custom-constructor path.

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

`AppSettings.get_settings()` uses the same structural-context and fresh-result contract. It pins selected source inputs while keeping runtime fields and returned mutable state invocation-local. The Profile-specific origin/template behavior remains the later MAS-SEC-005 joint integration.

#### Diagram: AppSettings Inheritance and Integration

<iframe src="../../sims/app-settings-integration/main.html" width="100%" height="500px" scrolling="no"></iframe>
<details markdown="1">
<summary>AppSettings Inheritance and Integration</summary>
Type: diagram
**sim-id:** app-settings-integration<br/>
**Library:** vis-network<br/>
**Status:** Specified

The planned hierarchy diagram may show cached retrieval attached to `get_settings()`, but it must show a structural context and fresh result materialization rather than a returned cached instance or shallow overlay. The textbook-refresh tooling remains unavailable, so this specified simulation has not been regenerated.
</details>

## The Complete Caching Picture

1. Caller invokes `get_settings()` or `cls.get_settings()` with selectors and
   optional runtime fields.
2. `SettingsParameters.create()` and `merge()` normalize the request.
3. The five structural selectors select a private source context.
4. On first access, that context captures the ordered supported source inputs
   and baseline-resolved references.
5. For every access, the manager combines those inputs with current runtime
   fields and validates the complete invocation.
6. The manager installs and returns one independently owned result graph.

This reuses source state without retaining request-specific values or exposing
shared live mutable state. `reinitialise` remains an operation control, not a
refresh; cached custom sources use capture/project and unsupported legacy
hooks or plain custom constructors are rejected before reads.

## Key Takeaways

- **Get Settings Function** is the public entry point for structural context selection and fresh materialization.
- **SettingsManager** owns private contexts; it does not expose a mutable result dictionary.
- **Structural Cache Key** is the five-selector identity that reuses pinned source state across runtime invocations.
- **Runtime fields** are complete-invocation inputs and do not enter baseline state.
- **Defaults** and default factories remain Pydantic behavior evaluated per materialization.
- **CacheableSettingsSource** makes capture/project source participation explicit and keeps projector results terminal.
- **AppSettings** provides pre-configured application fields with template expansion; its Profile joint gate remains separate work.
