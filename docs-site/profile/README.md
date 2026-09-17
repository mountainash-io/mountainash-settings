# mountainash-settings

**Typed, testable configuration for data applications -- one base class that loads any format, resolves secrets, and auto-derives connection parameters.**

## Vision

Configuration in data applications should be as trustworthy as the data pipelines it powers. mountainash-settings brings all configuration into typed settings classes built on Pydantic -- any format, any source, with secrets resolution, field templating, and auto-derived connection parameters. Every settings class is testable, documentable, and consistent from laptop to production.

YAML, TOML, JSON, .env files, and environment variables all flow into the same typed settings class. Pydantic validates everything -- type coercion, required fields, constrained values. IDE autocomplete works. Tests work. The config file format is a deployment choice, not an application concern. Template syntax lets fields reference other fields, connection strings build from host, port, and database fields, and paths compose from base directories and environment-specific suffixes. The derivation is declarative and transparent.

Secrets resolution is built into the construction pipeline. Write `secret:path/to/value` in a config file or environment variable. Register a secrets provider -- AWS SSM, HashiCorp Vault, Azure Key Vault, or your own. The secret resolves before Pydantic validation, so the settings class sees the real value and validates it normally. No special handling in application code. Every registered profile gets free pytest invariant coverage, and the caching layer ensures fast, predictable access throughout your application.

## Installation

```bash
pip install mountainash-settings
```

## Use Cases

### Configuration Governance at Scale

A platform team standardises configuration across fifteen services. One settings base class, typed connection profiles for every database, secrets resolved from Vault. Configuration becomes testable, version-controlled, and consistent. Every registered profile gets free pytest invariant coverage via `descriptor_invariants_for()`.

### The Data Pipeline That Configures Itself

A pipeline settings class loads from a YAML file in the repo, overrides from environment variables in CI, resolves secrets from SSM in production, and templates output paths from the run date and environment name. The same class, the same code, every deployment target. Runtime overrides for batch IDs or run-specific parameters get their own instance without polluting the cache.

### Multi-Database Connection Management

A data engineer defines profiles for PostgreSQL, Snowflake, and DuckDB. Each profile knows its auth requirements, its connection string format, and its driver kwargs. Switching databases means switching profiles -- the settings framework derives everything else. The connection profile is the documentation of how to connect.

## Key Capabilities

### Defining Settings Classes

Subclass `MountainAshBaseSettings` to declare your application's configuration as typed Python fields. Pydantic validation ensures every value meets your constraints as soon as the settings object is created. Use `post_init()` to compute any fields that depend on other values. Pass one or more file paths to `config_files` and the framework loads YAML, TOML, JSON, or .env files automatically based on extension. For advanced scenarios, `SettingsParameters.create()` lets you compose file lists, environment overrides, and kwargs into a single merged configuration with clear priority rules.

### Template-Driven Derived Fields

Use `{FIELD_NAME}` syntax in default values to build fields that derive their value from other settings. Combined with the UPath operator, this makes cross-platform path construction straightforward and declarative. Connection strings build themselves from host, port, and database fields. Log file paths compose from application name and run date. The derivation is always visible in the class definition.

### Cached Settings Instances

`get_settings()` retrieves settings using structural cache identity. MAS-SEC-001 privately owns supported source-form reconstruction recipes. It does not yet prevent cold runtime-input contamination or nested mutable-state sharing through shallow overlays; those remain MAS-SEC-002 work. `SettingsParameters.create()` and `merge()` normalize and combine source selectors and runtime inputs.

### Secrets Resolution

Register a secrets provider (Vault, SSM, KeyVault, or your own) and reference secrets in config files or kwargs with the `secret:path/to/value` prefix. The framework captures accepted kwargs privately in source form before resolving a working validation copy, then resolves loaded config fields after construction. Your application code works with plain typed values while credentials stay masked in logs and repr output via SecretStr; source-form extraction is a separate trusted reconstruction capability.

### Connection Profiles

Declare a `ProfileDescriptor` listing the parameters your connection needs, then subclass `DescriptorProfile` to get a fully-typed settings class with those fields wired in automatically. Each `ParameterSpec` defines a name, Python type, tier, default value, driver_key mapping, and optional secret, transform, validator, and template behaviour. Register profiles in a `Registry` so downstream code can look them up by name. The framework installs Pydantic fields, auth options, and template wiring automatically at class creation time.

### Authentication Modes

Choose from built-in auth modes including password, token, OAuth2, IAM, service account, Azure AD, Kerberos, and more. Each mode is an `AuthSpec` subclass selected via a `kind` literal field, so your configuration is explicit about which credentials are expected and how they are supplied. The discriminated union validates that the auth mode matches what the backend expects. Create custom auth modes by subclassing `AuthSpec` with a unique kind literal.

## Architecture

The current cache has an `_get_settings()` LRU and a `SettingsManager` dictionary keyed by structural parameters. Cold construction retains runtime inputs, no-input retrieval returns the cached object, and later overlays use shallow copies. The private reconstruction lifecycle protects provenance, not all live state. MAS-SEC-002 owns the single-owner cache cutover and full invocation validation.

Connection profiles use dynamic Pydantic field installation at class creation time. `__pydantic_init_subclass__` fires and installs fields from the profile descriptor into `model_fields` and `__annotations__`, followed by a `model_rebuild(force=True)` to finalise the updated schema. The auth discriminated union is assembled dynamically from the descriptor's auth_modes list. Config files are dispatched by extension into categorised groups, and the appropriate source priority tuple layers values predictably.

## Extending

Build domain-specific connection profiles for databases, storage backends, and APIs on top of the profiles framework. Define a `ProfileDescriptor` with typed parameters via `ParameterSpec` entries, register it via a `Registry`, and get a fully validated settings class with authentication, secret handling, and template derivation built in. You can extend the auth system with custom authentication modes by subclassing `AuthSpec` with a unique kind literal. Call `descriptor_invariants_for()` to get automatic test coverage of descriptor conventions. Profiles can be published as standalone packages that downstream teams install and use with their own config files.

## Contributing

Contributions welcome. The project uses hatch for environment management with preconfigured environments for testing, linting, and type checking.

## Maintaining

The two-level caching architecture requires care around concurrency. `model_config` mutation before `super().__init__()` operates at the class level, so concurrent first-construction of different file sets on the same class should be serialised. The `SettingsManager` dictionary is similarly designed for single-threaded first-creation.

Dynamic field installation via `model_rebuild()` should be verified after Pydantic version upgrades, as it depends on internal Pydantic class-creation machinery. The `validate_assignment=True` invariant means all attribute assignment triggers full validation; internal metadata fields use `object.__setattr__` to bypass revalidation and avoid polluting `model_fields_set`.

Secrets resolution runs in two passes during `__init__`: first, accepted kwargs are captured privately in source form and a working copy is resolved via `resolve_references_in_dict` before `super().__init__`; then loaded config fields are resolved via `resolve_references_in_model_tree` after construction. Nested BaseModel fields are rebuilt as fresh instances to respect the `frozen=True` constraint. When debugging secrets issues, trace through both passes without treating ordinary dumps or private reconstruction state as a generic redaction boundary.
