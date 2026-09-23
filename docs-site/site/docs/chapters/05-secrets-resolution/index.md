---
title: Secrets Resolution
description: The secrets resolution subsystem covering the registry, record-store protocols, two-pass resolution pipeline, prefix syntax, settings-owned local stores, and frozen model rebuilding.
generated_by: claude skill chapter-content-generator
date: 2026-06-03
version: 0.08
---

# Secrets Resolution

## Summary

This chapter covers the secrets resolution subsystem that transparently resolves secret references in configuration values. You will learn about the secrets registry, the record-store protocols that back it, the two-pass resolution pipeline (kwargs pass and model tree pass), helper functions for resolving references in dicts and model trees, secret prefix syntax for identifying references, the settings-owned local stores, and how frozen models are rebuilt after resolution.

---

<!-- concept:44 -->
<!-- concept:45 -->
<!-- concept:51 -->
## The Secrets Problem

Production applications store sensitive values -- database passwords, API keys, encryption keys, OAuth client secrets -- outside configuration files. However, the configuration layer still needs to know _which_ secret to retrieve. mountainash-settings solves this with a reference-based approach: configuration files and kwargs contain references like `secret:database.production.password`, and the framework resolves them transparently to their actual values during construction.

This chapter covers the resolution subsystem from the bottom up: first the registry that maps provider names to record stores, then the protocols those stores implement, then the two-pass pipeline that resolves references in both kwargs and the model tree, and finally the settings-owned local stores and how external secret managers fit in.

## Secrets Registry

The **secrets registry** is a module-level dictionary in `mountainash_settings.secrets.registry` that maps provider name strings to record stores. It provides a write-once registration pattern with four operations:

```python
_REGISTRY: dict[str, SecretsBackend] = {}

def register_secrets_backend(provider: str, backend: SecretsBackend) -> None:
    if provider in _REGISTRY:
        raise ValueError(...)  # use replace_secrets_backend() to overwrite
    _REGISTRY[provider] = backend

def get_secrets_backend(provider: str | None) -> SecretsBackend | None:
    if provider is None:
        return None
    return _REGISTRY[provider]

def replace_secrets_backend(provider: str, backend: SecretsBackend) -> None:
    _REGISTRY[provider] = backend

def clear_secrets_registry() -> None:
    _REGISTRY.clear()
```

Registration is deliberately asymmetric: registering an existing name raises `ValueError`, so a lookup cannot be silently redirected; intentional replacement uses `replace_secrets_backend()`.

| Operation | Behavior | Use Case |
|-----------|----------|----------|
| `register_secrets_backend` | Adds new; raises on duplicate | Application startup |
| `get_secrets_backend` | Returns the store; `None` for `None`; `KeyError` if unknown | Construction-time lookup |
| `replace_secrets_backend` | Overwrites unconditionally | Test fixtures |
| `clear_secrets_registry` | Empties the entire registry | Test teardown |

!!! note "Planned change"
    The registry and the `secrets_provider` parameter are current API only. The M4 cutover replaces them with a directly selected store on `SettingsParameters`, without compatibility shims.

<!-- concept:52 -->
<!-- concept:53 -->
<!-- concept:54 -->
## Secret Provider Protocol

A registered store is a **record store**, not a string-returning callable. One key maps to one structured record (a JSON-native dictionary):

```python
class SecretsBackend(Protocol):          # current broad protocol, removed in M4
    def get(self, key: str) -> dict[str, Any] | None: ...
    def set(self, key: str, data: dict[str, Any]) -> None: ...
    def delete(self, key: str) -> None: ...
    def transaction(self, key: str) -> AbstractContextManager[None]: ...
```

The settings-owned replacement splits this into capabilities so each consumer asks only for what it needs:

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
#### Diagram: Secret Reference Resolution Flow

