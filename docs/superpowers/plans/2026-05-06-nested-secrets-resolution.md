# Nested Model Secrets Resolution — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix unresolved `secret:` references in nested pydantic model fields (like `AuthSpec`) loaded from config files, and separate the general reference resolution mechanism from the secrets domain.

**Architecture:** Move resolution functions from `secrets/resolve.py` to a new top-level `resolve.py`, rename them from `resolve_secrets_*` to `resolve_references_*`, and add recursive model tree walking that rebuilds frozen nested models instead of mutating them in place.

**Tech Stack:** Python 3.12, pydantic 2.9, pydantic-settings 2.6, pytest 8.3

**Spec:** `docs/superpowers/specs/2026-05-06-nested-secrets-resolution-design.md`

---

### Task 1: Create `resolve.py` with renamed + recursive functions

**Files:**
- Create: `src/mountainash_settings/resolve.py`
- Test: `tests/unit/test_resolve.py`

This task creates the new top-level module with both functions: `resolve_references_in_dict` (renamed, same behavior) and `resolve_references_in_model_tree` (renamed + recursive nested model support via rebuild).

- [ ] **Step 1: Write tests for `resolve_references_in_dict`**

These are ports of the existing `test_resolve.py::TestResolveSecretsInDict` tests, targeting the new function name and import path. Create the file `tests/unit/test_resolve.py`:

```python
"""Unit tests for general reference resolution."""

import pytest
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from mountainash_settings.resolve import (
    resolve_references_in_dict,
    resolve_references_in_model_tree,
)
from mountainash_settings.settings.base_settings import MountainAshBaseSettings


def _test_resolver(path: str) -> str:
    return f"resolved_{path}"


@pytest.mark.unit
class TestResolveReferencesInDict:
    def test_flat_dict_resolves_prefixed_value(self):
        data = {"PASSWORD": "secret:db/password"}
        result = resolve_references_in_dict(data, _test_resolver)
        assert result == {"PASSWORD": "resolved_db/password"}

    def test_nested_dict_resolved_recursively(self):
        data = {"outer": {"inner": "secret:nested/key"}}
        result = resolve_references_in_dict(data, _test_resolver)
        assert result == {"outer": {"inner": "resolved_nested/key"}}

    def test_non_string_values_passed_through(self):
        data = {"count": 42, "flag": True, "items": [1, 2, 3]}
        result = resolve_references_in_dict(data, _test_resolver)
        assert result == data

    def test_non_prefixed_strings_passed_through(self):
        data = {"name": "plain_value", "host": "localhost"}
        result = resolve_references_in_dict(data, _test_resolver)
        assert result == data

    def test_empty_dict_returns_empty(self):
        assert resolve_references_in_dict({}, _test_resolver) == {}

    def test_custom_prefix(self):
        data = {"TOKEN": "vault:api/token"}
        result = resolve_references_in_dict(data, _test_resolver, prefix="vault:")
        assert result == {"TOKEN": "resolved_api/token"}

    def test_does_not_mutate_input(self):
        data = {"PASSWORD": "secret:db/password"}
        original = dict(data)
        resolve_references_in_dict(data, _test_resolver)
        assert data == original
```

- [ ] **Step 2: Write tests for `resolve_references_in_model_tree` — flat fields (existing behavior)**

Append to `tests/unit/test_resolve.py`:

```python
class _FlatTestSettings(MountainAshBaseSettings):
    USERNAME: str = Field(default="admin")
    PASSWORD: str = Field(default="changeme")
    PORT: int = Field(default=5432)


@pytest.mark.unit
class TestResolveReferencesInModelTreeFlat:
    def test_resolves_prefixed_string_fields(self):
        instance = _FlatTestSettings(USERNAME="admin", PASSWORD="secret:db/pass")
        resolve_references_in_model_tree(instance, _test_resolver)
        assert instance.PASSWORD == "resolved_db/pass"

    def test_skips_non_string_fields(self):
        instance = _FlatTestSettings(PORT=5432)
        resolve_references_in_model_tree(instance, _test_resolver)
        assert instance.PORT == 5432

    def test_skips_non_prefixed_strings(self):
        instance = _FlatTestSettings(USERNAME="admin", PASSWORD="plaintext")
        resolve_references_in_model_tree(instance, _test_resolver)
        assert instance.PASSWORD == "plaintext"

    def test_resolves_secretstr_field(self):
        class WithSecretStr(MountainAshBaseSettings):
            TOKEN: SecretStr = Field(default=SecretStr("default"))

        instance = WithSecretStr(TOKEN="secret:api/token")
        resolve_references_in_model_tree(instance, _test_resolver)
        assert instance.TOKEN.get_secret_value() == "resolved_api/token"

    def test_skips_settings_source_bookkeeping_fields(self):
        instance = _FlatTestSettings(USERNAME="admin")
        resolve_references_in_model_tree(instance, _test_resolver)
        assert instance.SETTINGS_CLASS is not None
```

