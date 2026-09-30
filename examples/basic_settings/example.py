"""Declare application fields and validate an invocation."""

from mountainash_settings import MountainAshBaseSettings


class AppSettings(MountainAshBaseSettings):
    APP_NAME: str = "reports"
    ENV: str = "development"
    DEBUG: bool = False
    DATABASE: str = "reports"


def main() -> None:
    ordinary = AppSettings(env_prefix="REPORT_")
    diagnostic = AppSettings(env_prefix="REPORT_", DEBUG="true")
    assert ordinary.APP_NAME == "reports"
    assert ordinary.ENV == "development"
    assert ordinary.DATABASE == "reports"
    assert ordinary.DEBUG is False
    assert diagnostic.DEBUG is True
    print(f"{ordinary.APP_NAME}: ordinary debug={ordinary.DEBUG}, diagnostic debug={diagnostic.DEBUG}")


if __name__ == "__main__":
    main()
