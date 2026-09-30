"""Resolve a database password through an explicitly selected store."""

from pydantic import SecretStr

from mountainash_settings import MountainAshBaseSettings
from mountainash_settings.secrets import MemorySecretStore, NamespacedSecretStore


class DatabaseSettings(MountainAshBaseSettings):
    DATABASE: str = "reports"
    PASSWORD: SecretStr


def main() -> None:
    store = MemorySecretStore()
    records = NamespacedSecretStore(store, "reports")
    with records.transaction("database"):
        records.set("database", {"password": "example-password"})
    settings = DatabaseSettings(
        env_prefix="REPORT_", secret_store=records,
        PASSWORD="secret:database.password",
    )
    assert settings.DATABASE == "reports"
    assert settings.PASSWORD.get_secret_value() == "example-password"
    print("Password reference resolved")


if __name__ == "__main__":
    main()
