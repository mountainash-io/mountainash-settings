# Frequently Asked Questions for Mountainash Settings

## Foundation and Base Settings

### What is mountainash-settings and what problem does it solve?

Mountainash-settings is a typed configuration framework for Python applications built on Pydantic v2. It solves the problem of managing application configuration across multiple sources (YAML, TOML, JSON, .env files, and environment variables) while providing type safety, validation, secrets resolution, and structural source-context reuse. Rather than scattering configuration loading logic throughout an application, mountainash-settings centralises it in a single validated model with support for derived values via field templates and reusable configuration profiles.

### How does MountainAshBaseSettings relate to Pydantic BaseSettings?

MountainAshBaseSettings is a subclass of Pydantic's BaseSettings that extends it with several framework-specific capabilities. It inherits Pydantic's environment variable loading, type coercion, and validation, then adds source customization for multi-format file loading (YAML, TOML, JSON and .env), a cache-safe source hook for cached retrieval, two-pass resolution of `secret:` references through an explicitly bound secret store, the `post_init` hook that subclasses override for template and derived-value work after references are resolved, the validate_assignment invariant that prevents silent mutation of validated fields, and integration with the SettingsParameters system for selecting files, environment prefix, secrets directory, secret store and runtime inputs. Developers subclass MountainAshBaseSettings rather than BaseSettings directly to gain these features. The class also configures a Settings Model Config (`extra="ignore"`, `validate_default=False`, `arbitrary_types_allowed=True`, `validate_assignment=True`).

### What configuration file formats does mountainash-settings support?

The framework supports four configuration file formats: YAML, TOML, JSON, and .env files. Multi-format file loading is handled by the FileHandler class, which uses file extension dispatch to route each file to the matching Pydantic source. You can mix formats freely in a single application. For example, you might use a YAML file for structured application settings, a TOML file for project metadata, a JSON file for machine-generated configuration, and a .env file for local development overrides. The Config Files Parameter on MountainAshBaseSettings accepts a list of file paths, and the file handler groups each path by extension and hands it to the matching Pydantic source, which reads it. Within one format, later files deep-merge over earlier ones.

### What is the Settings Model Config and how do I customise it?

Settings Model Config is the Pydantic `model_config` dictionary of MountainAshBaseSettings. It is a `SettingsConfigDict` with four defaults: `extra="ignore"` (config files may contain undeclared keys), `validate_default=False`, `arbitrary_types_allowed=True` (permits types such as UPath), and `validate_assignment=True` (assignments after construction are validated). A subclass adjusts these by declaring its own `model_config`, which Pydantic merges with the inherited one. Prefer the SettingsParameters selectors (or the matching constructor arguments) for the environment prefix, configuration-file list, secrets directory and secret store, because they also form the cache identity. A class-level `model_config` `env_prefix` or `secrets_dir` is used only as a fallback when no selector is supplied. Source order is controlled separately by the `settings_customise_sources` hook, and cached retrieval additionally uses `settings_capture_sources`. See chapter 2 for the details.

### What is the post_init lifecycle and when does it run?

The post_init lifecycle is a hook, `post_init()`, that runs at the end of construction, after Pydantic has loaded and validated the settings and after both secret-reference passes have completed. The base implementation is empty; subclasses override it for template expansion and other derived-value work. For example, AppSettings derives `RUNDATETIME` there, and Profile evaluates `ParameterSpec.template` fields there. Because `secret:` references are resolved before `post_init` runs, a template that references a field sees the resolved value. The base class does not expand templates on its own; templates are applied where a subclass calls `init_setting_from_template` or `format_template_from_settings`. The full construction order is listed in chapter 2.

### What is the validate_assignment invariant and why does it matter?

