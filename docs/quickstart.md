# Quickstart: mountainash-settings

Get from zero to a working, cached, typed settings class in five minutes.

## Installation

```bash
pip install mountainash-settings
```

## 1. Define a settings class

Subclass `MountainAshBaseSettings` and declare fields with pydantic `Field()`. Every field is typed, validated, and autocomplete-friendly.

```python
from pydantic import Field
from mountainash_settings import MountainAshBaseSettings

class AppSettings(MountainAshBaseSettings):
    APP_NAME: str = Field(default="MyApp")
    DEBUG: bool = Field(default=False)
    PORT: int = Field(default=8000)
    DATABASE_URL: str = Field(default="sqlite:///app.db")
```

Instantiate directly and your settings are ready:

```python
settings = AppSettings()
print(settings.APP_NAME)   # "MyApp"
print(settings.PORT)       # 8000
```

Pass keyword arguments to override any field at construction time:

```python
settings = AppSettings(DEBUG=True, PORT=9000)
```

Environment variables are loaded automatically — set `APP_NAME=prod` in your shell and it will be picked up without any extra configuration.

## 2. Load from configuration files

Pass one or more config files via `config_files`. YAML, TOML, JSON, and `.env` files are all supported and are detected by extension.

```python
settings = AppSettings(config_files=["config/base.yaml", "config/production.yaml"])
```

Files are merged in order — later files override earlier ones. Environment variables override everything.

**`config/base.yaml`:**

```yaml
APP_NAME: MyApp
PORT: 8000
```

**`config/production.yaml`:**

```yaml
PORT: 443
DATABASE_URL: postgresql://prod-db.example.com/myapp
```

The priority order (highest to lowest) is: **kwargs → environment variables → config files → Field defaults**.

### Using SettingsParameters for reusable config

When you need to share a configuration across multiple callsites, build a `SettingsParameters` object and pass it around:

```python
from mountainash_settings import SettingsParameters

params = SettingsParameters.create(
    settings_class=AppSettings,
    config_files=["config/production.yaml"],
    env_prefix="APP_",
)

settings = AppSettings(settings_parameters=params)
```

## 3. Derive fields from other fields (templates)

Fields can be automatically derived from other fields using `{FIELD_NAME}` placeholders. Override `post_init()` and call `init_setting_from_template()`:

```python
from pydantic import Field
from upath import UPath
from mountainash_settings import MountainAshBaseSettings

class AppSettings(MountainAshBaseSettings):
    APP_NAME: str = Field(default="myapp")
    ENVIRONMENT: str = Field(default="dev")
    RUNDATE: str = Field(default="20260513")

    # Template: build the path with UPath, convert to string for storage
    LOG_PATH_TEMPLATE: str = Field(
        default=str(UPath("~") / "logs" / "{APP_NAME}" / "{ENVIRONMENT}" / "{RUNDATE}.log")
    )

    LOG_PATH: str = Field(default=None)

    def post_init(self, reinitialise: bool = False):
        super().post_init(reinitialise=reinitialise)
        self.LOG_PATH = self.init_setting_from_template(
            template_str=self.LOG_PATH_TEMPLATE,
            current_value=self.LOG_PATH,
            reinitialise=reinitialise,
        )
```

```python
settings = AppSettings(APP_NAME="analytics", ENVIRONMENT="production")
print(settings.LOG_PATH)
# ~/logs/analytics/production/20260513.log
```

`init_setting_from_template()` is a no-op if `current_value` is already set — explicit values always win over templates.

> **Cross-platform paths:** Always use `UPath`'s `/` operator to build path templates rather than string concatenation. UPath handles POSIX and Windows separators automatically.

## 4. Get cached settings with `get_settings()`

`get_settings()` returns the same instance every time it is called with the same structural parameters (config files, settings class, env prefix). This is safe to call inside functions that run frequently — the settings are only loaded once.

```python
from mountainash_settings import get_settings

def process_batch():
    settings = get_settings(
        settings_class=AppSettings,
        config_files=["config/production.yaml"],
    )
    print(settings.DATABASE_URL)
```

