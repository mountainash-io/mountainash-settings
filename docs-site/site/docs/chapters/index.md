# Chapters

This documentation has 9 chapters covering the mountainash-settings typed configuration framework.

## Chapter List

1. [Pydantic and Configuration Foundations](./01-pydantic-and-configuration-foundations/index.md) — Pydantic BaseModel/BaseSettings, field validators, model config, file formats, environment variables, decorators, discriminated unions, and SecretStr.
2. [MountainAsh Base Settings](./02-mountainash-base-settings/index.md) — The MountainAshBaseSettings class, its model config, post-init lifecycle, source customization, validation invariants, and environment variable configuration.
3. [Settings Parameters and Merge Strategies](./03-settings-parameters-and-merge-strategies/index.md) — The SettingsParameters class with structural/runtime field split, custom hash/eq, parameter factories, and the merge strategies (ordered file lists, scalar last-wins, shallow kwargs).
4. [File Handling, Kwargs, and Field Templating](./04-file-handling-kwargs-and-field-templating/index.md) — FileHandler and KwargsHandler classes, multi-format file loading, template syntax, field name placeholders, and template resolution.
5. [Secrets Resolution](./05-secrets-resolution/index.md) — The `secret_store` binding, SecretReader/SecretWriter record-store protocols, two-pass resolution pipeline, secret prefix syntax, settings-owned local stores, and `persist()`.
6. [Connection Profiles](./06-connection-profiles/index.md) — ProfileSpec, ParameterSpec with tiers/defaults/transforms/validators, MISSING sentinel, Profile, native ProfileField declarations, dynamic field installation, and target-aware `emit()`.
7. [Profile Registry and Invariants](./07-profile-registry-and-invariants/index.md) — The Registry class, name-keyed store, decorator registration, duplicate prevention, spec invariants, and invariant test generation.
8. [Authentication Boundary](./08-authentication-system/index.md) — What settings does not implement since 0.1, adapter credential rendering, and migration from 0.x; authentication models live in mountainash-auth-client.
9. [Caching, Settings Management, and App Settings](./09-caching-settings-management-and-app-settings/index.md) — Structural source contexts, complete invocation validation, isolated runtime inputs and returns, SettingsManager, and the AppSettings convenience class.
