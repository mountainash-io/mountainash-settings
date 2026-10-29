# Frequently asked questions for mountainash-settings

## Foundation and base settings

### What is mountainash-settings and what problem does it solve?

Mountainash-settings is a typed configuration library for Python applications, built on Pydantic v2. It loads configuration from YAML, TOML, JSON and .env files and from environment variables, then validates it into one typed model. It also resolves `secret:` references, derives values from field templates, and offers reusable connection profiles. Loading logic lives in the settings class instead of being spread through the application.

### How does MountainAshBaseSettings relate to Pydantic BaseSettings?

MountainAshBaseSettings is a subclass of Pydantic's BaseSettings. It keeps Pydantic's environment variable loading, type coercion and validation, and adds:

- loading from YAML, TOML, JSON and .env files;
- cached retrieval through `get_settings`;
- two-pass resolution of `secret:` references through a secret store you bind explicitly;
- a `post_init()` hook that subclasses override for templates and derived values, called after references are resolved;
- validation on assignment, so changing a field after construction is checked like construction;
- SettingsParameters, which selects files, the environment prefix, the secrets directory, the secret store and runtime inputs.

You subclass MountainAshBaseSettings instead of BaseSettings to get these. Its model config sets `extra="ignore"`, `validate_default=False`, `arbitrary_types_allowed=True` and `validate_assignment=True`.

### Which configuration file formats does mountainash-settings support?

YAML, TOML, JSON and .env files. You can mix them in one application, for example YAML for application settings, TOML for project metadata and a .env file for local overrides. The config files parameter accepts a list of paths, and each path is routed by its extension to the matching Pydantic source. Within one format, later files deep-merge over earlier ones.

### What is the settings model config and how do I customise it?

It is the Pydantic `model_config` of MountainAshBaseSettings, a `SettingsConfigDict` with four defaults:

- `extra="ignore"`: config files may contain undeclared keys.
- `validate_default=False`.
- `arbitrary_types_allowed=True`: permits types such as UPath.
- `validate_assignment=True`: assignments after construction are validated.

A subclass adjusts these by declaring its own `model_config`, which Pydantic merges with the inherited one. For the environment prefix, configuration files, secrets directory and secret store, prefer the SettingsParameters selectors or the matching constructor arguments, because they also form the cache identity. A class-level `env_prefix` or `secrets_dir` in `model_config` is only a fallback when no selector is supplied. Source order is controlled separately by `settings_customise_sources`, and cached retrieval also uses `settings_capture_sources`. Chapter 2 has the details.

### What is the post_init lifecycle and when does it run?

`post_init()` is a hook that runs at the end of construction, after Pydantic has loaded and validated the settings and after both secret-reference passes. The base implementation is empty. Subclasses override it for template expansion and other derived values. AppSettings derives `RUNDATETIME` there, and Profile evaluates `ParameterSpec.template` fields there. Because `secret:` references are resolved first, a template that references a field sees the resolved value. The base class does not expand templates by itself; a template applies only where a subclass calls `init_setting_from_template` or `format_template_from_settings`. Chapter 2 lists the full construction order.

### What is the validate_assignment invariant and why does it matter?

Assigning to a field on a settings instance after construction goes through Pydantic's validation. Without that, you could assign an invalid value to a typed field and skip the checks that run at construction. Mountainash-settings enables it by default in the model config. The package's own bookkeeping `SETTINGS_*` fields are the one exception, since the framework has to set them without triggering validation. Template derivation and secret resolution both assign through the validated path.

### How does source customization and source priority work?

The default order, from highest to lowest priority, is:

1. keyword arguments passed to the constructor;
2. environment variables;
3. the dotenv file read with the configured environment prefix;
4. the same dotenv files read without a prefix;
5. YAML files;
6. TOML files;
7. JSON files;
8. Pydantic secret files;
9. field defaults.

