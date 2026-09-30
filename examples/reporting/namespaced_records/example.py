"""Keep the reporting application's records in its own namespace."""

from mountainash_settings.secrets import MemorySecretStore, NamespacedSecretStore


def main() -> None:
    store = MemorySecretStore()
    reports = NamespacedSecretStore(store, "reports")
    other_application = NamespacedSecretStore(store, "other_application")
    with reports.transaction("database"):
        reports.set("database", {"password": "example-password"})
    assert reports.get("database") == {"password": "example-password"}
    assert other_application.get("database") is None
    print("Database record: present in reports; absent in other_application")


if __name__ == "__main__":
    main()
