# Advanced Usage: mountainash-settings

This guide covers the topics listed in the quickstart's "What's next" section:

- [Merging settings parameters](#merging-settings-parameters)
- [Container secret references](#container-secret-references)
- [Auth modes reference](#auth-modes-reference)
- [Profile invariant tests](#profile-invariant-tests)
- [Dynamic settings resolution](#dynamic-settings-resolution)

---

## Merging settings parameters

`SettingsParameters.merge()` combines two parameter objects into one. The common pattern is a *base* set of structural parameters (config files, env prefix, settings class) merged with a *local* set of runtime overrides.

### Field-by-field merge rules

| Field | Default behaviour | With `prioritise_base=True` |
|---|---|---|
| `config_files` | Base order, then unseen files from `other` | Base files win when present |
| `settings_class` | Must be equal — raises `ValueError` if both set to different classes | Same |
| `env_prefix` | `other` wins | `base` wins |
| `secrets_dir` | `other` wins | `base` wins |
| `secrets_provider` | `other` wins | `base` wins |
| `kwargs` | Dict merge — `other` overwrites duplicate keys | `base` value kept for duplicate keys |

`config_files` keeps the first occurrence of each path. The merge does not sort paths.
With `prioritise_base=True`, the base file list stays in place when it is not empty.

### Structured config file merge

Files of one structured format use caller order. Later mappings merge recursively.
Later lists and scalar values replace earlier values. Lists do not concatenate.

The source priority, from highest to lowest, is:

1. init values
2. environment variables
3. dotenv files
4. YAML files
5. TOML files
6. JSON files
7. Pydantic secret files
8. field defaults

A dotenv file is read twice. The first read uses the configured `env_prefix`.
The second read uses no prefix and fills values that the first read does not set.
A prefixed key wins when both forms exist. Environment variables have higher priority than both dotenv reads.

### Layered configuration example

A typical pattern is to build a base parameter set for the environment (loaded from file) and merge application-specific runtime kwargs on top:

```python
from mountainash_settings import MountainAshBaseSettings, SettingsParameters, get_settings
from pydantic import Field

class AppSettings(MountainAshBaseSettings):
    HOST: str = Field(default="localhost")
    PORT: int = Field(default=8000)
    LOG_LEVEL: str = Field(default="INFO")
    TENANT_ID: str = Field(default="default")

# Base: shared configuration from file, no runtime kwargs
base_params = SettingsParameters.create(
    settings_class=AppSettings,
    config_files=["config/base.yaml", "config/production.yaml"],
    env_prefix="APP_",
)

# Local: runtime overrides for a specific request or job
runtime_params = SettingsParameters.create(
    settings_class=AppSettings,
    TENANT_ID="acme",
    LOG_LEVEL="DEBUG",
)

# Merge: base config + runtime overrides; runtime wins on conflicts
merged = SettingsParameters.merge(base_params, runtime_params)
settings = get_settings(settings_parameters=merged)
```

### Locking base values with `prioritise_base`

Pass `prioritise_base=True` when the base values must not be overridden by the second set — useful when a base set encodes security or compliance constraints:

```python
# Compliance base: secrets_provider must not be overridden
compliance_base = SettingsParameters.create(
    settings_class=AppSettings,
    config_files=["config/compliance.yaml"],
    secrets_provider="vault",
)

# Caller-supplied params — secrets_provider is ignored when base wins
caller_params = SettingsParameters.create(
    settings_class=AppSettings,
    secrets_provider="local",   # would normally win
    TENANT_ID="acme",           # new key — merged in regardless
)

locked = SettingsParameters.merge(compliance_base, caller_params, prioritise_base=True)
# locked.secrets_provider == "vault"  (base wins)
# locked.kwargs["TENANT_ID"] == "acme"  (new key, always merged)
```

### Controlled reconstruction from a live instance

`extract_settings_parameters()` is a controlled reconstruction capability, not a
general diagnostics dump. It returns the structural selectors together with a
fresh, independently owned tree of the accepted constructor and successful
update inputs in their original source form. For example, a
`secret:record.field` input remains a reference in the extracted kwargs rather
than a copied backend result. Extraction itself does not reread files,
environment variables, or secret backends.

Use `SETTINGS_SOURCE_KWARG_NAMES` when diagnostic code needs to know which
attribute inputs were accepted. It exposes names only. The removed
`SETTINGS_SOURCE_KWARGS` field has no compatibility alias: migrate diagnostic
uses to the names tuple, and use extraction only where reconstruction inputs
are intentionally needed.

```python
settings = AppSettings(config_files=["config/production.yaml"], TENANT_ID="acme")

# Trusted reconstruction — params.kwargs contains the source-form values.
params = settings.extract_settings_parameters()
assert settings.SETTINGS_SOURCE_KWARG_NAMES == ("TENANT_ID",)

# Extend the reconstruction input deliberately.
extended = SettingsParameters.merge(
    params,
    SettingsParameters.create(settings_class=AppSettings, LOG_LEVEL="WARNING"),
)
new_settings = get_settings(settings_parameters=extended)
```

Successful `update_settings_from_dict()` and `persist()` calls preserve
untouched accepted inputs and replace only the supplied logical fields in the
reconstruction recipe. A dict-valued field is replaced as a field, not
recursively merged. Existing partial-assignment behavior is unchanged: a
failed update does not roll back assignments that already succeeded, and it
does not publish failed or resolved input provenance. A persistence failure
after its backend write is not an atomic transaction.

The ordinary `repr()` of `SettingsParameters` omits `kwargs`, but that is a
safe-default diagnostic boundary, not a serialization guarantee. Explicit
`params.kwargs`, `to_dict()`, `dataclasses.asdict()`, pickle, debugger
inspection, and other intentional serialization or inspection can expose
caller-supplied values. Keep those operations in trusted code paths.

If an otherwise valid supplied value cannot be faithfully represented in, and independently owned by, the reconstruction recipe, construction and updates retain their normal behavior, but extraction raises a value-free `TypeError`. This includes an update whose accepted alias/path would make faithful reconstruction change an independently supplied sibling. It does not return a partial recipe, alter another field to invent a representation, or use a shared input tree.

### Service registry pattern

`SettingsParameters` objects are frozen and hashable — they can be stored in dicts and used as cache keys. This makes them a natural fit for service registries:

```python
REGISTRY = {
    "database": SettingsParameters.create(
        settings_class=DatabaseSettings,
        config_files=["config/db.yaml"],
        env_prefix="DB_",
    ),
    "cache": SettingsParameters.create(
        settings_class=CacheSettings,
        config_files=["config/cache.yaml"],
        env_prefix="CACHE_",
    ),
}

def get_service(name: str, **runtime_overrides):
    base = REGISTRY[name]
    if runtime_overrides:
        base = SettingsParameters.merge(
            base,
            SettingsParameters.create(settings_class=base.settings_class, **runtime_overrides),
        )
    return get_settings(settings_parameters=base)
```

## Cache contexts and runtime materialization

`get_settings()` retains one private source context for each structural selector
set: `config_files`, `settings_class`, `env_prefix`, `secrets_dir`, and
`secrets_provider`. It pins the selected source inputs and baseline resolved
references for that context. It does **not** retain a settings result or the
runtime kwargs from the first caller.

Every cached retrieval materializes a fresh, independently owned settings
object. Runtime fields are validated together with the pinned source inputs;
a caller's mutable field, extra value, private attribute, or non-field state
cannot become another caller's state. Missing source fields are left absent
from the retained candidate, so Pydantic evaluates defaults and default
factories for each materialization with the class's normal validation policy.

Cached results support ordinary containers, Pydantic models, secret wrappers,
and local paths through the same ownership policy as reconstruction. Standard
enum members are shared schema identities only when their values are exact
immutable scalars (or tuples/frozensets of them) and they have no custom member
state or slots. Opaque resources, cycles, and mutable enum state are rejected
without falling back to another source read.

Generic cached `post_init` hooks must assign declared fields through normal
validated assignment. In-place or `object.__setattr__` changes that bypass
that assignment origin are rejected. Only successful source-only calls with
`reinitialise=False` may establish raw derived carry; rejected assignments and
runtime calls never become that carry. Current explicit runtime fields win.
Default-factory outputs remain per-invocation; their secret-reference
interpretation is a separate compatibility backlog, not certified here.

References read from a selected source are resolved before final validation
and retained as the context's baseline value tree. An explicit runtime
`secret:` reference is instead resolved once for that invocation, even when
its text matches the baseline reference. Runtime values never replace the
baseline. Projected source values are terminal values: the cache does not
interpret a projector result that merely looks like a `secret:` reference.

`reinitialise` is a keyword-only cached-retrieval operation control:

```python
settings = get_settings(
    settings_class=AppSettings,
    config_files="config/production.yaml",
    HOST="alternate.example",
    reinitialise=True,
)
```

It is neither a source reload nor a cache refresh and is not part of
structural identity. The later Profile origin/template integration is
MAS-SEC-005 work; this control does not claim that integration here. Source
control/direct-constructor framing remains MAS-SEC-004, shared cached error
handling remains MAS-SEC-006, and provider/context refresh belongs to the
separate lifecycle work.

### Cacheable custom sources

Cached retrieval supports custom external sources only through the explicit
`CacheableSettingsSource` contract exported from the package root:

`CacheableSettingsSource` still has the ordinary
`PydanticBaseSettingsSource` requirements. Implement its normal source methods
as appropriate for direct construction in addition to `capture()` and
`project()`.

```python
from mountainash_settings import CacheableSettingsSource

class InventorySource(CacheableSettingsSource):
    def capture(self) -> dict:
        """Read external state once and return an independently ownable snapshot."""

    @staticmethod
    def project(snapshot, current_state, sources_data) -> dict:
        """Return pure terminal candidate values; perform no external I/O."""
```

The settings class selects participating cache sources with the cache-only
hook `settings_capture_sources(sources)`. Its argument and result are ordered
source tuples, so a class can retain the configured built-ins and replace or
add only sources that implement capture/project:

```python
@classmethod
def settings_capture_sources(cls, sources):
    return sources
```

This hook is separate from the direct-construction
`settings_customise_sources` hook. A class that overrides the legacy hook
must explicitly adapt it for cached retrieval; otherwise cached retrieval
fails before source reads. Ordinary direct construction retains its existing
semantics. Standard plain `BaseSettings` classes whose constructor is the
inherited `BaseSettings.__init__` remain supported by cached retrieval.
Plain subclasses with a custom constructor are rejected by cached retrieval
before reads; direct construction remains available, and
`MountainAshBaseSettings` supplies the supported cached custom-constructor
path.

## Container secret references

Use the `secret:` prefix for a value that a secrets backend resolves.
The resolver walks nested values in dictionaries, lists, tuples, and Pydantic models.

References resolve inside:

- Declared string (`str`) fields.
- Declared `SecretStr` fields.
- Nested Pydantic models.
- Dictionary fields.
- List fields.
- Tuple values supplied through init values or runtime overrides.

A tuple remains a tuple after resolution. A resolved `SecretStr` remains wrapped as `SecretStr`.
Nested model validation aliases remain supported, including `AliasChoices` and `AliasPath`.
The resolver creates new dictionaries, lists, and tuples. It does not mutate input dictionaries or containers.

The resolver rebuilds a nested model only when a reference changes one of its values.
Pydantic validation runs during that rebuild.

---


## Auth modes reference

All auth modes are pydantic models. They validate on construction, reject unknown fields (`extra="forbid"`), and are immutable (`frozen=True`). `SecretStr` fields protect credentials from appearing in logs and `repr()` output.

Import any auth mode from the package root:

```python
from mountainash_settings import PasswordAuth, TokenAuth, IAMAuth  # etc.
```

### Available modes

| Class | `kind` | Required fields | Optional fields | Default dispatch |
|---|---|---|---|---|
| `NoAuth` | `none` | — | — | `{}` |
| `PasswordAuth` | `password` | `username`, `password` | — | `{"user": ..., "password": ...}` |
| `TokenAuth` | `token` | `token` | — | `{"token": ...}` |
| `JWTAuth` | `jwt` | `token` | — | `{"token": ...}` |
| `OAuth2Auth` | `oauth2` | — | `client_id`, `client_secret`, `token`, `refresh_token`, `server_uri`, `scope` | token or `client_id:client_secret` |
| `OAuth1Auth` | `oauth1` | `consumer_key`, `consumer_secret` | `access_token`, `access_token_secret` | none — adapter handles |
| `OAuth2AuthCodeAuth` | `oauth2_authcode` | `client_id`, `client_secret` | `access_token`, `refresh_token`, `token_expires_at`, `scope` | none — adapter handles |
| `IAMAuth` | `iam` | — | `role_arn`, `access_key_id`, `secret_access_key`, `session_token`, `profile_name` | ambient credentials if all None |
| `AzureADAuth` | `azure_ad` | — | `tenant_id`, `client_id`, `client_secret`, `managed_identity`, `msi_endpoint` | none — adapter handles |
| `WindowsAuth` | `windows` | — | `username`, `domain` | none — adapter handles |
| `KerberosAuth` | `kerberos` | — | `principal`, `keytab`; `service_name` defaults to `"postgres"` | none — adapter handles |
| `CertificateAuth` | `certificate` | — | `private_key`, `private_key_path`, `passphrase` | none — adapter handles |
| `ServiceAccountAuth` | `service_account` | — | `info` (dict), `file` (Path) | none — adapter handles |

### Choosing an auth mode

- **No credentials needed** (SQLite, local DuckDB, PySpark): `NoAuth`
- **Username + password** (PostgreSQL, MySQL, most databases): `PasswordAuth`
- **Bearer token** (MotherDuck, PyIceberg REST, simple APIs): `TokenAuth`
- **JWT** (Trino): `JWTAuth`
- **OAuth2 client credentials or pre-issued token** (Snowflake, Trino, REST APIs): `OAuth2Auth`
- **OAuth2 authorization code** (interactive user flows, token refresh scenarios): `OAuth2AuthCodeAuth`
- **AWS IAM** (Redshift, S3, Athena): `IAMAuth` — leave all fields None for ambient credentials
- **Azure AD** (MSSQL, Azure services): `AzureADAuth`
- **Windows integrated** (on-prem MSSQL): `WindowsAuth`
- **Kerberos/GSSAPI** (Trino on Kerberos, PostgreSQL via GSS): `KerberosAuth`
- **Private key / certificate** (Snowflake JWT): `CertificateAuth`
- **Google service account** (BigQuery, GCS): `ServiceAccountAuth`

### Usage examples

```python
from mountainash_settings import (
    PasswordAuth, TokenAuth, OAuth2Auth, IAMAuth,
    ServiceAccountAuth, AzureADAuth,
)
from pydantic import SecretStr

# Password
auth = PasswordAuth(username="app_user", password=SecretStr("s3cr3t"))

# Bearer token
auth = TokenAuth(token=SecretStr("mytoken"))

# OAuth2 — client credentials
auth = OAuth2Auth(client_id="my-client", client_secret=SecretStr("my-secret"))

# OAuth2 — pre-issued token
auth = OAuth2Auth(token=SecretStr("access-token-xyz"))

# AWS IAM — explicit credentials
auth = IAMAuth(
    access_key_id="AKIAIOSFODNN7EXAMPLE",
    secret_access_key=SecretStr("wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"),
)

# AWS IAM — ambient credentials (env vars, instance profile, SSO)
auth = IAMAuth()

# Google service account — inline JSON key
auth = ServiceAccountAuth(info={"type": "service_account", "project_id": "my-project", ...})

# Google service account — path to key file
from pathlib import Path
auth = ServiceAccountAuth(file=Path("/secrets/sa-key.json"))

# Azure AD — managed identity
auth = AzureADAuth(managed_identity=True)

# Azure AD — client credentials
auth = AzureADAuth(
    tenant_id="my-tenant-id",
    client_id="my-client-id",
    client_secret=SecretStr("my-client-secret"),
)
```

### How `auth_to_driver_kwargs()` works

For the six auth modes with default dispatch (`NoAuth`, `PasswordAuth`, `TokenAuth`, `JWTAuth`, `OAuth2Auth`, `IAMAuth`), call `auth_to_driver_kwargs()` to convert to driver-ready kwargs:

```python
from mountainash_settings import auth_to_driver_kwargs, PasswordAuth
from pydantic import SecretStr

auth = PasswordAuth(username="app_user", password=SecretStr("s3cr3t"))
kwargs = auth_to_driver_kwargs(auth)
# {"user": "app_user", "password": "s3cr3t"}
```

For the other seven modes (`OAuth1Auth`, `OAuth2AuthCodeAuth`, `AzureADAuth`, `WindowsAuth`, `KerberosAuth`, `CertificateAuth`, `ServiceAccountAuth`), your backend adapter is responsible for converting to driver kwargs. `auth_to_driver_kwargs()` will raise `KeyError` for these — that is intentional.

### Using auth in a `Profile`

When a profile has multiple `auth_modes`, pydantic uses the `kind` literal to discriminate:

```python
from mountainash_settings import (
    Profile, ParameterSpec, ProfileSpec, Registry,
    NoAuth, PasswordAuth, IAMAuth,
)

REDSHIFT_SPEC = ProfileSpec(
    name="redshift",
    provider_type="redshift",
    parameters=[
        ParameterSpec(name="HOST",     type=str, tier="core", driver_key="host"),
        ParameterSpec(name="DATABASE", type=str, tier="core", driver_key="database"),
        ParameterSpec(name="PORT",     type=int, tier="core", driver_key="port", default=5439),
    ],
    auth_modes=[PasswordAuth, IAMAuth],
)

class RedshiftSettings(Profile):
    __spec__ = REDSHIFT_SPEC

# Instantiate with the right auth — pydantic validates the kind discriminator
settings = RedshiftSettings(
    HOST="my-cluster.us-east-1.redshift.amazonaws.com",
    DATABASE="analytics",
    auth=IAMAuth(),                  # ambient AWS credentials
)

driver_kwargs = {**settings._default_kwargs(), **settings._auth_kwargs()}
# {"host": "...", "database": "analytics", "port": 5439}
# (IAMAuth with no explicit creds emits an empty dict — driver picks up ambient credentials)
```

---

## Profile invariant tests

Every domain that builds a `Registry` gets free pytest coverage with one line:

```python
from mountainash_settings import spec_invariants_for
from my_package.settings import MY_REGISTRY

TestMyInvariants = spec_invariants_for(MY_REGISTRY)
```

Drop this in any `test_*.py` file. Pytest collects it as a parametrised test class — every spec registered in `MY_REGISTRY` is tested automatically.

### What is checked

For each registered descriptor:

| Invariant | What it verifies |
|---|---|
| Name matches registry key | `descriptor.name == key` used to register it |
| Name is lowercase and non-empty | Prevents `"PostgreSQL"` vs `"postgresql"` mismatches |
| Parameter names are uppercase and unique | `ParameterSpec.name` conventions |
| `driver_key` values are unique | No two params map to the same driver kwarg |
| Parameter `tier` is `"core"` or `"advanced"` | Valid tier values |
| `auth_modes` is non-empty | Use `[NoAuth]` for auth-free backends — never leave this empty |
| All `auth_modes` are `AuthSpec` subclasses | Catches accidental non-auth objects |
| `provider_type` is not `None` | Required for downstream dispatching |

### Full example

```python
# tests/unit/test_db_profiles.py

import pytest
from mountainash_settings import (
    Profile, MISSING, ParameterSpec, ProfileSpec,
    Registry, NoAuth, PasswordAuth, IAMAuth,
    spec_invariants_for,
)

# Build the registry under test
DATABASES = Registry("databases")
register = DATABASES.decorator()

POSTGRESQL_SPEC = ProfileSpec(
    name="postgresql",
    provider_type="postgresql",
    parameters=[
        ParameterSpec(name="HOST",     type=str, tier="core",     driver_key="host"),
        ParameterSpec(name="PORT",     type=int, tier="core",     driver_key="port",   default=5432),
        ParameterSpec(name="DATABASE", type=str, tier="core",     driver_key="dbname"),
        ParameterSpec(name="SSL_MODE", type=str, tier="advanced", driver_key="sslmode", default="prefer"),
    ],
    auth_modes=[NoAuth, PasswordAuth],
)

REDSHIFT_SPEC = ProfileSpec(
    name="redshift",
    provider_type="redshift",
    parameters=[
        ParameterSpec(name="HOST",     type=str, tier="core", driver_key="host"),
        ParameterSpec(name="PORT",     type=int, tier="core", driver_key="port", default=5439),
        ParameterSpec(name="DATABASE", type=str, tier="core", driver_key="database"),
    ],
    auth_modes=[PasswordAuth, IAMAuth],
)

@register
class PostgreSQLSettings(Profile):
    __spec__ = POSTGRESQL_SPEC

@register
class RedshiftSettings(Profile):
    __spec__ = REDSHIFT_SPEC

# This one line gives you parametrised invariant tests for BOTH specs.
# Add more specs to the registry — they are covered automatically.
TestDatabaseInvariants = spec_invariants_for(DATABASES)
```

Running `pytest tests/unit/test_db_profiles.py` will produce one test per invariant per descriptor:

```
tests/unit/test_db_profiles.py::TestDatabaseInvariants_databases::postgresql::test_name_matches_registry_key PASSED
tests/unit/test_db_profiles.py::TestDatabaseInvariants_databases::postgresql::test_auth_modes_nonempty PASSED
tests/unit/test_db_profiles.py::TestDatabaseInvariants_databases::redshift::test_driver_keys_unique PASSED
...
```

### Resetting the registry between tests

If tests register descriptors dynamically, use the built-in test seams to snapshot and restore state:

```python
import pytest
from my_package.settings import DATABASES

@pytest.fixture(autouse=True)
def isolate_registry():
    snap = DATABASES._snapshot_for_tests()
    yield
    DATABASES._reset_for_tests(*snap)
```

---

## Dynamic settings resolution

The `get_settings()` function resolves any `SettingsParameters` — including those where the settings class is only known at runtime. This enables generic service registries and plugin architectures where the calling code does not know which settings class it will receive.

### Type-agnostic factory

```python
from mountainash_settings import get_settings, SettingsParameters, MountainAshBaseSettings

SERVICE_PARAMS: dict[str, SettingsParameters] = {}

def register_service(name: str, params: SettingsParameters) -> None:
    SERVICE_PARAMS[name] = params

def get_service_settings(name: str, **overrides) -> MountainAshBaseSettings:
    base = SERVICE_PARAMS[name]
    if overrides:
        base = SettingsParameters.merge(
            base,
            SettingsParameters.create(settings_class=base.settings_class, **overrides),
        )
    return get_settings(settings_parameters=base)
```

Callers register their settings classes once; `get_service_settings()` selects pinned source state and materializes the concrete type without callers needing to name it.

### Multi-tenant configuration

Each tenant gets its own structural parameters, so the cache naturally isolates their settings:

```python
def build_tenant_params(tenant_id: str) -> SettingsParameters:
    return SettingsParameters.create(
        settings_class=AppSettings,
        config_files=[f"config/tenants/{tenant_id}.yaml", "config/base.yaml"],
        env_prefix=f"{tenant_id.upper()}_",
    )

# Called once per tenant to capture that tenant's source context; later calls
# reuse the pinned source baseline and materialize fresh owned results.
settings_acme = get_settings(settings_parameters=build_tenant_params("acme"))
settings_globex = get_settings(settings_parameters=build_tenant_params("globex"))
```

### Caching guarantees

- `get_settings()` selects one private source context for the five structural
  selectors (config files, settings class, env prefix, secrets dir, and
  secrets provider). It returns a fresh independently owned result for every
  retrieval.
- **Runtime kwargs do not affect structural identity.** They are
  invocation-local complete-validation inputs and never become retained
  baseline state.
- Selected source inputs remain pinned for a context. Normal retrieval does
  not clear, refresh, or reread them; a new structural context may capture its
  own source state. Context/provider refresh is separate lifecycle work.

```python
# These calls share pinned source state, not a returned settings instance:
s1 = get_settings(settings_class=AppSettings, config_files=["cfg.yaml"], LOG_LEVEL="DEBUG")
s2 = get_settings(settings_class=AppSettings, config_files=["cfg.yaml"], LOG_LEVEL="WARNING")

assert s1.LOG_LEVEL == "DEBUG"
assert s2.LOG_LEVEL == "WARNING"
```
