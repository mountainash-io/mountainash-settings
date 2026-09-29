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

# 5. The same cache key reuses captured sources, not a mutable settings object.
first = get_settings(settings_parameters=report_params)
second = get_settings(settings_parameters=report_params)
assert first is not second
assert first.DATABASE == second.DATABASE == "reports"

# 6. Enable debugging for one report without changing another caller's settings.
diagnostic = get_settings(settings_parameters=report_params, DEBUG=True)
ordinary = get_settings(settings_parameters=report_params)
assert diagnostic.DEBUG is True
assert ordinary.DEBUG is False

# Even direct mutation stays local to the returned instance.
diagnostic.DATABASE = "scratch_reports"
assert get_settings(settings_parameters=report_params).DATABASE == "reports"

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

# 8. Give the reporting application a namespaced password record.
# Memory storage keeps this example self-contained and makes no disk writes.
from mountainash_settings.secrets import MemorySecretStore, NamespacedSecretStore

store = MemorySecretStore()
report_records = NamespacedSecretStore(store, "reports")
with report_records.transaction("database"):
    report_records.set("database", {"password": "example-password"})

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

# 13. Turn the registered profile specs into pytest invariant checks.
# Run `python -m pytest reporting.py -q` to collect and execute this class.
from mountainash_settings import spec_invariants_for

TestDatabaseInvariants = spec_invariants_for(DATABASES)
