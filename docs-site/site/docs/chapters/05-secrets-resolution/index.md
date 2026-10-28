---
title: Secrets Resolution
description: The secrets resolution subsystem covering the secret_store binding, record-store protocols, two-pass resolution pipeline, prefix syntax, settings-owned local stores, and frozen model rebuilding.
generated_by: claude skill chapter-content-generator
date: 2026-06-03
version: 0.08
---

# Secrets Resolution

The secrets subsystem resolves `secret:` references in configuration values to their stored values while settings are constructed. A `secret_store` bound directly to the settings parameters supplies the records; resolution runs in two passes (kwargs before Pydantic validation, the populated model tree after it); and settings ships its own local record stores plus `persist()` / `persist_key()` for writing records back.

<!-- concept:44 -->
<!-- concept:45 -->
<!-- concept:51 -->
## The Secrets Problem

Production applications store sensitive values -- database passwords, API keys, encryption keys, OAuth client secrets -- outside configuration files. However, the configuration layer still needs to know _which_ secret to retrieve. mountainash-settings solves this with a reference-based approach: configuration files and kwargs contain references like `secret:database.production.password`, and the framework resolves them transparently to their actual values during construction.

## Secret Store Binding

A `secret_store` is a directly selected object — a `SecretReader`, or a `SecretWriter` when the settings instance also calls `persist()` — never looked up by a name string. It travels on `SettingsParameters.secret_store` and, for direct construction, as the `secret_store=` keyword:

```python
from mountainash_settings import SettingsParameters, get_settings
from mountainash_settings.secrets import FilesystemBackend

store = FilesystemBackend("/path/to/provisioned/private-records")
params = SettingsParameters.create(
    settings_class=AppSettings,
    config_files=["config.yaml"],
    secret_store=store,
)
settings = get_settings(settings_parameters=params)
```

The binding participates in cache identity by **object identity**, never content: hashing and equality use `id(store)`, never the store's own `__hash__`/`__eq__`, and the store is never included in `repr()`, `to_dict()`, `model_dump()` or provenance diagnostics. Two `SettingsParameters` with identical `config_files`/`settings_class`/`env_prefix`/`secrets_dir` but *different* store objects never share a cached context, even if the stores would compare equal by content. Merging two parameter sets keeps the last non-`None` store (tested with `is None`, never truthiness); `None` never detaches an already-bound store.

A `secret:` reference with no bound store raises a value-free `SecretCapabilityError` immediately — there is no silent literal pass-through and no process-global fallback.

## Record-Store Protocols

A bound store is a **record store**, not a string-returning callable. One key maps to one structured record (a JSON-native dictionary). The library splits the contract into capabilities so each consumer asks only for what it needs:

| Protocol | Adds | Needed by |
|---|---|---|
| `SecretReader` | `get(key) -> SecretRecord \| None` | Reference resolution |
| `SecretWriter` | `set`, `delete`, `transaction(key)` | Explicit `persist()` |
| `ClearableSecretStore` | `is_cleared(key)` | Token lifecycles, `NamespacedSecretStore` |

A reference names a record and, optionally, a field: `secret:live_db.postgres.password` loads record `live_db.postgres` and selects `password`; `secret:api_token` requires a single-field record. A missing record or field raises `KeyError`. Stores are synchronous because resolution runs inside the synchronous `MountainAshBaseSettings.__init__`.

## Secret Prefix Syntax

The **secret prefix syntax** is the string pattern that identifies a value as a reference to an external secret rather than a literal value. The default prefix is `secret:`, and any string value that starts with this prefix is treated as a reference.

```yaml
# In a YAML config file:
database:
  host: db.example.com          # literal value
  password: secret:db.prod.pw   # record "db.prod", field "pw"
  api_key: secret:api_key       # single-field record "api_key"
```

The prefix is configurable -- the `resolve_references_in_dict()` and `resolve_references_in_model_tree()` functions accept a `prefix` parameter that defaults to `"secret:"`.

For any string value that starts with the prefix, the resolver strips it and splits the remainder at the last dot: the part before is the record key, the part after is the field. A reference with no dot selects the only field of a single-field record; a multi-field record is ambiguous and fails. Missing records and fields raise `KeyError`.

References can appear in any value position -- top-level fields, nested dictionary values, or `SecretStr` fields. The two-pass resolution pipeline ensures all positions are covered.

<!-- concept:46 -->
<!-- concept:47 -->

## Two Pass Resolution

The **two-pass resolution** pipeline is the core architectural pattern of the secrets subsystem. It runs in two distinct phases during `MountainAshBaseSettings.__init__`, each targeting a different data structure:

1. **Pass 1 (kwargs pass)** -- resolves references in the kwargs dictionary _before_ `BaseSettings.__init__` runs
2. **Pass 2 (model tree pass)** -- resolves references in the populated model tree _after_ `BaseSettings.__init__` completes

The two-pass design is necessary because configuration values arrive through different channels. Kwargs are available before construction as a plain dictionary, so they can be resolved early. But values loaded from config files and environment variables are not available until after `BaseSettings.__init__` populates the model fields -- so those must be resolved in a second pass over the live model tree.

