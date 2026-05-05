# Secrets Resolution in SettingsParameters

**Date:** 2026-05-05
**Updated:** 2026-05-06 (post adversarial review)
**Requested by:** mountainash-wearables
**Branch:** feature/secrets-resolution

## Summary

Add secrets resolution support to SettingsParameters so that config files and kwargs containing `secret:` prefixed values are transparently resolved to plaintext at `get_settings()` time. This preserves the JIT settings resolution principle — SettingsParameters remains a secret-free transport handle, and secrets are only materialised at the point of use.

## Problem

Config files store sensitive values (passwords, tokens, client secrets) as plaintext. The existing backlog spec (`secrets-resolution-in-config.md`) proposed handling this at the consumer level via kwargs pre-processing. However, this approach prevents SettingsParameters from being passed as a transport mechanism for JIT resolution — consumers would need to pre-resolve secrets and embed plaintext into kwargs, defeating the security benefit of late resolution.

## Design Decisions

### secrets_provider as a structural parameter

`SettingsParameters` gains a new field: `secrets_provider: str | None = None`

- **Classification: structural.** Different providers (or no provider) produce different field values during construction, so it affects the cache key. Included in `__hash__` and `__eq__`.
- **Merge strategy: last-wins.** Same as `env_prefix` and `secrets_dir`. With `prioritise_base=True`, base wins.
- **Accepted by `create()` as a named parameter** (not via `**kwargs`).
- **Safe to log/serialize** — it's a string identifier, contains no secrets.

### Resolver protocol

The resolver is a simple callable: `(secret_path: str) -> str`. mountainash-settings does not know or care what backend it talks to. The resolver takes a path (the string after the `secret:` prefix) and returns the plaintext secret value.

### Registry

A module-level registry in `src/mountainash_settings/secrets/`. Consumers register resolvers at app startup:

```python
from mountainash_settings.secrets import register_secrets_resolver

register_secrets_resolver("local", my_handler.get_secret)
```

The registry is a plain dict with the following semantics:

- `get_secrets_resolver(provider)` raises `KeyError` if not registered.
- `register_secrets_resolver(provider, resolver)` raises `ValueError` if the provider is already registered. This prevents silent replacement that could cause cache/resolver inconsistency in long-lived processes.
- `replace_secrets_resolver(provider, resolver)` explicitly replaces an existing entry. Callers should be aware that previously cached settings instances retain values resolved by the old resolver — the settings cache is NOT invalidated on replacement.
- No default providers are shipped — the registry starts empty.

### Dict-walking logic

`resolve_secrets_in_dict(data, resolver, prefix="secret:")` lives in mountainash-settings. It:
- Walks dicts recursively
- For each string value starting with `prefix`, strips the prefix and calls `resolver(path)`
- Passes non-string values and non-prefixed strings through unchanged
- Returns a new dict (does not mutate input)

This centralises the `secret:` convention in mountainash-settings rather than each consumer reimplementing it.

A companion function `resolve_secrets_on_instance(instance, resolver, prefix="secret:")` walks a constructed settings instance's string fields and resolves any `secret:` prefixed values via `setattr`. This is used for post-construction resolution of config-file-sourced values.

## Integration into MountainAshBaseSettings

Three interception points cover all paths through which `secret:` prefixed values can enter:

### 1. kwargs resolution (construction path)

After `valid_attribute_kwargs` is extracted but before `super().__init__()`:

```python
if local_settings_params.secrets_provider:
    resolver = get_secrets_resolver(local_settings_params.secrets_provider)
    valid_attribute_kwargs = resolve_secrets_in_dict(valid_attribute_kwargs, resolver)
```

This resolves secrets in kwargs before pydantic validation, so SecretStr coercion and type validation work normally.

### 2. Config file resolution (post-construction)

After `super().__init__()` completes but before `post_init()`, walk the instance's fields and resolve any `secret:` prefixed string values:

```python
if local_settings_params.secrets_provider:
    resolver = get_secrets_resolver(local_settings_params.secrets_provider)
    resolve_secrets_on_instance(self, resolver)
```

This replaces the earlier `SecretsResolvingSource` wrapper design. The wrapper approach required threading the provider through `model_config`, which is a class-level mutable dict — concurrent or interleaved constructions of the same settings class with different providers would race and potentially resolve secrets with the wrong provider. Post-construction resolution avoids this entirely by operating on the instance, not the class.