The validate_assignment invariant ensures that any field assignment on a settings instance after initial construction is still subject to Pydantic's full validation pipeline. Without this, you could accidentally assign an invalid value to a typed field and bypass all the type checking and validation that Pydantic provides at construction time. Mountainash-settings enables this by default through the Settings Model Config. The related Object Setattr Bypass mechanism provides a controlled escape hatch for internal framework code that needs to set fields without triggering validation, and it is used only for the framework's `SETTINGS_*` bookkeeping fields. Template derivation and secret resolution both assign through the validated path.

### How does source customization and source priority work?

Source customization controls which configuration sources are consulted and in what order. The default chain, from highest to lowest priority, is: keyword arguments passed to the constructor, environment variables, the dotenv file read with the configured environment prefix, the same dotenv files read without a prefix, YAML files, TOML files, JSON files, Pydantic secret files, and field defaults. An environment variable therefore overrides a YAML value, and an explicit keyword argument overrides everything. Overriding `settings_customise_sources` changes the order for direct construction. Cached retrieval through `get_settings` does not call that hook: a class that overrides it must also override `settings_capture_sources`, and custom sources must extend `CacheableSettingsSource`, or cached retrieval raises `ValueError`. The environment prefix, supplied through SettingsParameters, namespaces environment variables so that settings classes in one process do not collide.

### What is multi-format file loading and how does file extension dispatch work?

Multi-format file loading is the capability to load configuration from YAML, TOML, JSON, and .env files within a single settings class. When you specify a list of config files via the Config Files Parameter, the FileHandler class processes each file by examining its extension. File extension dispatch routes .yaml and .yml files to the YAML parser, .toml files to the TOML parser, .json files to the JSON parser, and .env files to the dotenv parser. Categorization groups the paths into env, YAML, TOML and JSON buckets for the matching Pydantic sources. This design means you never need to specify which parser to use; the framework infers it from the filename.

## Settings Parameters and Merge Strategies

### What is the SettingsParameters class and what does it do?

SettingsParameters is a companion class that describes how a settings result is materialized and merged. Its structural fields identify the private source context to capture: the settings class, file list, environment prefix, secrets directory and secret store (selected by object identity). Its runtime keyword arguments are inputs for one invocation. The manager captures the structural sources once, then each request projects its runtime inputs and validates a fresh result. SettingsParameters provides the Parameter Create Factory for construction, a `merge()` operation for combining parameter sets, and uses the KwargsHandler to normalise keyword arguments before they reach the settings constructor.

### What is the difference between structural fields and runtime fields?

Structural fields identify the source context: the settings class, configuration-file list, environment prefix, secrets directory and secret store. The secret store is compared and hashed by object identity, never by content, so two different store objects never share a captured context. Requests with the same structural fields share the captured source context, not a settings object. Runtime fields are the current call's keyword arguments; they do not change the structural key and are projected during that call's materialization. The Custom Hash And Eq implementation covers the structural fields so that source capture can be reused while every retrieval still returns a newly validated, isolated result.

### How do merge strategies work for combining configuration from multiple sources?

Merging happens at two levels. When two SettingsParameters are combined with `merge()`, the `config_files` lists are joined in base-then-other order with duplicates removed at their first position (Ordered File List Merge); scalar selectors (`env_prefix`, `secrets_dir`) take the other value, or the base value with `prioritise_base=True` (Scalar Last Wins Strategy), and `secret_store` takes the other store when it is not `None`; `kwargs` are merged shallowly, with the other side overwriting duplicate keys and nested values replaced rather than merged. Separately, when several structured files of one format are loaded as sources, they are read in caller order: later mappings merge recursively into earlier ones, while later lists and scalars replace earlier values. Lists are not concatenated. Chapter 3 documents the parameter merge and chapter 2 the source merge.

### What is the FileHandler class?

