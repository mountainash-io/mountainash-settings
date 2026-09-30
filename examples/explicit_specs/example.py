"""Install fields from an explicitly authored, data-driven profile spec."""

from mountainash_settings import ParameterSpec, Profile, ProfileSpec


POSTGRESQL_SPEC = ProfileSpec(
    name="postgresql", provider_type="postgresql",
    parameters=[
        ParameterSpec(name="HOST", type=str, tier="core", driver_key="host"),
        ParameterSpec(name="PORT", type=int, tier="core", driver_key="port", default=5432),
        ParameterSpec(name="DATABASE", type=str, tier="core", driver_key="dbname"),
        ParameterSpec(name="USERNAME", type=str, tier="core", driver_key="user"),
        ParameterSpec(name="PASSWORD", type=str, tier="core", driver_key="password", secret=True),
    ],
)


class PostgreSQLSettings(Profile):
    __spec__ = POSTGRESQL_SPEC


def main() -> None:
    settings = PostgreSQLSettings(
        env_prefix="REPORT_", HOST="prod-db.example.com", DATABASE="reports_db",
        USERNAME="report_user", PASSWORD="example-password",
    )
    kwargs = settings.emit()
    assert kwargs == {
        "host": "prod-db.example.com", "port": 5432, "dbname": "reports_db",
        "user": "report_user", "password": "example-password",
    }
    print("Prepared PostgreSQL arguments for reports_db (credentials omitted)")


if __name__ == "__main__":
    main()
