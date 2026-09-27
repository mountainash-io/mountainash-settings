# Migrating to 0.1.0

0.1.0 starts the SemVer API. Removed names have no aliases or warning shims.

| Removed surface | Replacement |
|---|---|
| `profiles.descriptor`, `ProfileDescriptor` | `profiles.spec`, `ProfileSpec` |
| `DescriptorProfile` | `Profile` |
| `_Missing` | `Missing` (or the `MISSING` singleton) |
| `descriptor_invariants_for` | `spec_invariants_for` |
| `__descriptor__` | Class-body `__spec__` |
| `profile.backend` | `profile.profile_name` |
| `registry.descriptors`, `get_descriptor(name)` | `registry.specs`, `get_spec(name)` |
| `ConfigFileType`, `ConfigFileList` in `filehandler` | `ConfigPath`, `ConfigFilesInput` for inputs; explicit `list[ConfigPath]` or `tuple[ConfigPath, ...]` for outputs |
| `@register(spec)` | Bare `@register`, with `__spec__` on the class |
| Singular `__adapter__` | Target-specific `__adapters__` |
| Plain Pydantic `BaseSettings` passed to a cache | Subclass `MountainAshBaseSettings`; plain Pydantic classes still support direct construction |
| `get_secrets_backend`, registry/provider lookup, `secrets_provider` | Construct/select a store and pass `secret_store=store` explicitly |
| `SecretsBackend`, `ClearableBackend` | `SecretReader`, `SecretWriter`, `ClearableSecretStore` capabilities |

The removed secrets-registry operations also include `register_secrets_backend`,
`replace_secrets_backend` and `clear_secrets_registry`. Store implementations are
in `mountainash_settings.secrets`; applications own selection and lifetime.

## Adapter migration

An adapter takes **two arguments**: the profile and already merged base/driver
kwargs. Forward those kwargs and modify what the target needs. Use copy-on-write
for nested values: the caller owns `base` and its containers.

```python
from mountainash_settings.profiles import ParameterSpec, Profile, ProfileSpec, Registry

def render_http(profile, kwargs):
    return {**kwargs, "headers": {**kwargs.get("headers", {}), "X-Profile": profile.profile_name}}

registry = Registry("endpoints")
register = registry.decorator()

@register
class Endpoint(Profile):
    __spec__ = ProfileSpec(name="endpoint", provider_type="http", parameters=[
        ParameterSpec(name="HOST", type=str, tier="core", driver_key={"http": "host"}),
    ])
    __adapters__ = {"http": render_http}

def test_adapter_contract():
    base = {"timeout": 10, "headers": {"Accept": "application/json"}}
    output = Endpoint(HOST="example.test").emit("http", base=base)
    assert output["host"] == "example.test"
    assert output["timeout"] == 10
    assert output["headers"] == {"Accept": "application/json", "X-Profile": "endpoint"}
    assert base["headers"] == {"Accept": "application/json"}
    assert registry.get_spec("endpoint") is Endpoint.__spec__
```

Use your domain's target enum where applicable; strings above are valid hashable
targets. Target-scoped profiles require explicit `emit(target)` and reject
unknown targets, including `None` unless registered. Rebuilding kwargs from
scratch in the adapter discards the caller's base configuration.

## Inputs and cached settings

Kwargs helpers return `{}` or `()` for absent values. They accept mappings and
iterables of key/value pairs; a nested `kwargs` must be a mapping. Malformed
kwargs raise `TypeError`; the second merge input wins.

Config-file helpers accept a string, UPath, sequence of paths, or `None`.
Absent file collections are empty; `SettingsFiles` groups are immutable tuples.
Deduplication preserves first-seen order. Unknown extensions raise `ValueError`
instead of printing a warning. Structured-file UPaths retain remote capability.

Cached classes must derive from `MountainAshBaseSettings`. Direct-source
customization through Pydantic's `settings_customise_sources` still works for
direct construction. Cached custom sources must opt in via
`settings_capture_sources` and implement capture/project semantics; changing
the direct hook alone does not make a source cache-safe.

## Downstream delivery

Develop and test consumer migrations against identified non-editable candidate
artifacts before settings source freeze. Merge/publish downstream only after
settings 0.1.0; consumer import failures are fixed at the consuming package,
without restoring removed settings shims. Full settings requalification follows
the passing ecosystem rehearsal.
