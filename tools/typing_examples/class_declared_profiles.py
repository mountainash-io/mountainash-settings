"""Consumer field typing; constructor/header completeness is checked at runtime."""

from mountainash_settings import Profile, ProfileField


class Database(Profile, name="database", provider_type="db", driver_keys="lower"):
    PORT: int = ProfileField(default=5432, ge=1)


def port(settings: Database) -> int:
    return settings.PORT


assert Database.__spec__ is not None