An environment variable therefore overrides a YAML value, and an explicit keyword argument overrides everything. Overriding `settings_customise_sources` changes the order for direct construction. Cached retrieval through `get_settings` does not call that hook. A class that overrides it must also override `settings_capture_sources`, and its custom sources must extend `CacheableSettingsSource`, or cached retrieval raises `ValueError`. The environment prefix, supplied through SettingsParameters, namespaces environment variables so settings classes in one process do not collide. Environment and `.env` lookups are case-sensitive and use the field name exactly: with prefix `DB_`, a field `host` reads `DB_host`, not `DB_HOST`.

### How does multi-format loading choose a parser for each file?

By file extension. When you pass a list of paths as the config files parameter, `.yaml` and `.yml` files go to the YAML source, `.toml` to TOML, `.json` to JSON and `.env` to dotenv. The paths are grouped into those four buckets before the matching Pydantic sources read them. You never name a parser. A file with an unknown extension raises `ValueError`.

## Settings parameters and merge strategies

### What is SettingsParameters and what does it do?

SettingsParameters describes how one settings result is materialized and merged. Its structural fields identify the source context to capture: the settings class, file list, environment prefix, secrets directory and secret store (selected by object identity). Its runtime keyword arguments are inputs for a single call. The manager captures the structural sources once. Each request then projects its runtime inputs and validates a fresh result. You combine two parameter sets with `merge()`.

### What is the difference between structural fields and runtime fields?

Structural fields identify the source context: the settings class, configuration-file list, environment prefix, secrets directory and secret store. The secret store is compared and hashed by object identity, never by content, so two different store objects never share a captured context. Requests with the same structural fields share the captured source context, not a settings object. Runtime fields are the keyword arguments of the current call. They do not change the structural key and are applied only during that call. Every retrieval still returns a newly validated, isolated result.

### How are SettingsParameters and configuration sources merged?

Merging happens at two levels.

When you combine two SettingsParameters with `merge()`:

- `config_files` lists are joined base-then-other, with duplicates removed at their first position.
- Scalar selectors (`env_prefix`, `secrets_dir`) take the other value, or the base value with `prioritise_base=True`.
- `secret_store` takes the other store when it is not `None`.
- `kwargs` merge shallowly: the other side overwrites duplicate keys, and nested values are replaced, not merged.

When several structured files of one format are loaded as sources, they are read in caller order. Later mappings merge recursively into earlier ones, while later lists and scalars replace earlier values. Lists are not concatenated. Chapter 3 covers the parameter merge and chapter 2 the source merge.

### How does mountainash-settings select and order configuration files?

Before loading, the file list is normalised. You can pass a string, a UPath, a sequence of paths or `None`. The result is an ordered list with duplicates removed in first-seen order. Each file's type comes from its extension, and an unknown extension raises `ValueError`. The files are then grouped into env, YAML, TOML and JSON sets for the matching Pydantic sources, which read them. This happens during construction, so application code rarely deals with it directly. It is useful to know when debugging which files were selected and in what order.

### How are keyword arguments normalised before they reach the settings constructor?

Keyword arguments can be given as a mapping or as an iterable of key/value pairs, or be `None`. Either form becomes a fresh dictionary, and a nested `kwargs` mapping is unwrapped when one is present. When two inputs are merged, the second takes precedence. Malformed input raises a `TypeError`. Values are not converted and keys are not checked against the model's fields. Pydantic does type coercion and field validation when the model is constructed.

## Field templating

### What is the {FIELD_NAME} template syntax and how does it work?

A template is a string with `{ANOTHER_FIELD}` placeholders. When it is applied, each placeholder is replaced by the current value of that field on the same settings model. Templates are not expanded automatically. They apply only where a subclass calls `init_setting_from_template` in `post_init`, or where a Profile declares `ProfileField(template="...")`. For example, a subclass can set `self.ENDPOINT = self.init_setting_from_template("{BASE_URL}/v1/data", self.ENDPOINT)`. With `BASE_URL` set to `"https://api.example.com"`, `ENDPOINT` then resolves to `"https://api.example.com/v1/data"`. This happens in `post_init`, after all sources (files, environment variables, kwargs) have been merged and validated.

