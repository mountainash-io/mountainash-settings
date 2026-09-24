# mountainash-settings

![Python](https://img.shields.io/badge/python-3.12%2B-blue) ![Category](https://img.shields.io/badge/category-core-purple) ![Tests](https://img.shields.io/badge/tests-✓-green) ![Docs](https://img.shields.io/badge/docs-✓-blue)

Advanced configuration management for Python applications — typed settings with smart caching, multi-format file loading, template-driven derived fields, a pluggable secrets layer, and a declarative system for building typed connection profiles.
Requires Python 3.12 or later.

> Public PyPI publication is not confirmed by these source changes. Treat builds as unpublished candidates until the public confirmation stage succeeds; the install command below describes the published distribution. See [RELEASE.md](RELEASE.md) for candidate verification and separately authorized publishing.

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

`get_settings()` reuses captured sources for the same structural parameters:
`config_files`, `settings_class`, `env_prefix`, `secrets_dir`, and the bound
`secret_store`'s object identity. Each call validates a complete invocation and returns an
independently owned settings object:

```python
from mountainash_settings import get_settings

settings = get_settings(
    settings_class=AppSettings,
    config_files=["config/production.yaml"],
)
```

Runtime overrides never become shared baseline values, and mutating a returned
object cannot change another retrieval. Defaults and default factories remain
per-materialization behavior. Explicit runtime secret references resolve fresh;
baseline source values remain pinned. See the [cache lifecycle and compatibility
boundaries](docs/advanced-usage.md#cache-contexts-and-runtime-materialization).

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

### Local record storage

The settings-owned storage surface lives in `mountainash_settings.secrets`.
Ordinary environment/configuration/Pydantic secret inputs do not require a local store.

```python
from pathlib import Path
from mountainash_settings.secrets import FilesystemBackend, NamespacedSecretStore

# Application/deployment provisions this directory and its access policy.
root = Path("/path/to/provisioned/private-records")
with FilesystemBackend(root) as store:
    records = NamespacedSecretStore(store, "application")
    with records.transaction("account"):
        records.set("account", {"token": "dummy-token"})
        assert records.get("account") == {"token": "dummy-token"}
```

Local records are exact JSON-native mappings: dictionaries with string keys,
lists, strings, integers, finite floats, booleans and null; `{}` is valid.
Values such as bytes, dates, custom objects, non-finite floats and cycles are
rejected before mutation. Invalid existing YAML/UTF-8/record shapes raise
`SecretStoreUnavailableError`, not absence. Catch its stable `.reason`, not its
message. Invalid caller keys/payloads raise value-free `ValueError`.

The application owns store lifetime and must stop new work and finish every
operation/entered transaction before `close()`. Close is terminal and idempotent;
borrowed namespace views do not own the store. Wrap compound writes in an explicit
transaction, or otherwise ensure exclusive writer ownership. No implicit locking
of `get/set/delete`, reentrant filesystem transaction, distributed lock,
crash durability, automatic repair or secure deletion is promised.

After interrupted marker-first deletion, a valid record and clear marker can both
remain: `get()` returns the record and `is_cleared()` is true. A successful set
followed by marker-cleanup failure raises reason `write_committed_cleanup_failed`;
the new record is committed. Do not blindly retry or assume an exception means
nothing changed. OAuth marker precedence belongs to the separately migrated
authentication lifecycle, not this raw record API.

The native mechanisms use Linux `libacl.so.1`, macOS libSystem ACL operations,
or Windows kernel32/advapi32/ntdll APIs through standard-library facilities.
No native binaries or new Python binding are vendored. Receipts record the actual
OS library/package builds; native prerequisites and their licensing are reviewed
against the approved native-dependency record. Generic imports do not load the
irrelevant platform's libraries.

This M3 candidate is not a package-release or consumer-cutover claim. Existing
settings registry/provider integration remains until coordinated M4 migration;
do not infer that `secret_store=` integration or OAuth migration is already delivered.

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

## Textbook

The [production textbook](https://docs.mountainash.io/mountainash-settings/) is
built from `main`; the [development textbook](https://docs.mountainash.io/mountainash-settings/dev/)
is built from `develop`. Each push to either branch builds both snapshots and
publishes them together. A failed build leaves the previous paired site live.

For initial activation, merge the textbook changes into both branches and
configure Pages, its environment, and the shared custom domain first. Then set
the repository Actions variable `TEXTBOOK_PUBLISHING_ENABLED` to `true` and
manually dispatch `deploy-textbook.yml`. Until enabled, publishing runs are
skipped; a one-sided bootstrap cannot deploy an incomplete site.

The source artifacts live together in this repository:

- `docs-site/profile/`: package profile and source provenance.
- `docs-site/learning-graph/`: canonical graph and FAQ artifacts.
- `docs-site/site/`: MkDocs configuration, textbook Markdown, and refresh state.

Preview locally without installing the source package or sibling repositories:

```bash
uv run --no-project --with-requirements docs-site/requirements.txt \
  python -m mkdocs serve --config-file docs-site/site/mkdocs.yml
```

Refreshes are manual. Load `textbook-refresh` from the central
`hiivmind-documentation-profile` tooling project and supply this repository's
absolute root as `source_repo`, starting with `mode: check`. For a separate
profile update, supply `docs-site/profile/` as the profiler's explicit output.
Do not regenerate content merely to publish it or advance source baselines on
a directory move. Preserve the existing FAQ format; the marker-only FAQ
exporter does not support it and must not overwrite its JSON.

A strict build currently reports two pre-existing content gaps, inherited
from the source content and unrelated to this relocation: five
`learning-graph/` pages (`concept-list.md`, `concept-taxonomy.md`, `faq.md`,
`quality-metrics.md`, `taxonomy-distribution.md`) exist but are not wired
into the site nav, and `learning-graph/index.md` links to a
`course-description.md` that lives at the docs root rather than alongside
it. Neither is fixed here.

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
