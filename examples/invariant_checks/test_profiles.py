"""Generate convention checks for a database profile registry."""

from mountainash_settings import Profile, ProfileField, Registry, spec_invariants_for

DATABASES = Registry("databases")
register = DATABASES.decorator()


@register
class PostgreSQLSettings(Profile, name="postgresql", provider_type="postgresql", driver_keys="lower"):
    HOST: str
    PORT: int = ProfileField(default=5432, ge=1, le=65535)
    DATABASE: str = ProfileField(driver_key="dbname")


TestDatabaseInvariants = spec_invariants_for(DATABASES)
