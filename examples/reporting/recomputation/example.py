"""Recompute a profile-derived value while preserving explicit values."""

from mountainash_settings import Profile, ProfileField, SettingsParameters, get_settings


class DatabaseSettings(Profile, name="reporting_database", provider_type="postgresql"):
    HOST: str = "prod-db.example.com"
    PORT: int = 5432
    URL: str | None = ProfileField(default=None, template="{HOST}:{PORT}")


def main() -> None:
    params = SettingsParameters.create(settings_class=DatabaseSettings, env_prefix="REPORT_")
    baseline = get_settings(settings_parameters=params)
    unchanged = get_settings(settings_parameters=params, HOST="diagnostic.example.com")
    local = get_settings(settings_parameters=params, HOST="diagnostic.example.com", reinitialise=True)
    explicit = get_settings(settings_parameters=params, URL="explicit", reinitialise=True)
    assert baseline.URL == "prod-db.example.com:5432"
    assert unchanged.HOST == "diagnostic.example.com"
    assert unchanged.URL == baseline.URL
    assert local.URL == "diagnostic.example.com:5432"
    assert explicit.URL == "explicit"
    print(f"Baseline: {baseline.URL}")
    print(f"Recomputed: {local.URL}; explicit: {explicit.URL}")


if __name__ == "__main__":
    main()