The file handler is implemented by `SettingsFileHandler`. It normalises configuration-file inputs (a string, UPath, sequence of paths, or `None`) into an ordered tuple with duplicates removed in first-seen order, identifies each file's type from its extension (an unknown extension raises `ValueError`), can check that files exist, and groups the files into the immutable `SettingsFiles` structure with separate env, YAML, TOML and JSON tuples. It does not parse file contents: the grouped paths are handed to the Pydantic YAML, TOML, JSON and dotenv sources, which read the files, and merge behaviour is documented separately. MountainAshBaseSettings uses it internally during construction, so application code rarely calls it directly, but it is useful when debugging which files were selected and in what order.

### What does the KwargsHandler do?

The `SettingsKwargsHandler` class normalises keyword arguments before they are passed to the settings constructor. It accepts a mapping or an iterable of key/value pairs (or `None`), returns a fresh dictionary, and unwraps a nested `kwargs` mapping when one is present. It can also return the items as a tuple in deterministic key order, and `merge_kwargs` combines two inputs with the second taking precedence. Malformed input raises a `TypeError`. It does not convert value types or check keys against the model's fields; type coercion and field validation are performed by Pydantic when the model is constructed.

## Field Templating

### What is the {FIELD_NAME} template syntax and how does it work?

The {FIELD_NAME} template syntax allows you to define field values that are derived from other fields on the same settings model. A template is a string containing {ANOTHER_FIELD} placeholders; when it is applied, each placeholder is replaced with the current value of the referenced field. Field values are not expanded automatically: a template applies only where a subclass calls `init_setting_from_template` in `post_init` (for example `self.ENDPOINT = self.init_setting_from_template("{BASE_URL}/v1/data", self.ENDPOINT)`) or where a Profile declares `ProfileField(template="{BASE_URL}/v1/data")`. With BASE_URL set to "https://api.example.com", ENDPOINT then resolves to "https://api.example.com/v1/data". Template resolution happens during the post_init lifecycle, after Pydantic has validated all fields but before the instance is returned. This means all source values (files, environment variables, kwargs) have already been merged and validated before templates are expanded.

### What are template priority rules?

Template priority rules govern when a template is evaluated and when an explicit value is kept. For the low-level `init_setting_from_template()` helper, a non-`None` current value is kept unless `reinitialise=True`; otherwise the template is evaluated. `Profile` uses a stricter, origin-aware rule that never compares values: on initial construction every template field not explicitly supplied to that call is derived, and on `reinitialise=True` only fields previously recorded as template-derived are re-derived, excluding any supplied to that call through the cache route. An explicit value from keyword arguments, environment variables or files is therefore not overwritten by a template. A direct call to `post_init(reinitialise=True)` on a hand-built instance has no per-call override protection. Chapter 4 describes the rules in full.

### How does nested template resolution work?

Templates can reference fields that are themselves template-derived, but resolution is a single ordered pass using ordinary `str.format()`. There is no recursive expansion and no cycle detection. A subclass resolves templates in its `post_init()` in declaration order, so a field that references another derived field must be resolved after it. A template that references a field not yet resolved reads that field's current value at that moment: a mutually referencing pair resolves with `None` in the text rather than raising an error. See chapter 4 for an example.

### What is UPath path derivation?

Templates produce strings. UPath support applies to `config_files` paths (normalisation, existence checks against the named filesystem). To get a UPath field from a template, convert explicitly in `post_init` (`UPath(self.format_template_from_settings(...))`).

## Secrets Resolution

### What is the two-pass secrets resolution pipeline?

The two-pass pipeline resolves `secret:` references wherever they enter the settings. In the first pass (kwargs pass resolution), the framework resolves references in the keyword arguments before `BaseSettings.__init__` runs. In the second pass (model tree pass resolution), after the sources (files, environment, secrets directory) have been loaded and validated, the framework walks the constructed model and resolves references in the loaded values, including nested models, lists and dictionaries. Two passes are needed because file- and environment-sourced values only exist once the base constructor has run. Both passes resolve through the secret store bound on the request (`secret_store`); a reference with no bound store raises `SecretCapabilityError`. Both complete before `post_init` runs.

