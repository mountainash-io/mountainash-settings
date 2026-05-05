# Secrets Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add transparent `secret:` prefix resolution to SettingsParameters so config files and kwargs containing secret references are resolved at `get_settings()` time via a pluggable resolver registry.

**Architecture:** A new `secrets/` module provides a write-once registry mapping provider strings to resolver callables, plus dict-walking and instance-walking helpers. `SettingsParameters` gains a structural `secrets_provider` field. Resolution fires at three points: kwargs before construction, instance fields after construction, and runtime overrides on cache hits.

**Tech Stack:** Python 3.12, Pydantic 2.9.2, pydantic-settings 2.6.1, pytest 8.3.5

---

## File Structure

| File | Responsibility |
|------|---------------|
| **Create:** `src/mountainash_settings/secrets/__init__.py` | Public exports for registry and type alias |
| **Create:** `src/mountainash_settings/secrets/registry.py` | `SecretsResolver` type, `_REGISTRY` dict, register/get/replace/clear functions |
| **Create:** `src/mountainash_settings/secrets/resolve.py` | `resolve_secrets_in_dict()`, `resolve_secrets_on_instance()` |
| **Create:** `tests/unit/secrets/__init__.py` | Test package init |
| **Create:** `tests/unit/secrets/test_registry.py` | Registry unit tests |
| **Create:** `tests/unit/secrets/test_resolve.py` | Resolver unit tests |
| **Modify:** `src/mountainash_settings/settings_parameters/settings_parameters.py` | New `secrets_provider` field, hash/eq/create/merge/to_dict/apply_runtime_overrides |
| **Modify:** `src/mountainash_settings/settings/base_settings.py` | kwargs resolution + post-construction instance resolution + bookkeeping field |
| **Modify:** `src/mountainash_settings/__init__.py` | Export new public API |
| **Modify:** `tests/unit/test_public_api.py` | Smoke test for new exports |
| **Modify:** `tests/test_settings_parameters/test_settings_parameters.py` | secrets_provider field tests |

---

### Task 1: Secrets registry — test and implementation

**Files:**
- Create: `src/mountainash_settings/secrets/__init__.py`
- Create: `src/mountainash_settings/secrets/registry.py`
- Create: `tests/unit/secrets/__init__.py`
- Create: `tests/unit/secrets/test_registry.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/secrets/__init__.py` (empty file) and `tests/unit/secrets/test_registry.py`:

```python
"""Unit tests for the secrets resolver registry."""

import pytest

from mountainash_settings.secrets.registry import (
    SecretsResolver,
    register_secrets_resolver,
    get_secrets_resolver,
    replace_secrets_resolver,
    clear_secrets_registry,
)


@pytest.fixture(autouse=True)
def clean_registry():
    """Ensure every test starts and ends with an empty registry."""
    clear_secrets_registry()
    yield
    clear_secrets_registry()


def _dummy_resolver(path: str) -> str:
    return f"resolved_{path}"


def _other_resolver(path: str) -> str:
    return f"other_{path}"


@pytest.mark.unit
class TestSecretsRegistry:
    def test_register_and_retrieve(self):
        register_secrets_resolver("local", _dummy_resolver)
        assert get_secrets_resolver("local") is _dummy_resolver

    def test_get_unregistered_raises_keyerror(self):
        with pytest.raises(KeyError):
            get_secrets_resolver("nonexistent")

    def test_duplicate_registration_raises_valueerror(self):
        register_secrets_resolver("local", _dummy_resolver)
        with pytest.raises(ValueError):
            register_secrets_resolver("local", _other_resolver)

    def test_replace_overwrites_existing(self):
        register_secrets_resolver("local", _dummy_resolver)
        replace_secrets_resolver("local", _other_resolver)
        assert get_secrets_resolver("local") is _other_resolver

    def test_replace_unregistered_registers(self):
        replace_secrets_resolver("new_provider", _dummy_resolver)
        assert get_secrets_resolver("new_provider") is _dummy_resolver

    def test_clear_removes_all(self):
        register_secrets_resolver("a", _dummy_resolver)
        register_secrets_resolver("b", _other_resolver)
        clear_secrets_registry()
        with pytest.raises(KeyError):
            get_secrets_resolver("a")
        with pytest.raises(KeyError):
            get_secrets_resolver("b")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `hatch run test:test tests/unit/secrets/test_registry.py -v`
Expected: ImportError — `cannot import name 'SecretsResolver' from 'mountainash_settings.secrets.registry'`

- [ ] **Step 3: Write the implementation**

Create `src/mountainash_settings/secrets/registry.py`:

```python
"""Secrets resolver registry — write-once provider mapping."""