The trade-off: pydantic validates config-file values with the literal `"secret:..."` string first, then the resolved value is assigned via `setattr` (which re-validates due to `validate_assignment=True`). This means:
- `str` fields: work — the literal string passes initial validation, resolved value passes re-validation.
- `SecretStr` fields: work — pydantic coerces strings to SecretStr on both passes.
- Non-string fields (e.g., `int`): would fail initial validation with the literal `"secret:..."` string. In practice, secrets are always strings (passwords, tokens, keys), so this constraint is acceptable.

### 3. Runtime override resolution (cache-hit path)

`SettingsParameters.apply_runtime_overrides()` resolves secrets in kwargs before applying them to the cached copy:

```python
def apply_runtime_overrides(self, cached_settings: BaseSettings) -> BaseSettings:
    if self.kwargs:
        settings_copy = cached_settings.model_copy()
        override_kwargs = self.get_attribute_settings_kwargs()
        if override_kwargs:
            if self.secrets_provider:
                resolver = get_secrets_resolver(self.secrets_provider)
                override_kwargs = resolve_secrets_in_dict(override_kwargs, resolver)
            settings_copy.update_settings_from_dict(settings_dict=override_kwargs)
        return settings_copy
    return cached_settings
```

This covers the case where a cached settings instance exists and a subsequent `get_settings()` call supplies new kwargs containing `secret:` references. Without this, the literal `"secret:..."` string would be written directly to the settings copy.

### Result

- Config files with `secret:garmin/nathaniel/password` values resolved transparently
- Kwargs with `secret:` prefixed values resolved transparently — both on initial construction and on cache-hit runtime overrides
- Fields receive real values — SecretStr coercion and all pydantic validation works normally
- No consumer-side dict walking needed
- No class-level state mutation — no cross-request bleed risk

## New Module: `src/mountainash_settings/secrets/`

```
src/mountainash_settings/secrets/
├── __init__.py          # Exports: register_secrets_resolver, get_secrets_resolver,
│                        #          replace_secrets_resolver, clear_secrets_registry, SecretsResolver
├── registry.py          # Registry dict, register/get/replace functions, SecretsResolver type alias
└── resolve.py           # resolve_secrets_in_dict, resolve_secrets_on_instance
```

### Public API

Exported from top-level `mountainash_settings`:
- `register_secrets_resolver(provider: str, resolver: SecretsResolver) -> None` — raises ValueError if already registered
- `get_secrets_resolver(provider: str) -> SecretsResolver` — raises KeyError if not registered
- `replace_secrets_resolver(provider: str, resolver: SecretsResolver) -> None` — explicit replacement (does not invalidate cached settings)
- `clear_secrets_registry() -> None` — removes all registered resolvers. **Test use only.** Intended for fixtures that need a clean registry per test. Does not invalidate cached settings — pair with `_get_settings.cache_clear()` or the `isolated_settings_manager` fixture if test isolation requires both.
- `SecretsResolver` — type alias: `Callable[[str], str]`

`resolve_secrets_in_dict` and `resolve_secrets_on_instance` are internal — consumers don't need to call them directly.

### Registry integrity guarantees

The registry is designed to be **write-once per provider** in production:

| Operation | Behaviour | Use case |
|-----------|-----------|----------|
| `register_secrets_resolver("local", fn)` | Succeeds | App startup |
| `register_secrets_resolver("local", fn2)` | Raises `ValueError` | Catches accidental double-registration |
| `replace_secrets_resolver("local", fn2)` | Succeeds, overwrites | Controlled rotation, explicit intent |
| `clear_secrets_registry()` | Removes all entries | Test fixtures only |

**Cache interaction:** The settings cache keys on the provider *string*, not the resolver *function*. If a resolver is replaced under the same name, previously cached settings retain values from the old resolver. New constructions use the new resolver. This is by design — silent replacement would create split behaviour in long-lived processes. The explicit `replace` + manual cache invalidation pattern makes the consequences visible.

## Changes to Existing Files

### SettingsParameters (`settings_parameters.py`)