<iframe src="../../sims/secret-reference-flow/main.html" width="100%" height="500px" scrolling="no"></iframe>
<details markdown="1">
<summary>Secret Reference Resolution Flow</summary>
Type: workflow
**sim-id:** secret-reference-flow<br/>
**Library:** vis-network<br/>
**Status:** Specified

A directed graph showing how a secret reference string flows through the resolution pipeline: the string "secret:db.prod.pw" enters, the prefix "secret:" is stripped, the remainder splits at the last dot into record key "db.prod" and field "pw", the registered record store returns the record, the field is selected, and the resolved value replaces the reference in the data structure. Learning objective: Trace how a secret reference is resolved from prefix detection through record lookup to value substitution (Bloom: Understand).
</details>

## Two Pass Resolution

The **two-pass resolution** pipeline is the core architectural pattern of the secrets subsystem. It runs in two distinct phases during `MountainAshBaseSettings.__init__`, each targeting a different data structure:

1. **Pass 1 (kwargs pass)** -- resolves references in the kwargs dictionary _before_ `BaseSettings.__init__` runs
2. **Pass 2 (model tree pass)** -- resolves references in the populated model tree _after_ `BaseSettings.__init__` completes

The two-pass design is necessary because configuration values arrive through different channels. Kwargs are available before construction as a plain dictionary, so they can be resolved early. But values loaded from config files and environment variables are not available until after `BaseSettings.__init__` populates the model fields -- so those must be resolved in a second pass over the live model tree.

```python
# Inside MountainAshBaseSettings.__init__:

# Pass 1: resolve secret references in kwargs
_backend = get_secrets_backend(local_settings_params.secrets_provider)
valid_attribute_kwargs = resolve_references_in_dict(valid_attribute_kwargs, _backend)

# ... BaseSettings.__init__ runs here ...

# Pass 2: resolve secret references in model tree
_backend = _get_backend(local_settings_params.secrets_provider)
resolve_references_in_model_tree(self, _backend)
```

This two-pass approach means that secret references work identically regardless of where they appear -- in kwargs, in YAML files, in environment variables, or in `.env` files. The caller does not need to know which pass will handle their reference.

## Kwargs Pass Resolution

The **kwargs pass** runs before Pydantic's `BaseSettings.__init__` and processes the `valid_attribute_kwargs` dictionary. At this point, the dictionary contains only the kwargs that have been validated as belonging to fields on the target settings class (the routing performed by `get_attribute_settings_kwargs()`).

The pass calls `resolve_references_in_dict()`, which recursively walks the dictionary and replaces any string value matching the secret prefix with its resolved value. Because this happens before Pydantic validation, the resolved values then flow through the normal validation pipeline -- `SecretStr` wrapping, type coercion, and field validators all apply to the resolved secret value.

This ordering is important. If a field is typed as `SecretStr` and the kwarg value is `"secret:db.prod.pw"`, the kwargs pass resolves it to the actual password string, and then Pydantic wraps that string in a `SecretStr` during validation. The end result is a properly wrapped secret that is protected from accidental exposure.

<!-- concept:48 -->
## Model Tree Pass Resolution

The **model tree pass** runs after `BaseSettings.__init__` has populated all fields from all sources. It walks the live model instance, inspecting every field value for secret references. This pass catches references that entered through config files, environment variables, or `.env` files -- sources that are only read during `BaseSettings.__init__`.

The pass calls `resolve_references_in_model_tree()`, which handles three value types:

- **Plain strings** -- checked for the prefix, resolved in place via `setattr`
- **SecretStr values** -- unwrapped via `.get_secret_value()`, checked for the prefix, resolved, and the new value assigned (Pydantic re-wraps it as `SecretStr` due to `validate_assignment=True`)
- **Nested BaseModel instances** -- recursively extracted, resolved, and rebuilt

The model tree pass deliberately skips meta-fields (those starting with `SETTINGS_SOURCE_` and the `SETTINGS_CLASS` / `SETTINGS_CLASS_NAME` fields). These contain infrastructure data, not configuration values, and should never be treated as secret references.