### What are template priority rules?

They decide when a template is evaluated and when an explicit value is kept. With `init_setting_from_template()`, a non-`None` current value is kept unless `reinitialise=True`. Otherwise the template is evaluated.

`Profile` uses a stricter rule based on where a value came from, not on comparing values. On first construction, every template field you did not supply to that call is derived. With `reinitialise=True`, only fields previously recorded as template-derived are re-derived, except any you supplied to that call through the cache route. An explicit value from keyword arguments, environment variables or files is therefore not overwritten by a template. Calling `post_init(reinitialise=True)` directly on a hand-built instance has no such per-call protection. Chapter 4 describes the rules in full.

### Can a template reference another templated field?

Yes, but resolution is a single ordered pass using ordinary `str.format()`. There is no recursive expansion and no cycle detection. A subclass resolves templates in `post_init()` in declaration order, so a field that references another derived field must be resolved after it. A template that references a field not yet resolved reads that field's current value, so a pair that references each other resolves with `None` in the text instead of raising an error. Chapter 4 has an example.

### Can a template produce a UPath field?

Not directly. Templates produce strings. UPath support applies to `config_files` paths, which are normalised and checked for existence against the named filesystem. To get a UPath field from a template, convert it in `post_init`, for example `UPath(self.format_template_from_settings(...))`.

## Secrets resolution

### What is the two-pass secrets resolution pipeline?

It resolves `secret:` references wherever they enter the settings.

1. Keyword arguments pass. References in the keyword arguments are resolved before `BaseSettings.__init__` runs.
2. Model pass. After the sources (files, environment, secrets directory) have been loaded and validated, the constructed model is walked and references in the loaded values are resolved, including those in nested models, lists and dictionaries.

Two passes are needed because file and environment values only exist once the base constructor has run. Both passes resolve through the `secret_store` bound on the request, and a reference with no bound store raises `SecretCapabilityError`. Both complete before `post_init` runs.

### How do I choose a secret store?

You pass one explicitly. A store is any object that satisfies the `SecretReader` protocol: `get(key)` returning a record or `None`. `SecretWriter` adds `set`, `delete` and `transaction`, and `ClearableSecretStore` adds `is_cleared`. The package supplies `FilesystemBackend`, `MemorySecretStore` and `NamespacedSecretStore`, a prefix view over another store. Pass the store as `secret_store` on SettingsParameters or as the constructor keyword. It is never registered under a name, and it takes part in cache identity by object identity. Version 0.1.0 removed the secrets registry and provider lookup (`register_secrets_backend`, `get_secrets_backend` and the `secrets_provider` parameter), with no replacement shims. Chapter 5 covers stores.

### What is the secret prefix syntax?

The prefix is `secret:`. A value that begins with it is resolved from the bound store. A dotted reference such as `secret:live_db.postgres.password` splits at the last dot into the record key (`live_db.postgres`) and the field (`password`). A simple reference such as `secret:api_token` needs a record with exactly one field and returns that field's value. A missing record or field raises `KeyError`, and a reference with no bound store raises `SecretCapabilityError`. A reference is never left in place as literal text. The earlier `vault://`, `ssm://` and `keyvault://` prefixes no longer exist.

### Does mountainash-settings include Vault, SSM or Key Vault providers?

No. It includes no Vault, AWS SSM or Azure Key Vault clients, and no remote secret writer, caching, versioning or encryption. The `secrets` module provides local record storage only: `FilesystemBackend` (a hardened on-disk store), `MemorySecretStore` (for tests and short-lived use) and `NamespacedSecretStore`. Ordinary environment variables, configuration files and `secrets_dir` files need no store. If your secrets live in a cloud manager, write a `SecretReader` adapter for that service and pass it as `secret_store`.

