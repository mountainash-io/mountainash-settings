"""Compare a captured source snapshot with a fresh direct read."""

from pathlib import Path
from shutil import copyfile
from tempfile import TemporaryDirectory

from mountainash_settings import MountainAshBaseSettings, SettingsParameters, get_settings


class AppSettings(MountainAshBaseSettings):
    DATABASE: str


def main() -> None:
    source = Path(__file__).resolve().parents[1] / "config" / "base.yaml"
        # Change only a temporary copy, never the shared deployment fixture.
    with TemporaryDirectory(prefix="configuration-snapshot-") as directory:
        config = Path(directory) / "deployment.yaml"
        copyfile(source, config)
        params = SettingsParameters.create(
            settings_class=AppSettings, config_files=[config], env_prefix="REPORT_",
        )
        first = get_settings(settings_parameters=params)
        config.write_text("DATABASE: changed_reports\n", encoding="utf-8")
        second = get_settings(settings_parameters=params)
        direct = AppSettings(config_files=[config], env_prefix="REPORT_")
        assert first is not second
        assert first.DATABASE == "reports_db"
        assert second.DATABASE == "reports_db"
        assert direct.DATABASE == "changed_reports"
        print(f"Cached: {second.DATABASE}; direct: {direct.DATABASE}")


if __name__ == "__main__":
    main()
