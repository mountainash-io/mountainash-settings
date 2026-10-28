---
title: Authentication Boundary
description: What mountainash-settings owns and does not own for authentication, how profile emission and secret fields integrate an external auth layer, and where the removed 0.x auth names went.
generated_by: claude skill chapter-content-generator
date: 2026-06-03
version: 0.08
---

# Authentication Boundary

mountainash-settings does not implement authentication. Since 0.1 it bundles no auth models, no discriminated auth union, no OAuth flows, and no auth-mode selection or validation; the `auth/` subtree, `auth_modes` and `auth_to_driver_kwargs()` were removed and have no compatibility shims. Authentication models and credential rendering are owned by the separate `mountainash-auth-client` package. Settings supplies the generic pieces an auth layer plugs into: profile declarations, secret handling, and target-aware kwargs emission.

<!-- concept:97 -->
## Authentication Ownership Boundary

| Concern | Owner |
|---|---|
| Auth models, mode taxonomy, OAuth flows | `mountainash-auth-client` |
| Choosing and validating an auth mode | the consuming application or auth package |
| Declaring connection fields (host, user, password, token) | `Profile` / `ProfileSpec` in Settings |
| Mapping fields to driver or SDK keyword arguments | Settings (`driver_key`, `Profile.emit`) |
| Resolving `secret:` references from a bound store | Settings (see [Secrets Resolution](../05-secrets-resolution/index.md)) |
| Rendering credentials for a specific client | an adapter registered in `__adapters__` |

Settings provides Profile declarations, parameter-to-kwargs mappings, secret-store integration and target-aware emission. It does not interpret what a field means for authentication. A `ProfileSpec` subclass may carry domain metadata such as a `supported_auth` field, and the test suite does exactly that, but Settings attaches no built-in semantics to it: it is stored on the spec and nothing in this package reads it. Any meaning is a convention of the domain package that declares it.

<!-- concept:85 -->
## Adapter Credential Rendering

An auth layer integrates through `Profile.emit(target, base=...)`. Emission layers the profile's mapped fields over the caller-owned `base` kwargs, then calls the adapter registered for that target in the plural class variable `__adapters__` (`{target: adapter}`), where `adapter(profile, kwargs)` returns the final dict. The details are in [Target-Aware Emission](../06-connection-profiles/index.md#target-aware-emission); the points that matter at the auth boundary are:

- **Fail-closed targets.** A profile with an adapter or a `dict` `driver_key` is target-scoped. `emit()` with no target, or with a target the profile does not know, raises `ValueError` rather than returning a partial dict.
- **Copy nested values.** `emit()` takes only a shallow copy of `base`. An adapter that changes a nested container (such as `headers`) must copy it first so the caller's `base` is not mutated.
- **Secret-bearing fields.** Declare credentials as `SecretStr` fields (or `secret=True` on a `ParameterSpec`). The instance masks them, but emission unwraps them with `get_secret_value()`. A field set to a `secret:` reference is resolved through the bound secret store before the profile holds it; with no bound store resolution fails with `SecretCapabilityError`.
- **Fields excluded from mapping.** `driver_key=None` keeps a field out of the default mapping, so only an adapter can place it in the output.

```python
from pydantic import SecretStr
from mountainash_settings import Profile, ProfileField


def http_client(profile, kwargs):
    # Copy the nested dict before changing it; base is caller-owned.
    headers = {**kwargs.get("headers", {})}
    headers["Authorization"] = "Bearer " + profile.TOKEN.get_secret_value()
    return {**kwargs, "headers": headers}


class Service(Profile, name="service", provider_type="http"):
    HOST: str = ProfileField(default="api.example.test", driver_key="host")
    PASSWORD: SecretStr | None = ProfileField(default=None, driver_key={"driver": "password"})
    TOKEN: SecretStr = ProfileField(driver_key=None)
    __adapters__ = {"http": http_client, "driver": lambda profile, kwargs: kwargs}


svc = Service(PASSWORD="example-password", TOKEN="example-token")
base = {"headers": {"X-Client": "report"}}
print(repr(svc.PASSWORD))
print(svc.emit("driver"))
print(svc.emit("http", base=base))
print(base)
# SecretStr('**********')
# {'host': 'api.example.test', 'password': 'example-password'}
# {'headers': {'X-Client': 'report', 'Authorization': 'Bearer example-token'}, 'host': 'api.example.test'}
# {'headers': {'X-Client': 'report'}}
```

Calling `svc.emit()` here raises `ValueError: Service is target-scoped; call emit(<target>).`

**Warning.** Emitted kwargs contain plaintext credentials. Do not log them, include them in error messages, or persist them. The masking on the profile instance does not apply to the dict that `emit()` returns.

## Migrating From 0.x

Code written against 0.x that imports any of the following will fail to import on 0.1; look for these names and move to `mountainash-auth-client`:

- `auth_modes` on `ProfileSpec`, and the generated `auth` discriminated-union field
- `auth_to_driver_kwargs()` and `Profile._auth_kwargs()`
- `AuthSpec` and the concrete auth-mode classes (`NoneAuth`, `PasswordAuth`, `TokenAuth`, the OAuth, IAM, Azure AD, Kerberos, certificate and service-account modes)

Plain credential fields keep working as ordinary secret-bearing profile fields. The rest of the migration is covered in the 0.1 migration guide (`docs/migration-0.1.md`).