### How do I supply a custom secret store?

Implement the `SecretReader` protocol: an object with a `get(key)` method that returns a record (a mapping of field names to JSON-compatible values) or `None` when the record does not exist. If the settings instance also needs to `persist()` values, implement `SecretWriter`, which adds `set`, `delete` and a `transaction(key)` context manager. There is no registration step and no prefix to choose. Pass the object as `secret_store` on SettingsParameters or the constructor, and every `secret:` reference in that request resolves through it, in both passes. The store can use any transport or authentication it needs.

### How are secrets handled in frozen models?

Pydantic does not allow assigning to a field of a frozen sub-model, so resolution cannot just overwrite a `SecretStr` field there. Instead, any nested model in which a reference resolved is rebuilt as a new validated instance, frozen or not. Models with no resolved reference are left as they were. This happens in the model pass, because that is where nested models are walked. The result keeps Pydantic's immutability guarantees while still resolving secrets transparently.

### How are secret references resolved in plain dictionaries and in model instances?

Both resolution steps use the bound store and the `secret:` prefix by default.

- For a plain dictionary (the keyword arguments pass), values are walked recursively. Any string beginning with the prefix is resolved through the store, and a new dictionary with the resolved values is returned.
- For a constructed Pydantic model (the model pass), fields are walked, including nested models, lists and dictionaries. Resolved values are assigned, and any nested model in which a reference resolved is rebuilt.

Resolution failures are raised without echoing secret values. You normally do not call these steps yourself, since construction runs them for you.

## Connection profiles

### What is a ProfileSpec and what does it define?

A ProfileSpec is a frozen dataclass that declares a connection profile. It defines the profile's identity (`name` and `provider_type`), its parameters (a list of ParameterSpec instances) and optional `metadata`. It holds no values. It describes the values a connection needs, with their types and defaults. Authentication is not part of the spec: credentials are ordinary parameters, typically with `secret=True`. When a Profile subclass has a class-body `__spec__`, the spec installs typed Pydantic fields on that class. A profile can instead be declared with native Pydantic fields, in which case the package generates the `__spec__`. `ProfileDescriptor` was removed in 0.1.0; use `ProfileSpec`.

### What is a ParameterSpec and what are its fields?

A ParameterSpec defines one parameter in a ProfileSpec. Its fields are:

- `name`: the uppercase settings-facing name.
- `type`: the Pydantic-compatible annotation.
- `tier`: `"core"` or `"advanced"`.
- `default`: a literal value, `MISSING` for a required field, or `FACTORY_DEFAULT` for fields that use a native default factory.
- `description`.
- `driver_key`: the output keyword name, either a string for all targets, a mapping per emission target, or `None` when a domain adapter handles emission.
- `secret`: wrap the value in `SecretStr`.
- `transform`: an optional callable applied when emitting kwargs.
- `validator`: an optional field-level validator.
- `template`: an optional template string that Profile evaluates in `post_init`.

### What is the MISSING sentinel and why is it needed?

MISSING marks a parameter as having no default, as opposed to a default of `None`. Since `None` is a valid default for optional parameters, it cannot also mean "required". When a ParameterSpec's default is MISSING, the parameter must come from configuration files, environment variables or kwargs, and validation fails with a clear error if it does not. In the generated Pydantic fields, MISSING defaults become required fields, while actual defaults (including `None`) become optional.

### How does a ProfileSpec become fields on a Profile class?

When a Profile subclass defines a class-body `__spec__`, the package adds one Pydantic field per ParameterSpec at class creation time. The field's type comes from the parameter type and its default from the parameter default (MISSING makes it required). `SecretStr` wrapping is applied when `secret` is set, and fields with a `template` are populated in `post_init`. You can instead declare a Profile with ordinary Pydantic annotations and `ProfileField` metadata, and the package generates the `__spec__` from those fields. The two forms are not combined on one class.

### What is a Profile?