You can also call `get_settings()` as a classmethod on your settings class:

```python
settings = AppSettings.get_settings(config_files=["config/production.yaml"])
```

### Runtime overrides

Pass extra keyword arguments to override specific fields without affecting the cache. Each call with different overrides gets a copy of the cached instance with the overrides applied — the cache is never mutated.

```python
# Cached base is shared; each call gets a lightweight copy with the override
settings_a = get_settings(settings_class=AppSettings, PORT=8001)
settings_b = get_settings(settings_class=AppSettings, PORT=8002)
```

## 5. Resolve secrets automatically

Register a secrets resolver before constructing settings that reference external secrets:

```python
from mountainash_settings import register_secrets_resolver

def my_vault_resolver(secret_path: str) -> str:
    # Call your secrets backend here (AWS SSM, HashiCorp Vault, etc.)
    return fetch_from_vault(secret_path)

register_secrets_resolver("vault", my_vault_resolver)
```

Then reference secrets with the `secret:` prefix in your YAML config or as kwargs:

```yaml
# config/production.yaml
DATABASE_URL: "secret:db/production/url"
```

```python
settings = AppSettings(
    config_files=["config/production.yaml"],
    secrets_provider="vault",
)
# settings.DATABASE_URL is now the resolved value from Vault
```

The prefix is stripped before your resolver is called — it receives `"db/production/url"`, not `"secret:db/production/url"`.

## 6. Build typed connection profiles

For database or service connections, use the declarative profile system to define once and reuse across your codebase.

```python
from mountainash_settings import (
    DescriptorProfile,
    MISSING,
    ParameterSpec,
    ProfileDescriptor,
    Registry,
    NoAuth,
    PasswordAuth,
)

# 1. Describe the connection
POSTGRESQL_DESCRIPTOR = ProfileDescriptor(
    name="postgresql",
    provider_type="postgresql",
    parameters=[
        ParameterSpec(name="HOST",     type=str, tier="core",     driver_key="host"),
        ParameterSpec(name="PORT",     type=int, tier="core",     driver_key="port",   default=5432),
        ParameterSpec(name="DATABASE", type=str, tier="core",     driver_key="dbname"),
        ParameterSpec(name="PASSWORD", type=str, tier="core",     driver_key="password",
                      secret=True, default=None),
    ],
    auth_modes=[NoAuth, PasswordAuth],
)

# 2. Create a registry for your domain
DATABASES = Registry("databases")
register = DATABASES.decorator()

# 3. Define the settings class
@register(POSTGRESQL_DESCRIPTOR)
class PostgreSQLSettings(DescriptorProfile):
    __descriptor__ = POSTGRESQL_DESCRIPTOR
```

Pydantic fields, type validation, and SecretStr wrapping are installed automatically from the descriptor. No boilerplate.

```python
settings = PostgreSQLSettings(
    HOST="prod-db.example.com",
    DATABASE="myapp",
    auth=PasswordAuth(username="app_user", password="s3cr3t"),
)

# Get driver kwargs for psycopg2, asyncpg, etc.
kwargs = {**settings._default_kwargs(), **settings._auth_kwargs()}
# {"host": "prod-db.example.com", "port": 5432, "dbname": "myapp",
#  "user": "app_user", "password": "s3cr3t"}
```

## What's next

- **Multiple config files and merging** — `SettingsParameters.merge()` for combining base and environment-specific parameters
- **Auth modes reference** — 13 typed auth modes: `PasswordAuth`, `TokenAuth`, `JWTAuth`, `OAuth2Auth`, `OAuth1Auth`, `OAuth2AuthCodeAuth`, `IAMAuth`, `AzureADAuth`, `WindowsAuth`, `KerberosAuth`, `CertificateAuth`, `ServiceAccountAuth`, `NoAuth`
- **Profile invariant tests** — `descriptor_invariants_for(REGISTRY)` gives automatic pytest coverage for every registered profile
- **Examples** — `examples/` directory contains working code for path templating, smart merging, and comprehensive patterns
