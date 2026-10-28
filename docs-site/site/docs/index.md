---
title: 'Mountainash Settings'
description: 'Documentation for mountainash-settings — typed configuration for Python applications built on Pydantic v2'
---


[← Back to Ecosystem](https://docs.mountainash.io/)
# Mountainash Settings

**0.1.0 API reset:** read the [migration guide](https://github.com/mountainash-io/mountainash-settings/blob/develop/docs/migration-0.1.md)
for supported names, target adapters and MountainAsh-only cached retrieval. The chapters in this documentation
describe the 0.1 source; the migration guide lists what changed from 0.x.

Define fully-typed application settings with Pydantic, load configuration from YAML, TOML, JSON, or .env files, and retrieve a cached instance with a single call.

## About This Documentation

The API reference lists what each class and function does. This documentation explains the design behind them: when to use field templating instead of a custom validator, how the merge framework decides which value wins, and how the two-pass secrets resolution pipeline works.

## What's Inside

- **[Chapters](chapters/index.md)**: 9 chapters covering Pydantic foundations, base settings, merge strategies, file handling and templating, secrets, connection profiles, the profile registry, the authentication boundary, and caching with app settings
- **[Package Overview](course-description.md)**: scope, capabilities and ecosystem context
- **[About](about.md)**: authorship, license and the relationship to the code repository

## Audience

Python developers and platform engineers who configure applications, data pipelines, or multi-service platforms, particularly those who have used Pydantic `BaseSettings` and need secrets, connection profiles, and multi-file merging handled in one place.