Profile is the settings class for a connection profile. `DescriptorProfile` was removed in 0.1.0. It is a subclass of MountainAshBaseSettings, so it keeps multi-format file loading, template evaluation, secrets resolution and cached retrieval. You declare one either with a class-body `__spec__ = ProfileSpec(...)` or natively, with `name=` and `provider_type=` class headers and `ProfileField` fields. It exposes `profile_name` and `provider_type`. `emit(target, base=...)` produces driver keyword arguments by applying each parameter's `driver_key`, `transform` and any adapter registered for that target in `__adapters__`. Authentication models belong to the separate auth-client package, not to Profile.

### What are driver keys and transform functions?

A driver key maps a parameter name from the configuration side to the name a driver expects. For example, your configuration may call a parameter `DATABASE_HOST`, while the database driver expects a keyword argument `host`. Setting `driver_key="host"` on the ParameterSpec makes `emit()` output `host`. A transform is an optional callable applied to the value before it goes into the driver kwargs. It might turn a comma-separated string into a list, or a duration like "30s" into milliseconds.

### What does the secret parameter flag do?

`secret=True` on a ParameterSpec makes the generated field a `SecretStr`, so the value is masked in `repr` and string output. It also makes `emit()` unwrap the value with `get_secret_value()` at the kwargs boundary, so the emitted kwargs contain the plaintext value and should not be logged. The flag is about masking and emission only. It does not trigger reference resolution: a value beginning with `secret:` is resolved through the bound store whether or not the field is flagged. Using both gives a field that is resolved from a store and then held as a `SecretStr`.

## Authentication boundary

### Where did the authentication modes go?

Authentication models are no longer part of mountainash-settings. Since 0.1.0 the package has no AuthSpec base class, no discriminated auth union, no built-in auth modes (password, token, OAuth, IAM, Azure AD, Kerberos, certificate, service account or `NoneAuth`), no `auth_modes` on ProfileSpec and no `auth_to_driver_kwargs()`. None of these names has a compatibility shim. Auth models, mode selection and OAuth flows belong to the separate `mountainash-auth-client` package and the consuming application. Settings provides the generic pieces an auth layer plugs into: connection fields declared on a Profile, `secret:` reference resolution, and `Profile.emit(target, base=...)` with adapters registered in `__adapters__` that render credentials for a specific client. Chapter 8 covers the boundary.

## Caching and settings retrieval

### How does source-context reuse work?

The package keeps one captured source context for each structural key. It does not keep a cache of settings results. On the first request for a key, it captures the configured sources and resolves declared static secret references. Ordinary defaults and default factories are evaluated for each result. Later requests reuse the captured context, apply their own runtime inputs through the source order, and validate in full to produce a new settings object. No earlier result is reused.

### What is the get_settings function and how do I use it?

`get_settings` is the main entry point for getting settings. It takes a settings class and optional SettingsParameters, combines explicit arguments with the supplied parameters, and asks the process-wide SettingsManager for the matching source context. Use `settings = get_settings(settings_class=MyAppSettings)` for default parameters, or `settings = get_settings(settings_parameters=params)` for a prepared request. Each call applies its runtime inputs, runs the normal settings lifecycle and validation, and returns an isolated result.

### How do runtime inputs interact with source-context reuse?

Runtime keyword arguments apply to one call only. They are not applied to a cached settings instance, and they are left out of the structural key. Calls with the same source-defining parameters can therefore reuse the captured source context while each applies its own runtime values. The result is fully validated and returned as a fresh, detached settings object, so results are never shared between callers.

### What is the SettingsManager class?

SettingsManager is the process-wide owner of captured source contexts. It performs one capture per structural key, makes concurrent callers wait when a capture is in progress, and builds an isolated settings result for each request. It is not a registry of settings instances. It retains source snapshots and static defaults, never a result it has returned. `get_settings_manager()` returns the shared instance. The profile Registry is a separate, name-keyed facility.

### What is the structural context key and how is it computed?

