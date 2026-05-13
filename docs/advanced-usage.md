# Advanced Usage: mountainash-settings

This guide covers the topics listed in the quickstart's "What's next" section:

- [Merging settings parameters](#merging-settings-parameters)
- [Auth modes reference](#auth-modes-reference)
- [Profile invariant tests](#profile-invariant-tests)
- [Dynamic settings resolution](#dynamic-settings-resolution)

---

## Merging settings parameters

`SettingsParameters.merge()` combines two parameter objects into one. The common pattern is a *base* set of structural parameters (config files, env prefix, settings class) merged with a *local* set of runtime overrides.

### Field-by-field merge rules

| Field | Default behaviour | With `prioritise_base=True` |
|---|---|---|
| `config_files` | Union + dedup (both kept) | First set wins; second ignored if first present |
| `settings_class` | Must be equal — raises `ValueError` if both set to different classes | Same |
| `env_prefix` | `other` wins | `base` wins |
| `secrets_dir` | `other` wins | `base` wins |
| `secrets_provider` | `other` wins | `base` wins |
| `kwargs` | Dict merge — `other` overwrites duplicate keys | `base` value kept for duplicate keys |

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

### Extracting parameters from a live instance

A settings instance records the parameters it was created with. Use `extract_settings_parameters()` to reconstruct a `SettingsParameters` that can be merged, extended, or passed elsewhere:

```python
settings = AppSettings(config_files=["config/production.yaml"], TENANT_ID="acme")

# Reconstruct — reflects config files, env prefix, env files, kwargs
params = settings.extract_settings_parameters()

# Extend it
extended = SettingsParameters.merge(
    params,
    SettingsParameters.create(settings_class=AppSettings, LOG_LEVEL="WARNING"),
)
new_settings = get_settings(settings_parameters=extended)
```

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

Callers register their settings classes once; `get_service_settings()` resolves and caches them without needing to know the concrete type.

### Multi-tenant configuration

Each tenant gets its own structural parameters, so the cache naturally isolates their settings:

```python
def build_tenant_params(tenant_id: str) -> SettingsParameters:
    return SettingsParameters.create(
        settings_class=AppSettings,
        config_files=[f"config/tenants/{tenant_id}.yaml", "config/base.yaml"],
        env_prefix=f"{tenant_id.upper()}_",
    )

# Called once per tenant — subsequent calls hit the LRU cache
settings_acme  = get_settings(settings_parameters=build_tenant_params("acme"))
settings_globex = get_settings(settings_parameters=build_tenant_params("globex"))
```

### Caching guarantees

- `get_settings()` returns the **same instance** for the same structural parameters (config files, settings class, env prefix, secrets dir, secrets provider). The cache is `lru_cache(maxsize=None)` — unbounded, process-global.
- **Runtime kwargs do not affect the cache key.** Two calls with the same structure but different kwargs share a cached base; each gets a `model_copy()` with its own overrides applied.
- The cache is **never cleared** during normal operation. In long-running processes, settings loaded at startup will not pick up subsequent changes to environment variables or config files. If you need cache invalidation, restart the process or use a new `SettingsParameters` object with a different structural identity.

```python
# These two calls share the same cached base instance:
s1 = get_settings(settings_class=AppSettings, config_files=["cfg.yaml"], LOG_LEVEL="DEBUG")
s2 = get_settings(settings_class=AppSettings, config_files=["cfg.yaml"], LOG_LEVEL="WARNING")

# s1 and s2 are different objects (model_copy), but the underlying loaded
# config was only read from disk once.
assert s1.LOG_LEVEL == "DEBUG"
assert s2.LOG_LEVEL == "WARNING"
```