from __future__ import annotations

import typing as t

__all__ = [
    "SecretsResolver",
    "register_secrets_resolver",
    "get_secrets_resolver",
    "replace_secrets_resolver",
    "clear_secrets_registry",
]

SecretsResolver = t.Callable[[str], str]

_REGISTRY: dict[str, SecretsResolver] = {}


def register_secrets_resolver(provider: str, resolver: SecretsResolver) -> None:
    if provider in _REGISTRY:
        raise ValueError(
            f"Secrets resolver '{provider}' is already registered. "
            f"Use replace_secrets_resolver() for explicit replacement."
        )
    _REGISTRY[provider] = resolver


def get_secrets_resolver(provider: str) -> SecretsResolver:
    return _REGISTRY[provider]


def replace_secrets_resolver(provider: str, resolver: SecretsResolver) -> None:
    _REGISTRY[provider] = resolver


def clear_secrets_registry() -> None:
    _REGISTRY.clear()
```

Create `src/mountainash_settings/secrets/__init__.py`:

```python
"""Secrets resolver registry and resolution utilities."""

from .registry import (
    SecretsResolver,
    register_secrets_resolver,
    get_secrets_resolver,
    replace_secrets_resolver,
    clear_secrets_registry,
)

__all__ = [
    "SecretsResolver",
    "register_secrets_resolver",
    "get_secrets_resolver",
    "replace_secrets_resolver",
    "clear_secrets_registry",
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `hatch run test:test tests/unit/secrets/test_registry.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_settings/secrets/__init__.py src/mountainash_settings/secrets/registry.py tests/unit/secrets/__init__.py tests/unit/secrets/test_registry.py
git commit -m "feat(secrets): add write-once resolver registry with tests"
```

---

### Task 2: Dict-walking and instance-walking resolvers — test and implementation

**Files:**
- Create: `src/mountainash_settings/secrets/resolve.py`
- Create: `tests/unit/secrets/test_resolve.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/secrets/test_resolve.py`:

```python
"""Unit tests for secret resolution helpers."""

import pytest
from pydantic import Field, SecretStr

from mountainash_settings.secrets.resolve import (
    resolve_secrets_in_dict,
    resolve_secrets_on_instance,
)
from mountainash_settings.settings.base_settings import MountainAshBaseSettings


def _test_resolver(path: str) -> str:
    return f"resolved_{path}"


@pytest.mark.unit
class TestResolveSecretsInDict:
    def test_flat_dict_resolves_prefixed_value(self):
        data = {"PASSWORD": "secret:db/password"}
        result = resolve_secrets_in_dict(data, _test_resolver)
        assert result == {"PASSWORD": "resolved_db/password"}

    def test_nested_dict_resolved_recursively(self):
        data = {"outer": {"inner": "secret:nested/key"}}
        result = resolve_secrets_in_dict(data, _test_resolver)
        assert result == {"outer": {"inner": "resolved_nested/key"}}

    def test_non_string_values_passed_through(self):
        data = {"count": 42, "flag": True, "items": [1, 2, 3]}
        result = resolve_secrets_in_dict(data, _test_resolver)
        assert result == data

    def test_non_prefixed_strings_passed_through(self):
        data = {"name": "plain_value", "host": "localhost"}
        result = resolve_secrets_in_dict(data, _test_resolver)
        assert result == data

    def test_empty_dict_returns_empty(self):
        assert resolve_secrets_in_dict({}, _test_resolver) == {}

    def test_custom_prefix(self):
        data = {"TOKEN": "vault:api/token"}
        result = resolve_secrets_in_dict(data, _test_resolver, prefix="vault:")
        assert result == {"TOKEN": "resolved_api/token"}

    def test_does_not_mutate_input(self):
        data = {"PASSWORD": "secret:db/password"}
        original = dict(data)
        resolve_secrets_in_dict(data, _test_resolver)
        assert data == original


class _SecretTestSettings(MountainAshBaseSettings):
    USERNAME: str = Field(default="admin")
    PASSWORD: str = Field(default="changeme")
    PORT: int = Field(default=5432)


@pytest.mark.unit
class TestResolveSecretsOnInstance:
    def test_resolves_prefixed_string_fields(self):
        instance = _SecretTestSettings(USERNAME="admin", PASSWORD="secret:db/pass")
        resolve_secrets_on_instance(instance, _test_resolver)
        assert instance.PASSWORD == "resolved_db/pass"

    def test_skips_non_string_fields(self):
        instance = _SecretTestSettings(PORT=5432)
        resolve_secrets_on_instance(instance, _test_resolver)
        assert instance.PORT == 5432

    def test_skips_non_prefixed_strings(self):
        instance = _SecretTestSettings(USERNAME="admin", PASSWORD="plaintext")
        resolve_secrets_on_instance(instance, _test_resolver)
        assert instance.PASSWORD == "plaintext"

    def test_resolves_secretstr_field(self):
        """SecretStr fields store the secret: prefix as the secret value."""

        class WithSecretStr(MountainAshBaseSettings):
            TOKEN: SecretStr = Field(default=SecretStr("default"))

        instance = WithSecretStr(TOKEN="secret:api/token")
        resolve_secrets_on_instance(instance, _test_resolver)
        assert instance.TOKEN.get_secret_value() == "resolved_api/token"

    def test_skips_settings_source_bookkeeping_fields(self):
        instance = _SecretTestSettings(USERNAME="admin")
        resolve_secrets_on_instance(instance, _test_resolver)
        assert instance.SETTINGS_CLASS is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `hatch run test:test tests/unit/secrets/test_resolve.py -v`
Expected: ImportError — `cannot import name 'resolve_secrets_in_dict' from 'mountainash_settings.secrets.resolve'`

- [ ] **Step 3: Write the implementation**

Create `src/mountainash_settings/secrets/resolve.py`:

```python
"""Secret reference resolution for dicts and settings instances."""

from __future__ import annotations

import typing as t

from pydantic import SecretStr

if t.TYPE_CHECKING:
    from .registry import SecretsResolver

__all__ = ["resolve_secrets_in_dict", "resolve_secrets_on_instance"]

_SETTINGS_SOURCE_PREFIX = "SETTINGS_SOURCE_"
_SETTINGS_META_FIELDS = {"SETTINGS_CLASS", "SETTINGS_CLASS_NAME"}


def resolve_secrets_in_dict(
    data: dict[str, t.Any],
    resolver: SecretsResolver,
    prefix: str = "secret:",
) -> dict[str, t.Any]:
    resolved: dict[str, t.Any] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            resolved[key] = resolve_secrets_in_dict(value, resolver, prefix)
        elif isinstance(value, str) and value.startswith(prefix):
            secret_path = value[len(prefix):]
            resolved[key] = resolver(secret_path)
        else:
            resolved[key] = value
    return resolved


def resolve_secrets_on_instance(
    instance: t.Any,
    resolver: SecretsResolver,
    prefix: str = "secret:",
) -> None:
    for field_name in instance.model_fields:
        if field_name.startswith(_SETTINGS_SOURCE_PREFIX) or field_name in _SETTINGS_META_FIELDS:
            continue
        value = getattr(instance, field_name)
        if isinstance(value, SecretStr):
            raw = value.get_secret_value()
            if isinstance(raw, str) and raw.startswith(prefix):
                secret_path = raw[len(prefix):]
                setattr(instance, field_name, resolver(secret_path))
        elif isinstance(value, str) and value.startswith(prefix):
            secret_path = value[len(prefix):]
            setattr(instance, field_name, resolver(secret_path))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `hatch run test:test tests/unit/secrets/test_resolve.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_settings/secrets/resolve.py tests/unit/secrets/test_resolve.py
git commit -m "feat(secrets): add dict-walking and instance-walking resolvers with tests"
```

---

### Task 3: SettingsParameters — add secrets_provider field

**Files:**
- Modify: `src/mountainash_settings/settings_parameters/settings_parameters.py`
- Modify: `tests/test_settings_parameters/test_settings_parameters.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_settings_parameters/test_settings_parameters.py`:

```python
# --- Secrets provider tests ---

class TestSecretsProvider:
    def test_default_is_none(self):
        params = SettingsParameters()
        assert params.secrets_provider is None

    def test_create_accepts_secrets_provider(self):
        params = SettingsParameters.create(
            settings_class=MockSettings,
            secrets_provider="local",
        )
        assert params.secrets_provider == "local"

    def test_secrets_provider_in_hash(self):
        params_a = SettingsParameters.create(
            settings_class=MockSettings,
            secrets_provider="local",
        )
        params_b = SettingsParameters.create(
            settings_class=MockSettings,
            secrets_provider="vault",
        )
        assert hash(params_a) != hash(params_b)

    def test_secrets_provider_none_matches_no_provider(self):
        params_a = SettingsParameters.create(settings_class=MockSettings)
        params_b = SettingsParameters.create(
            settings_class=MockSettings,
            secrets_provider=None,
        )
        assert hash(params_a) == hash(params_b)

    def test_secrets_provider_in_eq(self):
        params_a = SettingsParameters.create(
            settings_class=MockSettings,
            secrets_provider="local",
        )
        params_b = SettingsParameters.create(
            settings_class=MockSettings,
            secrets_provider="vault",
        )
        assert params_a != params_b

    def test_to_dict_includes_secrets_provider(self):
        params = SettingsParameters.create(
            settings_class=MockSettings,
            secrets_provider="local",
        )
        d = params.to_dict()
        assert d["secrets_provider"] == "local"

    def test_to_dict_secrets_provider_none(self):
        params = SettingsParameters()
        d = params.to_dict()
        assert d["secrets_provider"] is None

    def test_merge_last_wins(self):
        base = SettingsParameters.create(
            settings_class=MockSettings,
            secrets_provider="local",
        )
        other = SettingsParameters.create(
            settings_class=MockSettings,
            secrets_provider="vault",
        )
        merged = SettingsParameters.merge(base, other)
        assert merged.secrets_provider == "vault"

    def test_merge_prioritise_base(self):
        base = SettingsParameters.create(
            settings_class=MockSettings,
            secrets_provider="local",
        )
        other = SettingsParameters.create(
            settings_class=MockSettings,
            secrets_provider="vault",
        )
        merged = SettingsParameters.merge(base, other, prioritise_base=True)
        assert merged.secrets_provider == "local"

    def test_merge_base_none_takes_other(self):
        base = SettingsParameters.create(settings_class=MockSettings)
        other = SettingsParameters.create(
            settings_class=MockSettings,
            secrets_provider="vault",
        )
        merged = SettingsParameters.merge(base, other)
        assert merged.secrets_provider == "vault"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `hatch run test:test tests/test_settings_parameters/test_settings_parameters.py::TestSecretsProvider -v`
Expected: AttributeError — `SettingsParameters` has no attribute `secrets_provider`

- [ ] **Step 3: Modify SettingsParameters**

In `src/mountainash_settings/settings_parameters/settings_parameters.py`:

**Add field** (after line 51, after `kwargs`):

```python
    secrets_provider: Optional[str] = None
```

**Update `__hash__`** (add `self.secrets_provider` to `hashable_attrs` tuple, line 120-126):

```python
        hashable_attrs = tuple([
            hashable_config_files,
            self.settings_class,
            self.env_prefix,
            self.secrets_dir,
            self.secrets_provider,
            # Deliberately exclude: self.kwargs
        ])
```

**Update `__eq__`** (add comparison, line 152-157):

```python
        return (
            self_hashable_config_files == other_hashable_config_files and
            self.settings_class == other.settings_class and
            self.env_prefix == other.env_prefix and
            self.secrets_dir == other.secrets_dir and
            self.secrets_provider == other.secrets_provider
            # Deliberately exclude: kwargs comparison
        )
```

**Update `create()`** (add `secrets_provider` parameter, lines 172-192):

```python
    @classmethod
    def create(cls,
               config_files: Optional[str|UPath|List[str|UPath]|Tuple[str|UPath]] = None,
               settings_class: Optional[Type[BaseSettings]] = None,
               env_prefix: Optional[str] = None,
               secrets_dir: Optional[str] = None,
               secrets_provider: Optional[str] = None,
               **kwargs: Any
               ) -> 'SettingsParameters':

        resolved_config_files =  SettingsFileHandler.format_config_file_tuple(config_files)
        resolved_kwargs =        SettingsKwargsHandler.format_kwargs_dict(kwargs) if kwargs else None

        return cls(
            config_files=resolved_config_files,
            settings_class=settings_class,
            env_prefix=env_prefix,
            secrets_dir=secrets_dir,
            secrets_provider=secrets_provider,
            kwargs=resolved_kwargs
        )
```

**Update `merge()`** (add secrets_provider merge after `merged_secrets_dir`, before kwargs merge):

```python
        # Secrets provider: simple priority (same as scalars)
        if prioritise_base:
            merged_secrets_provider = base.secrets_provider or other.secrets_provider
        else:
            merged_secrets_provider = other.secrets_provider or base.secrets_provider
```

And pass it to `cls.create()` at the end of `merge()`:

```python
        return cls.create(
            settings_class=merged_class,
            config_files=merged_config_files,
            env_prefix=merged_env_prefix,
            secrets_dir=merged_secrets_dir,
            secrets_provider=merged_secrets_provider,
            **(merged_kwargs or {})
        )
```

**Update `to_dict()`** (line 275-282):

```python
    def to_dict(self) -> Dict[str, Any]:
        return {
            'config_files': list(self.config_files) if self.config_files else None,
            'kwargs': self.get_all_kwargs() if self.kwargs else None,
            'settings_class': self.settings_class,
            'env_prefix': self.env_prefix,
            'secrets_dir': self.secrets_dir,
            'secrets_provider': self.secrets_provider,
        }
```

**Update `apply_runtime_overrides()`** (line 341-367) — add secrets resolution before applying overrides:

```python
    def apply_runtime_overrides(self, cached_settings: BaseSettings) -> BaseSettings:
        if self.kwargs:
            settings_copy = cached_settings.model_copy()
            override_kwargs = self.get_attribute_settings_kwargs()
            if override_kwargs:
                if self.secrets_provider:
                    from ..secrets.registry import get_secrets_resolver
                    from ..secrets.resolve import resolve_secrets_in_dict
                    resolver = get_secrets_resolver(self.secrets_provider)
                    override_kwargs = resolve_secrets_in_dict(override_kwargs, resolver)
                settings_copy.update_settings_from_dict(settings_dict=override_kwargs)
            return settings_copy
        return cached_settings
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `hatch run test:test tests/test_settings_parameters/test_settings_parameters.py -v`
Expected: All PASS (existing tests + new TestSecretsProvider)

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_settings/settings_parameters/settings_parameters.py tests/test_settings_parameters/test_settings_parameters.py
git commit -m "feat(settings_parameters): add secrets_provider structural field"
```

---

### Task 4: MountainAshBaseSettings — wire in secrets resolution

**Files:**
- Modify: `src/mountainash_settings/settings/base_settings.py`

- [ ] **Step 1: Modify `__init__` to resolve kwargs before `super().__init__()`**

In `base_settings.py`, after line 78 (after `valid_pydantic_kwargs` is extracted) and before line 82 (model_config assignments), add:

```python
        # Resolve secret: prefixed values in kwargs before pydantic validation
        if local_settings_params.secrets_provider:
            from mountainash_settings.secrets.registry import get_secrets_resolver
            from mountainash_settings.secrets.resolve import resolve_secrets_in_dict
            _secrets_resolver = get_secrets_resolver(local_settings_params.secrets_provider)
            valid_attribute_kwargs = resolve_secrets_in_dict(valid_attribute_kwargs, _secrets_resolver)
```

- [ ] **Step 2: Add post-construction instance resolution**

After line 125 (`object.__setattr__` for `SETTINGS_SOURCE_SECRETS_DIR`) and before line 128 (`self.post_init()`), add:

```python
        object.__setattr__(self, "SETTINGS_SOURCE_SECRETS_PROVIDER", local_settings_params.secrets_provider)

        # Resolve secret: prefixed values loaded from config files
        if local_settings_params.secrets_provider:
            from mountainash_settings.secrets.registry import get_secrets_resolver
            from mountainash_settings.secrets.resolve import resolve_secrets_on_instance
            _secrets_resolver = get_secrets_resolver(local_settings_params.secrets_provider)
            resolve_secrets_on_instance(self, _secrets_resolver)
```

- [ ] **Step 3: Add the bookkeeping field declaration**

Add to the field declarations (after line 43, `SETTINGS_SOURCE_SECRETS_DIR`):

```python
    SETTINGS_SOURCE_SECRETS_PROVIDER: Optional[str] =                              Field(default=None)
```

- [ ] **Step 4: Update `extract_settings_parameters()`**

In `extract_settings_parameters()` (around line 294-328), add `secrets_provider` to the reconstruction. After `existing_env_prefix` extraction, add:

```python
        existing_secrets_provider = self.SETTINGS_SOURCE_SECRETS_PROVIDER or None
```

And pass it to the `SettingsParameters.create()` call:

```python
        params: SettingsParameters = SettingsParameters.create(
            settings_class=     existing_settings_class,
            config_files=       existing_config_files,
            kwargs=             existing_kwargs,
            env_prefix=         existing_env_prefix,
            secrets_provider=   existing_secrets_provider)
```

- [ ] **Step 5: Run existing tests to verify no regressions**

Run: `hatch run test:test -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/mountainash_settings/settings/base_settings.py
git commit -m "feat(base_settings): wire secrets resolution into init and post-construction"
```

---

### Task 5: Integration tests — kwargs, config file, and cache-hit paths

**Files:**
- Modify: `tests/test_base_settings.py`
- Create: `tests/config/secrets_test.yaml`

- [ ] **Step 1: Create test config file**

Create `tests/config/secrets_test.yaml`:

```yaml
PASSWORD: "secret:db/password"
USERNAME: "admin"
```

- [ ] **Step 2: Write the integration tests**

Add to `tests/test_base_settings.py`:

```python
from mountainash_settings.secrets import (
    register_secrets_resolver,
    clear_secrets_registry,
)


def _test_resolver(path: str) -> str:
    return f"resolved_{path}"


@pytest.fixture
def secrets_registry():
    """Register a test resolver and clean up after."""
    clear_secrets_registry()
    register_secrets_resolver("test", _test_resolver)
    yield
    clear_secrets_registry()


class _SecretsTestSettings(MountainAshBaseSettings):
    USERNAME: str = Field(default="default_user")
    PASSWORD: str = Field(default="default_pass")


class TestSecretsResolution:
    def test_kwargs_secret_resolved_on_construction(self, secrets_registry):
        settings = _SecretsTestSettings(
            settings_parameters=SettingsParameters.create(
                settings_class=_SecretsTestSettings,
                secrets_provider="test",
                PASSWORD="secret:db/password",
            )
        )
        assert settings.PASSWORD == "resolved_db/password"

    def test_config_file_secret_resolved_post_construction(self, secrets_registry):
        settings = _SecretsTestSettings(
            settings_parameters=SettingsParameters.create(
                settings_class=_SecretsTestSettings,
                secrets_provider="test",
                config_files=["tests/config/secrets_test.yaml"],
            )
        )
        assert settings.PASSWORD == "resolved_db/password"
        assert settings.USERNAME == "admin"

    def test_no_provider_leaves_secret_prefix_as_literal(self):
        settings = _SecretsTestSettings(PASSWORD="secret:db/password")
        assert settings.PASSWORD == "secret:db/password"

    def test_cache_hit_runtime_override_resolves_secret(self, secrets_registry):
        from mountainash_settings.settings_cache.settings_functions import _get_settings

        params_base = SettingsParameters.create(
            settings_class=_SecretsTestSettings,
            secrets_provider="test",
            config_files=["tests/config/secrets_test.yaml"],
        )

        # First call — constructs and caches
        settings1 = get_settings(settings_parameters=params_base)
        assert settings1.PASSWORD == "resolved_db/password"

        # Second call — cache hit with runtime override containing a secret ref
        settings2 = get_settings(
            settings_parameters=params_base,
            PASSWORD="secret:other/password",
        )
        assert settings2.PASSWORD == "resolved_other/password"
        # Original cached instance untouched
        assert settings1.PASSWORD == "resolved_db/password"

        # Cleanup: clear the lru_cache entry we just created
        _get_settings.cache_clear()
```

- [ ] **Step 3: Run the integration tests**

Run: `hatch run test:test tests/test_base_settings.py::TestSecretsResolution -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_base_settings.py tests/config/secrets_test.yaml
git commit -m "test(secrets): add integration tests for kwargs, config file, and cache-hit paths"
```

---

### Task 6: Top-level exports and public API smoke test

**Files:**
- Modify: `src/mountainash_settings/__init__.py`
- Modify: `tests/unit/test_public_api.py`

- [ ] **Step 1: Update `src/mountainash_settings/__init__.py`**

Add after the `from .auth import (...)` block:

```python
from .secrets import (
    SecretsResolver,
    register_secrets_resolver,
    get_secrets_resolver,
    replace_secrets_resolver,
    clear_secrets_registry,
)
```

Add to `__all__` (new `# Secrets` section after Auth):

```python
    # Secrets
    "SecretsResolver",
    "register_secrets_resolver",
    "get_secrets_resolver",
    "replace_secrets_resolver",
    "clear_secrets_registry",
```

- [ ] **Step 2: Add public API smoke test**

Add to `tests/unit/test_public_api.py`:

```python
@pytest.mark.unit
def test_secrets_surface_imports():
    from mountainash_settings import (
        SecretsResolver,
        register_secrets_resolver,
        get_secrets_resolver,
        replace_secrets_resolver,
        clear_secrets_registry,
    )
    assert callable(register_secrets_resolver)
    assert callable(get_secrets_resolver)
    assert callable(replace_secrets_resolver)
    assert callable(clear_secrets_registry)
```

- [ ] **Step 3: Run tests**

Run: `hatch run test:test tests/unit/test_public_api.py -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add src/mountainash_settings/__init__.py tests/unit/test_public_api.py
git commit -m "feat(secrets): export public API and add smoke test"
```

---

### Task 7: Final verification

- [ ] **Step 1: Run full test suite with coverage**

Run: `hatch run test:cov`
Expected: All pass, new files have coverage

- [ ] **Step 2: Run linter**

Run: `hatch run ruff:check`
Expected: No errors

- [ ] **Step 3: Run type checker**

Run: `hatch run mypy:check`
Expected: No new errors on new files (pre-existing errors in other files are acceptable)
