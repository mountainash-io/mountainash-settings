# Nested Model Secrets Resolution — Design Spec

> **Status:** APPROVED
> **Date:** 2026-05-06
> **Triggered by:** Downstream consumer (mountainash-wearables) reporting unresolved `secret:` references in nested `AuthSpec` fields loaded from YAML config files.

## Problem

The secrets resolution system (PR #40) has three interception points, but none of them handle secret references inside nested pydantic model fields loaded from config files.

**What happens today:**

1. Consumer calls `get_settings(settings_parameters=params)`.
2. `MountainAshBaseSettings.__init__` runs.
3. **Point 1** fires: `resolve_secrets_in_dict` runs on direct kwargs — but config file values aren't in kwargs yet.
4. `super().__init__()` calls pydantic's `BaseSettings.__init__`. Pydantic's settings source machinery reads the YAML file, gets a raw dict like `{"auth": {"kind": "oauth2_authcode", "client_secret": "secret:strava/..."}}`, and validates it into models. The nested auth dict becomes a constructed `OAuth2AuthCodeAuth` instance. The literal string `"secret:strava/..."` is baked into a `SecretStr` field on that model.
5. **Point 2** fires: `resolve_secrets_on_instance` walks `self.model_fields`. It finds `self.auth`, but it's an `OAuth2AuthCodeAuth` object, not a string — so the string-prefix check doesn't match. It does not recurse into nested model instances.

**The gap:** There is no interception point between "config source returns raw dict" and "pydantic validates that dict into models." The raw dict passes through pydantic's internal machinery where mountainash-settings cannot touch it. `resolve_secrets_in_dict` can handle nested dicts (it recurses), but it never sees the config file data.

**Example config file that triggers the bug:**

```yaml
# ~/.config/mountainash/wearables/strava-nathaniel.yaml
host: "api.strava.com"
auth:
  kind: oauth2_authcode
  client_id: "12345"
  client_secret: "secret:strava/nathaniel/client_secret"
  access_token: "secret:strava/nathaniel/access_token"
  refresh_token: "secret:strava/nathaniel/refresh_token"
```

After construction, `settings.auth.client_secret.get_secret_value()` returns the literal `"secret:strava/nathaniel/client_secret"` instead of the resolved plaintext value.

## Design Decisions

### Decision 1: Recursive model tree walking (Approach A)

**Chosen:** Extend the existing Point 2 function to recurse into any field whose value is a `BaseModel` instance.

**Rejected alternatives:**

- **Custom settings sources (Approach B):** Subclassing `YamlConfigSettingsSource` et al. to intercept raw dicts before pydantic validation. Requires subclassing three source classes, threading resolver context through `model_config`, and coupling to pydantic-settings internals.
- **Model validator interception (Approach C):** Adding `model_validator(mode='before')` to intercept raw dicts. Requires class-level state for resolver context, risking cross-request bleed — exactly the problem already fixed in the original secrets design.

**Rationale:** Approach A is the smallest change, stays within the existing pattern, doesn't require subclassing pydantic-settings internals, and handles arbitrary nesting depth. The only assumption is that pydantic's validators accept the literal `"secret:..."` string — which they do for `str` and `SecretStr` fields.

### Decision 2: Separate mechanism from domain

The current `secrets/` module conflates two things: the secrets provider registry (domain-specific) and the reference resolution functions (general mechanism). The resolution functions are a general "walk a data structure, find strings matching a prefix, pass them through a resolver" capability. The secrets provider is just one consumer of that capability.

**New structure:**

```
src/mountainash_settings/
├── resolve.py              # General reference resolution mechanism
│   ├── resolve_references_in_dict()
│   └── resolve_references_in_model_tree()
├── secrets/
│   ├── __init__.py         # Exports registry functions only
│   └── registry.py         # SecretsResolver type, register/get/replace/clear
```

**`resolve.py`** — General-purpose, no dependency on `secrets/`. Takes a plain `Callable[[str], str]` resolver and a prefix string. Reusable for any future prefixed-reference pattern.

**`secrets/`** — Domain-specific provider registry. Owns the `SecretsResolver` type alias and the write-once registry. No resolution logic.

**`secrets/resolve.py`** — Deleted. Functions move to top-level `resolve.py` with renamed signatures.

### Decision 3: Function naming

Old names reflected the secrets domain. New names reflect the general mechanism:

| Old | New | Location |
|-----|-----|----------|
| `resolve_secrets_in_dict` | `resolve_references_in_dict` | `resolve.py` |
| `resolve_secrets_on_instance` | `resolve_references_in_model_tree` | `resolve.py` |

The `_in_dict` / `_in_model_tree` suffix describes the data structure being walked. Both take the same `(data/instance, resolver, prefix)` signature.

### Decision 4: Rebuild frozen nested models instead of mutating in place

**Problem identified by adversarial review:** `AuthSpec` (and all auth subclasses) use `ConfigDict(frozen=True)`. The original design proposed recursing into nested `BaseModel` instances and calling `setattr` on their fields — this raises `ValidationError` on frozen models.

**Fix:** When `resolve_references_in_model_tree` encounters a nested `BaseModel` field, it does NOT recurse into the model and mutate fields. Instead it:

1. Extracts the nested model's current values as a dict (handling `SecretStr` unwrapping).
2. Runs `resolve_references_in_dict` on that dict — which already handles nested dicts and the `secret:` prefix.
3. Constructs a **new instance** of the same type with the resolved values.
4. Assigns the new instance to the **parent's** field via `setattr`.

This works because:
- The parent (`MountainAshBaseSettings` / `DescriptorProfile`) is NOT frozen — it has `validate_assignment=True` and allows field assignment.
- `resolve_references_in_dict` already exists and handles arbitrary dict nesting.
- The new instance is constructed through pydantic's normal validation, so all field types (`SecretStr`, discriminators, etc.) are handled correctly.
- One code path works for both frozen and non-frozen nested models.

## Recursive Resolution Specification

### `resolve_references_in_model_tree(instance, resolver, prefix)`

Walks `instance.model_fields`. For each field:

1. **`str`** starting with `prefix` → resolve via `resolver`, `setattr` the result.
2. **`SecretStr`** whose `get_secret_value()` starts with `prefix` → resolve via `resolver`, `setattr` the result. Pydantic re-wraps as `SecretStr` via `validate_assignment=True`.
3. **`BaseModel` instance** → extract values as dict, run `resolve_references_in_dict` on the dict, construct a new instance of the same type with resolved values, `setattr` the new instance on the parent. This handles frozen models (like `AuthSpec`) without mutation, and supports arbitrary nesting depth because `resolve_references_in_dict` recurses into nested dicts.
4. **Everything else** → skip.

The `SETTINGS_SOURCE_*` / `SETTINGS_CLASS*` skip logic applies when checking field names. Only `MountainAshBaseSettings` subclasses declare these fields — nested models like `AuthSpec` subclasses do not have them, so the check is a no-op at nested levels.

### Extracting nested model values for reconstruction

To build the dict for reconstruction, the function iterates the nested model's `model_fields` and calls `getattr` for each field. `SecretStr` values are unwrapped via `get_secret_value()` so the resolver can match the `secret:` prefix. The resolved dict is passed to `type(nested_model)(**resolved_dict)` which re-validates and re-wraps `SecretStr` fields.

### Mutation safety

The root instance is mutated in place via `setattr`. This is safe because:
- Point 2 runs on the freshly constructed instance before `post_init()`.
- Point 3 runs on a `model_copy()` produced by `apply_runtime_overrides()`.

Nested models are never mutated — they are replaced with new instances.

### `resolve_references_in_dict(data, resolver, prefix)`

No behavioral change from the existing `resolve_secrets_in_dict` — just renamed and relocated. Already handles nested dicts recursively.

## Call Site Changes

### `base_settings.py`

Import paths change from:
```python
from mountainash_settings.secrets.resolve import resolve_secrets_in_dict
from mountainash_settings.secrets.resolve import resolve_secrets_on_instance
```
To:
```python
from mountainash_settings.resolve import resolve_references_in_dict
from mountainash_settings.resolve import resolve_references_in_model_tree
```

No behavioral change at call sites — same three interception points, same arguments.

### `settings_parameters.py`

`apply_runtime_overrides()` import path changes similarly.

### `__init__.py`

Top-level exports: no change to the public API. The `secrets/` package still exports `SecretsResolver`, `register_secrets_resolver`, `get_secrets_resolver`, `replace_secrets_resolver`, `clear_secrets_registry`. The resolution functions are internal — not part of the public API.

## Testing

### New tests

- Nested `BaseModel` field with `secret:` prefixed `str` field — resolved after construction.
- Nested `BaseModel` field with `secret:` prefixed `SecretStr` field — resolved after construction.
- Nested **frozen** `BaseModel` field (like `AuthSpec`) with `secret:` prefixed `SecretStr` field — resolved via rebuild, no `ValidationError`.
- Two levels of nesting (model → model → secret field) — resolved recursively.
- Nested model in kwargs (dict form) — resolved at Point 1 via `resolve_references_in_dict` (already works).
- Integration test: `DescriptorProfile` subclass with `auth: OAuth2AuthCodeAuth` loaded from YAML, `client_secret: "secret:..."` — resolved after construction. This is the exact scenario that triggered this spec.
- Cache-hit runtime override containing a nested dict with `secret:` prefixed value — resolved at Point 3.

### Existing tests

All existing secrets tests continue to pass — the behavioral change is additive (recursion into nested models). Existing tests cover flat fields only and are unaffected by the rename (import paths are internal).

## Principles Update

Update the mountainash-settings principles in mountainash-central to reflect:

1. **`a.architecture/secrets-resolution.md`** — rename to reflect the mechanism/domain separation. Document the general reference resolution mechanism and the secrets provider as a consumer of it. Update technical references to new file paths and function names.
2. **README.md** — update summary line if the document is renamed.

## Backwards Compatibility

The resolution functions are internal (not in `__all__`, not documented as public API). The rename is safe. The `secrets/` public API (`SecretsResolver`, registry functions) is unchanged.

No consumer-facing API changes. The fix is transparent — nested model fields that previously retained literal `"secret:..."` strings will now be resolved.
