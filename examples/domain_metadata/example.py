"""Attach strictly typed domain metadata to a profile declaration."""

from dataclasses import dataclass

from mountainash_settings import Profile, ProfileField, ProfileSpec


@dataclass(frozen=True, kw_only=True)
class BackendSpec(ProfileSpec):
    default_port: int = 5432


class SQLProfile(Profile, spec_type=BackendSpec, driver_keys="lower"):
    HOST: str
    DATABASE: str = ProfileField(driver_key="dbname")


class PostgreSQLSettings(SQLProfile, name="postgresql", provider_type="postgresql", default_port=5432):
    PORT: int = 5432


def main() -> None:
    assert SQLProfile.__spec__ is None  # Intermediate bases are not concrete profiles.
    spec = PostgreSQLSettings.__spec__
    assert isinstance(spec, BackendSpec)
    assert spec.default_port == 5432
    settings = PostgreSQLSettings(env_prefix="REPORT_", HOST="prod-db.example.com", DATABASE="reports")
    assert settings.emit()["port"] == 5432
    print(f"PostgreSQL domain default port: {spec.default_port}")


if __name__ == "__main__":
    main()
