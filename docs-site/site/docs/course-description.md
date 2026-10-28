---
title: 'Package Overview'
description: 'Package overview of mountainash-settings — what it is, what it covers, what it does not, and where it fits in the mountainash ecosystem'
---

[← Back to Home](index.md)

# Package Overview

mountainash-settings is a typed configuration framework for Python applications built on Pydantic v2. It loads configuration from multiple file formats, resolves secrets transparently, supports field templating for derived values, and provides a profile system for reusable connection configurations. Structural source-context caching reuses captured inputs while each retrieval validates a fresh, independently owned result. Authentication is not part of the package: it is owned by `mountainash-auth-client` (see [Chapter 8](chapters/08-authentication-system/index.md)).

## Audience

Python developers and platform engineers responsible for how applications are configured across environments: data engineers who need consistent pipeline settings across dev, staging and production; backend developers managing typed, reusable connection parameters for databases and services; and platform engineers standardising configuration and secret-reference conventions across a fleet of services. It picks up where Pydantic `BaseSettings` leaves off: secrets, connection profiles and multi-file merging.

Assumed knowledge: Python type annotations, dataclasses and decorators; Pydantic v2 (`BaseModel`, `BaseSettings`, validators); at least one of YAML, TOML, JSON or `.env`; and the general role of a secrets manager. [Chapter 1](chapters/01-pydantic-and-configuration-foundations/index.md) summarises the Pydantic and file-loading concepts the other chapters rely on.

## Key Capabilities

**Any config source, one base class.** YAML, TOML, JSON, .env files, and environment variables all flow into the same typed settings class. Pydantic validates everything: type coercion, required fields, constrained values. File lists merge in the order given, and kwargs merge shallowly with later values winning.

**Fields that build on each other.** Template syntax lets fields reference other fields: `log_file = 'logs/{APP_NAME}/{RUNDATE}.log'`. Connection strings build from host, port and database fields; paths compose from base directories and environment-specific suffixes.

**Secrets that resolve themselves.** Write `secret:path/to/value` in a config file or environment variable. A `secret_store` bound directly to the settings parameters (any `SecretReader`, or a `SecretWriter` for `persist()`) supplies the records, and the reference resolves before Pydantic validation, so the settings class sees the real value. Settings ships local record stores (filesystem, memory, namespaced); external secret managers such as Vault, AWS SSM or Azure Key Vault integrate by implementing the store protocols. There is no secrets registry and no bundled cloud provider.

**Connection profiles that know their targets.** A profile is declared with an explicit `ProfileSpec` or with native `ProfileField` declarations on the class. Pydantic fields and template wiring are installed automatically, and `emit(target, base=)` together with `__adapters__` renders target-specific driver keyword arguments.

**Authentication kept at the boundary.** Authentication models, auth-mode selection and credential rendering live in `mountainash-auth-client`. Settings supplies the generic pieces an auth layer plugs into: profile declarations, secret handling and target adapters.

**Source caching for pipelines.** `get_settings()` reuses a private structural source context while validating each invocation into a fresh, independently owned result. Runtime overrides stay invocation-local, including on the first call.

## Chapters

Full descriptions are on the [Chapters](chapters/index.md) page.

| # | Chapter | Documents |
|---|---------|-----------|
| 1 | Pydantic and Configuration Foundations | Pydantic and file/env-loading concepts the package builds on |
| 2 | MountainAsh Base Settings | The `MountainAshBaseSettings` class and its lifecycle |
| 3 | Settings Parameters and Merge Strategies | Structural vs. runtime parameters, the merge framework |
| 4 | File Handling, Kwargs, and Field Templating | Multi-format loading and `{FIELD_NAME}` templating |
| 5 | Secrets Resolution | `secret_store` binding, record-store protocols, two-pass resolution, local stores |
| 6 | Connection Profiles | `ProfileSpec`, `ParameterSpec`, native `ProfileField` declarations, target-aware `emit()` |
| 7 | Profile Registry and Invariants | Registration, duplicate prevention, invariant testing |
| 8 | Authentication Boundary | What settings does not implement, and how credentials are rendered through adapters |
| 9 | Caching, Settings Management, and App Settings | Structural source-context reuse, fresh owned materialization, `SettingsManager`, `AppSettings` |

## Scope

Out of scope: application-specific business logic, cloud IAM setup, secrets-engine administration, database driver internals, authentication models and flows, and Pydantic internals beyond what `mountainash-settings` extends.

## Ecosystem

mountainash-settings is part of the [mountainash](https://github.com/mountainash-io/mountainash) project, a collection of typed Python libraries for data engineering and platform development. It is the configuration layer other mountainash packages depend on for settings management, connection configuration and secrets resolution; authentication is provided by the separate `mountainash-auth-client` package.
