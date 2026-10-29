# Profiles: declaration, emission and extension

`Profile` extends `MountainAshBaseSettings` with a shared mapping from settings
fields to driver arguments. It retains the same sources, templates, selected
stores and direct/cached retrieval paths as an ordinary settings class.

## When to use each approach

| Need | Start with |
|---|---|
| Application fields or a short explicit driver mapping | [Ordinary settings](../examples/driver_mapping/) |
| Visible typed fields with reusable emission conventions | [Native profile fields](../examples/profile_emission/) |
| Field lists assembled as data | [Explicit specs](../examples/explicit_specs/) |
| Metadata inspection without loading values | [Spec inspection](../examples/spec_inspection/) |
| Caller selection by name | [Optional registry](../examples/registry_discovery/) |
| Domain-specific declaration metadata | [Typed spec subclass](../examples/domain_metadata/) |
| Several driver/client argument shapes | [Target mappings and adapters](../examples/target_adapters/) |

Ordinary Pydantic classes already support inheritance, aliases, validators, custom
metadata and `model_fields` inspection. Profiles give these consumers a common
spec and emission convention. A registry is an optional discovery layer.

## Native field declarations

Declare annotated fields on `Profile`, with concrete `name` and `provider_type`
class headers. `ProfileField(...)` combines Pydantic field arguments with:

| Option | Meaning |
|---|---|
| `driver_key` | Output name, target-to-name mapping, or explicit `None` to exclude |
| `tier` | `"core"` or `"advanced"` classification |
| `transform` | Callable applied to an emitted value |
| `template` | Brace template used to derive the field after inputs load |

Lowercase output mapping is opt-in through `driver_keys="lower"`. An omitted
mapping follows that convention; explicit names and exclusions take precedence.
Use `SecretStr` annotations and native Pydantic validators for generated fields.
Aliases, constraints, factories and decorator validators retain Pydantic semantics.

The completed class publishes a generated `__spec__`. Its fields remain native
Pydantic fields; the generated spec describes them for profile consumers.

## Explicit specs

An authored `ProfileSpec` assigned to a class's own `__spec__` installs its fields.
Each `ParameterSpec` supplies the field's name, type and tier, plus optional
default, description, mapping, secret, validator, transform and template settings.
The [explicit-spec recipe](../examples/explicit_specs/) emits the same
database arguments as the native declaration.

Do not combine an own `__spec__` with generated-mode headers on one class.
Generated specs cannot fully reconstruct aliases, factories or decorator
validators and must not be fed back into the explicit-spec installer.

## Inheritance and completion

Generated application field names must be uppercase. Untouched inherited fields
retain metadata; redeclaring a field follows Pydantic's replacement rules.
For example, `PORT: int = 6432` replaces prior constraints and field options.
Repeat any constraints and `ProfileField` options that should remain. Pydantic
rejects unannotated `PORT = 6432` overrides.

Concrete generated subclasses declare their own lowercase `name` and non-None
`provider_type`. A class declaring neither is intermediate. Intermediate and
unresolved classes expose their own `__spec__ = None` and cannot construct or
register. Resolve forward references with a successful `model_rebuild()` before
use; `defer_build=True` also requires an explicit successful rebuild.
A no-change rebuild preserves completed spec identity. Dynamic declaration
mutation is unsupported.

One profile ancestry chain plus ordinary behavior mixins is supported; competing
profile bases are rejected. A generated child can extend an explicit-spec parent:
untouched installed fields retain mappings and exclusions, while additional body
fields enter the generated spec. Under `driver_keys="lower"` those additions emit
unless excluded explicitly.

## Inspection and typing

Inspect `__spec__.parameters` for domain field metadata and output mappings,
without constructing a settings instance. The spec is a frozen dataclass, but
its parameter list and metadata dictionary remain mutable; treat declarations
as fixed.

- `default is MISSING` means required.
- `default is FACTORY_DEFAULT` means a native factory exists on the owning field.
  Projection does not evaluate factories. Inspect `model_fields` for the factory.
- Annotated attributes retain static types. Pinned mypy 1.10.1 does not catch
  every missing required `ProfileField` constructor argument or invalid class
  header; runtime validation remains authoritative.
- Both declaration styles support class-level `model_json_schema()` in validation
  and serialization modes for fields supported by Pydantic. The schema omits
  `SETTINGS_CLASS`, which holds a Python class object; other bookkeeping fields
  remain included. Runtime class identity, Python-mode dumps and parameter
  extraction are unchanged. Arbitrary application types still need Pydantic schema
  support; this is not a serializer for runtime class objects.

## Domain metadata

Domains can select a `ProfileSpec` dataclass subtype with `spec_type=` and supply
its typed metadata in class headers. Validation is strict: coercible but wrongly
typed values and unknown options fail at declaration time. Metadata inherits by
key; supplied dictionaries replace inherited dictionaries. Metadata does not
automatically set the defaults of application fields.

Put Pydantic settings options in `model_config`. The
[domain recipe](../examples/domain_metadata/) keeps header metadata
and field defaults explicit.

## Extending emission

`emit()` maps fields, skips excluded fields and `None` values, unwraps `SecretStr`,
and applies output transforms. It returns driver kwargs; the application owns
connections and their lifetime. Emission may expose credentials, so do not log
the resulting dictionary.

A string `driver_key` applies to every target; a dictionary scopes names per
target. Targets can be any hashable value. Small local examples use strings;
shared domain libraries can define their own enums or other namespaced identifiers.

Declare plural `__adapters__ = {target: callable}` on the profile. An adapter
receives `(profile, merged_kwargs)` and returns the final dictionary. Emitted
field values override same-named `base` values before the adapter runs.
Only a shallow copy of `base` is taken, so adapters must copy nested containers
before modifying them. See the [runnable adapter recipe](../examples/target_adapters/).

Profiles with target-scoped mappings or adapters require `emit(target)` and reject
unknown targets. No target is needed for a profile with only bare mappings and
no adapters.

`ProfileField(template=...)` derives values after loading. With cached retrieval,
`reinitialise=True` recomputes eligible derived values from current invocation
inputs while preserving explicit values. It does not reload sources. See
[recomputation](../examples/recomputation/).

## Registration and invariant checks

Use `Registry.register(spec, cls)` to register a completed class, or obtain
`register = registry.decorator()` and use bare `@register` on its declaration.
Register a name only once. Generated classes register their own published spec.
Registry lookup selects a class, not an instance or a settings cache.

`spec_invariants_for(registry)` creates pytest checks for registrations present
when called. See [the executable invariant module](../examples/invariant_checks/).
Keep separate tests for compatibility with the actual driver.

## Authentication

Authentication models and OAuth flows belong to
[mountainash-auth-client](https://github.com/mountainash-io/mountainash-auth-client).
Settings provides profiles and selected local stores; it no longer bundles auth
models, auth unions or `auth_to_driver_kwargs()`. See the [0.1 migration guide](migration-0.1.md).
