"""Inspect declaration metadata without constructing a settings instance."""

from pydantic import SecretStr

from mountainash_settings import FACTORY_DEFAULT, MISSING, Profile, ProfileField


class PostgreSQLSettings(Profile, name="postgresql", provider_type="postgresql", driver_keys="lower"):
    HOST: str
    DATABASE: str = ProfileField(driver_key="dbname")
    PASSWORD: SecretStr
    TAGS: list[str] = ProfileField(default_factory=list, driver_key=None)


def main() -> None:
    spec = PostgreSQLSettings.__spec__
    assert spec is not None
    parameters = {parameter.name: parameter for parameter in spec.parameters}
    assert parameters["DATABASE"].driver_key == "dbname"
    assert parameters["PASSWORD"].secret is True
    assert parameters["HOST"].default is MISSING
    assert parameters["TAGS"].default is FACTORY_DEFAULT
    # HOST and PASSWORD have no supplied values: no instance or source read is needed.
    print("DATABASE maps to dbname; PASSWORD is secret; TAGS has a factory")


if __name__ == "__main__":
    main()
