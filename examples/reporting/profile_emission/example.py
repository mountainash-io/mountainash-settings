"""Generate an emission spec from visible native profile fields."""

from pydantic import SecretStr

from mountainash_settings import Profile, ProfileField


class PostgreSQLSettings(
    Profile, name="postgresql", provider_type="postgresql", driver_keys="lower",
):
    HOST: str
    PORT: int = ProfileField(default=5432, ge=1, le=65535)
    DATABASE: str = ProfileField(driver_key="dbname")
    USERNAME: str = ProfileField(driver_key="user")
    PASSWORD: SecretStr
    LOCAL_NOTE: str | None = ProfileField(default=None, driver_key=None)


def main() -> None:
    settings = PostgreSQLSettings(
        env_prefix="REPORT_", HOST="prod-db.example.com", DATABASE="reports",
        USERNAME="report_user", PASSWORD="example-password", LOCAL_NOTE="daily report",
    )
    kwargs = settings.emit()
    assert kwargs == {
        "host": "prod-db.example.com", "port": 5432, "dbname": "reports",
        "user": "report_user", "password": "example-password",
    }
    print("Prepared PostgreSQL arguments for reports (credentials omitted)")


if __name__ == "__main__":
    main()
