# Advanced Usage: mountainash-settings

Use the [configuration recipes](../examples/) for independently runnable
examples. This reference covers:

- [Merging settings parameters](#merging-settings-parameters)
- [Cache contexts and runtime materialization](#cache-contexts-and-runtime-materialization)
- [Container secret references](#container-secret-references)
- [Auth modes reference](#auth-modes-reference)
- [Profile invariant tests](#profile-invariant-tests)
- [Dynamic settings resolution](#dynamic-settings-resolution)

---

## Merging settings parameters

`SettingsParameters.merge()` combines two parameter objects into one. The common pattern is a *base* set of structural parameters (config files, env prefix, settings class) merged with a *local* set of runtime overrides.

### Field-by-field merge rules

| Field | Default behaviour | With `prioritise_base=True` |
|---|---|---|
| `config_files` | Base order, then unseen files from `other` | Base files win when present |
| `settings_class` | Must be equal — raises `ValueError` if both set to different classes | Same |
| `env_prefix` | `other` wins | `base` wins |
| `secrets_dir` | `other` wins | `base` wins |
| `secret_store` | `other` wins if non-`None` (never truthiness) | `base` wins if non-`None` |
| `kwargs` | Dict merge — `other` overwrites duplicate keys | The complete base kwargs dictionary wins when nonempty |

`config_files` keeps the first occurrence of each path. The merge does not sort paths.
With `prioritise_base=True`, the base file list stays in place when it is not empty.
The same option selects the complete nonempty base kwargs dictionary; new keys
from `other` are not added in that case. Environment-prefix and secrets-directory
selectors use the winning nonempty value; the store uses non-`None` identity.

### Structured config file merge

Files of one structured format use caller order. Later mappings merge recursively.
Later lists and scalar values replace earlier values. Lists do not concatenate.

The source priority, from highest to lowest, is:

1. init values
2. environment variables
3. configured-prefix dotenv
4. unprefixed dotenv fallback
5. YAML files
6. TOML files
7. JSON files
8. Pydantic secret files
9. field defaults

The prefixed dotenv source and unprefixed fallback share source state. A prefixed
key wins when both forms exist. Cross-format priority is fixed regardless of path
order; caller order applies inside one format. See the
[source precedence recipe](../examples/source_precedence/).

### Layered configuration example

A typical pattern is to build a base parameter set for the environment (loaded from file) and merge application-specific runtime kwargs on top:

```python
from mountainash_settings import MountainAshBaseSettings, SettingsParameters, get_settings
from pydantic import Field

class AppSettings(MountainAshBaseSettings):
    HOST: str = Field(default="localhost")
    PORT: int = Field(default=8000)
    LOG_LEVEL: str = Field(default="INFO")
    TENANT_ID: str = Field(default="default")

# Base: shared configuration from file, no runtime kwargs
base_params = SettingsParameters.create(
    settings_class=AppSettings,
    config_files=["config/base.yaml", "config/production.yaml"],
    env_prefix="APP_",
)

# Local: runtime overrides for a specific request or job
runtime_params = SettingsParameters.create(
    settings_class=AppSettings,
    TENANT_ID="acme",
    LOG_LEVEL="DEBUG",
)

# Merge: base config + runtime overrides; runtime wins on conflicts
merged = SettingsParameters.merge(base_params, runtime_params)
settings = get_settings(settings_parameters=merged)
```

### Locking base values with `prioritise_base`

Pass `prioritise_base=True` when the base values must not be overridden by the second set — useful when a base set encodes security or compliance constraints:

```python
# Illustrative selected objects; no filesystem lifetime to manage here.
from mountainash_settings.secrets import MemorySecretStore

compliance_store = MemorySecretStore()
compliance_base = SettingsParameters.create(
    settings_class=AppSettings,
    config_files=["config/compliance.yaml"],
    secret_store=compliance_store,
    LOG_LEVEL="INFO",
)

# Caller-supplied params — secret_store is ignored when base wins
caller_store = MemorySecretStore()
caller_params = SettingsParameters.create(
    settings_class=AppSettings,
    secret_store=caller_store,   # would normally win
    TENANT_ID="acme",            # omitted when nonempty base kwargs win
)

locked = SettingsParameters.merge(compliance_base, caller_params, prioritise_base=True)
# locked.secret_store is compliance_store  (base wins, by object identity)
# locked.kwargs == {"LOG_LEVEL": "INFO"}  (the complete nonempty base dict wins)
```

### Controlled reconstruction from a live instance

`extract_settings_parameters()` is a controlled reconstruction capability, not a
general diagnostics dump. It returns the structural selectors together with a
fresh, independently owned tree of the accepted constructor and successful
update inputs in their original source form. For example, a
`secret:record.field` input remains a reference in the extracted kwargs rather
than a copied backend result. Extraction itself does not reread files,
environment variables, or secret backends.

Use `SETTINGS_SOURCE_KWARG_NAMES` when diagnostic code needs to know which
attribute inputs were accepted. It exposes names only. The removed
`SETTINGS_SOURCE_KWARGS` field has no compatibility alias: migrate diagnostic
uses to the names tuple, and use extraction only where reconstruction inputs
are intentionally needed.

```python
settings = AppSettings(config_files=["config/production.yaml"], TENANT_ID="acme")

# Trusted reconstruction — params.kwargs contains the source-form values.
params = settings.extract_settings_parameters()
assert settings.SETTINGS_SOURCE_KWARG_NAMES == ("TENANT_ID",)

# Extend the reconstruction input deliberately.
extended = SettingsParameters.merge(
    params,
    SettingsParameters.create(settings_class=AppSettings, LOG_LEVEL="WARNING"),
)
new_settings = get_settings(settings_parameters=extended)
```

Successful `update_settings_from_dict()` and `persist()` calls preserve
untouched accepted inputs and replace only the supplied logical fields in the
reconstruction recipe. A dict-valued field is replaced as a field, not
recursively merged. Existing partial-assignment behavior is unchanged: a
failed update does not roll back assignments that already succeeded, and it
does not publish failed or resolved input provenance. A persistence failure
after its backend write is not an atomic transaction.

The ordinary `repr()` of `SettingsParameters` omits `kwargs`, but that is a
safe-default diagnostic boundary, not a serialization guarantee. Explicit
`params.kwargs`, `to_dict()`, `dataclasses.asdict()`, pickle, debugger
inspection, and other intentional serialization or inspection can expose
caller-supplied values. Keep those operations in trusted code paths.

If an otherwise valid supplied value cannot be faithfully represented in, and independently owned by, the reconstruction recipe, construction and updates retain their normal behavior, but extraction raises a value-free `TypeError`. This includes an update whose accepted alias/path would make faithful reconstruction change an independently supplied sibling. It does not return a partial recipe, alter another field to invent a representation, or use a shared input tree.

### Service registry pattern

`SettingsParameters` objects are frozen and hashable — they can be stored in dicts and used as cache keys. This makes them a natural fit for service registries:

```python
REGISTRY = {
    "database": SettingsParameters.create(
        settings_class=DatabaseSettings,
        config_files=["config/db.yaml"],
        env_prefix="DB_",
    ),
    "cache": SettingsParameters.create(
        settings_class=CacheSettings,
        config_files=["config/cache.yaml"],
        env_prefix="CACHE_",
    ),
}

def get_service(name: str, **runtime_overrides):
    base = REGISTRY[name]
    if runtime_overrides:
        base = SettingsParameters.merge(
            base,
            SettingsParameters.create(settings_class=base.settings_class, **runtime_overrides),
        )
    return get_settings(settings_parameters=base)
```

## Cache contexts and runtime materialization

`get_settings()` retains one private source context for each structural selector
set: `config_files`, `settings_class`, `env_prefix`, `secrets_dir`, and the
bound `secret_store`'s object identity. It pins the selected source inputs and baseline resolved
references for that context. It does **not** retain a settings result or the
runtime kwargs from the first caller.

Every cached retrieval materializes a fresh, independently owned settings
object. Runtime fields are validated together with the pinned source inputs;
a caller's mutable field, extra value, private attribute, or non-field state
cannot become another caller's state. Missing source fields are left absent
from the retained candidate, so Pydantic evaluates defaults and default
factories for each materialization with the class's normal validation policy.

Cached results support ordinary containers, Pydantic models, secret wrappers,
and local paths through the same ownership policy as reconstruction. Standard
enum members are shared schema identities only when their values are exact
immutable scalars (or tuples/frozensets of them) and they have no custom member
state or slots. Opaque resources, cycles, and mutable enum state are rejected
without falling back to another source read.

Generic cached `post_init` hooks must assign declared fields through normal
validated assignment. In-place or `object.__setattr__` changes that bypass
that assignment origin are rejected. Only successful source-only calls with
`reinitialise=False` may establish raw derived carry; rejected assignments and
runtime calls never become that carry. Current explicit runtime fields win.
Default-factory outputs remain per-invocation; their secret-reference
interpretation is a separate compatibility backlog, not certified here.

References read from a selected source are resolved before final validation
and retained as the context's baseline value tree. An explicit runtime
`secret:` reference is instead resolved once for that invocation, even when
its text matches the baseline reference. Runtime values never replace the
baseline. Projected source values are terminal values: the cache does not
interpret a projector result that merely looks like a `secret:` reference.

`reinitialise` is a keyword-only cached-retrieval operation control:

```python
settings = get_settings(
    settings_class=AppSettings,
    config_files="config/production.yaml",
    HOST="alternate.example",
    reinitialise=True,
)
```

It is neither a source reload nor a cache refresh and is not part of structural
identity. Profiles recompute eligible derived fields from effective invocation
inputs while preserving explicitly supplied values. Without the flag, changing
a dependency may leave an already-derived value unchanged. See the
[recomputation recipe](../examples/recomputation/).

Capture known configurations during application startup when they should observe
stable deployment inputs. Each structural configuration initializes separately,
even when classes share file paths. Snapshots are process-local; new processes
load current deployment inputs. The cache saves source reads but still performs
validation and ownership work on retrieval. Applications own live clients and
their lifetimes; settings describe those connections.

### Cacheable custom sources

Cached retrieval supports custom external sources only through the explicit
`CacheableSettingsSource` contract exported from the package root:

`CacheableSettingsSource` still has the ordinary
`PydanticBaseSettingsSource` requirements. Implement its normal source methods
as appropriate for direct construction in addition to `capture()` and
`project()`.

```python
from mountainash_settings import CacheableSettingsSource

class InventorySource(CacheableSettingsSource):
    def capture(self) -> dict:
        """Read external state once and return an independently ownable snapshot."""

    @staticmethod
    def project(snapshot, current_state, sources_data) -> dict:
        """Return pure terminal candidate values; perform no external I/O."""
```

The settings class selects participating cache sources with the cache-only
hook `settings_capture_sources(sources)`. Its argument and result are ordered
source tuples, so a class can retain the configured built-ins and replace or
add only sources that implement capture/project:

```python
@classmethod
def settings_capture_sources(cls, sources):
    return sources
```

This hook is separate from the direct-construction
`settings_customise_sources` hook. A class that overrides the legacy hook
must explicitly adapt it for cached retrieval; otherwise cached retrieval
fails before source reads. Ordinary direct construction retains its existing
semantics. Cached retrieval requires a `MountainAshBaseSettings` subclass.
Plain Pydantic `BaseSettings` classes are rejected before source reads,
regardless of their constructor; ordinary direct construction remains available.
See the [0.1 migration guide](migration-0.1.md).

## Container secret references

Use the `secret:` prefix for a value that a secrets backend resolves.
The resolver walks nested values in dictionaries, lists, tuples, and Pydantic models.

References resolve inside:

- Declared string (`str`) fields.
- Declared `SecretStr` fields.
- Nested Pydantic models.
- Dictionary fields.
- List fields.
- Tuple values supplied through init values or runtime overrides.

A tuple remains a tuple after resolution. A resolved `SecretStr` remains wrapped as `SecretStr`.
Nested model validation aliases remain supported, including `AliasChoices` and `AliasPath`.
The resolver creates new dictionaries, lists, and tuples. It does not mutate input dictionaries or containers.

The resolver rebuilds a nested model only when a reference changes one of its values.
Pydantic validation runs during that rebuild.

---


## Auth modes reference

Authentication models and OAuth flows are owned by
[mountainash-auth-client](https://github.com/mountainash-io/mountainash-auth-client).
The 0.1 settings API no longer exports bundled auth models, `auth_modes` unions or
`auth_to_driver_kwargs()`. Settings provides the profile framework and selected
local record stores those consumers use. See [migration to 0.1](migration-0.1.md)
and [profile emission](profile-spec-pattern.md#extending-emission).

---

## Profile invariant tests

Generate convention checks for a registry in a pytest module:

```python
from mountainash_settings import spec_invariants_for
from my_package.settings import MY_REGISTRY

TestMyInvariants = spec_invariants_for(MY_REGISTRY)
```

Pytest collects the returned class. Registrations present when
`spec_invariants_for()` is called are included. Import the application's registry
before generating the class. For a complete runnable module, see
[the invariant-check recipe](../examples/invariant_checks/).

### What is checked

For each registered spec:

| Invariant | What it verifies |
|---|---|
| Name matches registry key | `spec.name == key` used to register it |
| Name is lowercase and non-empty | Prevents `"PostgreSQL"` vs `"postgresql"` mismatches |
| Parameter names are uppercase and unique | `ParameterSpec.name` conventions |
| `driver_key` values are unique | No two params map to the same output key for a target |
| Parameter `tier` is `"core"` or `"advanced"` | Valid tier values |
| `provider_type` is not `None` | Required for downstream dispatching |

These checks do not prove that kwargs work with a real driver. Keep the domain's
driver-contract tests separately. For tests that register classes dynamically,
create a fresh registry per test instead of depending on another test's state.

---

## Dynamic settings resolution

The `get_settings()` function resolves any `SettingsParameters` — including those where the settings class is only known at runtime. This enables generic service registries and plugin architectures where the calling code does not know which settings class it will receive.

### Type-agnostic factory

```python
from mountainash_settings import get_settings, SettingsParameters, MountainAshBaseSettings

SERVICE_PARAMS: dict[str, SettingsParameters] = {}

def register_service(name: str, params: SettingsParameters) -> None:
    SERVICE_PARAMS[name] = params

def get_service_settings(name: str, **overrides) -> MountainAshBaseSettings:
    base = SERVICE_PARAMS[name]
    if overrides:
        base = SettingsParameters.merge(
            base,
            SettingsParameters.create(settings_class=base.settings_class, **overrides),
        )
    return get_settings(settings_parameters=base)
```

Callers register their settings classes once; `get_service_settings()` selects pinned source state and materializes the concrete type without callers needing to name it.

### Multi-tenant configuration

Each tenant gets its own structural parameters, so the cache naturally isolates their settings:

```python
def build_tenant_params(tenant_id: str) -> SettingsParameters:
    return SettingsParameters.create(
        settings_class=AppSettings,
        config_files=["config/base.yaml", f"config/tenants/{tenant_id}.yaml"],
        env_prefix=f"{tenant_id.upper()}_",
    )

# Called once per tenant to capture that tenant's source context; later calls
# reuse the pinned source baseline and materialize fresh owned results.
settings_acme = get_settings(settings_parameters=build_tenant_params("acme"))
settings_globex = get_settings(settings_parameters=build_tenant_params("globex"))
```

### Caching guarantees

- `get_settings()` selects one private source context for the five structural
  selectors (config files, settings class, env prefix, secrets dir, and
   selected secret store's identity). It returns a fresh independently owned result for every
  retrieval.
- **Runtime kwargs do not affect structural identity.** They are
  invocation-local complete-validation inputs and never become retained
  baseline state.
- Selected source inputs remain pinned for a context. Normal retrieval does
  not clear, refresh, or reread them; a new structural context may capture its
  own source state. A new process loads changed deployment inputs.

```python
# These calls share pinned source state, not a returned settings instance:
s1 = get_settings(settings_class=AppSettings, config_files=["cfg.yaml"], LOG_LEVEL="DEBUG")
s2 = get_settings(settings_class=AppSettings, config_files=["cfg.yaml"], LOG_LEVEL="WARNING")

assert s1.LOG_LEVEL == "DEBUG"
assert s2.LOG_LEVEL == "WARNING"
```