The structural context key identifies the source data that may be captured and reused. It is built from the settings class, the normalised configuration-file list, the environment prefix, the secrets directory and the bound secret store. The store contributes by object identity, not by contents: the same store object reuses the capture, and a different one does not. Runtime keyword arguments are left out because they belong to a single call. Equivalent structural parameters share one capture, and each call still gets its own validated result.

## Registry and app settings

### What is the Registry class and how does it work?

Registry is a name-keyed store for profiles. Each entry pairs a ProfileSpec with its Profile class under the spec's name. You create one with a name, for example `Registry("databases")`, so a package can keep its own typed collection of profiles. It supports registration, lookup with `get_spec(name)` and `get_settings_class(name)`, membership tests, `len()` and access to the registered specs. Registering a second profile under an existing name raises an error. A Registry does not manage secret stores or settings instances. The SettingsManager and the bound `secret_store` handle those.

### How do I register a profile with the decorator?

Get a decorator from the registry with `register = registry.decorator()`, then apply `@register` to a Profile subclass that has a class-body `__spec__ = ProfileSpec(...)`. The spec and class are registered under the spec's name, and the class is returned unchanged. The decorator takes no name argument, because the name comes from the spec. It rejects classes that are not Profile subclasses or that lack a class-body ProfileSpec. The `@register(spec)` form was removed in 0.1.0. Chapter 7 covers registration.

### What happens if I register two profiles under the same name?

Registering a second profile under a name already present in a Registry raises `ValueError`. The message names the existing registration by module and class. This catches accidents such as two ProfileSpecs both named "postgres" in the same Registry, which would otherwise silently replace the first. Registries are independent, so the same name may appear in two different Registry instances. Other correctness rules for specs, such as the name matching the registry key and unique parameter names, are checked by the spec invariants.

### What are spec invariants and how do I run them?

Spec invariants are rules every registered ProfileSpec must satisfy:

- the spec name matches its registry key and is lowercase and non-empty;
- parameter names are unique and uppercase;
- driver keys do not collide within any one emission target;
- every tier is `"core"` or `"advanced"`;
- `provider_type` is not `None`.

There is no authentication invariant, because authentication is not part of the spec. `spec_invariants_for(registry)` returns a pytest class parameterized over every registered spec, so one line in a test module produces all the checks for a registry. Running them in CI catches definition errors early.

### What is the AppSettings class?

AppSettings is a subclass of MountainAshBaseSettings that supplies run-time defaults. Its fields are:

- `LOCALE_TIMEZONE`, default `"UTC"`;
- `DEBUG`, default `False`;
- `RUNDATE` (`YYYYMMDD`);
- `RUNTIME` (`HHMMSS`);
- `RUNDATETIME`, derived from the other two.

`RUNDATE` and `RUNTIME` are captured when an instance or source context is initialised, not when the module is imported. The class variable `RUN_TIMESTAMP_SCOPE` selects the lifetime. `"context"`, the default, captures one instant per source context for cached retrieval and a fresh instant per direct construction. `"process"` shares one lazily captured instant across the process. Subclasses add application-specific fields. Chapter 9 covers AppSettings.

### How do AppSettings templates work?

AppSettings has one built-in template, `RUNDATETIME_TEMPLATE`, held on `AppSettingsTemplates` and defaulting to `{RUNDATE}T{RUNTIME}`. During `post_init`, AppSettings formats `RUNDATETIME` from the effective `RUNDATE` and `RUNTIME`, so overriding either one changes the result. The usual template priority rules apply: if `RUNDATETIME` already has a value, it is kept unless `reinitialise=True`. You can supply a different template through `template_settings_parameters` on direct construction. `RUNDATE` and `RUNTIME` are default-factory fields, not templates.

### How does AppSettings work with get_settings?

