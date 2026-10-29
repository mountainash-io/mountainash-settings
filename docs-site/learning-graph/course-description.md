---
title: Mountainash settings package description
description: A detailed description of the mountainash-settings typed configuration framework for Python applications
quality_score: 87
---

# Mountainash settings package description

## Title

Mountainash Settings: Typed Configuration Framework for Python Applications

## Target Audience

Python developers and platform engineers who need a validated, multi-source configuration system with support for secrets resolution, connection profiles, and cached retrieval.

## Prerequisites

- Intermediate Python (type annotations, dataclasses, decorators)
- Familiarity with Pydantic v2 (BaseModel, BaseSettings, validators)
- Basic understanding of configuration file formats (YAML, TOML, JSON, .env)
- Awareness of secrets management concepts

## Topics Covered

1. Foundation: Pydantic BaseSettings, multi-format file loading (YAML, TOML, JSON, .env), environment variables
2. Base settings: MountainAshBaseSettings class, construction lifecycle, validation on assignment
3. Settings parameters: SettingsParameters, merge strategies for files and kwargs
4. Field templating: {FIELD_NAME} template syntax, path derivation
5. Secrets resolution: `secret_store` binding (SecretReader/SecretWriter), two-pass resolution pipeline, local record stores, `persist()`
6. Connection profiles: ProfileSpec, ParameterSpec, MISSING sentinel, native ProfileField declarations, dynamic Pydantic field installation, Profile, target-aware `emit()`
7. Profile registry: Name-keyed store, @decorator registration pattern, duplicate prevention, invariant testing
8. Authentication boundary: auth removed in 0.1 and owned by mountainash-auth-client; adapter credential rendering
9. Caching: source caching with `get_settings()`, runtime overrides, fresh instance on every call
10. App settings: AppSettings convenience class, app settings templates

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
- Name the secret record-store protocols (SecretReader, SecretWriter)
- Identify the structural vs runtime parameter split in SettingsParameters

### Understand

- Explain the two-pass secrets resolution pipeline (kwargs then model tree)
- Describe how a ProfileSpec or native ProfileField declarations install Pydantic fields at class creation
- Explain how `get_settings()` reuses cached inputs while returning a fresh instance

### Apply

- Subclass MountainAshBaseSettings to define typed application configuration
- Use {FIELD_NAME} templates to derive field values from other settings
- Retrieve isolated settings instances with get_settings()

### Analyze

- Compare merge strategies for file lists (ordered), scalars (last-wins), and kwargs (shallow merge)
- Analyze how `emit(target, base=)` and `__adapters__` render target-specific driver kwargs

### Evaluate

- Assess where authentication responsibility sits between settings and mountainash-auth-client
- Evaluate ParameterSpec tier and secret/template configuration for profile designs

### Create

- Implement new profile declarations with typed parameters
- Implement custom secret stores satisfying the SecretReader/SecretWriter protocols

## Context

mountainash-settings is a typed configuration framework for Python applications built on Pydantic v2. It loads configuration from several file formats and environment variables, resolves secrets, derives field values with templates, and provides profiles for reusable connection configuration. `get_settings()` caches the inputs it reads and returns a freshly validated instance on every call. Authentication is not part of the package: it lives in `mountainash-auth-client`.
