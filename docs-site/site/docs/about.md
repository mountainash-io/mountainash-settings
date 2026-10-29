---
title: 'About'
description: 'About the Mountainash Settings documentation: authorship, license, and relationship to the mountainash-settings code repository'
---

[← Back to Home](index.md)

# About this documentation

This is the manual for `mountainash-settings`, a typed configuration framework for Python applications built on Pydantic v2.

The manual has [nine chapters](chapters/index.md). They cover loading settings from files and environment variables, merging configuration from several sources, field templating for derived values, `secret:` references resolved from a secret store, connection profiles that render driver keyword arguments, and caching. Authentication is not part of the package; it lives in `mountainash-auth-client`. See the [Package overview](course-description.md) for audience and scope.

## About the author

This manual and the `mountainash-settings` library are written and maintained by Nathaniel Ramm. Questions, corrections and feedback are welcome. The [Contact](contact.md) page lists ways to reach out, including opening an issue on GitHub.

## Relationship to the code repository

`mountainash-settings` is developed in the open at [github.com/mountainash-io/mountainash-settings](https://github.com/mountainash-io/mountainash-settings). Every page in this manual has an edit link to its source file under `docs-site/site/docs/` in that repository, so you can propose corrections as pull requests against the page you are reading.

The library is part of the [mountainash](https://github.com/mountainash-io/mountainash) project, a collection of typed Python libraries for data engineering and platform development. Within that project, `mountainash-settings` is the configuration layer: other mountainash packages use it for settings, connection profiles and secrets resolution.

## License

`mountainash-settings` and this manual are licensed under the [Apache License, Version 2.0](license.md). Copyright 2024-2026 Mountain Ash Solutions Pty. Ltd.