- [ ] **Step 3: Write tests for `resolve_references_in_model_tree` — nested model support**

Append to `tests/unit/test_resolve.py`:

```python
class _NestedModel(BaseModel):
    """Non-frozen nested model for testing."""
    host: str = "localhost"
    password: str = "changeme"


class _FrozenNestedModel(BaseModel):
    """Frozen nested model (like AuthSpec)."""
    model_config = ConfigDict(frozen=True)
    kind: str = "test"
    token: SecretStr


class _DeepNestedInner(BaseModel):
    model_config = ConfigDict(frozen=True)
    api_key: str = "default"


class _DeepNestedOuter(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str = "outer"
    inner: _DeepNestedInner


class _SettingsWithNested(MountainAshBaseSettings):
    APP_NAME: str = Field(default="test")
    nested: _NestedModel = Field(default_factory=_NestedModel)


class _SettingsWithFrozenNested(MountainAshBaseSettings):
    APP_NAME: str = Field(default="test")
    frozen_nested: _FrozenNestedModel


class _SettingsWithDeepNesting(MountainAshBaseSettings):
    APP_NAME: str = Field(default="test")
    deep: _DeepNestedOuter


@pytest.mark.unit
class TestResolveReferencesInModelTreeNested:
    def test_resolves_nested_model_str_field(self):
        instance = _SettingsWithNested(
            nested={"host": "localhost", "password": "secret:db/pass"}
        )
        resolve_references_in_model_tree(instance, _test_resolver)
        assert instance.nested.password == "resolved_db/pass"
        assert instance.nested.host == "localhost"

    def test_resolves_frozen_nested_model_secretstr_field(self):
        instance = _SettingsWithFrozenNested(
            frozen_nested={"kind": "test", "token": "secret:api/token"}
        )
        resolve_references_in_model_tree(instance, _test_resolver)
        assert instance.frozen_nested.token.get_secret_value() == "resolved_api/token"
        assert instance.frozen_nested.kind == "test"

    def test_frozen_nested_is_new_instance(self):
        instance = _SettingsWithFrozenNested(
            frozen_nested={"kind": "test", "token": "secret:api/token"}
        )
        original_nested = instance.frozen_nested
        resolve_references_in_model_tree(instance, _test_resolver)
        assert instance.frozen_nested is not original_nested

    def test_no_rebuild_when_no_secrets(self):
        instance = _SettingsWithFrozenNested(
            frozen_nested={"kind": "test", "token": "plain_token"}
        )
        original_nested = instance.frozen_nested
        resolve_references_in_model_tree(instance, _test_resolver)
        assert instance.frozen_nested is original_nested

    def test_two_levels_of_nesting(self):
        instance = _SettingsWithDeepNesting(
            deep={"name": "outer", "inner": {"api_key": "secret:deep/key"}}
        )
        resolve_references_in_model_tree(instance, _test_resolver)
        assert instance.deep.inner.api_key == "resolved_deep/key"
        assert instance.deep.name == "outer"

    def test_custom_prefix_on_nested(self):
        instance = _SettingsWithNested(
            nested={"host": "localhost", "password": "vault:db/pass"}
        )
        resolve_references_in_model_tree(instance, _test_resolver, prefix="vault:")
        assert instance.nested.password == "resolved_db/pass"
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `pytest tests/unit/test_resolve.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mountainash_settings.resolve'`

- [ ] **Step 5: Implement `resolve.py`**

Create `src/mountainash_settings/resolve.py`:

```python
"""General-purpose reference resolution for dicts and pydantic model trees.

This module provides the mechanism for resolving prefixed string references
(e.g., ``secret:path/to/value``) in data structures. It is domain-agnostic —
the caller supplies a resolver callable and a prefix string. The ``secrets``
package is one consumer; future reference patterns can reuse the same mechanism.
"""

from __future__ import annotations

import typing as t

from pydantic import BaseModel, SecretStr

__all__ = ["resolve_references_in_dict", "resolve_references_in_model_tree"]

_SETTINGS_SOURCE_PREFIX = "SETTINGS_SOURCE_"
_SETTINGS_META_FIELDS = {"SETTINGS_CLASS", "SETTINGS_CLASS_NAME"}


def resolve_references_in_dict(
    data: dict[str, t.Any],
    resolver: t.Callable[[str], str],
    prefix: str = "secret:",
) -> dict[str, t.Any]:
    resolved: dict[str, t.Any] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            resolved[key] = resolve_references_in_dict(value, resolver, prefix)
        elif isinstance(value, str) and value.startswith(prefix):
            resolved[key] = resolver(value[len(prefix):])
        else:
            resolved[key] = value
    return resolved


def _extract_model_values(
    instance: BaseModel,
    prefix: str,
) -> tuple[dict[str, t.Any], bool]:
    """Extract field values from a BaseModel, unwrapping SecretStr.

    Returns (field_dict, has_references) where has_references is True
    if any string value starts with the given prefix.
    """
    values: dict[str, t.Any] = {}
    has_refs = False
    for field_name in instance.model_fields:
        value = getattr(instance, field_name)
        if isinstance(value, SecretStr):
            raw = value.get_secret_value()
            values[field_name] = raw
            if isinstance(raw, str) and raw.startswith(prefix):
                has_refs = True
        elif isinstance(value, BaseModel):
            inner_values, inner_has_refs = _extract_model_values(value, prefix)
            values[field_name] = inner_values
            if inner_has_refs:
                has_refs = True
        else:
            values[field_name] = value
            if isinstance(value, str) and value.startswith(prefix):
                has_refs = True
    return values, has_refs


def resolve_references_in_model_tree(
    instance: t.Any,
    resolver: t.Callable[[str], str],
    prefix: str = "secret:",
) -> None:
    for field_name in instance.model_fields:
        if field_name.startswith(_SETTINGS_SOURCE_PREFIX) or field_name in _SETTINGS_META_FIELDS:
            continue
        value = getattr(instance, field_name)
        if isinstance(value, BaseModel):
            raw_dict, has_refs = _extract_model_values(value, prefix)
            if has_refs:
                resolved_dict = resolve_references_in_dict(raw_dict, resolver, prefix)
                rebuilt = type(value)(**resolved_dict)
                setattr(instance, field_name, rebuilt)
        elif isinstance(value, SecretStr):
            raw = value.get_secret_value()
            if isinstance(raw, str) and raw.startswith(prefix):
                setattr(instance, field_name, resolver(raw[len(prefix):]))
        elif isinstance(value, str) and value.startswith(prefix):
            setattr(instance, field_name, resolver(value[len(prefix):]))
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/unit/test_resolve.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add src/mountainash_settings/resolve.py tests/unit/test_resolve.py
git commit -m "feat: add resolve.py with recursive model tree resolution"
```

---

### Task 2: Update call sites to use new `resolve.py`

**Files:**
- Modify: `src/mountainash_settings/settings/base_settings.py:82-141`
- Modify: `src/mountainash_settings/settings_parameters/settings_parameters.py:378-382`

This task rewires the three interception points from the old `secrets/resolve.py` imports to the new `resolve.py` imports.

- [ ] **Step 1: Run the full test suite to confirm green baseline**

Run: `pytest tests/ -v --tb=short`
Expected: All PASS

- [ ] **Step 2: Update `base_settings.py` Point 1 (kwargs before construction)**

In `src/mountainash_settings/settings/base_settings.py`, replace lines 82-87:

Old:
```python
        # Resolve secret: prefixed values in kwargs before pydantic validation
        if local_settings_params.secrets_provider:
            from mountainash_settings.secrets.registry import get_secrets_resolver
            from mountainash_settings.secrets.resolve import resolve_secrets_in_dict
            _secrets_resolver = get_secrets_resolver(local_settings_params.secrets_provider)
            valid_attribute_kwargs = resolve_secrets_in_dict(valid_attribute_kwargs, _secrets_resolver)
```

New:
```python
        # Resolve prefixed references (e.g. secret:) in kwargs before pydantic validation
        if local_settings_params.secrets_provider:
            from mountainash_settings.secrets.registry import get_secrets_resolver
            from mountainash_settings.resolve import resolve_references_in_dict
            _secrets_resolver = get_secrets_resolver(local_settings_params.secrets_provider)
            valid_attribute_kwargs = resolve_references_in_dict(valid_attribute_kwargs, _secrets_resolver)
```

- [ ] **Step 3: Update `base_settings.py` Point 2 (instance fields after construction)**

In `src/mountainash_settings/settings/base_settings.py`, replace lines 136-141:

