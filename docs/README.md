# Documentation

These pages describe the current 0.1 development API. Start with the
[README quick start](../README.md#quick-start) or the independently runnable
[configuration recipes](../examples/).

| Guide | Scope |
|---|---|
| [Getting started](quickstart.md) | Reading routes and differences from Pydantic Settings |
| [Advanced usage](advanced-usage.md) | Parameter merging, source snapshots, ownership and custom sources |
| [Profiles](profile-spec-pattern.md) | Native declarations, explicit specs, inheritance, emission and registration |
| [Secrets and local records](README_SECRETS.md) | Selected stores, references, persistence and platform requirements |
| [Migrating to 0.1](migration-0.1.md) | Breaking changes for consumers of the earlier API |

All five guides remain maintained; the migration guide specifically serves
existing consumers. Release procedure and qualification evidence live in
[RELEASE.md](../RELEASE.md).

Designs, implementation plans and superseded planning records belong in the
[central planning catalogue](https://github.com/mountainash-io/mountainash-central/blob/main/04.planning/mountainash-settings/superpowers/INDEX.md).
The former `docs/superpowers/` adapter-registration design and plan have moved
there as superseded history. Current adapter usage is covered by the profile guide.