### How are secret stores selected now that the secrets registry is gone?

Secrets are resolved through a store that the caller selects explicitly. The secrets registry and provider lookup were removed in 0.1.0 (`register_secrets_backend`, `get_secrets_backend` and the `secrets_provider` parameter have no replacement shims). A store is any object that satisfies the `SecretReader` protocol (`get(key)` returning a record or `None`); `SecretWriter` adds `set`, `delete` and `transaction`, and `ClearableSecretStore` adds `is_cleared`. The package supplies local stores: `FilesystemBackend`, `MemorySecretStore` and the borrowed-prefix view `NamespacedSecretStore`. The store is passed as `secret_store` on SettingsParameters (or the constructor keyword), is never registered under a name, and participates in cache identity by object identity. See chapter 5.

### What is the secret prefix syntax?

The secret prefix is `secret:`. A configuration value that begins with it is resolved from the bound record store. A dotted reference such as `secret:live_db.postgres.password` splits at the last dot into the record key (`live_db.postgres`) and the field (`password`). A simple reference such as `secret:api_token` requires the record to hold exactly one field and returns that field's value. A missing record or field raises `KeyError`, and a reference with no bound store raises `SecretCapabilityError`; the reference is never left in place as literal text. The earlier `vault://`, `ssm://` and `keyvault://` prefixes no longer exist.

### Does mountainash-settings include Vault, SSM or Key Vault providers?

No. mountainash-settings does not include Vault, AWS SSM or Azure Key Vault clients, and it provides no remote secret writer, caching, versioning or encryption. The `secrets` module supplies local record storage only: `FilesystemBackend` (a hardened on-disk store), `MemorySecretStore` (for tests and ephemeral use) and `NamespacedSecretStore` (a prefix view over another store). Ordinary environment variables, configuration files and `secrets_dir` files need no store. An application that keeps secrets in a cloud manager supplies its own `SecretReader` adapter for that service and passes it as `secret_store`.

### How do I supply a custom secret store?

Implement the `SecretReader` protocol: an object with a `get(key)` method that returns a record (a mapping of field names to JSON-compatible values) or `None` when the record does not exist. If the settings instance also needs to `persist()` values, implement `SecretWriter`, which adds `set`, `delete` and a `transaction(key)` context manager. There is no registration step and no prefix to choose: pass the object as `secret_store` on SettingsParameters (or the constructor keyword) and every `secret:` reference in that request resolves through it, in both passes of the pipeline. The store may use any transport or authentication it needs.

### What is the frozen model rebuild on resolve?

Frozen model rebuild on resolve addresses a challenge with Pydantic's immutability model. When a settings model contains SecretStr fields within frozen (immutable) sub-models, the secrets resolution pipeline cannot simply assign new values to those fields. Instead, the framework rebuilds the frozen sub-model with the resolved secret values, effectively creating a new instance with the secrets populated. This ensures that Pydantic's immutability guarantees are maintained while still allowing transparent secrets resolution. The rebuild happens during the model tree pass resolution, the second pass of the two-pass pipeline, because that is when the framework walks nested models. Any nested model in which a reference resolved is rebuilt as a new validated instance, frozen or not; unchanged models keep their identity.

### What do resolve_references_in_dict and resolve_references_in_model_tree do?

These are the two core functions behind the two-pass pipeline; both take the bound store as an argument and use the `secret:` prefix by default. `resolve_references_in_dict(data, store)` operates on a plain dictionary (the kwargs pass): it recursively walks the values, resolves any string beginning with the prefix through the store, and returns a new dictionary with the resolved values. `resolve_references_in_model_tree(instance, store)` operates on a constructed Pydantic model (the model tree pass): it walks the model's fields, including nested models, lists and dictionaries, and assigns resolved values, rebuilding any nested model in which a reference resolved. Resolution failures are raised without echoing secret values.

## Connection Profiles

### What is a ProfileSpec and what does it define?