```python
# Inside MountainAshBaseSettings.__init__ (equivalent to; the implementation calls
# _resolve_dict_with_changed_fields, which also returns the changed field names
# used for error sanitisation):

# Pass 1: resolve secret references in kwargs
valid_attribute_kwargs = resolve_references_in_dict(valid_attribute_kwargs, local_settings_params.secret_store)

# ... BaseSettings.__init__ runs here ...

# Pass 2: resolve secret references in model tree
resolve_references_in_model_tree(self, local_settings_params.secret_store)
```

This two-pass approach means that secret references work identically regardless of where they appear -- in kwargs, in YAML files, in environment variables, or in `.env` files. The caller does not need to know which pass will handle their reference.

!!! note "Cached retrieval timing"
    With cached retrieval (`get_settings`), references found in captured sources (config files, environment, `secrets_dir`, static defaults) are resolved once when the source snapshot is captured and stay pinned for the cached context. References passed as explicit runtime overrides are resolved on each invocation.

## Kwargs Pass Resolution

The **kwargs pass** runs before Pydantic's `BaseSettings.__init__` and processes the `valid_attribute_kwargs` dictionary. At this point, the dictionary contains only the kwargs that have been validated as belonging to fields on the target settings class (the routing performed by `get_attribute_settings_kwargs()`).

The pass calls `resolve_references_in_dict()`, which recursively walks the dictionary and replaces any string value matching the secret prefix with its resolved value. Because this happens before Pydantic validation, the resolved values then flow through the normal validation pipeline -- `SecretStr` wrapping, type coercion, and field validators all apply to the resolved secret value.

This ordering is important. If a field is typed as `SecretStr` and the kwarg value is `"secret:db.prod.pw"`, the kwargs pass resolves it to the actual password string, and then Pydantic wraps that string in a `SecretStr` during validation. The end result is a properly wrapped secret that is protected from accidental exposure.

<!-- concept:48 -->
## Model Tree Pass Resolution

The **model tree pass** runs after `BaseSettings.__init__` has populated all fields from all sources. It walks the live model instance, inspecting every field value for secret references. This pass catches references that entered through config files, environment variables, or `.env` files -- sources that are only read during `BaseSettings.__init__`.

The pass calls `resolve_references_in_model_tree()`, which handles four kinds of value:

- **Plain strings** -- checked for the prefix and resolved
- **SecretStr values** -- unwrapped via `.get_secret_value()`, checked for the prefix, resolved, and re-wrapped as `SecretStr`
- **Nested BaseModel instances** -- each field is inspected recursively, and the model is rebuilt only if a reference was resolved inside it
- **dict, list and tuple containers** -- traversed recursively; only containers that hold a changed value are rebuilt (a tuple stays a tuple), unchanged containers are returned as the same object

A resolved top-level field is then assigned back to the instance with `setattr`, so `validate_assignment=True` revalidates it. If revalidation of a resolved value fails for a field that carried a reference, the raised `ValueError` names the model and field but never the resolved value.

The model tree pass deliberately skips meta-fields (those starting with `SETTINGS_SOURCE_` and the `SETTINGS_CLASS` / `SETTINGS_CLASS_NAME` fields). These contain infrastructure data, not configuration values, and should never be treated as secret references.

<!-- concept:49 -->
## Resolve References In Dict

The `resolve_references_in_dict()` function in `mountainash_settings/resolve.py` is a pure, recursive transformer. It takes a data dictionary, a record store and a prefix, and returns new containers with every matching reference resolved:

```python
def resolve_references_in_dict(
    data: dict[str, Any],
    store: SecretReader | None,
    prefix: str = "secret:",
) -> dict[str, Any]: ...
```

It walks nested dictionaries, lists and tuples, unwraps `SecretStr` to inspect references and re-wraps resolved values, and never mutates its input. That matters because the input may be shared, for example as a frozen field on `SettingsParameters`.

<!-- concept:50 -->
## Resolve References In Model Tree

The `resolve_references_in_model_tree()` function operates on a live Pydantic model instance, assigning resolved values back onto it. Unlike the dict resolver, it has to work with Pydantic's type system -- `SecretStr` values are unwrapped to inspect the underlying string, and nested `BaseModel` instances are rebuilt rather than edited.

```python
def resolve_references_in_model_tree(
    instance: BaseModel,
    store: SecretReader | None,
    prefix: str = "secret:",
) -> None: ...
```

Every top-level field except the meta-fields (`SETTINGS_SOURCE_*`, `SETTINGS_CLASS`, `SETTINGS_CLASS_NAME`) is passed through the same recursive engine used by `resolve_references_in_dict()`, so strings, `SecretStr` values, nested models and containers all follow one set of rules. If a field changed, the new value is assigned with `setattr`.

<!-- concept:111 -->
## Local Record Stores

Settings ships the stores that back references, in `mountainash_settings.secrets`:

| Store | Purpose |
|---|---|
| `FilesystemBackend(base_dir)` | Hardened on-disk store: pinned root handle, redirect/hard-link/special-file refusal, private exclusive temporaries, marker-first deletion, per-key locks, terminal `close()` |
| `MemorySecretStore()` | Deterministic in-process store for tests |
| `NamespacedSecretStore(inner, prefix)` | Borrowed prefix view over a clearable store |

