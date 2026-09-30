"""Package a recurring diagnostic override into reusable parameters."""

from pathlib import Path

from mountainash_settings import MountainAshBaseSettings, SettingsParameters, get_settings


class AppSettings(MountainAshBaseSettings):
    DATABASE: str
    DEBUG: bool = False


def main() -> None:
    base = SettingsParameters.create(
        settings_class=AppSettings, env_prefix="REPORT_",
        config_files=[Path(__file__).resolve().parents[1] / "config" / "base.yaml"],
    )
    diagnostic = SettingsParameters.merge(
        base, SettingsParameters.create(settings_class=AppSettings, DEBUG=True),
    )
    assert diagnostic == base  # Equality describes the structural source key.
    assert hash(diagnostic) == hash(base)
    ordinary_settings = get_settings(settings_parameters=base)
    diagnostic_settings = get_settings(settings_parameters=diagnostic)
    assert ordinary_settings.DEBUG is False
    assert diagnostic_settings.DEBUG is True
    assert diagnostic_settings.DATABASE == "reports_db"
    print(f"Same source key: {diagnostic == base}; ordinary debug=False; diagnostic debug=True")


if __name__ == "__main__":
    main()