A ProfileSpec is a frozen dataclass that declares a connection profile. It defines the profile's identity (`name` and `provider_type`), its parameters (a list of ParameterSpec instances), and optional `metadata`. It holds no configuration values; it describes the values a connection needs, with their types and defaults. Authentication is not part of the spec: credentials are ordinary parameters, typically with `secret=True`. When a Profile subclass carries a class-body `__spec__`, the framework uses the spec to install typed Pydantic fields on that class. A profile can alternatively be declared with native Pydantic fields, in which case the package generates the `__spec__`. `ProfileDescriptor` was removed in 0.1.0; use `ProfileSpec`.

### What is a ParameterSpec and what are its fields?

A ParameterSpec defines a single parameter within a ProfileSpec. Its fields are: `name` (the uppercase settings-facing name, see the parameter name convention), `type` (the Pydantic-compatible annotation), `tier` (either `"core"` or `"advanced"`), `default` (a literal value, the MISSING sentinel for a required field, or `FACTORY_DEFAULT` for generated fields that use a native default factory), `description`, `driver_key` (the output keyword name, either a string for all targets, a mapping per emission target, or `None` when a domain adapter handles emission), `secret` (wrap the value in SecretStr), `transform` (an optional callable applied when emitting kwargs), `validator` (an optional field-level validator), and `template` (an optional template string that Profile evaluates in `post_init`). ParameterSpec is the building block that makes profiles composable and reusable.

### What is the MISSING sentinel and why is it needed?

The MISSING sentinel is a special marker value that distinguishes "no default was provided" from "the default is None." In Python, None is a valid default value for optional parameters, so using None to mean "required" would be ambiguous. The MISSING sentinel resolves this by providing an unambiguous marker. When a ParameterSpec has its default value set to MISSING, the framework knows that the parameter is required and must be provided by the user through configuration files, environment variables, or kwargs. If the parameter is not provided, validation fails with a clear error message. MISSING integrates with the dynamic field installation system: fields with MISSING defaults become required Pydantic fields, while fields with actual defaults (including None) become optional.

### How does dynamic field installation work?

Dynamic field installation is the process by which an authored ProfileSpec's ParameterSpec list becomes Pydantic fields on a Profile class at class creation time. When a Profile subclass defines a class-body `__spec__`, the framework iterates over its ParameterSpec entries and adds a field for each one. The field's type comes from the parameter type, its default from the parameter default (a MISSING default makes the field required), SecretStr wrapping is applied when `secret` is set, and fields with a `template` are populated in `post_init`. Alternatively, a Profile can be declared with ordinary Pydantic annotations and `ProfileField` metadata, in which case the package generates the `__spec__` from the declared fields. The two forms are not combined on one class.

### What is a Profile?

Profile is the settings class for a connection profile; `DescriptorProfile` was removed in 0.1.0. It is a subclass of MountainAshBaseSettings, so it keeps multi-format file loading, template evaluation, secrets resolution and cached retrieval. A Profile is declared either with a class-body `__spec__ = ProfileSpec(...)` or natively, with `name=` and `provider_type=` class headers and `ProfileField` fields. It exposes `profile_name` and `provider_type`, and `emit(target, base=...)` produces driver keyword arguments by applying each parameter's `driver_key`, `transform` and any adapter registered for that target in `__adapters__`. Authentication models are not part of Profile; they belong to the separate auth-client package.

### What are driver key mapping and transform functions?

Driver key mapping translates parameter names from the configuration domain to the driver domain. For example, your configuration might use the name "DATABASE_HOST" (following the parameter name convention), but the actual database driver expects the keyword argument "host". The driver key mapping on the ParameterSpec tells the framework to output "host" when generating driver kwargs. The transform function is an optional callable that transforms a parameter value before it is included in the driver kwargs. For example, a transform function might convert a comma-separated string into a list, or convert a human-readable duration like "30s" into an integer of milliseconds. Together, these features bridge the gap between user-friendly configuration and driver-specific API expectations.

