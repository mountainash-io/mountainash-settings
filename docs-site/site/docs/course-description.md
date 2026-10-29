---
title: 'Package overview'
description: 'Package overview of mountainash-settings: what it is, what it covers and where it fits in the mountainash ecosystem'
---

[← Back to Home](index.md)

# Package overview

mountainash-settings is a typed configuration framework for Python applications built on Pydantic v2. It loads configuration from several file formats and environment variables, resolves secrets, derives field values with templates, and provides profiles for reusable connection configuration. `get_settings()` caches the inputs it reads and returns a freshly validated instance on every call. Authentication is not part of the package: it lives in `mountainash-auth-client` (see [Chapter 8](chapters/08-authentication-system/index.md)).

## Audience

Python developers and platform engineers responsible for how applications are configured across environments: data engineers who need consistent pipeline settings across dev, staging and production, backend developers managing typed connection parameters for databases and services, and platform engineers standardising configuration and secret references across a fleet of services. The package picks up where Pydantic `BaseSettings` leaves off: secrets, connection profiles and multi-file merging.

You should be comfortable with Python type annotations and decorators, Pydantic v2 (`BaseModel`, `BaseSettings`, validators), at least one of YAML, TOML, JSON or `.env`, and the general role of a secrets manager. [Chapter 1](chapters/01-pydantic-and-configuration-foundations/index.md) summarises the Pydantic and file-loading concepts the other chapters rely on.

## Key capabilities

- Any config source, one base class. YAML, TOML, JSON, `.env` files and environment variables all feed the same typed settings class, and Pydantic validates the result. Within one format, later files override earlier ones; across formats a fixed priority applies (`.env`, then YAML, TOML, JSON).
- Templated fields. A `post_init()` override can build a field from others with `init_setting_from_template("logs/{APP_NAME}/{RUNDATE}.log", ...)`, and a `Profile` field declares `template=` to have it derived automatically.
- Secret references. Write `secret:db.prod.password` in a config file or environment variable and bind a `secret_store` to the settings. The reference is replaced with the real value when the settings are constructed. Settings ships local stores (filesystem, memory, namespaced), and external managers such as Vault, AWS SSM or Azure Key Vault plug in by implementing the store protocols.
- Connection profiles. Declare a profile with `ProfileSpec` or with `ProfileField` declarations on a class, then call `emit(target, base=)` to get the keyword arguments a specific driver or SDK expects.
- Cached retrieval. `get_settings()` reuses what it has already read and still validates a new instance for each call. Runtime overrides apply only to the call that supplies them.

## Chapters

The [Chapters](chapters/index.md) page has the full list.

| # | Chapter | Covers |
|---|---------|--------|
| 1 | Pydantic and configuration foundations | Pydantic and file or environment loading concepts the package builds on |
| 2 | MountainAsh base settings | Defining a settings class with `MountainAshBaseSettings` |
| 3 | Settings parameters and merge strategies | Choosing files and kwargs, and how values merge |
| 4 | File handling, kwargs, and field templating | Multi-format loading and `{FIELD_NAME}` templates |
| 5 | Secrets resolution | Binding a `secret_store`, store protocols and local stores |
| 6 | Connection profiles | `ProfileSpec`, `ProfileField` and `emit()` |
| 7 | Profile registry and invariants | Registering profiles by name and testing their invariants |
| 8 | Authentication boundary | What settings leaves to `mountainash-auth-client` |
| 9 | Caching, settings management and app settings | `get_settings()`, `SettingsManager` and `AppSettings` |

## Ecosystem

mountainash-settings is part of the [mountainash](https://github.com/mountainash-io/mountainash) project, a collection of typed Python libraries for data engineering and platform development. Other mountainash packages use it for settings, connection configuration and secrets resolution. Authentication comes from the separate `mountainash-auth-client` package.
