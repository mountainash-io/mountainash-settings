# Chapters

This textbook is organized into 9 chapters covering the mountainash-settings typed configuration framework. Chapters are sequenced so that each builds on the concepts introduced in earlier chapters.

## Chapter List

1. [Pydantic and Configuration Foundations](./01-pydantic-and-configuration-foundations/index.md) — Prerequisite knowledge including Pydantic BaseModel/BaseSettings, field validators, model config, file formats, environment variables, decorators, discriminated unions, and SecretStr.
2. [MountainAsh Base Settings](./02-mountainash-base-settings/index.md) — The MountainAshBaseSettings class, its model config, post-init lifecycle, source customization, validation invariants, and environment variable configuration.
3. [Settings Parameters and Merge Strategies](./03-settings-parameters-and-merge-strategies/index.md) — The SettingsParameters class with structural/runtime field split, custom hash/eq, parameter factories, and three merge strategies.
4. [File Handling, Kwargs, and Field Templating](./04-file-handling-kwargs-and-field-templating/index.md) — FileHandler and KwargsHandler classes, multi-format file loading, template syntax, field name placeholders, and template resolution.
5. [Secrets Resolution](./05-secrets-resolution/index.md) — The secrets registry, provider protocol, two-pass resolution pipeline, secret prefix syntax, and pluggable providers (Vault, SSM, Key Vault).
6. [Connection Profiles](./06-connection-profiles/index.md) — ProfileDescriptor, ParameterSpec with tiers/defaults/transforms/validators, MISSING sentinel, DescriptorProfile, and dynamic field installation.
7. [Profile Registry and Invariants](./07-profile-registry-and-invariants/index.md) — The Registry class, name-keyed store, decorator registration, duplicate prevention, descriptor invariants, and invariant test generation.
8. [Authentication System](./08-authentication-system/index.md) — AuthSpec base class, kind literal, discriminated union assembly, dispatch function, driver kwargs mapping, 11 concrete auth modes, and custom extension.
9. [Caching, Settings Management, and App Settings](./09-caching-settings-management-and-app-settings/index.md) — LRU caching, get_settings function, structural cache keys, runtime overrides, SettingsManager, and the AppSettings convenience class.

## Concept Coverage

This textbook covers all **110 concepts** from the mountainash-settings learning graph, distributed across 9 chapters with no dependency violations.