### What is the secret parameter flag?

The secret parameter flag is a boolean attribute on ParameterSpec (`secret=True`). It makes the generated field a SecretStr, so the value is masked in `repr` and string output, and it causes `emit()` to unwrap the value with `get_secret_value()` at the kwargs boundary. The emitted kwargs therefore contain the plaintext value and should not be logged. The flag concerns masking and emission only; it is not what triggers reference resolution. A value beginning with `secret:` is resolved through the bound secret store whether or not the field is flagged. Combining the two gives a field that is resolved from a store and then held as a SecretStr.

## Authentication Boundary

### Where did the authentication modes go?

Authentication models are no longer part of mountainash-settings. Since 0.1.0 the package bundles no AuthSpec base class, discriminated auth union, built-in auth modes (password, token, OAuth, IAM, Azure AD, Kerberos, certificate, service account or `NoneAuth`), `auth_modes` on ProfileSpec, or `auth_to_driver_kwargs()`; none of these names have compatibility shims. Auth models, mode selection and OAuth flows belong to the separate `mountainash-auth-client` package and the consuming application. Settings supplies the generic pieces an auth layer plugs into: connection fields declared on a Profile, `secret:` reference resolution, and `Profile.emit(target, base=...)` with adapters registered in `__adapters__` that render credentials for a specific client. See chapter 8 (Authentication Boundary).

## Caching and Settings Retrieval

### How does settings source-context reuse work?

The framework retains one private structural source context for each structural key rather than an LRU cache of settings results. On the first request for a key, it captures the configured sources and resolves declared static secret references. Ordinary defaults and default factories remain per-materialization behavior. Later requests reuse that captured context, project their current runtime inputs through the source order, and perform full validation to materialize a new settings object. No previously returned object is reused, and no second result cache or copy-on-override layer is involved.

### What is the get_settings function and how do I use it?

The get_settings function is the primary entry point for materializing settings. It accepts a settings class and optional SettingsParameters, combines explicit arguments with the supplied parameters, and asks the process-wide SettingsManager for the matching structural source context. Typical usage is settings = get_settings(settings_class=MyAppSettings) for default parameters or settings = get_settings(settings_parameters=params) for a prepared request. Each call applies its current runtime inputs, runs the normal settings lifecycle and validation, and returns an isolated result.

### How do runtime inputs work with source-context reuse?

Runtime keyword arguments are inputs to one materialization; they are not applied to a cached settings instance. They are excluded from the structural key, so calls with the same source-defining parameters can reuse the captured source context while still projecting the current runtime values. The resulting candidate is fully validated and returned as a fresh, detached settings object. This avoids shared result identity, shallow model copies, and a separate runtime-overlay cache.

### What is the SettingsManager class?

SettingsManager is the sole process-wide owner of private structural source contexts. It coordinates one capture per structural key, makes concurrent callers wait for an in-progress capture when necessary, and materializes an isolated settings result for each request. It is not a named registry or dictionary of settings instances: it retains source snapshots and static defaults, never a previously returned result. The profile Registry remains a separate name-keyed facility.

### What is the structural context key and how is it computed?

The structural context key identifies the source data that may be captured and reused. It is derived from the settings class, normalized configuration-file list, environment prefix, secrets directory, and the bound secret store. The secret store contributes by object identity, not by contents: the same store object reuses the capture, and a different store object does not. Runtime keyword arguments are deliberately absent because they belong to a single materialization, not to the source context. Equivalent structural parameters therefore use the same private capture, while their calls still receive independently validated results.

## Registry and App Settings

### What is the Registry class and how does it work?

The Registry class is a generic name-keyed store for profiles. Each entry pairs a ProfileSpec with its Profile class under the spec's name. It provides registration, lookup (`get_spec(name)` and `get_settings_class(name)`), membership tests, `len()`, and access to the registered specs. It enforces duplicate prevention, raising an error if two profiles are registered under the same name. A Registry is created with a name, for example `Registry("databases")`, so a package can keep its own typed collection of profiles. It does not manage secret stores or settings instances; the SettingsManager and the bound `secret_store` cover those separately.

