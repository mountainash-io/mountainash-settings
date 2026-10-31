---
title: 'About'
description: 'Why mountainash-settings exists, the design ideas behind it, where it fits in the mountainash project, and who maintains it'
---

[← Back to Home](index.md)

# About mountainash-settings

**Pydantic validates your settings. mountainash-settings decides where they come from, when they load and who gets to see them.**

!!! warning "Experimental"
    mountainash-settings 0.1.0 is experimental and not yet ready for production use. Its APIs can change between versions, and it is not yet published on PyPI.

## Why it exists

Pydantic Settings already reads environment variables and `.env` files into a typed model. That is enough for a single script. It starts to strain when an application grows into services, scheduled jobs and worker processes.

Two problems show up at that point. The first is that settings loaded once at startup are not there when a worker process, a thread pool or an orchestrator such as Dagster rebuilds your application somewhere else. The second is that a settings object full of passwords and API keys, passed from constructor to constructor, eventually ends up in a log line, an error report or a serialized message.

mountainash-settings answers both the same way. Your code carries a recipe, a `SettingsParameters` object that says which class, which files and which environment prefix to use, and asks for the settings where the work actually runs. The recipe is cheap to pass around, and printing it never shows the values you passed in.

## What it adds to Pydantic Settings

Pydantic supplies validation, field types, aliases and inheritance. Pydantic Settings supplies the source readers. mountainash-settings builds on both and adds:

| Area | What you get |
|---|---|
| Configuration loading | YAML, TOML, JSON, `.env` and environment inputs feeding one class, with a fixed precedence |
| Derived values | `{FIELD_NAME}` templates that build paths and names from other fields |
| Retrieval | `get_settings()` with cached inputs and an independent, validated copy for every caller |
| Secrets | `secret:` references resolved from a store you choose, plus built-in local stores |
| Connection profiles | One declaration per backend, rendered into the keyword arguments its driver expects |
| Extension | Registries of profiles with generated invariant tests, and store protocols for your own secret managers |

## Design ideas

These ideas shape the whole package. Knowing them makes the rest of the documentation easier to read.

Carry the recipe, not the values. Pass `SettingsParameters` through your application and retrieve settings at the point of use. Fewer objects hold live credentials, and workers can rebuild exactly the configuration they need.

Every caller gets its own copy. `get_settings()` reuses the inputs it has already read, but each call returns a freshly validated instance. One module changing its settings never affects another.

Configuration is fixed for the life of a process. Once a configuration has been read, later calls reuse it, even if the file on disk changes. A new process picks up a changed deployment; there is no hot-reload machinery to reason about.

Secrets stay references until they are needed. A `secret:` reference is resolved when the settings are constructed, and if a resolved value fails validation the error names the field, not the value.

It stays Pydantic. Your settings class is an ordinary Pydantic model with native field types and validators, so what you already know about Pydantic still applies.

## Where it fits

mountainash-settings is the configuration layer of the [mountainash](https://github.com/mountainash-io/mountainash) project, a collection of typed Python libraries for data engineering and platform development. Other mountainash packages use it for their settings, connection profiles and secret references. Authentication is a separate concern and lives in `mountainash-auth-client`.

## Who maintains it

The library and this documentation are written and maintained by Nathaniel Ramm. Both are developed in the open at [github.com/mountainash-io/mountainash-settings](https://github.com/mountainash-io/mountainash-settings), where the [examples directory](https://github.com/mountainash-io/mountainash-settings/tree/develop/examples) has runnable versions of the main patterns, including worker processes and Dagster jobs.

Every page here has an edit link to its source under `docs-site/site/docs/`, so a correction can go straight in as a pull request. For questions and feedback, the [Contact](contact.md) page lists the ways to get in touch.

## License

`mountainash-settings` and this documentation are licensed under the [Apache License, Version 2.0](license.md). Copyright 2024-2026 Mountain Ash Solutions Pty. Ltd.
