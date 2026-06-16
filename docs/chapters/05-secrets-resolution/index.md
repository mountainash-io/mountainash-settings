---
title: Secrets Resolution
description: The secrets resolution subsystem covering the registry, provider protocol, two-pass resolution pipeline, prefix syntax, built-in providers, and frozen model rebuilding.
generated_by: claude skill chapter-content-generator
date: 2026-06-03
version: 0.08
---

# Secrets Resolution

## Summary

This chapter covers the secrets resolution subsystem that transparently resolves secret references in configuration values. You will learn about the secrets registry, the secret provider protocol for implementing pluggable backends, the two-pass resolution pipeline (kwargs pass and model tree pass), helper functions for resolving references in dicts and model trees, secret prefix syntax for identifying references, the three built-in providers (Vault, SSM, Key Vault), and how frozen models are rebuilt after resolution.

---

<!-- concept:44 -->
<!-- concept:45 -->
<!-- concept:51 -->
## The Secrets Problem

Production applications store sensitive values -- database passwords, API keys, encryption keys, OAuth client secrets -- in dedicated secrets management systems rather than in configuration files or environment variables. However, the configuration layer still needs to know _which_ secret to retrieve. mountainash-settings solves this with a reference-based approach: configuration files and kwargs contain references like `secret:database/production/password`, and the framework resolves them transparently to their actual values during construction.

This chapter covers the resolution subsystem from the bottom up: first the registry that maps provider names to resolver functions, then the protocol that resolvers must implement, then the two-pass pipeline that resolves references in both kwargs and the model tree, and finally the three provider patterns that connect to external secrets managers.

## Secrets Registry

The **secrets registry** is a module-level dictionary that maps provider name strings to resolver callable objects. It provides a simple write-once registration pattern with four operations:

```python
# The registry is a plain dictionary
_REGISTRY: dict[str, SecretsResolver] = {}

def register_secrets_resolver(provider: str, resolver: SecretsResolver) -> None:
    if provider in _REGISTRY:
        raise ValueError(
            f"Secrets resolver '{provider}' is already registered. "
            f"Use replace_secrets_resolver() for explicit replacement."
        )
    _REGISTRY[provider] = resolver

def get_secrets_resolver(provider: str) -> SecretsResolver:
    return _REGISTRY[provider]

def replace_secrets_resolver(provider: str, resolver: SecretsResolver) -> None:
    _REGISTRY[provider] = resolver

def clear_secrets_registry() -> None:
    _REGISTRY.clear()
```

The registry enforces a deliberate asymmetry between initial registration and replacement. Calling `register_secrets_resolver()` with an already-registered name raises a `ValueError` -- this prevents accidental overwrites that could silently redirect secret lookups to the wrong backend. When intentional replacement is needed (for example, swapping a production Vault resolver for a test stub), the caller must use `replace_secrets_resolver()` explicitly.

| Operation | Behavior | Use Case |
|-----------|----------|----------|
| `register_secrets_resolver` | Adds new; raises on duplicate | Application startup |
| `get_secrets_resolver` | Returns callable; raises KeyError if missing | Construction-time lookup |
| `replace_secrets_resolver` | Overwrites unconditionally | Test fixtures, hot-reload |
| `clear_secrets_registry` | Empties the entire registry | Test teardown |

<!-- concept:52 -->
<!-- concept:53 -->
<!-- concept:54 -->
## Secret Provider Protocol

The **secret provider protocol** is defined by the `SecretsResolver` type alias:

```python
SecretsResolver = Callable[[str], str]
```

Any callable that accepts a string (the secret path) and returns a string (the resolved value) satisfies the protocol. This is deliberately minimal -- the framework does not impose a class hierarchy, abstract base class, or interface. A simple function works:

```python
def my_vault_resolver(path: str) -> str:
    """Resolve a secret from HashiCorp Vault."""
    client = hvac.Client(url="https://vault.example.com")
    secret = client.secrets.kv.v2.read_secret_version(path=path)
    return secret["data"]["data"]["value"]

register_secrets_resolver("vault", my_vault_resolver)
```

The protocol imposes one important contract: the resolver must be synchronous. The resolution pipeline runs during `MountainAshBaseSettings.__init__`, which is a synchronous constructor. Asynchronous resolvers must be wrapped with `asyncio.run()` or an equivalent blocking bridge.

Resolvers receive only the path portion of the reference (everything after the `secret:` prefix). The resolver is responsible for connecting to the appropriate backend, authenticating, retrieving the value, and returning it as a plain string. Error handling (network failures, missing paths, permission denials) is the resolver's responsibility -- unhandled exceptions propagate to the caller as construction failures.

