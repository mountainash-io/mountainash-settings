"""Derive a log path after application configuration has loaded."""

from pathlib import Path

from upath import UPath

from mountainash_settings import MountainAshBaseSettings


class AppSettings(MountainAshBaseSettings):
    APP_NAME: str
    ENV: str
    LOG_PATH_TEMPLATE: str = str(UPath("~") / "logs" / "{APP_NAME}" / "{ENV}.log")
    LOG_PATH: str | None = None

    def post_init(self, reinitialise: bool = False):
        super().post_init(reinitialise=reinitialise)
        self.LOG_PATH = self.init_setting_from_template(
            template_str=self.LOG_PATH_TEMPLATE,
            current_value=self.LOG_PATH,
            reinitialise=reinitialise,
        )


def main() -> None:
    config = Path(__file__).resolve().parents[1] / "config"
    settings = AppSettings(
        config_files=[config / "base.yaml", config / "production.toml"], env_prefix="REPORT_",
    )
    assert settings.LOG_PATH == str(UPath("~") / "logs" / "reports" / "production.log")
    # No directories or log files are created by deriving this path.
    print(f"Log path: {settings.LOG_PATH}")


if __name__ == "__main__":
    main()