AppSettings goes through `get_settings` and the same lifecycle as any other settings class. Call `get_settings(settings_class=AppSettings)` or `get_settings(settings_parameters=params)`. Its defaults and templates are resolved during `post_init`, and any secrets follow the normal resolution. A matching structural key may reuse its captured sources, but every call returns its own validated AppSettings object. Subclass AppSettings to add fields and keep its defaults.

## Advanced topics

### How do I subclass MountainAshBaseSettings for my application?

Define a class that inherits from MountainAshBaseSettings and declare fields with standard Pydantic annotations. Fields can use any type Pydantic supports, including nested models, enums and `SecretStr`. Use `model_config` for Pydantic behaviour such as validation settings. For the environment prefix, configuration files, secrets directory and secret store, prefer SettingsParameters or the constructor, since they also form the cache identity. A class-level `env_prefix` or `secrets_dir` in `model_config` is only a fallback when no selector is supplied. Compute derived values in `post_init()`. Use `get_settings` for source-context reuse with a fresh result on each call. For connection profiles, subclass Profile instead and declare a class-body ProfileSpec or native `ProfileField` fields.

### What happens when a configuration key appears in multiple sources?

The source priority decides which value wins. From highest to lowest: keyword arguments, environment variables, dotenv with the configured prefix, dotenv without a prefix, YAML files, TOML files, JSON files, Pydantic secret files, and field defaults. Priority across formats is fixed whatever the order of the file list. Caller order matters only within one format. Among files of one structured format, later mappings merge recursively into earlier ones, while later lists and scalars replace the earlier value. Lists are not concatenated or unioned. A base file plus an environment-specific overlay therefore overrides only the keys that differ, except that a list in the overlay replaces the whole list. Overriding `settings_customise_sources` can change the order.

### How do I debug configuration loading issues?

Check each stage in turn.

1. File selection. The list is normalised and duplicates are dropped. Missing files raise `FileNotFoundError` and unsupported extensions raise `ValueError`.
2. Source priority. Find out which source supplies the unexpected value. Environment variables are a common cause.
3. Templates. Confirm each `{FIELD_NAME}` reference is resolved after the field it depends on, since templates are applied in a single ordered pass.
4. Secrets. Confirm the reference starts with `secret:`, that the record key and field exist in the store (a simple reference needs a single-field record), and that a `secret_store` is bound on the request. A missing store raises `SecretCapabilityError`.

The SettingsParameters for the class shows which files and selectors are configured, and Pydantic's validation errors identify type mismatches and missing required fields.

### Can I use mountainash-settings without secrets resolution?

Yes. Secrets resolution acts only on values that begin with `secret:`. If no value uses that prefix, no store is needed and nothing is resolved. Environment variables, configuration files and `secrets_dir` files are ordinary Pydantic Settings inputs and need no store. File loading, templating, validation, source-context reuse and merging all work without secrets. The one case to avoid is a `secret:` value with no bound store, which raises `SecretCapabilityError` instead of passing through as text. This suits applications whose secrets arrive another way, such as environment variables injected by a container orchestrator.

### How do I test settings in a CI/CD environment?

Construct settings with keyword arguments, which have the highest priority and override file and environment values. Or use SettingsParameters to point at test-specific configuration files. Keyword arguments do not bypass secret handling: a kwarg value beginning with `secret:` is resolved in the first pass, before validation. For secrets, pass plain values directly, or supply a local store such as `MemorySecretStore` as `secret_store`. `spec_invariants_for(registry)` generates tests that verify the ProfileSpecs in a registry. Calls through `get_settings` already return isolated results, so you do not need to clear a cache between tests.

### How do SettingsParameters and MountainAshBaseSettings relate?

SettingsParameters describes how a settings object should be built, and MountainAshBaseSettings defines the typed fields of the result. SettingsParameters selects the sources to capture and the runtime inputs for a call. MountainAshBaseSettings holds the fields. `get_settings` connects them: it combines the parameters, finds or captures the source context, and returns a fully validated fresh instance. The structural fields select the source context, and runtime keyword arguments affect only the current call.
