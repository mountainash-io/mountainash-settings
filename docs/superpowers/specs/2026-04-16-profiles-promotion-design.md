# Profiles Promotion — Design Spec

**Date:** 2026-04-16
**Status:** Draft — pending implementation plan

## Problem Statement

The 2026-04-15 settings-registry refactor in `mountainash-data` replaced `BaseDBAuthSettings` inheritance with a declarative descriptor + registry pattern (`BackendDescriptor`, `ParameterSpec`, `ConnectionProfile`, `@register`, typed `AuthSpec` discriminated union, per-backend adapters). The result: 12 backends reduced to two-line shell classes with ~20-40 lines of descriptor data each, ~200 lines of per-backend boilerplate eliminated.

Three other `mountainash` packages exhibit the same pre-refactor shape:

- **`mountainash-utils-files`** — 18 storage providers (S3, Azure Blob, GCS, SFTP, FTP, NFS, etc.), each a `StorageAuthBase` subclass with 20+ inherited optional fields, hand-written `get_connection_args()` / `get_connection_url()` / `_init_provider_specific()`.
- **`mountainash-utils-secrets`** — 5 secrets providers (AWS/Azure/GCP/HashiCorp/Local), each a `SecretsAuthBase` subclass with 14+ inherited fields, repeated `init_setting_from_template()` boilerplate, per-provider `_init_dynamic_settings()` stubs.
- **`mountainash-acrds-core`** — deployable client-side app with a flat 60-field settings class; `post_init()` is a 150-line sequence of `init_setting_from_template()` calls, one per derived field.

Without intervention, each of these packages re-invents some or all of the descriptor/registry/auth/template pattern independently. The goal is to lift the reusable machinery into `mountainash-settings` so each consumer writes only what's genuinely domain-specific.

## Goals

1. **Extract two reusable patterns** from `mountainash-data` into `mountainash-settings`:
   - **Pattern A — Descriptor Registry:** `ProfileDescriptor`, `ParameterSpec`, `DescriptorProfile`, `Registry`, `@register`, adapter contract, full `AuthSpec` hierarchy with default dispatch.
   - **Pattern B — Declarative Templates:** `ParameterSpec.template` field auto-wired through `__pydantic_init_subclass__` to replace manual `post_init()` template resolution.
2. **Migrate the four target packages** to the new location with no external API change (`mountainash-data` re-exports stay stable).
3. **Per-domain registries** so `mountainash-utils-files` registers `"s3"`, `mountainash-data` registers `"postgresql"`, `mountainash-utils-secrets` registers `"vault"`, etc., without name collisions.
4. **Domain-specific outputs stay in domain packages** — `mountainash-settings` provides mechanism only, not `to_driver_kwargs()` / `to_connection_url()` etc.

## Non-Goals

- Rewriting `MountainAshBaseSettings` itself (it stays as-is).
- Changing `SettingsParameters` / `SettingsManager` / `SettingsConfigDict` / existing file-based config loading.
- Adding new backends / providers — just moving the pattern, consumers migrate their existing set.
- Replacing the setattr-bypass limitation — documented as a separate backlog item; possible resolution folded into `DescriptorProfile` as a follow-up but not blocking.

## Architecture

### Layer 1 — `mountainash-settings` (new sub-packages)

```
src/mountainash_settings/
├── profiles/                        # NEW — Pattern A + B mechanism
│   ├── __init__.py                  # Re-exports public API
│   ├── descriptor.py                # MISSING, ParameterSpec, ProfileDescriptor
│   ├── profile.py                   # DescriptorProfile (pure mechanism base)
│   ├── registry.py                  # Registry class, snapshot/reset test seams
│   └── invariants.py                # descriptor_invariants_for(registry) pytest helper
└── auth/                            # NEW — cross-cutting auth types
    ├── __init__.py                  # Re-exports all 11 subclasses + AuthSpec
    ├── base.py                      # AuthSpec (pydantic v2 BaseModel, discriminated)
    ├── none.py, password.py, token.py, oauth2.py, service_account.py,
    │ iam.py, azure.py, kerberos.py, certificate.py
    └── dispatch.py                  # AUTH_TO_DRIVER_KWARGS, auth_to_driver_kwargs()
```

All code lifts from `mountainash-data` verbatim with a single rename: `BackendDescriptor` → `ProfileDescriptor`, to drop the database-specific connotation.

