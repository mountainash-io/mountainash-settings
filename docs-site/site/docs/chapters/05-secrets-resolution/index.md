---
title: Secrets resolution
description: The secrets resolution subsystem covering the secret_store binding, record-store protocols, two-pass resolution pipeline, prefix syntax, settings-owned local stores, and frozen model rebuilding.
generated_by: claude skill chapter-content-generator
date: 2026-06-03
version: 0.08
---

# Secrets resolution

Settings values can be written as `secret:` references, and the library replaces them with stored values while the settings object is built. You bind a record store (in memory or on disk) to the settings, write references in kwargs, config files or environment variables, and read plain values off the finished object. `persist()` writes a record back to the same store.

<!-- concept:44 -->
<!-- concept:45 -->
<!-- concept:51 -->
## The secrets problem

Production applications keep sensitive values such as database passwords, API keys, encryption keys and OAuth client secrets out of configuration files. The configuration layer still needs to know which secret to retrieve. mountainash-settings uses references for this: configuration files and kwargs contain values like `secret:database.production.password`, and construction replaces them with the stored values.

## Secret store binding

A `secret_store` is an object you pass in directly: a `SecretReader`, or a `SecretWriter` when the settings instance also calls `persist()`. It is never looked up by a name string. It travels on `SettingsParameters.secret_store` and, for direct construction, as the `secret_store=` keyword.

This example binds a `MemorySecretStore` holding one record and resolves a reference in a keyword argument:

```python
from pydantic import SecretStr
from mountainash_settings import MountainAshBaseSettings
from mountainash_settings.secrets import MemorySecretStore

class DbSettings(MountainAshBaseSettings):
    HOST: str = "localhost"
    PASSWORD: SecretStr = SecretStr("")

store = MemorySecretStore()
with store.transaction("db.prod"):
    store.set("db.prod", {"pw": "s3cret", "user": "app"})

settings = DbSettings(HOST="db.example.com", PASSWORD="secret:db.prod.pw", secret_store=store)
print(settings.HOST)                           # db.example.com
print(settings.PASSWORD)                       # **********
print(settings.PASSWORD.get_secret_value())    # s3cret
```

The reference resolves before validation, so the `SecretStr` field wraps the real password. For an on-disk store, use `FilesystemBackend(directory)` in place of `MemorySecretStore()`; the two are interchangeable here.

The binding takes part in cache identity by object identity, never by content. Two `SettingsParameters` with identical `config_files`, `settings_class`, `env_prefix` and `secrets_dir` but different store objects never share a cached context, even if the stores would compare equal. The store is never included in `repr()`, `to_dict()`, `model_dump()` or provenance diagnostics. Merging two parameter sets keeps the last non-`None` store, and `None` never detaches a store that is already bound.

A `secret:` reference with no bound store raises a value-free `SecretCapabilityError` immediately. There is no silent literal pass-through and no process-global fallback:

```python
from mountainash_settings import SecretCapabilityError

try:
    DbSettings(PASSWORD="secret:db.prod.pw")
except SecretCapabilityError as exc:
    print(type(exc).__name__)    # SecretCapabilityError
```

## Record-store protocols

A bound store is a record store, not a string-returning callable. One key maps to one structured record (a JSON-native dictionary). The contract is split into capabilities so each consumer asks only for what it needs:

| Protocol | Adds | Needed by |
|---|---|---|
| `SecretReader` | `get(key) -> SecretRecord \| None` | Reference resolution |
| `SecretWriter` | `set`, `delete`, `transaction(key)` | Explicit `persist()` |
| `ClearableSecretStore` | `is_cleared(key)` | Token lifecycles, `NamespacedSecretStore` |

A reference names a record and, optionally, a field. `secret:db.prod.pw` loads record `db.prod` and selects `pw`; `secret:api_token` requires a single-field record. A missing record or field raises `KeyError`. Stores are synchronous because resolution runs inside the synchronous settings constructor.

## Secret prefix syntax

A string value that starts with `secret:` is treated as a reference rather than a literal. The prefix is fixed at `secret:`. In a YAML config file:

```yaml
database:
  host: db.example.com          # literal value
  password: secret:db.prod.pw   # record "db.prod", field "pw"
  api_key: secret:api_key       # single-field record "api_key"
```

The resolver strips the prefix and splits the remainder at the last dot. The part before the dot is the record key and the part after it is the field. A reference with no dot selects the only field of a single-field record; a multi-field record is ambiguous and fails. Missing records and fields raise `KeyError`.

References can appear in any value position: top-level fields, nested dictionary values, or `SecretStr` fields.

