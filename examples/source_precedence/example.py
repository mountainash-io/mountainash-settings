"""Observe source precedence and same-format deep merging."""

import os
from pathlib import Path

from pydantic import Field

from mountainash_settings import MountainAshBaseSettings


class AppSettings(MountainAshBaseSettings):
    DATABASE: str = "reports_db"
    OPTIONS: dict[str, object] = Field(default_factory=dict)


def main() -> None:
    config = Path(__file__).resolve().parent
    files = [config / "base.yaml", config / "production.yaml", config / "production.toml"]
    # This recipe deliberately controls the environment input it demonstrates.
    original = os.environ.pop("REPORT_DATABASE", None)
    try:
        merged = AppSettings(config_files=files, env_prefix="REPORT_")
        assert merged.DATABASE == "production_reports"  # YAML beats TOML, even when TOML is last.
        assert merged.OPTIONS == {
            "export": {"format": "csv", "batch_size": 250},
            "recipients": ["monthly"],  # Lists replace; they do not concatenate.
        }
        reversed_formats = AppSettings(config_files=[files[2], *files[:2]], env_prefix="REPORT_")
        assert reversed_formats.DATABASE == "production_reports"
        os.environ["REPORT_DATABASE"] = "environment_reports"
        environment = AppSettings(config_files=files, env_prefix="REPORT_")
        invocation = AppSettings(config_files=files, env_prefix="REPORT_", DATABASE="diagnostic_reports")
        assert environment.DATABASE == "environment_reports"
        assert invocation.DATABASE == "diagnostic_reports"
        print(f"Files: {merged.DATABASE}; environment: {environment.DATABASE}; invocation: {invocation.DATABASE}")
        print("Merged export: csv, batch=250; recipients: monthly")
    finally:
        if original is None:
            os.environ.pop("REPORT_DATABASE", None)
        else:
            os.environ["REPORT_DATABASE"] = original


if __name__ == "__main__":
    main()
