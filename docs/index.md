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
- **[MicroSims](sims/index.md)** — Interactive simulations that let you experiment with configuration concepts in the browser
- **[Learning Graph](learning-graph/index.md)** — A dependency map showing how concepts relate and the order they should be learned

## Who This Is For

Python developers and platform engineers who configure applications, data pipelines, or multi-service platforms. If you have used Pydantic BaseSettings before and wished it handled secrets, connection profiles, and multi-file merging out of the box, start with [About](about.md) for a fuller picture of what to expect.
