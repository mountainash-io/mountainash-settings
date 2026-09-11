---
title: 'Package Overview'
description: 'Course-style overview of the Mountainash Settings manual — audience, prerequisites, learning outcomes, and syllabus'
---

[← Back to Home](index.md)

# Package Overview

This page frames the [Mountainash Settings](index.md) manual the way a course syllabus would: who it is for, what you need to know before starting, what you will be able to do by the end, and how the material is sequenced across chapters. If you want the pitch for the library itself, start with the [Home](index.md) page; if you want to know how this manual is licensed and maintained, see [About](about.md).

## Audience

This is a manual for Python developers and platform engineers who are responsible for how their applications get configured — not just reading a value out of an environment variable, but designing a configuration system that stays correct as an application grows across environments. Three profiles get the most out of it:

- A **data engineer** who needs pipeline settings that behave consistently across dev, staging, and production, without hand-rolled environment-variable parsing.
- A **backend developer** who manages connection parameters for multiple databases or external services and wants those connections typed, validated, and reusable rather than copy-pasted.
- A **platform engineer** standardizing configuration conventions across a fleet of services, including how secrets are referenced and resolved.

If you have used Pydantic's `BaseSettings` and found yourself wanting built-in support for secrets, connection profiles, and multi-file merging, this manual picks up exactly where that experience leaves off.

## Prerequisites

Before starting, you should be comfortable with:

- Python type annotations, dataclasses, and decorators
- Pydantic v2 fundamentals — `BaseModel`, `BaseSettings`, and field validators
- At least one structured configuration format (YAML, TOML, JSON, or `.env`)
- The general shape of secrets management — you do not need to have administered Vault, AWS SSM, or Azure Key Vault, but you should know why teams use them

Chapter 1 is a deliberate on-ramp: it reviews the Pydantic and configuration-loading concepts the rest of the book assumes, including discriminated unions and `SecretStr`, so gaps in that prerequisite list are recoverable early rather than compounding later.

## Learning Outcomes

By working through this manual, you will be able to:

1. Define typed settings classes on `MountainAshBaseSettings` that validate configuration at startup and fail fast on bad input.
2. Load and merge configuration from multiple files and environment variables with predictable, well-understood priority rules.
3. Derive fields from other fields using `{FIELD_NAME}` template syntax — connection strings, log paths, output directories — without writing custom derivation code.
4. Wire up a secrets provider (Vault, AWS SSM, Azure Key Vault, or a custom one) so `secret:path/to/value` references resolve transparently before validation runs.
5. Build reusable connection profiles for databases, storage backends, and APIs using `ProfileDescriptor`, complete with typed parameters and auth-mode selection.
6. Select and configure the right authentication mode from a discriminated union of 10+ auth kinds, each with `SecretStr`-protected credentials.
7. Cache settings instances with `get_settings()` so an application constructs each configuration once and reuses it efficiently, while still supporting per-call runtime overrides.

## Syllabus

The manual proceeds as 9 chapters, each building on the concepts introduced before it. Full descriptions live on the [Chapters](chapters/index.md) page; in outline, the progression is:

| # | Chapter | Focus |
|---|---------|-------|
| 1 | Pydantic and Configuration Foundations | Prerequisite Pydantic and file/env-loading concepts |
| 2 | MountainAsh Base Settings | The `MountainAshBaseSettings` class and its lifecycle |
| 3 | Settings Parameters and Merge Strategies | Structural vs. runtime parameters, the merge framework |
| 4 | File Handling, Kwargs, and Field Templating | Multi-format loading and `{FIELD_NAME}` templating |
| 5 | Secrets Resolution | The secrets registry and two-pass resolution pipeline |
| 6 | Connection Profiles | `ProfileDescriptor`, `ParameterSpec`, dynamic field installation |
| 7 | Profile Registry and Invariants | Registration, duplicate prevention, invariant testing |
| 8 | Authentication System | `AuthSpec`, the auth-mode discriminated union, driver dispatch |
| 9 | Caching, Settings Management, and App Settings | LRU caching, `SettingsManager`, `AppSettings` |

Together the chapters cover all 110 concepts in the manual's [learning graph](learning-graph/index.md), sequenced so no chapter depends on material introduced later. Out of scope, deliberately: application-specific business logic, cloud IAM setup, secrets-engine administration, database driver internals, and Pydantic internals beyond what `mountainash-settings` extends.

## Where to Start

Read the chapters in order — the merge framework in Chapter 3 depends on the base-settings lifecycle from Chapter 2, the templating in Chapter 4 depends on the merge framework, and secrets, profiles, and auth in Chapters 5 through 8 all build on the file- and field-handling introduced in Chapter 4. Begin at [Chapter 1](chapters/01-pydantic-and-configuration-foundations/index.md) or, if the prerequisites above are already second nature, skip ahead to [Chapter 2](chapters/02-mountainash-base-settings/index.md).
