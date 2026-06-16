---
title: Package Overview
description: 'What mountainash-settings does, who it is for, and what this manual covers'
---

# Package Overview

mountainash-settings is a typed configuration framework for Python applications built on Pydantic v2. It loads configuration from multiple file formats, resolves secrets transparently, supports field templating for derived values, and provides a profile system for building reusable connection configurations. The auth system offers 10+ pluggable authentication modes as a discriminated union. Intelligent LRU caching ensures settings are constructed once and reused efficiently.

## Target Audience

Python developers and platform engineers who need a validated, multi-source configuration system with support for secrets resolution, connection profiles, pluggable authentication, and intelligent caching.

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