Old:
```python
        # Resolve secret: prefixed values loaded from config files
        if local_settings_params.secrets_provider:
            from mountainash_settings.secrets.registry import get_secrets_resolver as _get_resolver
            from mountainash_settings.secrets.resolve import resolve_secrets_on_instance
            _secrets_resolver = _get_resolver(local_settings_params.secrets_provider)
            resolve_secrets_on_instance(self, _secrets_resolver)
```

New:
```python
        # Resolve prefixed references (e.g. secret:) in fields loaded from config files
        if local_settings_params.secrets_provider:
            from mountainash_settings.secrets.registry import get_secrets_resolver as _get_resolver
            from mountainash_settings.resolve import resolve_references_in_model_tree
            _secrets_resolver = _get_resolver(local_settings_params.secrets_provider)
            resolve_references_in_model_tree(self, _secrets_resolver)
```

- [ ] **Step 4: Update `settings_parameters.py` Point 3 (runtime override kwargs)**

In `src/mountainash_settings/settings_parameters/settings_parameters.py`, replace lines 378-382 inside `apply_runtime_overrides()`:

Old:
```python
                if self.secrets_provider:
                    from ..secrets.registry import get_secrets_resolver
                    from ..secrets.resolve import resolve_secrets_in_dict
                    resolver = get_secrets_resolver(self.secrets_provider)
                    override_kwargs = resolve_secrets_in_dict(override_kwargs, resolver)
```

New:
```python
                if self.secrets_provider:
                    from ..secrets.registry import get_secrets_resolver
                    from ..resolve import resolve_references_in_dict
                    resolver = get_secrets_resolver(self.secrets_provider)
                    override_kwargs = resolve_references_in_dict(override_kwargs, resolver)
```

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All PASS — all existing tests work with the new import paths.

- [ ] **Step 6: Commit**

```bash
git add src/mountainash_settings/settings/base_settings.py src/mountainash_settings/settings_parameters/settings_parameters.py
git commit -m "refactor: rewire call sites from secrets/resolve to resolve.py"
```

---

### Task 3: Delete `secrets/resolve.py` and update `secrets/__init__.py`

**Files:**
- Delete: `src/mountainash_settings/secrets/resolve.py`
- Modify: `src/mountainash_settings/secrets/__init__.py`
- Modify: `tests/unit/secrets/test_resolve.py` → Delete
- Verify: `tests/unit/secrets/test_registry.py` (unchanged)

This task removes the old resolution module from the secrets package and cleans up the old tests.

- [ ] **Step 1: Update `secrets/__init__.py`**

The `secrets/__init__.py` currently only re-exports registry symbols — no imports from `resolve.py` in the init. Verify by reading the file. Update the docstring:

Replace `src/mountainash_settings/secrets/__init__.py` with:

```python
"""Secrets resolver registry — write-once provider mapping.

Resolution logic lives in ``mountainash_settings.resolve`` (domain-agnostic).
This package owns the secrets-specific provider registry only.
"""

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

- [ ] **Step 2: Delete old resolution module and its tests**

```bash
rm src/mountainash_settings/secrets/resolve.py
rm tests/unit/secrets/test_resolve.py
```

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All PASS — no code references `secrets.resolve` anymore.

- [ ] **Step 4: Commit**

```bash
git add -A src/mountainash_settings/secrets/ tests/unit/secrets/
git commit -m "refactor: remove secrets/resolve.py, resolution lives in resolve.py"
```

---

### Task 4: Integration test — nested `AuthSpec` with secrets from YAML

**Files:**
- Create: `tests/config/nested_secrets_test.yaml`
- Modify: `tests/test_base_settings.py`

This is the exact scenario that triggered the spec: a settings class with a nested frozen `AuthSpec` field loaded from a YAML config file, where auth fields contain `secret:` prefixed values.

- [ ] **Step 1: Create the YAML config file**

Create `tests/config/nested_secrets_test.yaml`:

```yaml
APP_NAME: "test_app"
auth:
  kind: "password"
  username: "admin"
  password: "secret:db/production/password"