### Layer 2 — Consumer packages (thin subclasses + per-domain registries)

Each consumer adds two small files and keeps its domain-specific descriptors, adapters, and output methods local.

**`mountainash-data`** (reference example, unchanged external surface):

```python
# core/settings/profile.py
from mountainash_settings.profiles import DescriptorProfile

class ConnectionProfile(DescriptorProfile):
    """Database connection settings with driver kwargs + URL outputs."""
    def to_driver_kwargs(self) -> dict: ...    # domain-specific
    def to_connection_string(self) -> str: ... # domain-specific

# core/settings/registry.py
from mountainash_settings.profiles import Registry
DATABASES_REGISTRY = Registry("databases")
register = DATABASES_REGISTRY.decorator()   # bound convenience

# core/settings/__init__.py (external API — unchanged symbols)
from .profile import ConnectionProfile
from .registry import DATABASES_REGISTRY, register
from mountainash_settings.auth import PasswordAuth, NoAuth, ...  # re-export
# ... all 12 backend shells unchanged
```

**`mountainash-utils-files`**:
```python
class StorageProfile(DescriptorProfile):
    def to_connection_args(self) -> dict: ...
    def to_connection_url(self) -> str: ...

STORAGE_REGISTRY = Registry("storage")
register = STORAGE_REGISTRY.decorator()
```

**`mountainash-utils-secrets`**:
```python
class SecretsProfile(DescriptorProfile):
    def to_client_kwargs(self) -> dict: ...

SECRETS_REGISTRY = Registry("secrets")
register = SECRETS_REGISTRY.decorator()
```

**`mountainash-acrds-core`** (Pattern B primary use case):
```python
class AppProfile(DescriptorProfile):
    """App settings with declarative templates; no kwargs output needed."""

# Single descriptor replaces the 60-field flat class + 150-line post_init.
# ParameterSpec(template="...") wires each derived field automatically.
```

### Key Contracts

**`ProfileDescriptor`** (`mountainash_settings.profiles.descriptor`)
- Frozen dataclass. Fields: `name`, `provider_type`, `parameters: list[ParameterSpec]`, `auth_modes: list[type[AuthSpec]]`.
- Optional `metadata: dict[str, Any]` for domain-specific extras (e.g. `default_port`, `connection_string_scheme` in mountainash-data).
- Domain packages can subclass: `ConnectionDescriptor(ProfileDescriptor)` adds typed `default_port: int | None`, etc.

**`ParameterSpec`** (gains one field for Pattern B)
- Existing: `name`, `type`, `tier`, `default`, `description`, `driver_key`, `secret`, `transform`, `validator`.
- **New:** `template: str | None = None` — when set, `DescriptorProfile.__pydantic_init_subclass__` wires `init_setting_from_template()` into the profile's `post_init` automatically.

**`DescriptorProfile`** (pure mechanism)
- `__descriptor__: ClassVar[ProfileDescriptor]` and `__adapter__: ClassVar[Callable | None] = None`.
- `__pydantic_init_subclass__` installs descriptor params as pydantic fields, composes auth discriminated union, wires templates.
- Helpers: `_default_kwargs()`, `_auth_kwargs()`, `backend` / `profile_name` / `provider_type` properties.
- **No** `to_driver_kwargs` / `to_connection_string` — those are domain subclass concerns.
- Adapter contract preserved: if set, adapter owns the full output pipeline.

**`Registry`** (one per consumer domain)
```python
registry = Registry("databases")          # name for error messages
registry.register(descriptor, cls)        # direct API
decorator = registry.decorator()          # @decorator(descriptor) class-decorator factory
registry.get_descriptor("postgresql")     # KeyError with "known: ..." hint
registry.get_settings_class("postgresql")
registry.descriptors                      # read-only view
len(registry)                             # iteration-friendly
```
- Includes `_snapshot_for_tests()` / `_reset_for_tests()` seams.
- Error messages include the registry name: `Backend 'foo' not registered in databases registry. Known: postgresql, ...`.

**`descriptor_invariants_for(registry)`** — pytest helper
- Returns a parametric test class factory. Each consumer drops it into its test suite:
  ```python
  # tests/test_descriptor_invariants.py
  TestDatabaseInvariants = descriptor_invariants_for(DATABASES_REGISTRY)
  ```
- Runs the 10 invariants (unique names/driver_keys, valid tiers, auth subclasses, port range, uppercase param names, etc.) over every descriptor in the given registry. New registrations get coverage for free.

