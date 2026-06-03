---
title: Authentication System
description: The pluggable authentication system covering 11 auth modes as a discriminated union, the AuthSpec base class, dispatch function, driver kwargs mapping, and custom extension.
generated_by: claude skill chapter-content-generator
date: 2026-06-03
version: 0.08
---

# Authentication System

## Summary

This chapter covers the pluggable authentication system that provides 11 concrete auth modes as a discriminated union. You will learn about the AuthSpec base class with its kind literal, how the discriminated union is assembled, the auth dispatch function and driver kwargs mapping, default auth kwargs, and each concrete mode: NoneAuth, PasswordAuth, TokenAuth, OAuth2 Client Credentials, OAuth1, OAuth2 Auth Code, IAM, Azure AD, Kerberos, Certificate, and Service Account. The chapter concludes with auth mode selection in profiles and extending the system with custom auth modes.

## Concepts Covered

- AuthSpec Base Class
- Auth Kind Literal
- Auth Discriminated Union
- Auth Dispatch Function
- Auth To Driver Kwargs Map
- Default Auth Kwargs
- NoneAuth Mode
- PasswordAuth Mode
- TokenAuth Mode
- OAuth2 Client Credentials Mode
- OAuth1 Mode
- OAuth2 Auth Code Mode
- IAM Auth Mode
- Azure AD Auth Mode
- Kerberos Auth Mode
- Certificate Auth Mode
- Service Account Auth Mode
- Auth Mode Selection In Profile
- Custom Auth Mode Extension

## Prerequisites

- Chapter 1: Pydantic and Configuration Foundations
- Chapter 6: Connection Profiles (for Auth Mode Selection In Profile)

---

## The Authentication Challenge

Every external system that requires credentials presents the configuration framework with a modeling challenge: different systems support different authentication mechanisms, and a single system might support multiple mechanisms (PostgreSQL accepts both password and certificate auth, for instance). The authentication system needs to be type-safe (each mode has its own set of required fields), extensible (new modes can be added without modifying existing code), and parseable from configuration files (YAML, TOML, or JSON).

mountainash-settings solves this with a discriminated union architecture: each auth mode is a Pydantic model with a `kind` literal field, and the profile system assembles these modes into a tagged union that Pydantic can efficiently parse and validate.

## AuthSpec Base Class

The **AuthSpec** base class is a Pydantic `BaseModel` that establishes the contract for all authentication modes. Every auth mode inherits from `AuthSpec` and declares its own fields alongside the shared `kind` discriminator field.

The base class provides the structural foundation:

```python
from pydantic import BaseModel
from typing import Literal

class AuthSpec(BaseModel):
    """Base class for all authentication specifications."""
    kind: str  # overridden by each concrete mode with a Literal type
```

Each concrete subclass narrows the `kind` field to a specific `Literal` value, creating a tag that Pydantic uses for discriminated union dispatch. The base class itself is abstract in practice -- it is never instantiated directly, only through its subclasses.

The `AuthSpec` base depends on two foundation concepts: `BaseModel` for data validation and `Discriminated Unions` for efficient tagged parsing. This dual dependency means that the auth system gets Pydantic's full validation pipeline (type coercion, `SecretStr` wrapping, field validators) plus O(1) dispatch based on the `kind` field.

## Auth Kind Literal

The **auth kind literal** is the discriminator value that identifies which authentication mode is active. Each concrete auth mode declares `kind` as a `Literal` type constrained to a single string value:

```python
class PasswordAuth(AuthSpec):
    kind: Literal["password"] = "password"
    username: str
    password: SecretStr

class TokenAuth(AuthSpec):
    kind: Literal["token"] = "token"
    token: SecretStr
```

The kind literal serves three purposes:

- **Discrimination** -- Pydantic reads `kind` first to select the correct variant
- **Serialization** -- the `kind` field appears in YAML/JSON config, making the auth mode explicit
- **Type narrowing** -- after parsing, type checkers know exactly which variant is active

In configuration files, users specify the auth mode naturally:

```yaml
auth:
  kind: password
  username: admin
  password: secret:db/prod/admin_pw
```

## Auth Discriminated Union

The **auth discriminated union** is the type that combines multiple auth modes into a single field. The `Profile` base class constructs this union automatically from the `auth_modes` list on the `ProfileSpec`:

```python
# During dynamic field installation in Profile.__pydantic_init_subclass__:
if spec.auth_modes:
    if len(spec.auth_modes) == 1:
        auth_union = spec.auth_modes[0]
        auth_info = FieldInfo(annotation=auth_union, default=...)
    else:
        auth_union = Union[tuple(spec.auth_modes)]
        auth_info = FieldInfo(
            annotation=auth_union,
            default=...,
            discriminator="kind",
        )
    new_fields["auth"] = (auth_union, auth_info)
```

