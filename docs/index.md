---
title: 'Mountainash Settings'
description: 'A practitioner manual for mountainash-settings — typed configuration for Python applications built on Pydantic v2'
---


[← Back to Ecosystem](../)
# Mountainash Settings

Define fully-typed application settings with Pydantic, load configuration from YAML, TOML, JSON, or .env files, and retrieve a cached instance with a single call.

## Why a Guided Manual?

The API reference tells you *what* each class and function does. This manual explains *why* you would use them — when to reach for field templating instead of a custom validator, how the merge framework decides which value wins, and what happens inside the two-pass secrets resolution pipeline. It is the difference between knowing the interface and understanding the design.

## What's Inside

- **[Chapters](chapters/index.md)** — 9 chapters covering foundations through caching and app settings, each building on the last

## Who This Is For

Python developers and platform engineers who configure applications, data pipelines, or multi-service platforms. If you have used Pydantic BaseSettings before and wished it handled secrets, connection profiles, and multi-file merging out of the box, start with [About](about.md) for a fuller picture of what to expect.



# Package Overview

mountainash-settings is a typed configuration framework for Python applications built on Pydantic v2. It loads configuration from multiple file formats, resolves secrets transparently, supports field templating for derived values, and provides a profile system for building reusable connection configurations. The auth system offers 10+ pluggable authentication modes as a discriminated union. Intelligent LRU caching ensures settings are constructed once and reused efficiently.

## Target Audience

Python developers and platform engineers who need a validated, multi-source configuration system with support for secrets resolution, connection profiles, pluggable authentication, and intelligent caching.


## Who This Is For

This manual is for Python developers and platform engineers who build applications that need validated, multi-source configuration. You might be a data engineer wiring up pipeline settings across dev, staging, and production, a backend developer managing connection profiles for multiple databases, or a platform engineer standardising configuration across a fleet of services. If you write Python and deal with configuration files, environment variables, or secrets, this is for you.

## What You Should Already Know

You should be comfortable with:

- Python type annotations, dataclasses, and decorators
- Pydantic v2 basics — `BaseModel`, `BaseSettings`, and validators
- At least one configuration file format (YAML, TOML, JSON, or .env)
- The general idea of secrets management (you have heard of Vault, AWS SSM, or Azure Key Vault, even if you have not administered them)

## What You'll Get Out of This

After working through this manual, you will know how to:

- Define typed settings classes that validate configuration at startup, catching errors before your application runs
- Load and merge configuration from multiple files and environment variables with predictable priority rules
- Use template syntax to derive fields from other fields — connection strings, log paths, output directories — without custom code
- Wire up secrets providers so that `secret:path/to/value` in a config file resolves transparently to the real credential
- Build reusable connection profiles for databases, storage backends, and APIs with typed parameters and auth mode selection
- Cache settings instances so your application constructs them once and reuses them efficiently across modules

## Prerequisites

- Intermediate Python (type annotations, dataclasses, decorators, metaclasses)
- Familiarity with Pydantic v2 (BaseModel, BaseSettings, validators)
- Basic understanding of configuration file formats (YAML, TOML, JSON, .env)
- Awareness of secrets management concepts (Vault, SSM, Key Vault)

## What This Manual Covers

1. **Pydantic and Configuration Foundations** — Pydantic BaseSettings, multi-format file loading (YAML, TOML, JSON, .env), environment variables
2. **MountainAsh Base Settings** — MountainAshBaseSettings class, post_init lifecycle, source customization, validate_assignment invariant
3. **Settings Parameters and Merge Strategies** — SettingsParameters with structural hash/eq, merge framework, FileHandler, KwargsHandler
4. **File Handling, Kwargs, and Field Templating** — {FIELD_NAME} template syntax, template resolution in post_init, UPath path derivation
5. **Secrets Resolution** — Secrets registry, two-pass resolution pipeline, pluggable providers (Vault, SSM, Key Vault)
6. **Connection Profiles** — ProfileDescriptor, ParameterSpec, MISSING sentinel, dynamic Pydantic field installation, DescriptorProfile
7. **Profile Registry and Invariants** — Name-keyed store, @decorator registration pattern, duplicate prevention, invariant testing
8. **Authentication System** — AuthSpec base with kind literal, 10+ concrete auth modes as discriminated union, dispatch to driver kwargs
9. **Caching, Settings Management, and App Settings** — LRU cache on _get_settings, SettingsManager dictionary store, runtime overrides via model_copy, AppSettings convenience class

## What This Manual Does Not Cover

- Application-specific business logic
- Cloud provider account setup and IAM policy authoring
- Secrets engine administration (Vault server setup, AWS SSM configuration)
- Database driver internals and connection pooling
- Pydantic internals beyond what the framework extends

## Key Capabilities

**Any config source, one base class** — YAML, TOML, JSON, .env files, and environment variables all flow into the same typed settings class. Pydantic validates everything — type coercion, required fields, constrained values. The config file format becomes a deployment choice, not an application concern.

**Fields that build on each other** — Template syntax lets fields reference other fields: `log_file = 'logs/{APP_NAME}/{RUNDATE}.log'`. Connection strings build from host, port, and database fields. Paths compose from base directories and environment-specific suffixes. The derivation is declarative and transparent.

**Secrets that resolve themselves** — Write `secret:path/to/value` in a config file or environment variable. Register a secrets provider — AWS SSM, HashiCorp Vault, Azure Key Vault, or your own. The secret resolves before Pydantic validation, so the settings class sees the real value and validates it normally. No special handling in application code.

**Connection profiles that know their databases** — Define a profile descriptor once and the framework installs Pydantic fields, auth options, and template wiring automatically. Each database backend gets typed settings with auto-derived connection parameters and driver kwargs.

**Auth modes that cover every backend** — From password through OAuth2 to service accounts to Kerberos to "none", every auth mode is a Pydantic model with SecretStr-protected credentials. The discriminated union validates that the auth mode matches what the backend expects.

**Smart caching for pipelines** — `get_settings()` returns the same instance on every call for the same configuration. Runtime overrides for batch IDs or run-specific parameters get their own instance without polluting the cache.

## Context

mountainash-settings is part of the [mountainash](https://github.com/mountainash-io/mountainash) project, a collection of typed Python libraries for data engineering and platform development. It serves as the configuration layer that other mountainash packages depend on for settings management, connection configuration, and secrets resolution.
