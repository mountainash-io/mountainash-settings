"""Map an ordinary settings class to PostgreSQL connection arguments."""

from pydantic import SecretStr

from mountainash_settings import MountainAshBaseSettings


class DatabaseSettings(MountainAshBaseSettings):
    HOST: str
    PORT: int = 5432
    DATABASE: str
    USERNAME: str
    PASSWORD: SecretStr

    def driver_kwargs(self) -> dict[str, object]:
        return {
            "host": self.HOST, "port": self.PORT, "dbname": self.DATABASE,
            "user": self.USERNAME, "password": self.PASSWORD.get_secret_value(),
        }


def main() -> None:
    settings = DatabaseSettings(
        env_prefix="REPORT_", HOST="prod-db.example.com", DATABASE="reports",
        USERNAME="report_user", PASSWORD="example-password",
    )
    kwargs = settings.driver_kwargs()
    assert kwargs == {
        "host": "prod-db.example.com", "port": 5432, "dbname": "reports",
        "user": "report_user", "password": "example-password",
    }
    print("Prepared PostgreSQL arguments for reports (credentials omitted)")


if __name__ == "__main__":
    main()