<!-- concept:49 -->
## Resolve References In Dict

The `resolve_references_in_dict()` function in `mountainash_settings/resolve.py` is a pure, recursive transformer. It takes a data dictionary, a record store and a prefix, and returns new containers with every matching reference resolved:

```python
def resolve_references_in_dict(
    data: dict[str, Any],
    backend: SecretsBackend,
    prefix: str = "secret:",
) -> dict[str, Any]: ...
```

It walks nested dictionaries, lists and tuples, unwraps `SecretStr` to inspect references and re-wraps resolved values, and never mutates its input. That matters because the input may be shared, for example as a frozen field on `SettingsParameters`.

<!-- concept:50 -->
## Resolve References In Model Tree

The `resolve_references_in_model_tree()` function operates on a live Pydantic model instance, mutating it in place. Unlike the dict resolver, this function handles the complexity of Pydantic's type system -- `SecretStr` values must be unwrapped to inspect the underlying string, and nested `BaseModel` instances require recursive processing.

The function handles three distinct cases for each field:

1. **BaseModel fields** -- extracted to a raw dictionary, checked for references, resolved, and rebuilt as a new model instance
2. **SecretStr fields** -- unwrapped, resolved if the underlying string is a reference, and re-assigned (triggering `SecretStr` re-wrapping via `validate_assignment`)
3. **Plain string fields** -- resolved directly if they match the prefix

```python
# Simplified structure of the model tree resolver:
for field_name in instance.model_fields:
    if field_name.startswith("SETTINGS_SOURCE_"):
        continue  # skip meta-fields

    value = getattr(instance, field_name)

    if isinstance(value, BaseModel):
        # Extract, resolve references, rebuild
        ...
    elif isinstance(value, SecretStr):
        # Unwrap, resolve, re-assign
        ...
    elif isinstance(value, str) and value.startswith(prefix):
        # Resolve directly
        ...
```

#### Diagram: Two-Pass Resolution Pipeline

<iframe src="../../sims/two-pass-resolution/main.html" width="100%" height="550px" scrolling="no"></iframe>
<details markdown="1">
<summary>Two-Pass Resolution Pipeline</summary>
Type: microsim
**sim-id:** two-pass-resolution<br/>
**Library:** p5.js<br/>
**Status:** Specified

An animated simulation of the two-pass pipeline. The left panel shows a settings class with five fields, each populated from a different source (kwarg, env var, YAML, .env, default). Values containing "secret:" prefix are highlighted in red. Pass 1 animates: kwargs references resolve (turn green). Then BaseSettings.__init__ runs (remaining fields populate). Pass 2 animates: model tree references resolve (turn green). Users can toggle which fields contain secret references and see how the two passes handle each case. A counter shows total resolver calls per pass. Learning objective: Predict which resolution pass handles a secret reference based on its configuration source (Bloom: Apply).
</details>

## Local Record Stores

Settings ships the stores that back references, in `mountainash_settings.secrets`:

| Store | Purpose |
|---|---|
| `FilesystemBackend(base_dir)` | Hardened on-disk store: pinned root handle, redirect/hard-link/special-file refusal, private exclusive temporaries, marker-first deletion, per-key locks, terminal `close()` |
| `MemorySecretStore()` | Deterministic in-process store for tests |
| `NamespacedSecretStore(inner, prefix)` | Borrowed prefix view over a clearable store |

```python
from mountainash_settings.secrets import FilesystemBackend, register_secrets_backend

store = FilesystemBackend("/path/to/provisioned/private-records")
register_secrets_backend("local", store)
```

Records are strict JSON-native mappings; malformed existing records raise value-free `SecretStoreUnavailableError` with a stable `.reason` rather than reading as absent. See `docs/README_SECRETS.md` for the full contract.