### How does the @decorator registration pattern work?

The decorator registration pattern registers a Profile class when the class is defined. A registry produces a bare decorator with `register = registry.decorator()`. Applied as `@register` to a Profile subclass that has a class-body `__spec__ = ProfileSpec(...)`, it registers that spec and class under the spec's name and returns the class unchanged. The decorator takes no name argument, because the name comes from the spec. It rejects classes that are not Profile subclasses or that lack a class-body ProfileSpec. The `@register(spec)` form was removed in 0.1.0. See chapter 7.

### What is duplicate prevention in the Registry?

Duplicate prevention is a safety mechanism that raises `ValueError` when you attempt to register a second profile under a name already present in a Registry. The message names the existing registration by module and class. It catches accidental cases such as two ProfileSpecs both named "postgres" in the same Registry, which would otherwise silently replace the first. Registries are independent, so the same name may appear in two different Registry instances. Related correctness rules for specs (name matches registry key, unique parameter names and so on) are checked by the spec invariants that the invariant test generator produces.

### What are spec invariants and the invariant test generator?

Spec invariants are rules that every registered ProfileSpec must satisfy. They check that the spec name matches its registry key and is lowercase and non-empty, that parameter names are unique and uppercase, that driver keys do not collide within any one emission target, that every tier is `"core"` or `"advanced"`, and that `provider_type` is not `None`. There is no authentication invariant, because authentication is not part of the spec. The invariant test generator, `spec_invariants_for(registry)`, returns a pytest class parameterized over every registered spec, so one line in a test module produces all the checks for a registry. Running them in CI catches definition errors before they reach production.

### What is the AppSettings class?

AppSettings is a convenience subclass of MountainAshBaseSettings that supplies run-time defaults. Its fields are `LOCALE_TIMEZONE` (default "UTC"), `DEBUG` (default `False`), `RUNDATE` (`YYYYMMDD`), `RUNTIME` (`HHMMSS`) and `RUNDATETIME`, which is derived from the other two. `RUNDATE` and `RUNTIME` are captured when an instance or structural context is initialized, not when the module is imported. The class variable `RUN_TIMESTAMP_SCOPE` selects the lifetime: `"context"` (the default) captures one instant per structural context for cached retrieval and a fresh instant per direct construction, while `"process"` shares one lazily captured instant across the process. Subclasses add application-specific fields. See chapter 9.

### How do app settings templates work?

AppSettings has one built-in template, held on `AppSettingsTemplates`: `RUNDATETIME_TEMPLATE`, which defaults to `{RUNDATE}T{RUNTIME}`. During `post_init`, AppSettings formats `RUNDATETIME` from the effective `RUNDATE` and `RUNTIME` values, so overriding either component changes the result. The ordinary template priority rules apply: if `RUNDATETIME` already has a value it is kept unless `reinitialise=True`. A different template can be supplied through `template_settings_parameters` on direct construction. `RUNDATE` and `RUNTIME` themselves are default-factory fields rather than templates.

### How does AppSettings integrate with get_settings?

AppSettings uses get_settings and the same full settings lifecycle as any other supported settings class. You call get_settings(settings_class=AppSettings) or get_settings(settings_parameters=params); its defaults and templates are resolved during post_init and any secrets follow the normal resolution pipeline. A matching structural key may reuse its captured sources, but each invocation materializes and returns its own validated AppSettings object. You can subclass AppSettings to add application-specific fields while retaining its convenience defaults.

## Advanced Topics

### How do I subclass MountainAshBaseSettings for my application?