When a spec declares multiple auth modes, the union uses `discriminator="kind"` so that Pydantic reads the `kind` field from the input data to determine which variant to validate against. When only one auth mode is declared, no discriminator is needed -- the field is typed directly as that single mode.

#### Diagram: Auth Discriminated Union Dispatch

<iframe src="../../sims/auth-union-dispatch/main.html" width="100%" height="500px" scrolling="no"></iframe>
<details markdown="1">
<summary>Auth Discriminated Union Dispatch</summary>
Type: workflow
**sim-id:** auth-union-dispatch<br/>
**Library:** vis-network<br/>
**Status:** Specified

A flow diagram showing YAML/JSON input entering a "Read kind field" decision node. From there, branches lead to each of the 11 auth mode variants. Each variant node shows its required fields. Clicking a variant highlights its fields and shows an example YAML snippet. A dropdown selector at the top lets users choose which auth mode to trace through the dispatch. Invalid kind values show the error path. Learning objective: Trace how Pydantic dispatches to the correct auth mode variant based on the kind discriminator (Bloom: Apply).
</details>

## Auth Dispatch Function

The **auth dispatch function** is a profile-level method that resolves the configured auth mode into driver-compatible keyword arguments. After Pydantic parses the `auth` field into the correct variant, the dispatch function reads the variant's fields and produces the kwargs that a connection driver expects.

The dispatch pattern typically follows this structure:

```python
def _auth_kwargs(self) -> dict[str, Any]:
    auth = self.auth
    if isinstance(auth, PasswordAuth):
        return {
            "user": auth.username,
            "password": auth.password.get_secret_value(),
        }
    elif isinstance(auth, TokenAuth):
        return {
            "token": auth.token.get_secret_value(),
        }
    elif isinstance(auth, NoneAuth):
        return {}
    # ... additional modes
```

Each branch handles the specific field layout of its auth mode. Secret fields are unwrapped via `.get_secret_value()` at this boundary -- the auth dispatch is where secrets cross from the protected settings domain to the driver domain.

## Auth To Driver Kwargs Map

The **auth to driver kwargs map** is a mapping (typically a dictionary or a method) that translates auth mode fields to driver keyword argument names. Different drivers expect different parameter names for the same concept:

| Auth Field | psycopg2 kwarg | SQLAlchemy kwarg | Redis kwarg |
|------------|---------------|-----------------|-------------|
| `username` | `user` | `username` | `username` |
| `password` | `password` | `password` | `password` |
| `token` | N/A | `token` | `password` |

The mapping is driver-specific and is typically defined in the domain package (e.g., mountainash-data) rather than in mountainash-settings itself. The settings framework provides the auth mode data structure; the domain package provides the translation to driver kwargs.

## Default Auth Kwargs

**Default auth kwargs** are the authentication parameters that a profile emits when no explicit auth dispatch override is provided. The `_default_kwargs()` method on `Profile` handles parameter-level kwargs (host, port, etc.) but delegates auth-level kwargs to the `_auth_kwargs()` method.

When a profile does not override `_auth_kwargs()`, the default implementation returns the auth mode's fields using a generic mapping. Profiles that need driver-specific translation override this method to provide the correct mapping for their target driver.

## The Eleven Auth Modes

mountainash-settings defines eleven concrete authentication modes that cover the most common authentication patterns across database, API, and cloud service connections. Each mode is a Pydantic model with its own set of typed, validated fields.

### NoneAuth Mode

**NoneAuth** represents connections that require no authentication. It is the simplest mode, containing only the `kind` discriminator:

```python
class NoneAuth(AuthSpec):
    kind: Literal["none"] = "none"
```

NoneAuth is required in every profile's `auth_modes` list when the backend supports unauthenticated connections (e.g., local development databases, public APIs). The invariant system enforces that `auth_modes` is never empty -- profiles that truly need no auth still declare `[NoneAuth]`.

### PasswordAuth Mode

**PasswordAuth** is the traditional username/password credential pair, the most widely supported authentication mechanism:

```python
class PasswordAuth(AuthSpec):
    kind: Literal["password"] = "password"
    username: str
    password: SecretStr
```

The `password` field is typed as `SecretStr`, ensuring it is masked in logs and serialization. The auth dispatch unwraps it via `.get_secret_value()` only at the driver boundary.

### TokenAuth Mode

**TokenAuth** represents bearer token authentication, common with REST APIs and cloud services:

```python
class TokenAuth(AuthSpec):
    kind: Literal["token"] = "token"
    token: SecretStr
```

### OAuth2 Client Credentials Mode

**OAuth2 Client Credentials** supports the OAuth2 client credentials grant, used for machine-to-machine communication:

```python
class OAuth2ClientCredentials(AuthSpec):
    kind: Literal["oauth2_client_credentials"] = "oauth2_client_credentials"
    client_id: str
    client_secret: SecretStr
    token_url: str
    scopes: list[str] = []
```

### OAuth1 Mode

**OAuth1** supports the older OAuth 1.0a protocol, still required by some legacy APIs (notably parts of the Twitter/X API):

```python
class OAuth1Auth(AuthSpec):
    kind: Literal["oauth1"] = "oauth1"
    consumer_key: str
    consumer_secret: SecretStr
    access_token: str
    access_token_secret: SecretStr
```

### OAuth2 Auth Code Mode

**OAuth2 Auth Code** supports the authorization code grant flow, used for user-delegated access:

```python
class OAuth2AuthCode(AuthSpec):
    kind: Literal["oauth2_auth_code"] = "oauth2_auth_code"
    client_id: str
    client_secret: SecretStr
    auth_url: str
    token_url: str
    redirect_uri: str
    scopes: list[str] = []
```

### IAM Auth Mode

**IAM Auth** supports AWS IAM role-based authentication, where credentials are derived from the instance's IAM role rather than explicit secrets:

```python
class IAMAuth(AuthSpec):
    kind: Literal["iam"] = "iam"
    region: str | None = None
    profile: str | None = None
```

### Azure AD Auth Mode

**Azure AD Auth** supports Microsoft Entra ID (Azure AD) token-based authentication:

```python
class AzureADAuth(AuthSpec):
    kind: Literal["azure_ad"] = "azure_ad"
    tenant_id: str
    client_id: str
    client_secret: SecretStr | None = None
    resource: str | None = None
```

### Kerberos Auth Mode

**Kerberos Auth** supports Kerberos/GSSAPI ticket-based authentication, common in enterprise environments:

```python
class KerberosAuth(AuthSpec):
    kind: Literal["kerberos"] = "kerberos"
    principal: str | None = None
    keytab: str | None = None
```

### Certificate Auth Mode

**Certificate Auth** supports mutual TLS (mTLS) authentication using client certificates:

```python
class CertificateAuth(AuthSpec):
    kind: Literal["certificate"] = "certificate"
    cert_path: str
    key_path: SecretStr
    ca_path: str | None = None
```

### Service Account Auth Mode

**Service Account Auth** supports Google Cloud service account authentication via JSON key files:

```python
class ServiceAccountAuth(AuthSpec):
    kind: Literal["service_account"] = "service_account"
    key_file: SecretStr
    project_id: str | None = None
```

The following table summarizes all eleven modes with their key characteristics:

| Mode | Kind Literal | Has Secrets | Primary Use Case |
|------|-------------|-------------|-----------------|
| NoneAuth | `"none"` | No | Local dev, public APIs |
| PasswordAuth | `"password"` | Yes | Databases, basic HTTP auth |
| TokenAuth | `"token"` | Yes | REST APIs, bearer tokens |
| OAuth2 Client Credentials | `"oauth2_client_credentials"` | Yes | Machine-to-machine APIs |
| OAuth1 | `"oauth1"` | Yes | Legacy APIs (Twitter/X) |
| OAuth2 Auth Code | `"oauth2_auth_code"` | Yes | User-delegated access |
| IAM Auth | `"iam"` | No | AWS services |
| Azure AD Auth | `"azure_ad"` | Optional | Azure/Microsoft services |
| Kerberos Auth | `"kerberos"` | No | Enterprise/Active Directory |
| Certificate Auth | `"certificate"` | Yes | mTLS, database TLS |
| Service Account Auth | `"service_account"` | Yes | Google Cloud services |

#### Diagram: Auth Mode Taxonomy

<iframe src="../../sims/auth-mode-taxonomy/main.html" width="100%" height="550px" scrolling="no"></iframe>
<details markdown="1">
<summary>Auth Mode Taxonomy</summary>
Type: graph-model
**sim-id:** auth-mode-taxonomy<br/>
**Library:** vis-network<br/>
**Status:** Specified

A hierarchical tree showing AuthSpec at the root, with 11 child nodes for each auth mode. Nodes are colored by category: green for credential-free modes (NoneAuth, IAM, Kerberos), blue for secret-bearing modes (Password, Token, Certificate), orange for OAuth modes (OAuth1, OAuth2 CC, OAuth2 AC), purple for cloud-provider modes (Azure AD, Service Account). Clicking a node shows its fields, kind literal, and example YAML config. Hovering shows the primary use case. A filter bar at the top lets users show/hide categories. Learning objective: Classify authentication modes by their credential patterns and use cases (Bloom: Analyze).
</details>