## Secret Prefix Syntax

The **secret prefix syntax** is the string pattern that identifies a value as a reference to an external secret rather than a literal value. The default prefix is `secret:`, and any string value that starts with this prefix is treated as a reference.

```yaml
# In a YAML config file:
database:
  host: db.example.com          # literal value
  password: secret:db/prod/pw   # secret reference
  api_key: secret:api/prod/key  # secret reference
```

The prefix is configurable -- the `resolve_references_in_dict()` and `resolve_references_in_model_tree()` functions accept a `prefix` parameter that defaults to `"secret:"`. This allows applications to define custom reference patterns (for example, `vault:`, `ssm:`, or `keyvault:`) if needed.

The resolution logic is straightforward: for any string value, check if it starts with the prefix; if so, strip the prefix and pass the remainder to the resolver:

```python
if isinstance(value, str) and value.startswith(prefix):
    resolved[key] = resolver(value[len(prefix):])
```

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

A directed graph showing how a secret reference string flows through the resolution pipeline: the string "secret:db/prod/pw" enters, the prefix "secret:" is stripped, the path "db/prod/pw" is passed to the registered resolver, the resolver returns the plain-text secret, and the resolved value replaces the reference in the data structure. Clicking on the resolver node shows a dropdown to switch between Vault, SSM, and Key Vault providers, with each showing its specific lookup mechanics. Learning objective: Trace how a secret reference is resolved from prefix detection through provider lookup to value substitution (Bloom: Understand).
</details>

## Two Pass Resolution

The **two-pass resolution** pipeline is the core architectural pattern of the secrets subsystem. It runs in two distinct phases during `MountainAshBaseSettings.__init__`, each targeting a different data structure:

1. **Pass 1 (kwargs pass)** -- resolves references in the kwargs dictionary _before_ `BaseSettings.__init__` runs
2. **Pass 2 (model tree pass)** -- resolves references in the populated model tree _after_ `BaseSettings.__init__` completes

The two-pass design is necessary because configuration values arrive through different channels. Kwargs are available before construction as a plain dictionary, so they can be resolved early. But values loaded from config files and environment variables are not available until after `BaseSettings.__init__` populates the model fields -- so those must be resolved in a second pass over the live model tree.

```python
# Inside MountainAshBaseSettings.__init__:

# Pass 1: resolve secret references in kwargs
if local_settings_params.secrets_provider:
    _secrets_resolver = get_secrets_resolver(
        local_settings_params.secrets_provider
    )
    valid_attribute_kwargs = resolve_references_in_dict(
        valid_attribute_kwargs, _secrets_resolver
    )

# ... BaseSettings.__init__ runs here ...

# Pass 2: resolve secret references in model tree
if local_settings_params.secrets_provider:
    _secrets_resolver = _get_resolver(
        local_settings_params.secrets_provider
    )
    resolve_references_in_model_tree(self, _secrets_resolver)
```

This two-pass approach means that secret references work identically regardless of where they appear -- in kwargs, in YAML files, in environment variables, or in `.env` files. The caller does not need to know which pass will handle their reference.

## Kwargs Pass Resolution

The **kwargs pass** runs before Pydantic's `BaseSettings.__init__` and processes the `valid_attribute_kwargs` dictionary. At this point, the dictionary contains only the kwargs that have been validated as belonging to fields on the target settings class (the routing performed by `get_attribute_settings_kwargs()`).

The pass calls `resolve_references_in_dict()`, which recursively walks the dictionary and replaces any string value matching the secret prefix with its resolved value. Because this happens before Pydantic validation, the resolved values then flow through the normal validation pipeline -- `SecretStr` wrapping, type coercion, and field validators all apply to the resolved secret value.

This ordering is important. If a field is typed as `SecretStr` and the kwarg value is `"secret:db/prod/pw"`, the kwargs pass resolves it to the actual password string, and then Pydantic wraps that string in a `SecretStr` during validation. The end result is a properly wrapped secret that is protected from accidental exposure.

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

The `resolve_references_in_dict()` function is a pure, recursive dictionary transformer. It takes a dictionary, a resolver callable, and a prefix string, and returns a new dictionary with all matching references resolved:

```python
def resolve_references_in_dict(
    data: dict[str, Any],
    resolver: Callable[[str], str],
    prefix: str = "secret:",
) -> dict[str, Any]:
    resolved: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            resolved[key] = resolve_references_in_dict(
                value, resolver, prefix
            )
        elif isinstance(value, str) and value.startswith(prefix):
            resolved[key] = resolver(value[len(prefix):])
        else:
            resolved[key] = value
    return resolved
```

