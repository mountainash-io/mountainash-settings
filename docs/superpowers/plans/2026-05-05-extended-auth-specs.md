# Extended Auth Specs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add OAuth2AuthCodeAuth and OAuth1Auth specs to the auth module, promoting local definitions from mountainash-wearables into the shared library.

**Architecture:** Two new frozen Pydantic models extending AuthSpec with Literal discriminators. Integrated into existing exports; no dispatch entries.

**Tech Stack:** Python 3.12, Pydantic 2.9.2, pytest 8.3.5

---

### Task 1: OAuth2AuthCodeAuth — test and implementation

**Files:**
- Create: `src/mountainash_settings/auth/oauth2_authcode.py`
- Test: `tests/unit/auth/test_subclasses.py` (modify)

- [ ] **Step 1: Write the failing tests**

Add to `tests/unit/auth/test_subclasses.py`:

```python
# Add to imports at top:
from mountainash_settings.auth import OAuth2AuthCodeAuth

# Add to TestAuthDiscriminator parametrize list:
(OAuth2AuthCodeAuth, "oauth2_authcode"),

# Update the test_every_auth_has_discriminator_kind body to handle the new required-fields class:
elif cls is OAuth2AuthCodeAuth:
    instance = cls(client_id="cid", client_secret=SecretStr("csec"))

# Add new test class after TestOAuth2Auth:
@pytest.mark.unit
class TestOAuth2AuthCodeAuth:
    def test_requires_client_id_and_secret(self):
        with pytest.raises(ValidationError):
            OAuth2AuthCodeAuth()  # type: ignore[call-arg]

    def test_client_secret_is_secretstr(self):
        auth = OAuth2AuthCodeAuth(client_id="cid", client_secret="secret")
        assert isinstance(auth.client_secret, SecretStr)
        assert auth.client_secret.get_secret_value() == "secret"

    def test_optional_fields_default_none(self):
        auth = OAuth2AuthCodeAuth(client_id="cid", client_secret="s")
        assert auth.access_token is None
        assert auth.refresh_token is None
        assert auth.token_expires_at is None
        assert auth.scope is None

    def test_access_token_is_secretstr(self):
        auth = OAuth2AuthCodeAuth(
            client_id="cid", client_secret="s", access_token="tok"
        )
        assert isinstance(auth.access_token, SecretStr)

    def test_token_expires_at_accepts_int(self):
        auth = OAuth2AuthCodeAuth(
            client_id="cid", client_secret="s", token_expires_at=1714900000
        )
        assert auth.token_expires_at == 1714900000
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `hatch run test:test tests/unit/auth/test_subclasses.py -v`
Expected: ImportError — `cannot import name 'OAuth2AuthCodeAuth'`

- [ ] **Step 3: Write the implementation**

Create `src/mountainash_settings/auth/oauth2_authcode.py`:

```python
"""OAuth 2.0 Authorization Code grant authentication."""

from __future__ import annotations

import typing as t

from pydantic import SecretStr

from .base import AuthSpec

__all__ = ["OAuth2AuthCodeAuth"]


class OAuth2AuthCodeAuth(AuthSpec):
    """OAuth 2.0 Authorization Code grant credentials and tokens."""

    kind: t.Literal["oauth2_authcode"] = "oauth2_authcode"
    client_id: str
    client_secret: SecretStr
    access_token: SecretStr | None = None
    refresh_token: SecretStr | None = None
    token_expires_at: int | None = None
    scope: str | None = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `hatch run test:test tests/unit/auth/test_subclasses.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_settings/auth/oauth2_authcode.py tests/unit/auth/test_subclasses.py
git commit -m "feat(auth): add OAuth2AuthCodeAuth spec with tests"
```

---

### Task 2: OAuth1Auth — test and implementation

**Files:**
- Create: `src/mountainash_settings/auth/oauth1.py`
- Test: `tests/unit/auth/test_subclasses.py` (modify)

- [ ] **Step 1: Write the failing tests**

Add to `tests/unit/auth/test_subclasses.py`:

```python
# Add to imports:
from mountainash_settings.auth import OAuth1Auth

# Add to TestAuthDiscriminator parametrize list:
(OAuth1Auth, "oauth1"),

# Update the test_every_auth_has_discriminator_kind body:
elif cls is OAuth1Auth:
    instance = cls(consumer_key="ck", consumer_secret=SecretStr("cs"))

# Add new test class:
@pytest.mark.unit
class TestOAuth1Auth:
    def test_requires_consumer_key_and_secret(self):
        with pytest.raises(ValidationError):
            OAuth1Auth()  # type: ignore[call-arg]

    def test_consumer_secret_is_secretstr(self):
        auth = OAuth1Auth(consumer_key="ck", consumer_secret="secret")
        assert isinstance(auth.consumer_secret, SecretStr)
        assert auth.consumer_secret.get_secret_value() == "secret"

    def test_optional_fields_default_none(self):
        auth = OAuth1Auth(consumer_key="ck", consumer_secret="s")
        assert auth.access_token is None
        assert auth.access_token_secret is None

    def test_access_token_is_secretstr(self):
        auth = OAuth1Auth(
            consumer_key="ck", consumer_secret="s", access_token="tok"
        )
        assert isinstance(auth.access_token, SecretStr)

    def test_access_token_secret_is_secretstr(self):
        auth = OAuth1Auth(
            consumer_key="ck", consumer_secret="s", access_token_secret="sec"
        )
        assert isinstance(auth.access_token_secret, SecretStr)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `hatch run test:test tests/unit/auth/test_subclasses.py -v`
Expected: ImportError — `cannot import name 'OAuth1Auth'`

- [ ] **Step 3: Write the implementation**

Create `src/mountainash_settings/auth/oauth1.py`:

```python
"""OAuth 1.0a authentication."""

from __future__ import annotations

import typing as t

from pydantic import SecretStr

from .base import AuthSpec

__all__ = ["OAuth1Auth"]


class OAuth1Auth(AuthSpec):
    """OAuth 1.0a credentials and tokens."""

    kind: t.Literal["oauth1"] = "oauth1"
    consumer_key: str
    consumer_secret: SecretStr
    access_token: SecretStr | None = None
    access_token_secret: SecretStr | None = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `hatch run test:test tests/unit/auth/test_subclasses.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_settings/auth/oauth1.py tests/unit/auth/test_subclasses.py
git commit -m "feat(auth): add OAuth1Auth spec with tests"
```

---

### Task 3: Export integration

**Files:**
- Modify: `src/mountainash_settings/auth/__init__.py`
- Modify: `src/mountainash_settings/__init__.py`
- Test: `tests/unit/test_public_api.py` (verify existing public API test picks them up)

- [ ] **Step 1: Update auth/__init__.py**

Add imports and `__all__` entries:

```python
# Add imports (alphabetical position):
from .oauth2_authcode import OAuth2AuthCodeAuth
from .oauth1 import OAuth1Auth

# Add to __all__ (alphabetical position):
"OAuth1Auth",
"OAuth2AuthCodeAuth",
```

- [ ] **Step 2: Update top-level __init__.py**

Add to the `from .auth import (...)` block:

```python
OAuth1Auth,
OAuth2AuthCodeAuth,
```

Add to `__all__` under the `# Auth` section:

```python
"OAuth1Auth",
"OAuth2AuthCodeAuth",
```

- [ ] **Step 3: Run full test suite**

Run: `hatch run test:test -v`
Expected: All PASS, including any public API surface tests

- [ ] **Step 4: Commit**

```bash
git add src/mountainash_settings/auth/__init__.py src/mountainash_settings/__init__.py
git commit -m "feat(auth): export OAuth2AuthCodeAuth and OAuth1Auth from package"
```

---

### Task 4: Final verification

- [ ] **Step 1: Run full test suite with coverage**

Run: `hatch run test:cov`
Expected: All pass, new files have coverage

- [ ] **Step 2: Run linter**

Run: `hatch run ruff:check`
Expected: No errors

- [ ] **Step 3: Run type checker**

Run: `hatch run mypy:check`
Expected: No errors on new files
