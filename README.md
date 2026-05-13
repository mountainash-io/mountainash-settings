# mountainash-settings

![Python](https://img.shields.io/badge/python-3.12%2B-blue) ![Category](https://img.shields.io/badge/category-core-purple) ![Tests](https://img.shields.io/badge/tests-✓-green) ![Docs](https://img.shields.io/badge/docs-✓-blue)

Advanced configuration management for Python applications — typed settings with smart caching, multi-format file loading, template-driven derived fields, a pluggable secrets layer, and a declarative system for building typed connection profiles.

## Installation

```bash
pip install mountainash-settings
```

## Quick start

Subclass `MountainAshBaseSettings`, declare fields with pydantic `Field()`, and load from config files, environment variables, or kwargs:

```python
from pydantic import Field
from mountainash_settings import MountainAshBaseSettings

class AppSettings(MountainAshBaseSettings):
    APP_NAME: str = Field(default="MyApp")
    DEBUG: bool = Field(default=False)
    DATABASE_URL: str = Field(default="sqlite:///app.db")

settings = AppSettings(config_files=["config/production.yaml"])
print(settings.APP_NAME)   # value from YAML, env var, or default
```

Priority order (highest wins): **kwargs → environment variables → config files → Field defaults**.

See [docs/quickstart.md](docs/quickstart.md) for a step-by-step introduction.

## Key features

### Multi-format configuration files

Pass YAML, TOML, JSON, and `.env` files in any combination. Files are detected by extension and merged in order:

```python
settings = AppSettings(config_files=[
    "config/base.yaml",
    "config/production.toml",
    ".env.production",
])
```

### Template-driven derived fields

Derive fields from other fields using `{FIELD_NAME}` placeholders, resolved in `post_init()`:

```python
from upath import UPath

class AppSettings(MountainAshBaseSettings):
    APP_NAME: str = Field(default="myapp")
    ENV: str = Field(default="dev")

    LOG_PATH_TEMPLATE: str = Field(
        default=str(UPath("~") / "logs" / "{APP_NAME}" / "{ENV}.log")
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

Use `UPath`'s `/` operator to build cross-platform path templates — no platform-specific separators needed.

### Smart caching

`get_settings()` returns the same instance for the same structural parameters (config files, settings class, env prefix). Call it freely inside frequently-executed code:

```python
from mountainash_settings import get_settings

settings = get_settings(
    settings_class=AppSettings,
    config_files=["config/production.yaml"],
)
```

Runtime overrides (extra kwargs) never pollute the cache — each override call gets a lightweight `model_copy()` with the overrides applied.

### SettingsParameters for reusable and composable configuration

`SettingsParameters` captures a full configuration identity as an immutable, hashable value. Build one and pass it around, merge two together, or store them in a service registry:

```python
from mountainash_settings import SettingsParameters

base = SettingsParameters.create(
    settings_class=AppSettings,
    config_files=["config/base.yaml", "config/production.yaml"],
    env_prefix="APP_",
)

# Merge with runtime overrides — base config files are preserved
merged = SettingsParameters.merge(
    base,
    SettingsParameters.create(settings_class=AppSettings, TENANT_ID="acme"),
)

settings = get_settings(settings_parameters=merged)
```

### Pluggable secrets resolution

Register a resolver callable for any secrets backend, then reference secrets with a `secret:` prefix in your YAML or kwargs:

```python
from mountainash_settings import register_secrets_resolver

register_secrets_resolver("vault", lambda path: fetch_from_vault(path))

settings = AppSettings(
    config_files=["config/production.yaml"],  # may contain secret:db/prod/url
    secrets_provider="vault",
)
```

### Declarative connection profiles

For database and service connections, the `Profile` + `ProfileSpec` system provides typed, inspectable, driver-ready settings with automatic field installation, auth mode validation, and runtime lookup by name:

```python
from mountainash_settings import (
    Profile, MISSING, ParameterSpec, ProfileSpec,
    Registry, NoAuth, PasswordAuth,
)

POSTGRESQL_SPEC = ProfileSpec(
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

DATABASES = Registry("databases")
register = DATABASES.decorator()

@register
class PostgreSQLSettings(Profile):
    __spec__ = POSTGRESQL_SPEC

settings = PostgreSQLSettings(
    HOST="prod-db.example.com",
    DATABASE="myapp",
    auth=PasswordAuth(username="app_user", password="s3cr3t"),
)

driver_kwargs = {**settings._default_kwargs(), **settings._auth_kwargs()}
# {"host": "prod-db.example.com", "port": 5432, "dbname": "myapp",
#  "user": "app_user", "password": "s3cr3t"}
```

See [docs/profile-spec-pattern.md](docs/profile-spec-pattern.md) for an explanation of when and why to use this pattern over a plain subclass.

### 13 typed auth modes

All authentication modes are validated pydantic models with `SecretStr` protection for credentials:

| Mode | Use for |
|---|---|
| `NoAuth` | SQLite, local DuckDB, PySpark |
| `PasswordAuth` | PostgreSQL, MySQL, most databases |
| `TokenAuth` | MotherDuck, PyIceberg REST, simple APIs |
| `JWTAuth` | Trino |
| `OAuth2Auth` | Snowflake, Trino, REST APIs |
| `OAuth2AuthCodeAuth` | Interactive OAuth2 / token refresh flows |
| `IAMAuth` | AWS Redshift, S3, Athena (explicit or ambient credentials) |
| `AzureADAuth` | MSSQL, Azure services |
| `WindowsAuth` | On-prem MSSQL (integrated Windows auth) |
| `KerberosAuth` | Trino on Kerberos, PostgreSQL via GSS |
| `CertificateAuth` | Snowflake JWT |
| `ServiceAccountAuth` | BigQuery, GCS |
| `OAuth1Auth` | OAuth 1.0a services |

### Profile invariant tests

Drop one line into a test module to get parametrised pytest coverage for every descriptor in a registry — name conventions, field uniqueness, valid auth modes, and more:

```python
from mountainash_settings import spec_invariants_for
from my_package.settings import DATABASES

TestDatabaseInvariants = spec_invariants_for(DATABASES)
```

New profile registrations are covered automatically.

## Documentation

| Document | Contents |
|---|---|
| [docs/quickstart.md](docs/quickstart.md) | Step-by-step introduction — settings class, config files, templates, caching, secrets, profiles |
| [docs/advanced-usage.md](docs/advanced-usage.md) | SettingsParameters merging, auth modes reference, invariant tests, dynamic resolution |
| [docs/profile-spec-pattern.md](docs/profile-spec-pattern.md) | When and why to use ProfileSpec vs a plain subclass |
| [examples/](examples/) | Working code: basic usage, path templating, smart merging, dynamic resolution |

## Development

### Testing

```bash
hatch run test:test        # run all tests
hatch run test:cov         # with coverage
pytest tests/path/to/test_file.py::TestClass::test_method -v  # single test
```

### Linting and type checking

```bash
hatch run ruff:check       # lint
hatch run ruff:fix         # auto-fix
hatch run mypy:check       # type check
```

### Build

```bash
hatch build
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes with tests
4. Run `hatch run test:test && hatch run ruff:check`
5. Open a pull request targeting `develop`

## License

MIT License — see [LICENSE](LICENSE) for details.

## Mountain Ash ecosystem

This package is part of the [Mountain Ash](https://github.com/mountainash-io) ecosystem of Python packages for building production-ready data applications.

Related packages: **mountainash-core** · **mountainash-data** · **mountainash-auth** · **mountainash-api**