<!-- concept:46 -->
<!-- concept:47 -->
## Two pass resolution

Resolution happens in two passes while the settings object is constructed, because values arrive through different channels:

1. Pass 1 (kwargs) resolves references in the keyword arguments before Pydantic validation.
2. Pass 2 (model tree) resolves references in the populated model after Pydantic has loaded every source.

Config files, environment variables and `.env` files are only read during Pydantic's own initialisation, so references from those sources can only be resolved in the second pass. The result is the same wherever the reference came from, and you do not need to know which pass handled it.

This example puts the reference in a YAML file (pass 2) and then in a keyword argument (pass 1):

```python
import tempfile, pathlib
from mountainash_settings import SettingsParameters, get_settings

with tempfile.TemporaryDirectory() as d:
    cfg = pathlib.Path(d) / "config.yaml"
    cfg.write_text("HOST: db.example.com\nPASSWORD: secret:db.prod.pw\n")

    params = SettingsParameters.create(
        settings_class=DbSettings, config_files=[str(cfg)], secret_store=store
    )
    settings = get_settings(settings_parameters=params)
    print(settings.HOST, settings.PASSWORD.get_secret_value())   # db.example.com s3cret

    from_kwargs = DbSettings(PASSWORD="secret:db.prod.pw", secret_store=store)
    print(from_kwargs.PASSWORD.get_secret_value())                # s3cret
```

This reuses `DbSettings` and `store` from the first example.

!!! note "Cached retrieval timing"
    With cached retrieval (`get_settings`), references found in captured sources (config files, environment, `secrets_dir`, static defaults) are resolved once, when the source snapshot is captured, and stay pinned for the cached context. If the record changes in the store afterwards, a second `get_settings` call with the same parameters still returns the old value. References passed as explicit runtime overrides are resolved on each call.

## Kwargs pass resolution

The kwargs pass runs before validation, over the keyword arguments that belong to fields on the settings class. It walks nested dictionaries, lists and tuples and replaces every string that starts with the prefix.

Because this happens before validation, the resolved value goes through the normal pipeline: `SecretStr` wrapping, type coercion and field validators all apply to it. A `SecretStr` field given `"secret:db.prod.pw"` ends up holding the stored password wrapped in a `SecretStr`, so it stays masked in `repr()` and logs, as the first example shows.

<!-- concept:48 -->
## Model tree pass resolution

The model tree pass runs after all fields have been populated from every source. It inspects each field value of the live settings instance, which is how references from config files, environment variables and `.env` files get resolved. It handles four kinds of value:

- Plain strings are checked for the prefix and resolved.
- `SecretStr` values are unwrapped, checked, resolved and wrapped again as `SecretStr`.
- Nested `BaseModel` instances are inspected field by field, and the model is rebuilt only if a reference was resolved inside it.
- Dicts, lists and tuples are traversed recursively. Only containers that hold a changed value are rebuilt, and a tuple stays a tuple.

A resolved top-level field is assigned back to the instance, so `validate_assignment=True` revalidates it. If revalidation of a resolved value fails for a field that carried a reference, the raised `ValueError` names the model and field but never the resolved value.

Settings metadata fields (those starting with `SETTINGS_SOURCE_`, plus `SETTINGS_CLASS` and `SETTINGS_CLASS_NAME`) are skipped. They hold infrastructure data, not configuration values.

<!-- concept:49 -->
## Inputs are never mutated

