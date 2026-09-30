"""Load application configuration from four file formats."""

from pathlib import Path

from mountainash_settings import MountainAshBaseSettings


class AppSettings(MountainAshBaseSettings):
    APP_NAME: str
    DATABASE: str
    ENV: str
    DEBUG: bool = True
    BATCH_SIZE: int


def main() -> None:
    config = Path(__file__).resolve().parents[1] / "config"
    settings = AppSettings(
        config_files=[
            config / "base.yaml", config / "production.toml",
            config / "application.json", config / ".env",
        ],
        env_prefix="REPORT_",
    )
    assert settings.APP_NAME == "reports"
    assert settings.DATABASE == "reports"
    assert settings.ENV == "production"
    assert settings.DEBUG is False
    assert settings.BATCH_SIZE == 100
    print(f"{settings.APP_NAME}: {settings.ENV}, batch={settings.BATCH_SIZE}, debug={settings.DEBUG}")


if __name__ == "__main__":
    main()