The function is domain-agnostic -- it does not import or reference the secrets module specifically. Its signature accepts any callable resolver and any prefix string, making it reusable for other reference patterns beyond secrets. The module docstring explicitly notes this design choice: "future reference patterns can reuse the same mechanism."

The function returns a new dictionary rather than modifying the input. This immutability is important because the input dictionary may be shared (for example, as a frozen dataclass field on `SettingsParameters`).

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

## Vault Provider

The **Vault provider** pattern implements a `SecretsResolver` that connects to HashiCorp Vault. While mountainash-settings does not ship a concrete Vault implementation (the resolver is application-supplied), the framework establishes the pattern for how Vault integration works:

```python
import hvac

def vault_resolver(path: str) -> str:
    client = hvac.Client(
        url="https://vault.example.com",
        token=os.environ["VAULT_TOKEN"]
    )
    response = client.secrets.kv.v2.read_secret_version(path=path)
    return response["data"]["data"]["value"]

register_secrets_resolver("vault", vault_resolver)
```

The Vault resolver typically reads its own connection parameters from environment variables (VAULT_ADDR, VAULT_TOKEN) since these cannot themselves be secret references (bootstrapping problem). The path format follows Vault's KV v2 convention: `engine/path/to/secret`.

## SSM Provider

The **SSM provider** pattern connects to AWS Systems Manager Parameter Store, which stores configuration data and secrets as named parameters in a hierarchical namespace:

```python
import boto3

def ssm_resolver(path: str) -> str:
    client = boto3.client("ssm")
    response = client.get_parameter(
        Name=path,
        WithDecryption=True
    )
    return response["Parameter"]["Value"]

register_secrets_resolver("ssm", ssm_resolver)
```

SSM paths use forward-slash hierarchy (e.g., `/production/database/password`). The `WithDecryption=True` parameter ensures that `SecureString` parameters are returned in plaintext rather than as encrypted blobs.

## Key Vault Provider

The **Key Vault provider** pattern connects to Azure Key Vault for secrets management in Azure environments:

```python
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

def keyvault_resolver(path: str) -> str:
    vault_url = os.environ["AZURE_KEYVAULT_URL"]
    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=vault_url, credential=credential)
    return client.get_secret(path).value

register_secrets_resolver("keyvault", keyvault_resolver)
```

All three provider patterns share the same architecture: they are plain functions that satisfy the `SecretsResolver` protocol (accept a path string, return a value string) and are registered under a name that configuration files reference via the `secrets_provider` parameter on `SettingsParameters`.

| Provider | Backend | Path Format | Authentication |
|----------|---------|-------------|----------------|
| Vault | HashiCorp Vault | `engine/path/secret` | Token, AppRole |
| SSM | AWS Parameter Store | `/hierarchy/path` | IAM role, credentials |
| Key Vault | Azure Key Vault | `secret-name` | DefaultAzureCredential |

<!-- concept:55 -->
## Frozen Model Rebuild On Resolve

When the model tree pass encounters a nested `BaseModel` field that contains secret references, it cannot simply modify the nested model in place -- Pydantic models may be frozen (immutable). Instead, the resolver extracts the model's fields as a raw dictionary, resolves any references in that dictionary, and rebuilds the nested model from scratch:

```python
if isinstance(value, BaseModel):
    raw_dict, has_refs = _extract_model_values(value, prefix)
    if has_refs:
        resolved_dict = resolve_references_in_dict(
            raw_dict, resolver, prefix
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

- **Secrets Registry** provides write-once registration with explicit replacement for safety, mapping provider names to resolver callables.
- **Secret Provider Protocol** is a minimal callable interface (`str -> str`) that any function or method can satisfy without inheriting from a base class.
- **Two Pass Resolution** handles secrets from all sources: Pass 1 resolves kwargs before Pydantic validation; Pass 2 resolves config-file and env-var values in the live model tree.
- **Kwargs Pass Resolution** runs before `BaseSettings.__init__`, allowing resolved values to flow through normal Pydantic validation and `SecretStr` wrapping.
- **Model Tree Pass Resolution** walks the live instance after construction, handling plain strings, `SecretStr` values, and nested `BaseModel` instances.
- **Secret Prefix Syntax** (`secret:path`) is configurable and domain-agnostic, enabling reuse of the resolution mechanism for non-secret reference patterns.
- **Vault, SSM, and Key Vault Providers** follow identical patterns: plain functions registered under a name, resolving paths to values from external backends.
- **Frozen Model Rebuild** extracts, resolves, and reconstructs nested models when they contain secret references, preserving immutability guarantees.
