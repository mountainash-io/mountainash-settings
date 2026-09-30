"""Use diagnostic values without changing another caller's settings."""

from pathlib import Path

from mountainash_settings import MountainAshBaseSettings, SettingsParameters, get_settings


class AppSettings(MountainAshBaseSettings):
    DATABASE: str
    DEBUG: bool = False


def main() -> None:
    params = SettingsParameters.create(
        settings_class=AppSettings, env_prefix="REPORT_",
        config_files=[Path(__file__).resolve().parents[1] / "config" / "base.yaml"],
    )
    # Capture the deployment inputs before accepting work.
    get_settings(settings_parameters=params)
    diagnostic = get_settings(settings_parameters=params, DEBUG=True)
    ordinary = get_settings(settings_parameters=params)
    assert diagnostic.DEBUG is True
    assert ordinary.DEBUG is False
    diagnostic.DATABASE = "scratch_reports"
    later = get_settings(settings_parameters=params)
    assert later.DATABASE == "reports_db"
    print(f"Diagnostic debug={diagnostic.DEBUG}; ordinary debug={ordinary.DEBUG}; later database={later.DATABASE}")


if __name__ == "__main__":
    main()
