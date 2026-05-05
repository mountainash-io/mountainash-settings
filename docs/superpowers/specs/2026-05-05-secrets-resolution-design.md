# Secrets Resolution in SettingsParameters

**Date:** 2026-05-05
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

The registry is a plain dict. `get_secrets_resolver(provider)` raises `KeyError` if not registered. No default providers are shipped — the registry starts empty.

### Dict-walking logic

`resolve_secrets_in_dict(data, resolver, prefix="secret:")` lives in mountainash-settings. It:
- Walks dicts recursively
- For each string value starting with `prefix`, strips the prefix and calls `resolver(path)`
- Passes non-string values and non-prefixed strings through unchanged
- Returns a new dict (does not mutate input)

This centralises the `secret:` convention in mountainash-settings rather than each consumer reimplementing it.

## Integration into MountainAshBaseSettings

Two interception points in `__init__`:

### 1. kwargs resolution

After `valid_attribute_kwargs` is extracted but before `super().__init__()`:

```python
if local_settings_params.secrets_provider:
    resolver = get_secrets_resolver(local_settings_params.secrets_provider)
    valid_attribute_kwargs = resolve_secrets_in_dict(valid_attribute_kwargs, resolver)
```

### 2. Config file resolution

A `SecretsResolvingSource` wrapper decorates pydantic-settings sources in `settings_customise_sources()`. It intercepts the dict returned by the wrapped source and runs `resolve_secrets_in_dict` on it before pydantic sees the values.

The provider string is threaded via `model_config` (same pattern as `yaml_file`, `toml_file`, `json_file`):

```python
self.model_config["secrets_provider"] = local_settings_params.secrets_provider
```

`settings_customise_sources` reads it from `settings_cls.model_config` and wraps sources only when a provider is set.

### Result

- Config files with `secret:garmin/nathaniel/password` values resolved transparently
- Kwargs with `secret:` prefixed values resolved transparently
- Fields receive real values — SecretStr coercion and all pydantic validation works normally
- No consumer-side dict walking needed

## New Module: `src/mountainash_settings/secrets/`

```
src/mountainash_settings/secrets/
├── __init__.py          # Exports: register_secrets_resolver, get_secrets_resolver, SecretsResolver
├── registry.py          # Registry dict, register/get functions, SecretsResolver type alias
└── resolve.py           # resolve_secrets_in_dict, SecretsResolvingSource wrapper
```

### Public API

Exported from top-level `mountainash_settings`:
- `register_secrets_resolver(provider: str, resolver: SecretsResolver) -> None`
- `get_secrets_resolver(provider: str) -> SecretsResolver`
- `SecretsResolver` — type alias: `Callable[[str], str]`

`resolve_secrets_in_dict` is internal — consumers don't need to call it directly.

## Changes to Existing Files

### SettingsParameters (`settings_parameters.py`)

- New field: `secrets_provider: str | None = None`
- `__hash__`: include `self.secrets_provider`
- `__eq__`: include `self.secrets_provider` comparison
- `create()`: accept `secrets_provider` parameter
- `merge()`: last-wins for `secrets_provider` (same as scalars)
- `to_dict()`: include `secrets_provider`
- `extract_settings_parameters()`: round-trip `secrets_provider`

### MountainAshBaseSettings (`base_settings.py`)

- `__init__`: resolve kwargs via registry when `secrets_provider` is set
- `__init__`: set `model_config["secrets_provider"]` for source wrapping
- `settings_customise_sources`: wrap sources with `SecretsResolvingSource` when provider is set

### Top-level `__init__.py`

- Export `register_secrets_resolver`, `get_secrets_resolver`, `SecretsResolver`

## Testing Strategy

### Unit tests: `tests/unit/secrets/`

**`test_registry.py`:**
- Register a resolver, retrieve it by name
- Retrieve unregistered provider raises KeyError
- Register overwrites existing entry

**`test_resolve.py`:**
- Flat dict with `secret:` prefixed value resolved
- Nested dict resolved recursively
- Non-string values passed through unchanged
- Strings without prefix passed through unchanged
- Empty dict returns empty dict
- Custom prefix works

### Integration tests

**`test_base_settings.py`:**
- MountainAshBaseSettings subclass with SecretStr field, constructed via `SettingsParameters.create(secrets_provider="test")` with config YAML containing `secret:test/my_password`. Verify field contains resolved value.

**`test_settings_parameters.py`:**
- `secrets_provider` included in hash/eq (structural)
- `secrets_provider` participates in merge (last-wins)
- `secrets_provider=None` by default
- `create()` accepts `secrets_provider`

All tests use a trivial lambda resolver: `lambda path: f"resolved_{path}"`. No actual secrets backend tested here.

## Backwards Compatibility

- `secrets_provider` defaults to `None` — all existing code unchanged
- Config file parsing unchanged when no provider active
- Caching strategy unchanged — `secrets_provider` participates in cache key (same pattern as `secrets_dir`)
- No changes to auth specs, profiles, or any other module

## Out of Scope

- Actual secrets provider implementations (mountainash-utils-secrets concern)
- Migration of existing plaintext config values
- `secret:` prefix in non-dict contexts (e.g., list values within config — only string values in dicts are walked)

## Future Considerations

- **Secret caching/TTL.** Currently the resolver is called every time a settings instance is constructed. If resolver calls are expensive (e.g., network round-trips to a vault), caching at the resolver level or within mountainash-settings may become necessary. This is deferred — the resolver callable contract allows backends to implement their own caching internally, and the settings-level cache means construction (and therefore resolution) only happens once per unique structural parameter set.
