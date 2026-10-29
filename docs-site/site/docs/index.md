---
title: 'Mountainash Settings'
description: 'Documentation for mountainash-settings: typed configuration for Python applications built on Pydantic v2'
---


[← Back to Ecosystem](https://docs.mountainash.io/)
# Mountainash Settings

**0.1.0 API reset:** read the [migration guide](https://github.com/mountainash-io/mountainash-settings/blob/develop/docs/migration-0.1.md)
for supported names, target adapters and cached retrieval. The chapters in this documentation
describe 0.1; the migration guide lists what changed from 0.x.

mountainash-settings lets you define typed application settings with Pydantic, load them from YAML, TOML, JSON or `.env` files, and retrieve a validated instance with a single call.

## About this documentation

This documentation explains how the pieces fit together: when to use field templating instead of a custom validator, how merging decides which value wins, and how `secret:` references are resolved.

## What's inside

- [Chapters](chapters/index.md): nine chapters, from Pydantic foundations and base settings through merging, secrets and connection profiles to caching
- [Package overview](course-description.md): scope, capabilities and ecosystem context
- [About](about.md): authorship, license and the relationship to the code repository