**Auth dispatch** (unchanged from mountainash-data)
- `auth_to_driver_kwargs(auth)` handles NoAuth / PasswordAuth / TokenAuth / JWTAuth / OAuth2Auth / IAMAuth by default.
- Adapter-handled types (ServiceAccountAuth, AzureADAuth, KerberosAuth, CertificateAuth, WindowsAuth) raise `KeyError` — domain adapters must handle them.

## Testing Strategy

- `mountainash-settings` gains full test suites for `profiles/` and `auth/` — lifted from `mountainash-data` and re-parented. Target ≥95% coverage on new mechanism.
- Each consumer uses `descriptor_invariants_for(THEIR_REGISTRY)` to pin descriptor correctness. New providers get coverage automatically.
- Per-consumer round-trip tests (e.g. `test_s3.py` for storage) validate adapters and audit-regression fixes — same pattern as `mountainash-data`'s 12 `test_<backend>.py` files.
- Migration step for each consumer keeps the existing test count green with zero regressions; new pattern's invariants add coverage.

## Migration Strategy

Sequenced for safety, each step a separate PR with tests green at each checkpoint.

1. **Build `mountainash-settings` `profiles/` + `auth/`** — new code, no consumers yet. Verbatim lift + `BackendDescriptor` → `ProfileDescriptor` rename + `Registry` class + invariants helper. Ship first.
2. **Migrate `mountainash-data`** — delete its local `descriptor.py`/`auth/`/`profile.py`/`registry.py`. Replace with `ConnectionProfile(DescriptorProfile)` subclass + `DATABASES_REGISTRY`. `settings/__init__.py` re-exports keep external API identical.
3. **Migrate `mountainash-utils-secrets`** — smallest (5 providers); proves pattern generalizes beyond databases.
4. **Migrate `mountainash-utils-files`** — largest (18 providers); validates Pattern A at scale.
5. **Migrate `mountainash-acrds-core`** — different shape; validates Pattern B (templates). Single big descriptor replaces the 60-field flat class and 150-line `post_init`.

## Risks

- **Setattr-bypass limitation inherits.** `MountainAshBaseSettings.update_settings_from_dict` bypasses pydantic, so `ParameterSpec.validator` enforces rejection but not transformation, and enum-identity checks require per-class `__setattr__` overrides. Documented in `mountainash-central/01.principles/mountainash-data/f.backlog/setattr-bypass-limitation.md`. A generic enum-coercing `__setattr__` on `DescriptorProfile` would resolve it for all four packages at once — flagged as a fast-follow after initial migration.
- **`mountainash-settings` surface growth.** Adding `profiles/` + `auth/` sub-packages roughly doubles the public API. Mitigation: clean sub-package boundaries; existing consumers unaffected until they opt in.
- **Hard cutover risk.** No deprecation shims — any downstream package importing from `mountainash-data`'s internal module paths (rather than the public `core.settings.__init__`) may break. Mitigation: public re-exports stay stable; internal paths are not considered public API.
- **Per-domain registries may feel over-engineered** for the smallest consumer (5 secrets providers). Mitigation: registry is opt-in — a consumer with ≤3 providers can skip it and just subclass `DescriptorProfile` directly.
- **Pattern B less battle-tested.** Only `mountainash-acrds-core` exercises templates. Mitigation: implement Pattern A first; validate B last; if B doesn't work cleanly on acrds-core, revert and leave its current `post_init` approach intact — Pattern A migrations ship regardless.

## File-Level Changes (Summary)

| Repo | Net change |
|---|---|
| `mountainash-settings` | +2 sub-packages (`profiles/`, `auth/`), ~700 LOC added |
| `mountainash-data` | Internal files deleted (descriptor/auth/profile/registry); subclass + registry added; external `__init__.py` API unchanged |
| `mountainash-utils-files` | 18 provider files → descriptor literals + adapters; `StorageAuthBase` deleted |
| `mountainash-utils-secrets` | 5 provider files → descriptor literals; `SecretsAuthBase` deleted |
| `mountainash-acrds-core` | 60-field class + 150-line `post_init` → single descriptor with `template=` wiring |
| `mountainash-central` | `descriptor-based-settings` principle updated to point at mountainash-settings as the canonical home |

## Open Questions

None blocking — the design is fully specified. Implementation plan will decompose each migration into TDD task sequences.
