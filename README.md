# mountainash-settings

![Python](https://img.shields.io/badge/python-3.12%2B-blue) ![Category](https://img.shields.io/badge/category-core-purple) ![Tests](https://img.shields.io/badge/tests-✓-green) ![Docs](https://img.shields.io/badge/docs-✓-blue)

Typed settings for Python applications, with configuration files, environment variables, cached source snapshots and local secret storage. Connection profiles define fields once and emit keyword arguments for drivers or clients.
Requires Python 3.12 or later.

Version 0.1.0 uses SemVer and removes the legacy APIs. See the
[0.1 migration guide](docs/migration-0.1.md) for profile, adapter, registry,
cached-settings and selected-store changes.

> Version 0.1.0 is an unpublished candidate. Release authorization is pending. The installation command below applies once the package is published. See [RELEASE.md](RELEASE.md) for the release procedure.

## Installation

```bash
pip install mountainash-settings
```

## Quick start

Start with settings for a reporting application. The Python examples below build
on each other and can be run in order in the same script. The first example needs
no configuration files.

The complete walkthrough and its configuration files are in
[examples/reporting/](examples/reporting/). Automated tests check that the files
match the snippets below and that the walkthrough runs successfully.

```python
"""Build a reporting application's configuration, one step at a time.

Run from examples/reporting/ with the package and pytest installed:
    python reporting.py

The accompanying config/ files and .env supply the deployment values.
Assertions show the expected behavior; success produces no output.
The database connection is described but never opened.
"""

# 1. Start with defaults so the application can run without config files.
from pydantic import Field
from mountainash_settings import MountainAshBaseSettings

class AppSettings(MountainAshBaseSettings):
    APP_NAME: str = Field(default="reports")
    ENV: str = Field(default="development")
    DEBUG: bool = Field(default=False)
    DATABASE: str = Field(default="reports")

settings = AppSettings()
assert settings.APP_NAME == "reports"
assert settings.DEBUG is False
```

Constructor arguments take precedence over environment variables, configuration files and field defaults, in that order.

See [docs/quickstart.md](docs/quickstart.md) for a step-by-step introduction.

## Configuration

### Multi-format configuration files

The reporting service now needs deployment-specific configuration. Create
`config/base.yaml`:

```yaml
APP_NAME: reports
DATABASE: reports
```

Set the deployment environment in `config/production.toml`:

```toml
ENV = "production"
```

Use a `.env` file for environment-style values:

```dotenv
REPORT_DEBUG=false
```

Load those files together. The `REPORT_` prefix applies to environment and dotenv
values; YAML and TOML use the model's field names. These examples assume no
conflicting environment variables are set.

```python
# 2. Load the same application for production, using the supplied files.
# Keep these paths together so later examples reuse the same configuration.
config_files = [
    "config/base.yaml",
    "config/production.toml",
    ".env",
]
settings = AppSettings(config_files=config_files, env_prefix="REPORT_")
assert settings.ENV == "production"
assert settings.DATABASE == "reports"
```

JSON files are also supported. When layering files of the same format, later
files override earlier values. See the quickstart for source precedence across
formats.

### Template-driven derived fields

Add a log path to the reporting settings. Extend the existing class so its
database and debug fields remain available. The template is resolved in
`post_init()` after the configuration has loaded:

```python
# 3. Extend the existing settings with a log path derived from loaded values.
# Inheriting AppSettings keeps its database and debug fields available.
from upath import UPath

class ReportingSettings(AppSettings):
    LOG_PATH_TEMPLATE: str = Field(
        default=str(UPath("~") / "logs" / "{APP_NAME}" / "{ENV}.log")
    )
    LOG_PATH: str | None = Field(default=None)

    def post_init(self, reinitialise: bool = False):
        super().post_init(reinitialise=reinitialise)
        self.LOG_PATH = self.init_setting_from_template(
            template_str=self.LOG_PATH_TEMPLATE,
            current_value=self.LOG_PATH,
            reinitialise=reinitialise,
        )

settings = ReportingSettings(config_files=config_files, env_prefix="REPORT_")
assert settings.LOG_PATH == str(UPath("~") / "logs" / "reports" / "production.log")
```

Use `UPath`'s `/` operator to build cross-platform path templates.

### Reusing configuration where it is needed

As the application grows, its functions can accept `SettingsParameters` and
retrieve settings when they run. This avoids passing a settings instance through
every layer of the application.

Define the reporting configuration once:

```python
# 4. Pass a configuration description to application code.
# Each function retrieves a settings instance only when it needs one.
from mountainash_settings import SettingsParameters, get_settings

report_params = SettingsParameters.create(
    settings_class=ReportingSettings,
    config_files=config_files,
    env_prefix="REPORT_",
)

def report_destination(params: SettingsParameters) -> str:
    # Rehydrate from the cached source context at the point of use.
    local = get_settings(settings_parameters=params)
    return local.DATABASE

assert report_destination(report_params) == "reports"
```

`SettingsParameters` supplies the cache key. Its equality and hash use
`config_files`, `settings_class`, `env_prefix`, `secrets_dir` and the bound
`secret_store` object's identity. Runtime field overrides are excluded.

The first cached retrieval captures the source context. Subsequent retrievals
with the same key rehydrate and validate a fresh settings instance from that
context. Files and environment values stay pinned to the captured snapshot;
changes to them are not a live reload. Defaults and default factories still run
for each materialization.

```python
# 5. The same cache key reuses captured sources, not a mutable settings object.
first = get_settings(settings_parameters=report_params)
second = get_settings(settings_parameters=report_params)
assert first is not second
assert first.DATABASE == second.DATABASE == "reports"
```

Cached retrieval requires a `MountainAshBaseSettings` subclass. Construct plain
Pydantic `BaseSettings` classes directly.

### Locally scoped overrides

A diagnostic report can enable debugging for its own invocation. The override
does not change the shared source context or another caller's settings:

```python
# 6. Enable debugging for one report without changing another caller's settings.
diagnostic = get_settings(settings_parameters=report_params, DEBUG=True)
ordinary = get_settings(settings_parameters=report_params)
assert diagnostic.DEBUG is True
assert ordinary.DEBUG is False

# Even direct mutation stays local to the returned instance.
diagnostic.DATABASE = "scratch_reports"
assert get_settings(settings_parameters=report_params).DATABASE == "reports"
```

If several calls need the same override, merge it into a reusable parameter set:

```python
# 7. Package a recurring override into its own parameter set.
# DEBUG is a runtime value, so both parameter sets use the same source cache key.
diagnostic_params = SettingsParameters.merge(
    report_params,
    SettingsParameters.create(settings_class=ReportingSettings, DEBUG=True),
)

assert diagnostic_params == report_params  # same structural cache key
assert hash(diagnostic_params) == hash(report_params)
assert get_settings(settings_parameters=diagnostic_params).DEBUG is True
assert get_settings(settings_parameters=report_params).DEBUG is False
```

Explicit runtime secret references resolve on each call; baseline source values
remain pinned. See the [cache lifecycle and compatibility
boundaries](docs/advanced-usage.md#cache-contexts-and-runtime-materialization)
for source capture and derived-field recomputation rules.

### Local record storage

The report's database password can come from a selected record store. Use an
in-memory store for this runnable example, with a namespace for the application:

```python
# 8. Give the reporting application a namespaced password record.
# Memory storage keeps this example self-contained and makes no disk writes.
from mountainash_settings.secrets import MemorySecretStore, NamespacedSecretStore

store = MemorySecretStore()
report_records = NamespacedSecretStore(store, "reports")
with report_records.transaction("database"):
    report_records.set("database", {"password": "example-password"})
```

The next example reads that password through `secret:database.password`: record
`database`, field `password`, within the `reports` namespace.

For on-disk storage, use `FilesystemBackend` with a directory whose access policy
has been provisioned by the deployment. It does not create or repair that root.
Keep the backend open for all settings operations that use it, then close it
after work has finished. Ordinary environment, configuration-file and Pydantic
secret inputs do not require a record store.

Local records are exact JSON-native mappings: dictionaries with string keys,
lists, strings, integers, finite floats, booleans and null; `{}` is valid.
Values such as bytes, dates, custom objects, non-finite floats and cycles are
rejected before mutation. Invalid existing YAML/UTF-8/record shapes raise
`SecretStoreUnavailableError`, not absence. Catch its stable `.reason`, not its
message. Invalid caller keys/payloads raise value-free `ValueError`.

For `FilesystemBackend`, the application owns store lifetime and must stop new work and finish every
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

Pass a store object through `secret_store=` when constructing settings or creating
`SettingsParameters`. The named secrets-provider registry has been removed.
See [the secrets README](docs/README_SECRETS.md) for reference syntax and store selection.

### Declarative connection profiles

The report now needs PostgreSQL connection arguments. `ProfileSpec` describes
connection fields, defaults and driver keyword mappings.
A `Profile` subclass installs those fields, validates supplied values and emits
driver arguments. A `Registry` provides lookup by name.

```python
# 9. Describe the report's database connection and resolve its stored password.
# The spec maps application-facing field names to database-driver arguments.
from mountainash_settings import (
    Profile, ParameterSpec, ProfileSpec, Registry,
)

POSTGRESQL_SPEC = ProfileSpec(
    name="postgresql",
    provider_type="postgresql",
    parameters=[
        ParameterSpec(name="HOST",     type=str, tier="core",     driver_key="host"),
        ParameterSpec(name="PORT",     type=int, tier="core",     driver_key="port",   default=5432),
        ParameterSpec(name="DATABASE", type=str, tier="core",     driver_key="dbname"),
        ParameterSpec(name="USERNAME", type=str, tier="core",     driver_key="user"),
        ParameterSpec(name="PASSWORD", type=str, tier="core",     driver_key="password",
                      secret=True, default=None),
    ],
)

DATABASES = Registry("databases")
register = DATABASES.decorator()

@register
class PostgreSQLSettings(Profile):
    __spec__ = POSTGRESQL_SPEC

database_params = SettingsParameters.create(
    settings_class=PostgreSQLSettings,
    secret_store=report_records,
    HOST="prod-db.example.com",
    DATABASE=report_destination(report_params),
    USERNAME="report_user",
    PASSWORD="secret:database.password",  # record "database", field "password"
)

database = get_settings(settings_parameters=database_params)
# Emission unwraps the password for the driver. Do not log this dictionary.
driver_kwargs = database.emit()
assert driver_kwargs == {
    "host": "prod-db.example.com",
    "port": 5432,
    "dbname": "reports",
    "user": "report_user",
    "password": "example-password",
}
```

Pass `driver_kwargs` to the database client when opening a connection. Emission
unwraps the password for the driver, so keep that dictionary out of logs.

See [docs/profile-spec-pattern.md](docs/profile-spec-pattern.md) for an explanation of when and why to use this pattern over a plain subclass.

### Authentication

Authentication models and OAuth flows belong to `mountainash-auth-client`.
Settings provides the profile framework and selected local stores that consumers
can use for configuration and persistence.

### Profile invariant tests

Generate pytest checks for the `DATABASES` registry defined above, including
naming conventions and parameter uniqueness:

```python
# 10. Turn the registered profile specs into pytest invariant checks.
# Run `python -m pytest reporting.py -q` to collect and execute this class.
from mountainash_settings import spec_invariants_for

TestDatabaseInvariants = spec_invariants_for(DATABASES)
```

In a separate test module, import `DATABASES` from the module containing the
profile declaration before generating the test class. New profile registrations
are covered automatically.

## Documentation

| Document | Contents |
|---|---|
| [docs/quickstart.md](docs/quickstart.md) | Introduction to settings classes, files, templates, caching, secrets and profiles |
| [docs/advanced-usage.md](docs/advanced-usage.md) | SettingsParameters merging, auth modes reference, invariant tests, dynamic resolution |
| [docs/profile-spec-pattern.md](docs/profile-spec-pattern.md) | When and why to use ProfileSpec vs a plain subclass |

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

The docs site has its own content-refresh workflow. Strict builds of the qualified
0.1.0 source passed under both production and development URL settings.

## Development

### Testing

The local test environment expects a sibling `mountainash-auth-client` checkout.
Use the `test_github` environment to run the settings suite without that dependency.

```bash
hatch run test:test        # run all tests with coverage reports
hatch run test_github:test # settings-only suite, without a sibling checkout
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

MIT License. See [LICENSE](LICENSE) for details.

## Mountain Ash ecosystem

This package is part of the [Mountain Ash](https://github.com/mountainash-io) Python ecosystem.

Consumers include `mountainash-auth-client`, `mountainash-transport`,
`mountainash-files`, `mountainash-data` and `mountainash`.
