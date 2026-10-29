# Chapters

1. [Pydantic and configuration foundations](./01-pydantic-and-configuration-foundations/index.md): the Pydantic and file-loading concepts the package builds on.
2. [MountainAsh base settings](./02-mountainash-base-settings/index.md): defining a settings class with `MountainAshBaseSettings`.
3. [Settings parameters and merge strategies](./03-settings-parameters-and-merge-strategies/index.md): choosing config files and kwargs, and how values merge.
4. [File handling, kwargs, and field templating](./04-file-handling-kwargs-and-field-templating/index.md): loading YAML, TOML, JSON and `.env` files, and deriving fields with `{FIELD_NAME}` templates.
5. [Secrets resolution](./05-secrets-resolution/index.md): resolving `secret:` references from a secret store.
6. [Connection profiles](./06-connection-profiles/index.md): declaring connection parameters once and rendering driver keyword arguments with `emit()`.
7. [Profile registry and invariants](./07-profile-registry-and-invariants/index.md): registering profiles by name and testing their invariants.
8. [Authentication boundary](./08-authentication-system/index.md): what settings leaves to `mountainash-auth-client`, and how credentials flow through adapters.
9. [Caching, settings management and app settings](./09-caching-settings-management-and-app-settings/index.md): `get_settings()`, `SettingsManager` and `AppSettings`.
