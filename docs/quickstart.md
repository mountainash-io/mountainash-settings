# Getting started with mountainash-settings

Start with the [README quick start](../README.md#quick-start) to install the
current checkout and load application configuration. Then choose a route through
the [configuration recipes](../examples/). Each recipe contains its
own declarations, run command, expected result and explanation.

## Application settings

1. [Declare fields and validate inputs](../examples/basic_settings/).
2. [Load configuration files](../examples/configuration_files/), then
   [understand precedence and merging](../examples/source_precedence/).
3. [Derive a log path](../examples/templates/) from loaded values.

These examples use direct construction. Each call reads its sources afresh.

## Retrieval in a growing application

1. [Capture source snapshots](../examples/cached_sources/) and pass
   `SettingsParameters` to functions that retrieve settings when they run.
2. [Override one invocation](../examples/local_overrides/) without
   changing another caller's settings.
3. [Merge reusable parameter sets](../examples/parameter_merging/) or
   [request derived-value recomputation](../examples/recomputation/).

Each cached retrieval validates a fresh instance from pinned source inputs.
Initialize known configurations during startup when they should share stable
deployment inputs. See [cache lifecycle](advanced-usage.md#cache-contexts-and-runtime-materialization).

## Optional stores and profiles

- Use [namespaced records](../examples/namespaced_records/) and
  [secret references](../examples/secret_references/) when configuration
  refers to values in a selected store. Ordinary file/env inputs need no store.
- [Persist a local record explicitly](../examples/settings_persistence/)
  when the application needs to write configuration.
- Compare [handwritten connection mapping](../examples/driver_mapping/)
  with [native profile emission](../examples/profile_emission/).
  Choose [explicit specs](../examples/explicit_specs/) for data-driven field lists.
- Add [inspection, discovery or domain extensions](../examples/#profile-extensions)
  when a consumer needs them. A profile requires no registry to construct or emit.

## Relationship to Pydantic Settings

`MountainAshBaseSettings` extends `pydantic_settings.BaseSettings`. Pydantic owns
field types, constraints, validators, aliases and model introspection. Pydantic
Settings supplies the source primitives; MountainAsh composes them through
per-invocation selectors and adds its retrieval, template, record and profile APIs.

MountainAsh ignores unknown inputs, does not validate defaults by default, and
validates assignments. Upstream `BaseSettings` forbids extra inputs and validates
defaults by default. Set `model_config` deliberately when those differences matter.
Use `config_files`, `env_prefix` and `secrets_dir` for per-invocation source
selection; underscore-prefixed source controls such as `_env_file` are rejected.

Declaration and retrieval are independent: ordinary settings or profiles can
both be constructed directly or retrieved through the cache API. Profile
spec inspection, `model_fields` and class-level `model_json_schema()` work without
loading settings. JSON Schema generation supports validation and serialization
modes for fields supported by Pydantic. It omits the Python class-identity field
`SETTINGS_CLASS`; other bookkeeping fields remain included. This omission does
not change runtime field access or Python-mode dumps, or make arbitrary Python
types JSON-serializable.

## What's next

- [Advanced usage](advanced-usage.md): parameter merging, ownership and custom sources.
- [Profile reference](profile-spec-pattern.md): inheritance, typing and emission contracts.
- [Secrets reference](README_SECRETS.md): storage, reference syntax and lifecycle.
- [0.1 migration](migration-0.1.md): breaking changes from the earlier API.
- [Pydantic Settings documentation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/).