- New field: `secrets_provider: str | None = None`
- `__hash__`: include `self.secrets_provider`
- `__eq__`: include `self.secrets_provider` comparison
- `create()`: accept `secrets_provider` parameter
- `merge()`: last-wins for `secrets_provider` (same as scalars)
- `to_dict()`: include `secrets_provider`
- `extract_settings_parameters()`: round-trip `secrets_provider`
- `apply_runtime_overrides()`: resolve secrets in kwargs before applying to cached copy

### MountainAshBaseSettings (`base_settings.py`)

- `__init__`: resolve kwargs before `super().__init__()` when `secrets_provider` is set
- `__init__`: resolve instance fields after `super().__init__()` but before `post_init()` when `secrets_provider` is set
- No changes to `settings_customise_sources` — config-file resolution is handled post-construction
- New bookkeeping field: `SETTINGS_SOURCE_SECRETS_PROVIDER` (set via `object.__setattr__`, same pattern as other SETTINGS_SOURCE fields)

### Top-level `__init__.py`

- Export `register_secrets_resolver`, `get_secrets_resolver`, `replace_secrets_resolver`, `clear_secrets_registry`, `SecretsResolver`

## Testing Strategy

### Unit tests: `tests/unit/secrets/`

**`test_registry.py`:**
- Register a resolver, retrieve it by name
- Retrieve unregistered provider raises KeyError
- Duplicate registration raises ValueError (not silent overwrite)
- `replace_secrets_resolver` overwrites existing entry
- `replace_secrets_resolver` on unregistered provider registers it (no error)
- `clear_secrets_registry` removes all entries
- After `clear_secrets_registry`, previously registered providers raise KeyError

**`test_resolve.py`:**
- Flat dict with `secret:` prefixed value resolved
- Nested dict resolved recursively
- Non-string values passed through unchanged
- Strings without prefix passed through unchanged
- Empty dict returns empty dict
- Custom prefix works
- `resolve_secrets_on_instance` resolves string fields on a settings instance
- `resolve_secrets_on_instance` skips non-string fields

### Integration tests

**`test_base_settings.py`:**
- MountainAshBaseSettings subclass with SecretStr field, constructed via `SettingsParameters.create(secrets_provider="test")` with config YAML containing `secret:test/my_password`. Verify field contains resolved value, not the literal string.
- Same test via kwargs (not config file) — verify kwargs resolution path.
- Cache-hit test: construct settings, then call `get_settings()` again with same structural params but new kwargs containing a `secret:` reference. Verify the runtime override is resolved.

**`test_settings_parameters.py`:**
- `secrets_provider` included in hash/eq (structural)
- `secrets_provider` participates in merge (last-wins)
- `secrets_provider=None` by default
- `create()` accepts `secrets_provider`

All tests use a trivial lambda resolver: `lambda path: f"resolved_{path}"`. No actual secrets backend tested here.

**Test isolation pattern:** A pytest fixture calls `clear_secrets_registry()` in teardown to prevent cross-test contamination. For tests that also exercise the settings cache, pair with `_get_settings.cache_clear()` or the `isolated_settings_manager` fixture.

## Backwards Compatibility

- `secrets_provider` defaults to `None` — all existing code unchanged
- Config file parsing unchanged when no provider active
- Caching strategy unchanged — `secrets_provider` participates in cache key (same pattern as `secrets_dir`)
- No changes to auth specs, profiles, or any other module
- No changes to `settings_customise_sources`

## Out of Scope

- Actual secrets provider implementations (mountainash-utils-secrets concern)
- Migration of existing plaintext config values
- `secret:` prefix in non-dict contexts (e.g., list values within config — only string values in dicts are walked)
- Secret references in non-string fields (e.g., `int` fields) — secrets are always strings in practice

## Future Considerations

- **Secret caching/TTL.** Currently the resolver is called every time a settings instance is constructed or runtime overrides are applied. If resolver calls are expensive (e.g., network round-trips to a vault), caching at the resolver level or within mountainash-settings may become necessary. This is deferred — the resolver callable contract allows backends to implement their own caching internally, and the settings-level cache means construction (and therefore resolution) only happens once per unique structural parameter set.
- **Cache invalidation on resolver replacement.** When `replace_secrets_resolver()` is called, previously cached settings instances retain values resolved by the old resolver. If hot-swapping resolvers in production becomes a requirement, a cache invalidation mechanism may be needed. Currently deferred — the primary use case is single-resolver-per-process.
