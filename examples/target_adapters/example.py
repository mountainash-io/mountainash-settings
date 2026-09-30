"""Emit two client shapes and compose an adapter with caller-supplied kwargs."""

from mountainash_settings import Profile, ProfileField


def connection_options(profile, kwargs):
    return {**kwargs, "connect_timeout": profile.CONNECT_TIMEOUT}


class PostgreSQLSettings(Profile, name="postgresql", provider_type="postgresql"):
    HOST: str = ProfileField(driver_key={"driver": "host", "url": "hostname"})
    DATABASE: str = ProfileField(driver_key={"driver": "dbname", "url": "database"})
    PORT: int = ProfileField(default=5432, driver_key={"url": "port"}, transform=str)
    CONNECT_TIMEOUT: int = ProfileField(default=5, driver_key=None)
    __adapters__ = {"driver": connection_options}


def main() -> None:
    settings = PostgreSQLSettings(env_prefix="REPORT_", HOST="prod-db.example.com", DATABASE="reports")
    base = {"application_name": "reports"}
    driver = settings.emit("driver", base=base)
    url = settings.emit("url")
    assert driver == {
        "application_name": "reports", "host": "prod-db.example.com",
        "dbname": "reports", "connect_timeout": 5,
    }
    assert url == {"hostname": "prod-db.example.com", "database": "reports", "port": "5432"}
    assert base == {"application_name": "reports"}
    print(f"Driver timeout: {driver['connect_timeout']}; URL port: {url['port']} (string)")


if __name__ == "__main__":
    main()
