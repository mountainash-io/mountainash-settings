# Profile coverage — mountainash-settings

Source `88f4df95` (previous profile `b09b31cf`). Requested behaviour: incremental; effective: **full profile scan** (module topology changed; changed modules exceed one third).

Discovered 41 modules: 34 profiled, 7 ignored (`__init__.py` aggregators excluded by scope).

## Missing

None — every in-scope module has a profile.

## Stale

None — all records carry the target source hash.

## Orphaned (removed since previous profile)

- `mountainash_settings.auth.azure` — source removed; record deleted
- `mountainash_settings.auth.base` — source removed; record deleted
- `mountainash_settings.auth.certificate` — source removed; record deleted
- `mountainash_settings.auth.dispatch` — source removed; record deleted
- `mountainash_settings.auth.iam` — source removed; record deleted
- `mountainash_settings.auth.kerberos` — source removed; record deleted
- `mountainash_settings.auth.none` — source removed; record deleted
- `mountainash_settings.auth.oauth1` — source removed; record deleted
- `mountainash_settings.auth.oauth2` — source removed; record deleted
- `mountainash_settings.auth.oauth2_authcode` — source removed; record deleted
- `mountainash_settings.auth.password` — source removed; record deleted
- `mountainash_settings.auth.service_account` — source removed; record deleted
- `mountainash_settings.auth.token` — source removed; record deleted
- `mountainash_settings.profiles.descriptor` — source removed; record deleted

## Added since previous profile

- `mountainash_settings.profiles._declaration`
- `mountainash_settings.profiles._metaclass`
- `mountainash_settings.profiles._projection`
- `mountainash_settings.profiles.fields`
- `mountainash_settings.profiles.lookup`
- `mountainash_settings.profiles.spec`
- `mountainash_settings.secrets._native`
- `mountainash_settings.secrets._native_posix`
- `mountainash_settings.secrets._native_windows`
- `mountainash_settings.secrets.backend`
- `mountainash_settings.secrets.errors`
- `mountainash_settings.secrets.filesystem`
- `mountainash_settings.secrets.keys`
- `mountainash_settings.secrets.memory`
- `mountainash_settings.secrets.namespaced`
- `mountainash_settings.secrets.records`
- `mountainash_settings.settings._metaclass`
- `mountainash_settings.settings.app._timestamps`
- `mountainash_settings.settings_cache._context`
- `mountainash_settings.settings_cache.sources`

## Low / medium confidence

- `mountainash_settings.settings.app._timestamps` (medium): classification from source structure only
- `mountainash_settings.settings_parameters.merge_framework` (medium): Module name suggests a broader framework than the single exception it contains

## Modules without direct tests

- `mountainash_settings.profiles._metaclass`
- `mountainash_settings.profiles._projection`
- `mountainash_settings.settings._metaclass`
- `mountainash_settings.settings_cache._context`

## Audience coverage

| Audience | Modules | Essential |
|---|---|---|
| users | 14 | 9 |
| maintainers | 33 | 9 |
| extension-authors | 14 | 6 |
| broader-hype | 5 | 5 |

## Notes

- The `auth` subpackage was removed (moved to `mountainash-auth-client`); see `docs/migration-0.1.md`.
- `contributors` and `backend-architecture` lenses are not requested audiences for this profile.
