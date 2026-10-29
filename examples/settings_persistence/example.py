"""Save configuration explicitly and read it back through a reopened store."""

from pathlib import Path
from tempfile import TemporaryDirectory

from mountainash_settings import MountainAshBaseSettings
from mountainash_settings.secrets import FilesystemBackend


class ReportSettings(MountainAshBaseSettings):
    DATABASE: str = "reports_db"


def main() -> None:
    # The application provisions the root; the backend does not create it.
    with TemporaryDirectory(prefix="configuration-store-") as directory:
        with FilesystemBackend(Path(directory)) as store:
            settings = ReportSettings(env_prefix="REPORT_", secret_store=store)
            with store.transaction("application"):
                settings.persist({"DATABASE": "archived_reports"}, key="application")
            assert settings.DATABASE == "archived_reports"
        with FilesystemBackend(Path(directory)) as reopened:
            assert reopened.get("application") == {"DATABASE": "archived_reports"}
    print("Saved and reopened application configuration")


if __name__ == "__main__":
    main()
