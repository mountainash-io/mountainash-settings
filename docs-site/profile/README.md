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

### Cached Settings Retrieval

`get_settings()` identifies a private source context from the five structural
selectors and materializes a fresh, independently owned result for every
caller. Selected source inputs and their prevalidation-resolved baseline
references are pinned per context; runtime fields and explicit runtime secret
references are invocation-local. Defaults and default factories remain
Pydantic behavior evaluated per materialization. This does not claim the
later Profile origin/template integration (MAS-SEC-005), direct-constructor
source isolation (MAS-SEC-004), common errors (MAS-SEC-006), or lifecycle
refresh work.

### Secrets Resolution

Register a secrets provider (Vault, SSM, KeyVault, or your own) and reference secrets in config files or kwargs with the `secret:path/to/value` prefix. The framework captures accepted kwargs privately in source form before resolving a working validation copy, then resolves loaded config fields after construction. Your application code works with plain typed values while credentials stay masked in logs and repr output via SecretStr; source-form extraction is a separate trusted reconstruction capability.

### Connection Profiles

Declare a `ProfileDescriptor` listing the parameters your connection needs, then subclass `DescriptorProfile` to get a fully-typed settings class with those fields wired in automatically. Each `ParameterSpec` defines a name, Python type, tier, default value, driver_key mapping, and optional secret, transform, validator, and template behaviour. Register profiles in a `Registry` so downstream code can look them up by name. The framework installs Pydantic fields, auth options, and template wiring automatically at class creation time.

### Authentication Modes

Choose from built-in auth modes including password, token, OAuth2, IAM, service account, Azure AD, Kerberos, and more. Each mode is an `AuthSpec` subclass selected via a `kind` literal field, so your configuration is explicit about which credentials are expected and how they are supplied. The discriminated union validates that the auth mode matches what the backend expects. Create custom auth modes by subclassing `AuthSpec` with a unique kind literal.

## Architecture

Cached retrieval uses one private structural-context owner, not `_get_settings`
or a public result dictionary. It captures source state once and validates each
complete invocation before returning an owned object graph. Cacheable custom
sources must opt into capture/project; legacy source hooks must explicitly
adapt through `settings_capture_sources`, while unsupported cached hooks and
plain `BaseSettings` custom constructors fail before reads. Ordinary direct
construction remains unchanged. `reinitialise` is cached-retrieval operation
control, not source reload or refresh.

Connection profiles use dynamic Pydantic field installation at class creation time. `__pydantic_init_subclass__` fires and installs fields from the profile descriptor into `model_fields` and `__annotations__`, followed by a `model_rebuild(force=True)` to finalise the updated schema. The auth discriminated union is assembled dynamically from the descriptor's auth_modes list. Config files are dispatched by extension into categorised groups, and the appropriate source priority tuple layers values predictably.

## Extending

Build domain-specific connection profiles for databases, storage backends, and APIs on top of the profiles framework. Define a `ProfileDescriptor` with typed parameters via `ParameterSpec` entries, register it via a `Registry`, and get a fully validated settings class with authentication, secret handling, and template derivation built in. You can extend the auth system with custom authentication modes by subclassing `AuthSpec` with a unique kind literal. Call `descriptor_invariants_for()` to get automatic test coverage of descriptor conventions. Profiles can be published as standalone packages that downstream teams install and use with their own config files.

## Contributing

Contributions welcome. The project uses hatch for environment management with preconfigured environments for testing, linting, and type checking.

## Maintaining

Cached contexts coordinate first source capture without retaining first-call
runtime values or returned settings instances. A later same-context request
uses the captured source baseline even if the external file is gone; a fresh
result still validates defaults, runtime fields, and post-init state for that
request. `CacheableSettingsSource.capture()` may perform the one external
capture; `project(snapshot, current_state, sources_data)` must be pure and
return terminal values. Do not treat its results as new source references.

The profile-specific template/origin lifecycle, direct source framing,
common error API, and refresh/rotation behavior remain the separately ordered
MAS-SEC-005, MAS-SEC-004, MAS-SEC-006, and lifecycle work.