```

- [ ] **Step 2: Write the integration test**

Append to `tests/test_base_settings.py`, inside the existing `TestSecretsResolution` class (after the last test method at around line 331):

```python
    def test_nested_frozen_model_secret_resolved_from_yaml(self, secrets_registry):
        from mountainash_settings.auth import PasswordAuth

        class _NestedAuthSettings(MountainAshBaseSettings):
            APP_NAME: str = Field(default="default")
            auth: PasswordAuth

        settings = _NestedAuthSettings(
            settings_parameters=SettingsParameters.create(
                settings_class=_NestedAuthSettings,
                secrets_provider="test",
                config_files=["tests/config/nested_secrets_test.yaml"],
                env_prefix="NESTEDSECTEST_",
            )
        )
        assert settings.APP_NAME == "test_app"
        assert settings.auth.username == "admin"
        assert settings.auth.password.get_secret_value() == "resolved_db/production/password"

    def test_nested_model_secret_in_kwargs_resolved(self, secrets_registry):
        from mountainash_settings.auth import PasswordAuth

        class _NestedAuthSettings(MountainAshBaseSettings):
            APP_NAME: str = Field(default="default")
            auth: PasswordAuth

        settings = _NestedAuthSettings(
            settings_parameters=SettingsParameters.create(
                settings_class=_NestedAuthSettings,
                secrets_provider="test",
                auth={"kind": "password", "username": "admin", "password": "secret:db/password"},
            )
        )
        assert settings.auth.password.get_secret_value() == "resolved_db/password"
```

- [ ] **Step 3: Run the new tests**

Run: `pytest tests/test_base_settings.py::TestSecretsResolution::test_nested_frozen_model_secret_resolved_from_yaml tests/test_base_settings.py::TestSecretsResolution::test_nested_model_secret_in_kwargs_resolved -v`
Expected: All PASS

- [ ] **Step 4: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add tests/config/nested_secrets_test.yaml tests/test_base_settings.py
git commit -m "test: add integration tests for nested model secrets resolution"
```

---

### Task 5: Update principles in mountainash-central

**Files:**
- Modify: `/home/nathanielramm/git/mountainash-io/mountainash/mountainash-central/01.principles/mountainash-settings/a.architecture/secrets-resolution.md`
- Modify: `/home/nathanielramm/git/mountainash-io/mountainash/mountainash-central/01.principles/mountainash-settings/README.md`

This task updates the principles to reflect the mechanism/domain separation and the recursive model tree resolution.

- [ ] **Step 1: Update `secrets-resolution.md`**

The document title should change to reflect the broader scope. Rename the file content (not the file itself — we just committed this file in the previous session) to update the architecture section. Key changes:

1. Add a section under **Architecture** explaining the mechanism/domain separation:
   - `resolve.py` is the general mechanism (no dependency on `secrets/`)
   - `secrets/` is the domain-specific provider registry
   - `base_settings.py` wires them together

2. Update **Three Interception Points** table — Point 2 mechanism column changes from `resolve_secrets_on_instance()` to `resolve_references_in_model_tree()`; Point 1 and 3 change from `resolve_secrets_in_dict()` to `resolve_references_in_dict()`.

3. Update **Technical Reference** paths:
   - `src/mountainash_settings/secrets/resolve.py` → `src/mountainash_settings/resolve.py`
   - Function names: `resolve_secrets_in_dict` → `resolve_references_in_dict`, `resolve_secrets_on_instance` → `resolve_references_in_model_tree`

4. Add to the nested model handling description:
   - Nested `BaseModel` fields are rebuilt, not mutated in place
   - Frozen models (like `AuthSpec`) are supported via dict extraction → resolution → reconstruction
   - Arbitrary nesting depth is supported

- [ ] **Step 2: Update `README.md` summary line**

In the README index table, update the `secrets-resolution.md` summary to mention nested model support and the mechanism/domain separation.

- [ ] **Step 3: Commit in mountainash-central**

```bash
cd /home/nathanielramm/git/mountainash-io/mountainash/mountainash-central
git add 01.principles/mountainash-settings/a.architecture/secrets-resolution.md 01.principles/mountainash-settings/README.md
git commit -m "docs(mountainash-settings): update secrets-resolution principle for nested models and module separation"
```

---

### Task 6: Final verification

**Files:** None — verification only.

- [ ] **Step 1: Run full test suite with coverage**

Run: `hatch run test:cov`
Expected: All PASS, no regressions.

- [ ] **Step 2: Run linter**

Run: `hatch run ruff:check`
Expected: Clean — no new lint issues.

- [ ] **Step 3: Verify old module is gone**

Run: `python -c "from mountainash_settings.secrets.resolve import resolve_secrets_in_dict" 2>&1`
Expected: `ModuleNotFoundError`

Run: `python -c "from mountainash_settings.resolve import resolve_references_in_dict; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Verify public API unchanged**

Run: `pytest tests/unit/test_public_api.py -v`
Expected: All PASS — `SecretsResolver`, `register_secrets_resolver`, etc. still importable from package root.