```python
from mountainash_settings import SettingsParameters
from mountainash_settings.secrets import FilesystemBackend

with FilesystemBackend("/path/to/provisioned/private-records") as store:
    params = SettingsParameters.create(settings_class=AppSettings, secret_store=store)
```

`FilesystemBackend` does not create or repair its root directory; the application provisions and secures it, owns the store, and finishes all operations before `close()`. `get`/`set`/`delete` take no implicit lock, so compound operations belong inside `store.transaction(key)`.

Settings does not ship cloud secret-manager clients (Vault, AWS, Azure, GCP) or a remote writer. Values held in those systems normally reach settings through ordinary Pydantic inputs (environment variables or `secrets_dir` files provisioned by the deployment). An application that must read them through `secret:` references supplies its own object implementing `SecretReader`.

### Records, Keys and Errors

A record is an exact `dict` with `str` keys whose values are JSON-native (`dict`, `list`, `str`, `int`, finite `float`, `bool`, `None`), recursively; the types are exported as `SecretRecord` and `JSONValue`. Anything else (subclasses, bytes, dates, sets, non-finite floats, reference cycles) is rejected before any mutation, and reads return owned copies. Only a missing record returns `None`; an existing record that is empty, malformed or not a JSON-native mapping raises `SecretStoreUnavailableError`.

Keys are one or more dot-separated segments matching `[a-z0-9_]+`; an invalid key raises a value-free `ValueError`. `to_key_segment(raw)` returns a valid segment unchanged and maps any other identifier (or one starting with `h_`) to a deterministic `h_<sha256 base32>` segment:

```python
from mountainash_settings.secrets import to_key_segment

to_key_segment("abc")          # 'abc'
to_key_segment("Hello World")  # 'h_uwi2nval6qqeasqbc4z47n5rsdlcyzn7bpg2gk2xwj35tlm7crxa'
```

Library-generated errors carry no record values, paths or chained causes, so callers branch on class and `.reason`, never on the message:

| Class | Meaning |
|---|---|
| `SecretStoreError` | Base class |
| `SecretCapabilityError` | A required capability is missing (no store bound, a store that cannot write, a non-clearable store given to `NamespacedSecretStore`) |
| `SecretStoreUnavailableError` | The operation failed; storage may or may not have changed. See `.reason` (for example `unsafe_entry`, `malformed_yaml`, `invalid_record_shape`, `store_closed`, `write_committed_cleanup_failed`) |

See `docs/README_SECRETS.md` for the full reason table and platform support.

### Persisting Settings: persist() and persist_key()

`settings.persist(data, key=None)` replaces one complete record through the bound `SecretWriter`, then updates the matching fields on the settings instance. `persist_key()` derives the default key: the lowercased class name, prefixed by the lowercased environment prefix (trailing underscores removed) when one is configured.

```python
from mountainash_settings import MountainAshBaseSettings
from mountainash_settings.secrets import MemorySecretStore

class ServiceSettings(MountainAshBaseSettings):
    TOKEN: str = ""
    REFRESH: str = ""

store = MemorySecretStore()
settings = ServiceSettings(TOKEN="old", env_prefix="APP_", secret_store=store)

settings.persist_key()                  # 'app.servicesettings'
with store.transaction(settings.persist_key()):
    settings.persist({"TOKEN": "new", "REFRESH": "r"})

settings.TOKEN                          # 'new'
store.get("app.servicesettings")        # {'TOKEN': 'new', 'REFRESH': 'r'}
```

`persist()` raises `SecretCapabilityError` if no store is bound or the store is not a `SecretWriter`, and `ValueError` if `data` is not a strict JSON-native record. Record validation happens before the write; field assignment happens afterward, so a field-validation failure can leave the record committed and earlier assignments applied. A transaction coordinates writers; it does not roll back across storage and model updates. Persistence does not rewrite configuration files or update a captured source snapshot, and later settings are not loaded from the saved record automatically -- use an explicit `secret:` reference to read it back.

<!-- concept:55 -->
## Frozen Model Rebuild On Resolve

A nested `BaseModel` that contains a secret reference cannot be modified in place -- Pydantic models may be frozen (immutable). Instead, the resolver inspects the model's fields recursively and, when at least one field (at any depth, including inside dict/list/tuple values) resolved from a reference, builds a new instance of the same model class from the resolved field values and validates it. The rebuild respects validation aliases, so aliased fields round-trip. The parent field is then assigned the rebuilt model through `setattr`, which revalidates it under `validate_assignment=True`.

A model in which no reference was found is returned as the same object, so no rebuild happens and its identity is preserved. If rebuilding fails validation, the error names the model and the changed fields but not the resolved values.

This rebuild pattern ensures that even deeply nested, frozen model configurations can contain secret references.

!!! note "Performance consideration"
    The rebuild reconstructs the entire nested model even if only one field within it contains a reference. For deeply nested models with many fields, this has a measurable cost. However, it runs only during construction, and only when references are actually present.
