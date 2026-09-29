# mountainash-settings

![Python](https://img.shields.io/badge/python-3.12%2B-blue) ![Category](https://img.shields.io/badge/category-core-purple) ![Tests](https://img.shields.io/badge/tests-✓-green) ![Docs](https://img.shields.io/badge/docs-✓-blue)

Typed settings for Python applications, with configuration files, environment variables, cached source snapshots and local secret storage. Connection profiles define fields once and emit keyword arguments for drivers or clients.
Requires Python 3.12 or later.

## Built on Pydantic Settings

`MountainAshBaseSettings` extends `pydantic_settings.BaseSettings`. Pydantic
provides field types, validation, aliases and model introspection. Pydantic
Settings provides environment, dotenv and secret-directory loading, plus
YAML/TOML/JSON source classes and configurable source ordering.

MountainAsh composes those sources through per-invocation `config_files`, adds
template helpers and selected-store `secret:` references, and provides cached
source snapshots with independently owned results. Optional profiles describe
how configuration becomes driver arguments.

The API supports two use cases, each with two patterns:

| Use case | Pattern | When to use it |
|---|---|---|
| Declare configuration | Ordinary fields on `MountainAshBaseSettings` | Application-specific settings and small, explicit driver mappings |
| Declare configuration | A `ProfileSpec` on a `Profile` subclass | Shared field declarations and driver-emission conventions |
| Retrieve settings | Direct construction | Read sources afresh for an invocation |
| Retrieve settings | `SettingsParameters` with `get_settings()` | Reuse a captured source context while obtaining independently owned instances |

Both declaration styles support both retrieval paths. A `ProfileSpec` describes
fields and emission rules; a `Profile` subclass turns it into a settings class.
An instance of that class holds the loaded values.

MountainAsh applies its own defaults: unknown inputs are ignored, field defaults
are not validated by default, and assignments are validated. Upstream
`BaseSettings` forbids extra inputs and validates defaults by default. Set model
configuration deliberately when those differences matter. Per-call source
selection uses `config_files`, `env_prefix` and `secrets_dir`; underscore-prefixed
controls such as `_env_file` are rejected. For upstream behavior, see
[Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/).

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

# Field declarations and validation still come from Pydantic.
one_report = AppSettings(DEBUG="true")
assert one_report.DEBUG is True
```

These calls construct settings directly and read sources for each instance.
They do not populate MountainAsh's source cache.

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

Source priority, highest first: constructor values, OS environment, prefixed
dotenv, unprefixed dotenv fallback, YAML, TOML, JSON, Pydantic secret files, then
field defaults. Across formats this order is fixed, regardless of path order.
Within one format, later files recursively merge mappings and replace lists or
scalars. The formats above set different fields to keep this example simple.

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

# Application startup captures the known configuration before accepting work.
get_settings(settings_parameters=report_params)

def report_destination(params: SettingsParameters) -> str:
    # Rehydrate from the cached source context at the point of use.
    local = get_settings(settings_parameters=params)
    return local.DATABASE

assert report_destination(report_params) == "reports"
```

The manager derives a structural cache key from `SettingsParameters`. Its selectors are
`config_files`, `settings_class`, `env_prefix`, `secrets_dir` and the bound
`secret_store` object's identity. Runtime field overrides are excluded from both
that key and parameter equality/hash.

The first cached retrieval captures the source context. Subsequent retrievals
with the same key rehydrate and validate a fresh settings instance from that
context. Files and environment values stay pinned to the captured snapshot;
changes to them are not a live reload. Defaults and default factories remain
per-instance behavior. Retrieval still performs validation and ownership work;
the cache saves repeated baseline source reads.

```python
# 5. The same cache key reuses captured sources, not a mutable settings object.
first = get_settings(settings_parameters=report_params)
second = get_settings(settings_parameters=report_params)
assert first is not second
assert first.DATABASE == second.DATABASE == "reports"
```

Cached retrieval requires a `MountainAshBaseSettings` subclass. Construct plain
Pydantic `BaseSettings` classes directly.

Each structural configuration initializes separately, even if several classes
use the same files. Initialize known configurations during application startup
when they should observe stable deployment inputs. The cache is process-local;
it does not coordinate snapshots across processes.

Treat parameters as trusted application wiring. They may contain literal
credentials in runtime kwargs, and are not inherently safe to serialize or log.
For custom sources, cached retrieval requires `settings_capture_sources` and a
capture/project implementation that can reuse owned data without further I/O.

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

`reinitialise=True` requests derived-field recomputation for the invocation; it
does not reload sources. Cached retrieval also rejects state it cannot safely
isolate, such as unsupported live resources. Settings describe connections;
the application owns the actual clients and their lifetimes.

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

<details>
<summary>Filesystem storage, record validation and lifetime</summary>

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

</details>

Pass a store object through `secret_store=` when constructing settings or creating
`SettingsParameters`. The named secrets-provider registry has been removed.
See [the secrets README](docs/README_SECRETS.md) for reference syntax and store selection.

## Choosing how to declare a connection

### A normal settings class is enough for one connection

The report needs PostgreSQL connection arguments. A regular settings subclass
can declare the connection fields and map them explicitly. It already supports
the selected store, validation and the same caching API used above:

```python
# 9. Start with an ordinary settings class for the report's one database.
# A short method handles the driver's naming and password-unwrapping rules.
from pydantic import SecretStr

class DatabaseSettings(MountainAshBaseSettings):
    HOST: str
    PORT: int = 5432
    DATABASE: str
    USERNAME: str
    PASSWORD: SecretStr

    def driver_kwargs(self) -> dict[str, object]:
        return {
            "host": self.HOST,
            "port": self.PORT,
            "dbname": self.DATABASE,
            "user": self.USERNAME,
            "password": self.PASSWORD.get_secret_value(),
        }

connection_values = {
    "HOST": "prod-db.example.com",
    "DATABASE": report_destination(report_params),
    "USERNAME": "report_user",
    "PASSWORD": "secret:database.password",
}
plain_database = DatabaseSettings(secret_store=report_records, **connection_values)
plain_kwargs = plain_database.driver_kwargs()
assert plain_kwargs["dbname"] == "reports"
assert plain_kwargs["password"] == "example-password"
```

This keeps the fields visible to readers, IDEs and type checkers. Ordinary
Pydantic classes also support aliases, custom field metadata and inspection
through `model_fields`; those capabilities do not require a profile spec.

### Use a profile when mapping conventions become reusable

If the reporting application grows to support several providers, repeating
mapping methods can become maintenance work. `ProfileSpec` collects field
declarations and emission rules so `Profile` can apply one shared mechanism.
Here is the same connection expressed that way, with the same inputs and output:

```python
# 10. Express the same fields and driver mappings as a reusable spec.
# Profile installs Pydantic fields; emit() applies the declared mapping rules.
from mountainash_settings import (
    Profile, ParameterSpec, ProfileSpec,
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
                      secret=True),
    ],
)

class PostgreSQLSettings(Profile):
    __spec__ = POSTGRESQL_SPEC

database_params = SettingsParameters.create(
    settings_class=PostgreSQLSettings,
    secret_store=report_records,
    **connection_values,
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
assert driver_kwargs == plain_kwargs
assert isinstance(database, MountainAshBaseSettings)
```

Pass `driver_kwargs` to the database client when opening a connection. Emission
unwraps the password for the driver, so keep that dictionary out of logs.

The spec version has the same source-loading and retrieval behavior as the
ordinary class. Its benefit is a convention for emission: `driver_key` renames
fields, `secret=True` wraps strings and unwraps them on emission, `transform`
converts output values, and `None` values are omitted. Specs can also declare
validators and templates. For multiple target shapes, scoped `driver_key`
mappings and `__adapters__` support explicit `emit(target)` calls.

This costs extra indirection. Fields are installed dynamically, which gives
static tooling less visibility and ties the implementation to Pydantic's model
internals. For a small application, the ordinary class above may remain clearer.
A registry is not needed to construct or emit a profile.

### Inspect the spec without loading values

A spec is useful when tooling needs the domain's declared fields and mappings
without loading configuration or resolving passwords:

```python
# 11. Inspect configuration metadata without constructing another instance.
driver_keys = {
    parameter.name: parameter.driver_key
    for parameter in POSTGRESQL_SPEC.parameters
}
secret_fields = [
    parameter.name for parameter in POSTGRESQL_SPEC.parameters if parameter.secret
]
assert driver_keys["DATABASE"] == "dbname"
assert secret_fields == ["PASSWORD"]
```

`ProfileSpec` is a frozen dataclass, but its parameter list and metadata
dictionary are still mutable. Treat a declared spec as fixed. This example
inspects spec metadata; it does not depend on JSON Schema generation.

### Add registration when callers choose a provider by name

A registry is an optional discovery layer. Register the existing class when
configuration selects a provider by name, or when a provider library needs a
catalogue with duplicate-name protection:

```python
# 12. Add name-based discovery only when the caller needs it.
# Registration does not create a connection or a new settings cache.
from mountainash_settings import Registry

DATABASES = Registry("databases")
DATABASES.register(POSTGRESQL_SPEC, PostgreSQLSettings)

selected_class = DATABASES.get_settings_class("postgresql")
assert selected_class is PostgreSQLSettings
selected_params = SettingsParameters.create(
    settings_class=selected_class,
    secret_store=report_records,
    **connection_values,
)
assert get_settings(settings_parameters=selected_params).emit() == driver_kwargs
```

For declarations that should register immediately, the equivalent decorator is
`register = DATABASES.decorator()` followed by bare `@register` on a class with
its own `__spec__`. Register a name only once.

### Authentication

Authentication models and OAuth flows belong to `mountainash-auth-client`.
Settings provides the profile framework and selected local stores that consumers
can use for configuration and persistence.

### Profile invariant tests

Generate pytest checks for the `DATABASES` registry defined above, including
naming conventions and parameter uniqueness:

```python
# 13. Turn the registered profile specs into pytest invariant checks.
# Run `python -m pytest reporting.py -q` to collect and execute this class.
from mountainash_settings import spec_invariants_for

TestDatabaseInvariants = spec_invariants_for(DATABASES)
```

In a separate test module, import `DATABASES` from the module containing the
profile declaration before generating the test class. New profile registrations
present when the test class is generated are covered automatically. These checks
verify spec conventions, including parameter and driver-key uniqueness. Keep
separate tests for whether emitted arguments work with the actual driver.

## Documentation

| Document | Contents |
|---|---|
| [docs/quickstart.md](docs/quickstart.md) | Introduction to settings classes, files, templates, caching, secrets and profiles |
| [docs/advanced-usage.md](docs/advanced-usage.md) | SettingsParameters merging, auth modes reference, invariant tests, dynamic resolution |
| [Choosing a connection declaration](#choosing-how-to-declare-a-connection) | Ordinary settings, optional profile emission, inspection and registration |

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
