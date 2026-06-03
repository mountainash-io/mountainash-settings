---
title: Mountainash Settings Package Description
description: A detailed description of the mountainash-settings typed configuration framework for Python applications
quality_score: 87
---

# Mountainash Settings Package Description

## Title

Mountainash Settings: Typed Configuration Framework for Python Applications

## Target Audience

Python developers and platform engineers who need a validated, multi-source configuration system with support for secrets resolution, connection profiles, pluggable authentication, and intelligent caching.

## Prerequisites

- Intermediate Python (type annotations, dataclasses, decorators, metaclasses)
- Familiarity with Pydantic v2 (BaseModel, BaseSettings, validators)
- Basic understanding of configuration file formats (YAML, TOML, JSON, .env)
- Awareness of secrets management concepts (Vault, SSM, Key Vault)

## Topics Covered

1. **Foundation** — Pydantic BaseSettings, multi-format file loading (YAML, TOML, JSON, .env), environment variables
2. **Base Settings** — MountainAshBaseSettings class, post_init lifecycle, source customization, validate_assignment invariant
3. **Settings Parameters** — SettingsParameters with structural hash/eq, merge framework, FileHandler, KwargsHandler
4. **Field Templating** — {FIELD_NAME} template syntax, template resolution in post_init, UPath path derivation
5. **Secrets Resolution** — Secrets registry, two-pass resolution pipeline, pluggable providers (Vault, SSM, Key Vault)
6. **Connection Profiles** — ProfileDescriptor, ParameterSpec, MISSING sentinel, dynamic Pydantic field installation, DescriptorProfile
7. **Profile Registry** — Name-keyed store, @decorator registration pattern, duplicate prevention, invariant testing
8. **Auth System** — AuthSpec base with kind literal, 10+ concrete auth modes as discriminated union, dispatch to driver kwargs
9. **Caching** — LRU cache on _get_settings, SettingsManager dictionary store, runtime overrides via model_copy
10. **App Settings** — AppSettings convenience class, app settings templates

## Topics Excluded

- Application-specific business logic
- Cloud provider account setup and IAM policy authoring
- Secrets engine administration (Vault server setup, AWS SSM configuration)
- Database driver internals and connection pooling
- Pydantic internals beyond what the framework extends

## Learning Outcomes

After studying this package, developers will be able to:

### Remember

- List the four configuration file formats supported (YAML, TOML, JSON, .env)
- Name the 10+ built-in authentication modes
- Identify the structural vs runtime parameter split in SettingsParameters

### Understand

- Explain the two-pass secrets resolution pipeline (kwargs then model tree)
- Describe how ProfileDescriptor dynamically installs Pydantic fields at class creation
- Explain the LRU caching strategy keyed by structural parameters

### Apply

- Subclass MountainAshBaseSettings to define typed application configuration
- Use {FIELD_NAME} templates to derive field values from other settings
- Register and retrieve cached settings instances via get_settings()

### Analyze

- Compare merge strategies for file lists (union), scalars (last-wins), and dicts (deep-merge)
- Analyze the auth discriminated union assembly from a descriptor's auth_modes list

### Evaluate

- Assess which auth mode suits a given backend's credential requirements
- Evaluate ParameterSpec tier and secret/template configuration for profile designs

### Create

- Implement new ProfileDescriptor definitions with typed parameters and auth modes
- Build custom secrets providers for the secrets registry
- Design new AuthSpec subclasses for proprietary authentication schemes

## Context

Mountainash-settings provides a typed configuration framework for Python applications built on Pydantic v2. It loads configuration from multiple file formats, resolves secrets transparently, supports field templating for derived values, and provides a profile system for building reusable connection configurations. The auth system offers 10+ pluggable authentication modes as a discriminated union. Intelligent LRU caching ensures settings are constructed once and reused efficiently.
