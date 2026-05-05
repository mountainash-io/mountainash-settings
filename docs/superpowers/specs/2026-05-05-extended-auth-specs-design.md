# Extended Auth Specs: OAuth2AuthCodeAuth + OAuth1Auth

**Date:** 2026-05-05
**Requested by:** mountainash-wearables
**Branch:** feature/auth-oauth-specs

## Summary

Add two new AuthSpec subclasses to mountainash-settings, promoting local definitions from mountainash-wearables into the shared library.

## Specs

### OAuth2AuthCodeAuth

OAuth 2.0 Authorization Code grant with expiry tracking. Distinct from existing `OAuth2Auth` which targets client-credentials/static-token flows.

```python
class OAuth2AuthCodeAuth(AuthSpec):
    kind: Literal["oauth2_authcode"] = "oauth2_authcode"
    client_id: str                        # required
    client_secret: SecretStr              # required
    access_token: SecretStr | None = None
    refresh_token: SecretStr | None = None
    token_expires_at: int | None = None   # unix timestamp
    scope: str | None = None
```

File: `src/mountainash_settings/auth/oauth2_authcode.py`

### OAuth1Auth

OAuth 1.0a credentials and tokens. Required for Garmin Health API and legacy integrations.

```python
class OAuth1Auth(AuthSpec):
    kind: Literal["oauth1"] = "oauth1"
    consumer_key: str                          # required
    consumer_secret: SecretStr                 # required
    access_token: SecretStr | None = None
    access_token_secret: SecretStr | None = None
```

File: `src/mountainash_settings/auth/oauth1.py`

## Integration

1. Both classes added to `src/mountainash_settings/auth/__init__.py` exports
2. Both classes added to `src/mountainash_settings/__init__.py` exports and `__all__`
3. No dispatch entries — consumers handle their own mapping

## Tests

Added to `tests/unit/auth/test_subclasses.py`:

- Parametrized discriminator test extended with both new kinds
- `TestOAuth2AuthCodeAuth`:
  - `client_id` and `client_secret` are required (ValidationError without them)
  - `client_secret` wrapped as SecretStr
  - Optional fields default to None
  - `token_expires_at` accepts int
- `TestOAuth1Auth`:
  - `consumer_key` and `consumer_secret` are required
  - `consumer_secret` wrapped as SecretStr
  - Optional fields default to None

Frozen immutability and extra-field rejection are already covered by existing base tests.

## Out of Scope

- Dispatch map entries (consumers handle auth-to-driver mapping)
- Token refresh logic (lives in mountainash-wearables)
- Migration of mountainash-wearables imports (separate PR after version bump)