Resolution never mutates what you pass in. It returns new containers, which matters because the input may be shared, for example as a frozen field on `SettingsParameters`. You can see this from the outside: a nested model passed as a keyword argument keeps its `secret:` text after the settings object holds the resolved copy (the full example is under [Frozen model rebuild on resolve](#frozen-model-rebuild-on-resolve)).

<!-- concept:50 -->
## Assigning resolved values

Each changed top-level field is reassigned to the live instance. Nested models are rebuilt, not edited.

<!-- concept:111 -->
## Local record stores

Settings ships the stores that back references, in `mountainash_settings.secrets`:

| Store | Purpose |
|---|---|
| `FilesystemBackend(base_dir)` | On-disk store with one record per file; refuses links and special files, locks per key, and must be closed when done |
| `MemorySecretStore()` | Deterministic in-process store for tests |
| `NamespacedSecretStore(inner, prefix)` | Borrowed prefix view over a clearable store |

`FilesystemBackend` does not create or repair its root directory. The application provisions and secures it, owns the store, and finishes all operations before `close()`. `get`, `set` and `delete` take no implicit lock, so compound operations belong inside `store.transaction(key)`.

Settings does not ship cloud secret-manager clients (Vault, AWS, Azure, GCP) or a remote writer. Values held in those systems normally reach settings through ordinary Pydantic inputs, such as environment variables or `secrets_dir` files provisioned by the deployment. An application that must read them through `secret:` references supplies its own object implementing `SecretReader`.

### Records, keys and errors

A record is an exact `dict` with `str` keys whose values are JSON-native (`dict`, `list`, `str`, `int`, finite `float`, `bool`, `None`), recursively. The types are exported as `SecretRecord` and `JSONValue`. Anything else (subclasses, bytes, dates, sets, non-finite floats, reference cycles) is rejected before any mutation, and reads return owned copies. Only a missing record returns `None`. An existing record that is empty, malformed or not a JSON-native mapping raises `SecretStoreUnavailableError`.

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

See [`docs/README_SECRETS.md`](https://github.com/mountainash-io/mountainash-settings/blob/develop/docs/README_SECRETS.md) for the full reason table and platform support.

### Persisting settings: persist() and persist_key()

`settings.persist(data, key=None)` replaces one complete record through the bound `SecretWriter`, then updates the matching fields on the settings instance. `persist_key()` returns the default key: the lowercased class name, prefixed by the lowercased environment prefix (trailing underscores removed) when one is configured.

This example binds a `FilesystemBackend` in a temporary directory, writes a record, and reads it back through a `secret:` reference:

```python
import tempfile
from mountainash_settings import FilesystemBackend, MountainAshBaseSettings

class ServiceSettings(MountainAshBaseSettings):
    TOKEN: str = ""
    REFRESH: str = ""

with tempfile.TemporaryDirectory() as d, FilesystemBackend(d) as store:
    settings = ServiceSettings(TOKEN="old", env_prefix="APP_", secret_store=store)
    key = settings.persist_key()
    print(key)                                  # app.servicesettings

    with store.transaction(key):
        settings.persist({"TOKEN": "new", "REFRESH": "r"})
    print(settings.TOKEN)                       # new
    print(store.get(key))                       # {'TOKEN': 'new', 'REFRESH': 'r'}

    reloaded = ServiceSettings(TOKEN=f"secret:{key}.TOKEN", secret_store=store)
    print(reloaded.TOKEN)                       # new
```

`persist()` raises `SecretCapabilityError` if no store is bound or the store is not a `SecretWriter`, and `ValueError` if `data` is not a strict JSON-native record. Record validation happens before the write, and field assignment happens afterward, so a field-validation failure can leave the record committed and earlier assignments applied. A transaction coordinates writers; it does not roll back across storage and model updates. Persistence does not rewrite configuration files or update a captured source snapshot, and later settings are not loaded from the saved record automatically. Use an explicit `secret:` reference to read it back, as above.

<!-- concept:55 -->
## Frozen model rebuild on resolve

A nested `BaseModel` that contains a secret reference cannot always be modified in place, because Pydantic models may be frozen. When at least one field at any depth, including inside dict, list or tuple values, resolves from a reference, the resolver builds a new instance of the same model class from the resolved values and validates it. The rebuild respects validation aliases, so aliased fields round-trip. The parent field is then assigned the rebuilt model, which revalidates it under `validate_assignment=True`.

A model in which no reference was found is returned as the same object, so its identity is preserved. If rebuilding fails validation, the error names the model and the changed fields but not the resolved values.

```python
from pydantic import BaseModel, ConfigDict
from mountainash_settings import MountainAshBaseSettings
from mountainash_settings.secrets import MemorySecretStore

class Credentials(BaseModel):
    model_config = ConfigDict(frozen=True)
    user: str
    password: str

class CredentialSettings(MountainAshBaseSettings):
    DB: Credentials
    TAGS: tuple[str, ...] = ()

store = MemorySecretStore()
with store.transaction("db.prod"):
    store.set("db.prod", {"pw": "s3cret"})

original = Credentials(user="app", password="secret:db.prod.pw")
settings = CredentialSettings(DB=original, TAGS=("a", "secret:db.prod.pw"), secret_store=store)
print(settings.DB)             # user='app' password='s3cret'
print(settings.TAGS)           # ('a', 's3cret')
print(settings.DB is original) # False
print(original.password)       # secret:db.prod.pw
```

!!! note "Rebuild cost"
    The rebuild reconstructs the entire nested model even if only one field within it contains a reference. For deeply nested models with many fields this has a measurable cost, but it runs only during construction and only when references are present.
