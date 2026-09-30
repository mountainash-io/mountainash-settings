"""Select a database profile by its registered name."""

from mountainash_settings import Profile, ProfileField, Registry


class PostgreSQLSettings(Profile, name="postgresql", provider_type="postgresql", driver_keys="lower"):
    HOST: str
    DATABASE: str = ProfileField(driver_key="dbname")


def main() -> None:
    databases = Registry("databases")
    spec = PostgreSQLSettings.__spec__
    assert spec is not None
    databases.register(spec, PostgreSQLSettings)
    selected = databases.get_settings_class("postgresql")
    assert selected is PostgreSQLSettings
    settings = selected(env_prefix="REPORT_", HOST="prod-db.example.com", DATABASE="reports")
    assert settings.emit() == {"host": "prod-db.example.com", "dbname": "reports"}
    print(f"Selected {selected.__name__} for reports")


if __name__ == "__main__":
    main()
