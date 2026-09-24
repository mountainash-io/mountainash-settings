# MountainAsh Settings — Secrets and Local Records

`mountainash_settings.secrets` is the settings-owned home for secret-reference
resolution and hardened local record storage. It replaced the separate
`mountainash-secrets` package as the owner of local storage.

This module does **not** provide cloud secret-manager clients (AWS, Azure, GCP,
Vault), a remote secret writer, caching, versioning or encryption. Ordinary
Pydantic Settings inputs — environment variables, configuration files and
`secrets_dir` files — need no local store.

## Contents

- [Secret references](#secret-references)
- [Local record storage](#local-record-storage)
- [Records and keys](#records-and-keys)
- [Errors](#errors)
- [Lifetime and concurrency](#lifetime-and-concurrency)
- [Platform support](#platform-support)

## Secret references

A configuration value beginning with `secret:` is resolved from a record store
during settings construction:

```yaml
database:
  password: secret:live_db.postgres.password   # record "live_db.postgres", field "password"
api_token: secret:api_token                    # single-field record
```

A dotted reference splits at the last dot into record key and field. A simple
reference requires the record to hold exactly one field.

A `secret_store` is selected directly — a `SecretReader` (or `SecretWriter` for
`persist()`) passed as an object, never registered under a name:

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
settings.persist({"TOKEN": "new"})  # requires a SecretWriter
```

A `secret:` reference with no bound store raises a value-free
`SecretCapabilityError`; it is never left as literal unresolved text. Two
`SettingsParameters` with the same `config_files`/`settings_class`/`env_prefix`/
`secrets_dir` but a *different* `secret_store` object never share a cached
context — cache identity includes the store's object identity, not its
content. Passing the same store object reuses the cached context; `None`
never detaches an already-bound store during a merge (last non-`None` wins).

## Local record storage

```python
from pathlib import Path
from mountainash_settings.secrets import FilesystemBackend, NamespacedSecretStore

root = Path("/path/to/provisioned/private-records")  # provisioned by the deployment
with FilesystemBackend(root) as store:
    records = NamespacedSecretStore(store, "application")
    with records.transaction("account"):
        records.set("account", {"token": "dummy-token"})
        assert records.get("account") == {"token": "dummy-token"}
```

| Export | Kind | Purpose |
|---|---|---|
| `SecretReader` | Protocol | `get(key) -> SecretRecord \| None` |
| `SecretWriter` | Protocol | Reader plus `set`, `delete`, `transaction(key)` |
| `ClearableSecretStore` | Protocol | Writer plus `is_cleared(key)` |
| `FilesystemBackend(base_dir)` | Store | Hardened on-disk store; context manager with terminal `close()` |
| `MemorySecretStore()` | Store | Deterministic in-process store for tests and ephemeral use |
| `NamespacedSecretStore(inner, prefix)` | View | Borrowed prefix view over a `ClearableSecretStore`; does not own the store |
| `SecretRecord`, `JSONValue` | Type aliases | Strict JSON-native record types |
| `to_key_segment(raw)` | Function | Encode an arbitrary identifier into a valid key segment |
| `SecretStoreError`, `SecretCapabilityError`, `SecretStoreUnavailableError` | Errors | See [Errors](#errors) |

`FilesystemBackend` does not create or repair the root directory or its ancestors.
It pins the opened root handle, refuses internal redirects (symlinks, reparse
points, hard links, special files) and private-access violations before touching
outside data, and writes through private exclusive temporaries with complete
replacement. `delete()` is marker-first: it records a clear marker, then removes
the record.

## Records and keys

A record is an exact `dict` with `str` keys whose values are `dict`, `list`, `str`,
`int`, finite `float`, `bool` or `None`, recursively. `{}` is valid. Subclasses,
bytes, dates, sets, custom objects, non-finite floats and reference cycles are
rejected before any mutation; repeated non-cyclic subtrees are allowed. Reads
return owned copies.

Only a missing record returns `None`. An existing record that is empty/null,
malformed or not JSON-native raises `SecretStoreUnavailableError` without
mutation. There is no legacy mode or automatic repair.

Keys are one or more dot-separated segments matching `[a-z0-9_]+`. Invalid keys
raise a value-free `ValueError`. `to_key_segment()` returns a valid segment
unchanged and maps anything else (or anything starting with `h_`) to a
deterministic `h_<sha256 base32>` segment.

The filesystem codec is PyYAML, so records nested deeper than its recursion limit
may not round-trip even though validation accepts them.

## Errors

Library-generated errors carry no record values, paths or chained causes. Branch
on class and `.reason`, never on the message.

| Class | Meaning |
|---|---|
| `SecretStoreError` | Base class |
| `SecretCapabilityError` | Required capability missing (for example a non-clearable store given to `NamespacedSecretStore`) |
| `SecretStoreUnavailableError` | Operation failed; storage may or may not have changed. See `.reason` |
| `ValueError` | Invalid key or record supplied by the caller |

| `.reason` | Meaning |
|---|---|
| `unavailable` | Generic failure; do not assume nothing changed |
| `unsupported_filesystem` | Platform or filesystem lacks a required native capability |
| `unsafe_entry` | Redirect, unsuitable entry type or access-policy violation refused |
| `decode_error` | Existing record is not valid UTF-8 |
| `malformed_yaml` | Existing record cannot be parsed |
| `invalid_record_shape` | Existing record is not a JSON-native mapping |
| `store_closed` | Store already closed |
| `write_committed_cleanup_failed` | `set()` committed the new record, but marker cleanup failed. Do not blindly retry |

## Lifetime and concurrency

The application owns each store. Stop new work and finish every operation and
entered transaction before `close()`. Close is terminal and idempotent.

`get`/`set`/`delete` take no implicit lock. Wrap compound operations in
`transaction(key)` (a real per-key lock; not reentrant on the filesystem store),
or guarantee a single writer. External edits require writers to be quiescent.
No distributed locking, crash durability or secure deletion is promised.

After an interrupted deletion, a valid record and a clear marker can coexist:
`get()` returns the record and `is_cleared()` is true. OAuth precedence for that
state belongs to the authentication consumer, not this raw record API.

## Platform support

Native operations use standard-library facilities only: POSIX descriptors,
`flock` and Linux `libacl`/macOS libSystem ACL calls; Windows NT handles, DACLs
and `LockFileEx`. Python ≥ 3.12. Linux, macOS and Windows are targeted.

Qualification status is tracked in the planning records. At the time of the M3
merge, Linux and macOS installed-candidate proofs passed; Windows had one known
diagnostic defect (a post-commit marker-close failure reports `unavailable`
instead of `write_committed_cleanup_failed`) held as a strict `xfail`.