## Auth Mode Selection In Profile

**Auth mode selection in profile** is the mechanism by which a `ProfileSpec` declares which auth modes are valid for a given backend. The `auth_modes` list on `ProfileSpec` controls which variants appear in the generated discriminated union:

```python
POSTGRESQL_SPEC = ProfileSpec(
    name="postgresql",
    provider_type=DatabaseType.POSTGRESQL,
    parameters=[...],
    auth_modes=[PasswordAuth, CertificateAuth, KerberosAuth],
)
```

When this spec is installed on a `Profile` subclass, the `auth` field becomes:

```python
auth: Annotated[
    Union[PasswordAuth, CertificateAuth, KerberosAuth],
    Field(discriminator="kind")
]
```

This means a PostgreSQL profile only accepts `kind: password`, `kind: certificate`, or `kind: kerberos` in its configuration. Attempting to configure `kind: oauth2_client_credentials` would produce a Pydantic validation error -- the discriminated union rejects variants not in the declared set.

The auth mode selection integrates with the invariant system: the `test_auth_modes_nonempty` invariant ensures every spec declares at least one auth mode (use `[NoneAuth]` for backends that support unauthenticated access).

## Custom Auth Mode Extension

**Custom auth mode extension** is the process of creating a new auth mode for a system that does not fit the eleven built-in modes. The extension process requires three steps:

1. Define a new `AuthSpec` subclass with a unique `kind` literal
2. Add it to the appropriate `ProfileSpec`'s `auth_modes` list
3. Handle it in the profile's `_auth_kwargs()` dispatch method

```python
class APIKeyAuth(AuthSpec):
    kind: Literal["api_key"] = "api_key"
    header_name: str = "X-API-Key"
    api_key: SecretStr

# Include in a profile spec
MY_API_SPEC = ProfileSpec(
    name="my_api",
    provider_type="rest_api",
    parameters=[...],
    auth_modes=[NoneAuth, TokenAuth, APIKeyAuth],  # custom mode included
)
```

The custom mode automatically participates in the discriminated union, inherits Pydantic validation, and is covered by the invariant system. No changes to the framework are required -- the auth system is open for extension without modification.

The extension relies on two principles from Chapter 1: the `kind` literal (a Literal type that uniquely tags the variant) and the discriminated union (which Pydantic assembles from the `auth_modes` list). As long as the custom mode follows these patterns, it integrates seamlessly.

#### Diagram: Custom Auth Mode Extension Flow

<iframe src="../../sims/custom-auth-extension/main.html" width="100%" height="450px" scrolling="no"></iframe>
<details markdown="1">
<summary>Custom Auth Mode Extension Flow</summary>
Type: workflow
**sim-id:** custom-auth-extension<br/>
**Library:** vis-network<br/>
**Status:** Specified

A three-step workflow showing the extension process: (1) Define AuthSpec subclass with unique kind literal, (2) Add to ProfileSpec.auth_modes list, (3) Handle in _auth_kwargs() dispatch. Each step shows before/after code snippets. After all three steps, the diagram shows the updated discriminated union including the custom mode, and an example YAML config using the new mode. An "Add Mode" button lets users type a custom kind and see it integrated into the flow. Learning objective: Create a custom auth mode that integrates with the profile system's discriminated union (Bloom: Create).
</details>

## Key Takeaways

- **AuthSpec Base Class** establishes the contract for all auth modes, with each subclass narrowing the `kind` field to a unique literal value.
- **Auth Kind Literal** serves as the discriminator tag that enables O(1) dispatch during Pydantic parsing from YAML/JSON configuration.
- **Auth Discriminated Union** is assembled automatically from `ProfileSpec.auth_modes`, constraining which auth modes a profile accepts.
- **Auth Dispatch Function** translates a parsed auth mode into driver-specific keyword arguments, unwrapping secrets at the boundary.
- **Auth To Driver Kwargs Map** is driver-specific, defined by the domain package rather than the settings framework.
- **Eleven built-in auth modes** cover credential-free, secret-bearing, OAuth, and cloud-provider authentication patterns.
- **Auth Mode Selection In Profile** restricts valid auth modes per backend, with the invariant system enforcing that at least one mode is declared.
- **Custom Auth Mode Extension** requires only three steps: define a subclass with a unique kind literal, add it to auth_modes, and handle it in dispatch.