Settings does not ship cloud secret-manager clients (Vault, AWS, Azure, GCP) or a remote writer. Values held in those systems normally reach settings through ordinary Pydantic inputs (environment variables or `secrets_dir` files provisioned by the deployment). An application that must read them through `secret:` references supplies its own object implementing `SecretReader`.

<!-- concept:55 -->
## Frozen Model Rebuild On Resolve

When the model tree pass encounters a nested `BaseModel` field that contains secret references, it cannot simply modify the nested model in place -- Pydantic models may be frozen (immutable). Instead, the resolver extracts the model's fields as a raw dictionary, resolves any references in that dictionary, and rebuilds the nested model from scratch:

```python
if isinstance(value, BaseModel):
    raw_dict, has_refs = _extract_model_values(value, prefix)
    if has_refs:
        resolved_dict = resolve_references_in_dict(
            raw_dict, backend, prefix
        )
        rebuilt = type(value)(**resolved_dict)
        setattr(instance, field_name, rebuilt)
```

The `_extract_model_values()` helper recursively walks the nested model tree, unwrapping `SecretStr` fields to expose their underlying strings for reference detection. It returns both the raw dictionary and a boolean flag indicating whether any references were found -- if no references exist, the rebuild is skipped entirely (an optimization that avoids unnecessary object construction).

This rebuild pattern ensures that even deeply nested, frozen model configurations can contain secret references. The resolved model is a new instance with all references replaced by their actual values, and the parent model's field is updated via `setattr` (which triggers revalidation due to `validate_assignment=True`).

!!! note "Performance consideration"
    The rebuild operation reconstructs the entire nested model even if only one field within it contains a reference. For deeply nested models with many fields, this has a measurable cost. However, it runs only once during construction, and only when references are actually present -- the `has_refs` guard ensures no unnecessary work.

#### Diagram: Frozen Model Rebuild Process

<iframe src="../../sims/frozen-model-rebuild/main.html" width="100%" height="450px" scrolling="no"></iframe>
<details markdown="1">
<summary>Frozen Model Rebuild Process</summary>
Type: workflow
**sim-id:** frozen-model-rebuild<br/>
**Library:** vis-network<br/>
**Status:** Specified

A step-by-step workflow showing the rebuild process for a nested frozen model: (1) detect BaseModel field, (2) extract values to dict (unwrapping SecretStr), (3) check for references (has_refs flag), (4) resolve references in the extracted dict, (5) construct new model instance from resolved dict, (6) assign new instance to parent field. Clicking each step shows the data at that stage. A toggle allows users to switch between a model with references (full rebuild path) and one without (early exit at step 3). Learning objective: Explain why frozen models require rebuild rather than in-place mutation during secrets resolution (Bloom: Understand).
</details>

## Key Takeaways

- **Secrets Registry** provides write-once registration with explicit replacement, mapping provider names to record stores; it is replaced by direct store selection in M4.
- **Record-store protocols** (`SecretReader`, `SecretWriter`, `ClearableSecretStore`) return structured records; references select a record and an optional field.
- **Two Pass Resolution** handles secrets from all sources: Pass 1 resolves kwargs before Pydantic validation; Pass 2 resolves config-file and env-var values in the live model tree.
- **Kwargs Pass Resolution** runs before `BaseSettings.__init__`, allowing resolved values to flow through normal Pydantic validation and `SecretStr` wrapping.
- **Model Tree Pass Resolution** walks the live instance after construction, handling plain strings, `SecretStr` values, and nested `BaseModel` instances.
- **Secret Prefix Syntax** (`secret:path`) is configurable and domain-agnostic, enabling reuse of the resolution mechanism for non-secret reference patterns.
- **Local Record Stores** (`FilesystemBackend`, `MemorySecretStore`, `NamespacedSecretStore`) are settings-owned; cloud managers are not shipped.
- **Frozen Model Rebuild** extracts, resolves, and reconstructs nested models when they contain secret references, preserving immutability guarantees.