To create custom application settings, define a class that inherits from MountainAshBaseSettings and declare fields using standard Pydantic type annotations. Use `model_config` to adjust Pydantic behaviour such as validation settings; prefer SettingsParameters or the constructor for the environment prefix, configuration files, secrets directory and secret store, since they also form the cache identity; a class-level `model_config` `env_prefix` or `secrets_dir` is only a fallback when no selector is supplied. Fields can use any Pydantic-supported type, including nested models, enums, and SecretStr, and a subclass can compute derived values in `post_init()`. Use get_settings when you want structural source-context reuse with a fresh materialized result for each call. For connection profiles, subclass Profile instead, declaring a class-body `ProfileSpec` or native `ProfileField` fields. The framework handles file loading, environment binding, secrets resolution, and validation automatically.

### What happens when a configuration key appears in multiple sources?

When the same key appears in multiple sources, the source priority decides which value wins. From highest to lowest: init values (keyword arguments), environment variables, dotenv with the configured prefix, dotenv without a prefix, YAML files, TOML files, JSON files, Pydantic secret files, and field defaults. Cross-format priority is fixed regardless of the order of the file list; caller order applies only within one format. Among files of one structured format, later mappings merge recursively into earlier ones, while later lists and scalars replace the earlier value. Lists are not concatenated or unioned. A base file with shared defaults plus an environment-specific overlay file therefore overrides only the keys that differ, except that a list in the overlay replaces the whole list. Source customization can change the order.

### How do I debug configuration loading issues?

When configuration does not load as expected, check each stage of the pipeline. First, verify file selection: the file handler normalises the list, drops duplicates, raises `FileNotFoundError` for missing files and `ValueError` for unsupported extensions. Second, check source priority by establishing which source provides the unexpected value (environment variables are a common culprit). Third, inspect template resolution by confirming that each `{FIELD_NAME}` reference is resolved after the field it depends on, since templates are applied in a single ordered pass. Fourth, check secret resolution: confirm the reference starts with `secret:`, that the record key and field exist in the store (a simple reference needs a single-field record), and that a `secret_store` is bound on the request; a missing store raises `SecretCapabilityError`. The SettingsParameters for the class shows which files and selectors are configured, and Pydantic's validation errors identify type mismatches and missing required fields.

### Can I use mountainash-settings without secrets resolution?

Yes. Secrets resolution only acts on values that begin with `secret:`. If no configuration value uses that prefix, no secret store is required and nothing is resolved. Environment variables, configuration files and `secrets_dir` files are ordinary Pydantic Settings inputs and need no store. The other features (multi-format file loading, field templating, type validation, source-context reuse, merging) work independently of secrets. The one failure to avoid is a `secret:` value with no bound store, which raises `SecretCapabilityError` rather than passing through as text. This makes the package usable for applications whose secrets arrive through other means, such as environment variables injected by a container orchestrator.

### How do I test settings in a CI/CD environment?

For CI/CD testing, construct settings with keyword arguments, which have the highest source priority and override file and environment values. Alternatively, use SettingsParameters to point at test-specific configuration files. Keyword arguments do not bypass secret handling: a kwarg value beginning with `secret:` is resolved in the first pass, before validation. For secrets, either pass plain values directly or supply a local store such as `MemorySecretStore` as `secret_store`. The `spec_invariants_for(registry)` generator produces tests that verify the ProfileSpecs in a registry. Calls through get_settings already materialize isolated results, so instance isolation does not require clearing a result cache.

### What is the relationship between SettingsParameters and MountainAshBaseSettings?

SettingsParameters describes how MountainAshBaseSettings should be materialized, while MountainAshBaseSettings defines the typed fields in the result. Think of SettingsParameters as the "how"—which sources to capture and which runtime inputs apply to this call—and MountainAshBaseSettings as the "what." The get_settings function bridges them by combining parameters, locating or capturing the structural source context, and returning a fully validated fresh instance. The structural fields select that source context; runtime keyword arguments affect only the current materialization. This keeps source capture reusable without making results shared state.
