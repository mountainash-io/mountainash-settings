# Architecture Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two correctness bugs (cached object mutation, secrets_dir misclassification), remove namespace, collapse the merge framework, and clean up dead code.

**Architecture:** Seven tasks executed in dependency order. P0 bugs first (safe, isolated fixes), then P1 simplifications (namespace removal, merge collapse, SettingsUtils removal), then P2 cleanup. Each task produces a passing test suite before moving on.

**Tech Stack:** Python, pydantic-settings, pytest, hatch

---

### Task 1: Fix cached object mutation in SettingsManager.get_settings_object()

**Files:**
- Modify: `src/mountainash_settings/settings_cache/settings_manager.py:34-55`
- Modify: `tests/test_settings_manager.py:197-253`

- [ ] **Step 1: Write the failing test that proves the mutation bug**

Add to `tests/test_settings_manager.py` in the `TestGetSettingsObject` class:

```python
@pytest.mark.unit
def test_runtime_overrides_do_not_mutate_cached_instance(self, isolated_settings_manager):
    """Test that runtime override kwargs do NOT mutate the cached instance."""
    # Create and cache settings
    params_create = SettingsParameters.create(
        settings_class=TestSettings,
        TEST_VAL_1="original_value"
    )
    created_settings = isolated_settings_manager.get_or_create_settings(params_create)
    assert created_settings.TEST_VAL_1 == "original_value"

    # Retrieve with override kwargs
    params_override = SettingsParameters.create(
        settings_class=TestSettings,
        TEST_VAL_1="overridden_value"
    )
    retrieved_settings = isolated_settings_manager.get_settings_object(params_override)
    assert retrieved_settings.TEST_VAL_1 == "overridden_value"

    # The CACHED instance must NOT have been mutated
    cached_directly = isolated_settings_manager.settings_object_cache[params_create]
    assert cached_directly.TEST_VAL_1 == "original_value"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `hatch run test:test tests/test_settings_manager.py::TestGetSettingsObject::test_runtime_overrides_do_not_mutate_cached_instance -v`

Expected: FAIL -- `cached_directly.TEST_VAL_1` is `"overridden_value"` instead of `"original_value"`

- [ ] **Step 3: Fix SettingsManager.get_settings_object() to copy before mutating**

In `src/mountainash_settings/settings_cache/settings_manager.py`, replace the `get_settings_object` method:

```python
def get_settings_object(self, settings_parameters: SettingsParameters) -> MountainAshBaseSettings:
    """
    Gets the configuration object for a given set of parameters.

    If the parameters contain runtime override kwargs, returns a copy
    with overrides applied. The cached instance is never mutated.

    Args:
        settings_parameters: The parameters identifying the settings.
    Returns:
        MountainAshBaseSettings: The settings object, possibly with runtime overrides.
    Raises:
        ValueError: If the cached object is not a MountainAshBaseSettings instance.
    """
    obj_settings: Optional[MountainAshBaseSettings] = self.settings_object_cache.get(settings_parameters, None)

    if not isinstance(obj_settings, MountainAshBaseSettings):
        raise ValueError(
            f"Configuration for '{settings_parameters}' found, but is not a "
            f"MountainAshBaseSettings object. Received a {type(obj_settings)}"
        )

    override_kwargs = settings_parameters.get_attribute_settings_kwargs()
    if override_kwargs:
        obj_settings = obj_settings.model_copy()
        obj_settings.update_settings_from_dict(settings_dict=override_kwargs)

    return obj_settings
```

- [ ] **Step 4: Update the existing test that relied on mutation behavior**

In `tests/test_settings_manager.py`, update `TestGetSettingsObject.test_applies_runtime_override_kwargs` to reflect the new correct behavior:

```python
@pytest.mark.unit
def test_applies_runtime_override_kwargs(self, isolated_settings_manager):
    """Test that runtime override kwargs are applied to a copy, not the cached instance."""
    # Create settings without override
    params_create = SettingsParameters.create(
        settings_class=TestSettings,
        TEST_VAL_1="original_value"
    )
    created_settings = isolated_settings_manager.get_or_create_settings(params_create)
    assert created_settings.TEST_VAL_1 == "original_value"

    # Retrieve with override kwargs
    params_override = SettingsParameters.create(
        settings_class=TestSettings,
        TEST_VAL_1="overridden_value"
    )
    retrieved_settings = isolated_settings_manager.get_settings_object(params_override)

    # Retrieved copy has the override
    assert retrieved_settings.TEST_VAL_1 == "overridden_value"
    # Original cached instance is untouched
    assert created_settings.TEST_VAL_1 == "original_value"
```

- [ ] **Step 5: Run all tests to verify the fix**

Run: `hatch run test:test tests/test_settings_manager.py -v`

Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/mountainash_settings/settings_cache/settings_manager.py tests/test_settings_manager.py
git commit -m "fix: prevent mutation of cached settings in SettingsManager.get_settings_object()

Copy the cached instance before applying runtime override kwargs,
preventing silent data corruption where one caller's overrides
permanently alter the cached object for all subsequent callers."
```

---

### Task 2: Move secrets_dir to structural parameters

**Files:**
- Modify: `src/mountainash_settings/settings_parameters/settings_parameters.py:92-160`
- Modify: `tests/test_settings_parameters/test_settings_parameters_coverage.py:86-102`
- Modify: `tests/test_settings_parameters/test_settings_parameters.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_settings_parameters/test_settings_parameters_coverage.py`, replace the `test_eq_ignores_secrets_dir_differences` test:

```python
@pytest.mark.unit
def test_eq_differs_on_secrets_dir(self):
    """Test that different secrets_dir values produce inequality (structural param)."""
    params1 = SettingsParameters.create(
        settings_class=TestSettings,
        secrets_dir="/secrets1"
    )
    params2 = SettingsParameters.create(
        settings_class=TestSettings,
        secrets_dir="/secrets2"
    )

    # secrets_dir is structural -- different values should NOT be equal
    assert params1 != params2
    assert hash(params1) != hash(params2)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `hatch run test:test tests/test_settings_parameters/test_settings_parameters_coverage.py::TestEquality::test_eq_differs_on_secrets_dir -v`

Expected: FAIL -- params are currently equal because secrets_dir is excluded from hash/eq

- [ ] **Step 3: Add secrets_dir to __hash__ and __eq__**

In `src/mountainash_settings/settings_parameters/settings_parameters.py`, update `__hash__`:

```python
def __hash__(self):
    """
    Custom hash implementation for efficient settings caching strategy.

    Includes all structural parameters that define the core configuration identity:
    - config_files: Source configuration files
    - settings_class: Type of settings object
    - env_prefix: Environment variable prefix
    - secrets_dir: Directory for secrets storage

    Deliberately EXCLUDES runtime parameters (kwargs) to enable
    cache reuse when only dynamic overrides differ.

    Returns:
        int: Hash value based on structural parameters only
    """
    hashable_config_files = SettingsFileHandler.format_config_file_tuple(self.config_files)

    hashable_attrs = tuple([
        hashable_config_files,
        self.settings_class,
        self.env_prefix,
        self.secrets_dir,
        # Deliberately exclude: self.kwargs
    ])

    return hash(hashable_attrs)
```

Update `__eq__`:

```python
def __eq__(self, other):
    """
    Equality based on the same structural parameters used in __hash__.

    Two SettingsParameters are equal if their core configuration identity
    matches, regardless of runtime parameter differences.

    Args:
        other: Object to compare with

    Returns:
        bool: True if structural parameters match, False otherwise
    """
    if not isinstance(other, SettingsParameters):
        return False

    self_hashable_config_files = SettingsFileHandler.format_config_file_tuple(self.config_files)
    other_hashable_config_files = SettingsFileHandler.format_config_file_tuple(other.config_files)

    return (
        self_hashable_config_files == other_hashable_config_files and
        self.settings_class == other.settings_class and
        self.env_prefix == other.env_prefix and
        self.secrets_dir == other.secrets_dir
        # Deliberately exclude: kwargs comparison
    )
```

Note: `namespace` is still included in hash/eq for now -- it will be removed in Task 3.

The updated `__hash__`:

```python
def __hash__(self):
    hashable_config_files = SettingsFileHandler.format_config_file_tuple(self.config_files)

    hashable_attrs = tuple([
        self.namespace,
        hashable_config_files,
        self.settings_class,
        self.env_prefix,
        self.secrets_dir,
        # Deliberately exclude: self.kwargs
    ])

    return hash(hashable_attrs)
```

The updated `__eq__`:

```python
def __eq__(self, other):
    if not isinstance(other, SettingsParameters):
        return False

    self_hashable_config_files = SettingsFileHandler.format_config_file_tuple(self.config_files)
    other_hashable_config_files = SettingsFileHandler.format_config_file_tuple(other.config_files)

    return (
        self.namespace == other.namespace and
        self_hashable_config_files == other_hashable_config_files and
        self.settings_class == other.settings_class and
        self.env_prefix == other.env_prefix and
        self.secrets_dir == other.secrets_dir
        # Deliberately exclude: kwargs comparison
    )
```

- [ ] **Step 4: Run the full test suite**

Run: `hatch run test:test tests/test_settings_parameters/ -v`

Expected: The new `test_eq_differs_on_secrets_dir` passes. The existing `test_eq_ignores_secrets_dir_differences` will now fail -- delete it since it tested the old (incorrect) behavior.

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_settings/settings_parameters/settings_parameters.py tests/test_settings_parameters/test_settings_parameters_coverage.py
git commit -m "fix: classify secrets_dir as structural parameter in hash/eq

secrets_dir is a configuration source (pydantic-settings reads from it),
not a runtime override. Two parameter sets with different secrets_dir
values must produce different cache entries."
```

---

### Task 3: Remove namespace field

**Files:**
- Modify: `src/mountainash_settings/settings_parameters/settings_parameters.py`
- Modify: `src/mountainash_settings/settings/base_settings.py`
- Modify: `src/mountainash_settings/settings_cache/settings_functions.py`
- Modify: `src/mountainash_settings/settings_cache/settings_manager.py`
- Modify: `src/mountainash_settings/settings_parameters/merge_framework.py`
- Modify: `src/mountainash_settings/settings_parameters/utils.py`
- Modify: `tests/test_base_settings.py`
- Modify: `tests/test_base_settings_coverage.py`
- Modify: `tests/test_settings_manager.py`
- Modify: `tests/test_settings_parameters/test_settings_parameters.py`
- Modify: `tests/test_settings_parameters/test_settings_parameters_coverage.py`
- Modify: `tests/test_settings_parameters/test_merge_framework.py`
- Modify: `tests/fixtures/parameters.py`
- Modify: `tests/fixtures/instances.py`

This is the largest task. The approach: remove namespace from the dataclass and all source code first, then fix all tests.

- [ ] **Step 1: Remove namespace from SettingsParameters dataclass**

In `src/mountainash_settings/settings_parameters/settings_parameters.py`:

1. Remove `namespace: Optional[str] = None` from the dataclass fields
2. Remove `self.namespace` from `__hash__` hashable_attrs
3. Remove `self.namespace == other.namespace` from `__eq__`
4. Remove `namespace` parameter from `create()` classmethod
5. Remove `namespace=namespace` from the `create()` return
6. Remove `_init_namespace()` static method
7. Remove `'namespace': self.namespace` from `to_dict()`
8. Update the docstring to remove namespace references

The `create()` method becomes:

```python
@classmethod
def create(cls,
           config_files: Optional[str|UPath|List[str|UPath]|Tuple[str|UPath]] = None,
           settings_class: Optional[Type[BaseSettings]] = None,
           env_prefix: Optional[str] = None,
           secrets_dir: Optional[str] = None,
           **kwargs: Any
           ) -> 'SettingsParameters':

    resolved_config_files = SettingsFileHandler.format_config_file_tuple(config_files)
    resolved_kwargs = SettingsKwargsHandler.format_kwargs_dict(kwargs) if kwargs else None

    return cls(
        config_files=resolved_config_files,
        settings_class=settings_class,
        env_prefix=env_prefix,
        secrets_dir=secrets_dir,
        kwargs=resolved_kwargs
    )
```

The `to_dict()` method becomes:

```python
def to_dict(self) -> Dict[str, Any]:
    return {
        'config_files': list(self.config_files) if self.config_files else None,
        'kwargs': self.get_all_kwargs() if self.kwargs else None,
        'settings_class': self.settings_class,
        'env_prefix': self.env_prefix,
        'secrets_dir': self.secrets_dir
    }
```

- [ ] **Step 2: Remove SETTINGS_NAMESPACE from MountainAshBaseSettings**

In `src/mountainash_settings/settings/base_settings.py`:

1. Remove `SETTINGS_NAMESPACE: str = Field(default=None)` field declaration
2. Remove `setattr(self, "SETTINGS_NAMESPACE", local_settings_params.namespace)` from `__init__`
3. Remove `self.SETTINGS_NAMESPACE` from `__hash__`
4. Remove `settings_namespace` parameter from `get_settings()` classmethod
5. Remove `settings_namespace=settings_namespace` from the `get_settings()` call inside
6. Remove `existing_namespace` from `extract_settings_parameters()` and `namespace=existing_namespace` from the `SettingsParameters.create()` call

The `__hash__` becomes:

```python
def __hash__(self) -> int:
    return hash((
        self.SETTINGS_CLASS_NAME,
        tuple(self.SETTINGS_SOURCE_ENV_FILES) if self.SETTINGS_SOURCE_ENV_FILES else None,
        tuple(self.SETTINGS_SOURCE_ENV_PREFIX) if self.SETTINGS_SOURCE_ENV_PREFIX else None,
        tuple(self.SETTINGS_SOURCE_YAML_FILES) if self.SETTINGS_SOURCE_YAML_FILES else None,
        tuple(self.SETTINGS_SOURCE_TOML_FILES) if self.SETTINGS_SOURCE_TOML_FILES else None,
        tuple(self.SETTINGS_SOURCE_JSON_FILES) if self.SETTINGS_SOURCE_JSON_FILES else None,
    ))
```

The `get_settings()` classmethod becomes:

```python
@classmethod
def get_settings(cls,
                settings_parameters:   Optional[SettingsParameters] = None,
                settings_class:        Optional[Type[T]] = None,
                config_files:          Optional[Union[UPath, str, List[UPath|str]]]  = None,
                env_prefix:            Optional[str] = None,
                **kwargs
                 ) -> Any:
    from mountainash_settings.settings_cache import get_settings

    if settings_class is None:
        class_module = cls.__module__
        class_name = cls.__name__
        settings_class = getattr(import_module(name=class_module), class_name)

    settings_instance: Any = get_settings(
                                settings_parameters=settings_parameters,
                                settings_class=settings_class,
                                config_files=config_files,
                                env_prefix=env_prefix,
                                **kwargs
                        )

    if not isinstance(settings_instance, cls):
        raise TypeError(
            f"Created instance of type {type(settings_instance).__name__} "
            f"but expected {cls.__name__} when calling {cls.__name__}.get_settings()"
        )

    return settings_instance
```

The `extract_settings_parameters()` becomes:

```python
def extract_settings_parameters(self) -> SettingsParameters:
    config_files: List = []
    if self.SETTINGS_SOURCE_ENV_FILES:
        config_files += self.SETTINGS_SOURCE_ENV_FILES
    if self.SETTINGS_SOURCE_YAML_FILES:
        config_files += self.SETTINGS_SOURCE_YAML_FILES
    if self.SETTINGS_SOURCE_TOML_FILES:
        config_files += self.SETTINGS_SOURCE_TOML_FILES
    if self.SETTINGS_SOURCE_JSON_FILES:
        config_files += self.SETTINGS_SOURCE_JSON_FILES

    existing_config_files = SettingsUtils.format_config_file_list(config_files=config_files)
    existing_kwargs = SettingsUtils.format_kwargs_dict(p_kwargs=self.SETTINGS_SOURCE_KWARGS)
    existing_settings_class = self.SETTINGS_CLASS or None
    existing_env_prefix = self.SETTINGS_SOURCE_ENV_PREFIX or None

    params: SettingsParameters = SettingsParameters.create(
        settings_class=existing_settings_class,
        config_files=existing_config_files,
        kwargs=existing_kwargs,
        env_prefix=existing_env_prefix)

    return params
```

- [ ] **Step 3: Remove settings_namespace from get_settings() function**

In `src/mountainash_settings/settings_cache/settings_functions.py`:

1. Remove `settings_namespace` parameter from `get_settings()`
2. Remove `namespace=settings_namespace` from both `SettingsParameters.create()` calls

The `get_settings()` function becomes:

```python
def get_settings(    settings_parameters: Optional[SettingsParameters] = None,
                     settings_class:        Optional[Type[MountainAshBaseSettings]] = None,
                     config_files:          Optional[Union[UPath, str, List[UPath|str]]]  = None,
                     env_prefix:            Optional[str] = None,
                     **kwargs
                     ) -> BaseSettings:
    """
    The main function to retrieve application settings.

    Args:
        settings_parameters: Pre-built settings parameters object.
        settings_class: The class of settings to create.
        config_files: Configuration files to load.
        env_prefix: Environment variable prefix.
        **kwargs: Additional keyword arguments passed as runtime overrides.

    Returns:
        BaseSettings: The settings instance.
    """
    if settings_parameters:
        if not isinstance(settings_parameters, SettingsParameters):
            raise ValueError("The settings_parameters parameter must be an instance of SettingsParameters.")

        local_settings_parameters = SettingsParameters.create(
            settings_class=settings_class,
            config_files=config_files,
            env_prefix=env_prefix,
            **kwargs
        )

        final_settings_parameters = SettingsUtils.merge_settings_parameter_objects(settings_parameters, local_settings_parameters)

    else:
        final_settings_parameters = SettingsParameters.create(
            settings_class=settings_class,
            config_files=config_files,
            env_prefix=env_prefix,
            **kwargs
        )

    cached_settings = _get_settings(settings_parameters=final_settings_parameters)
    return final_settings_parameters.apply_runtime_overrides(cached_settings)
```

- [ ] **Step 4: Remove namespace from merge framework**

In `src/mountainash_settings/settings_parameters/merge_framework.py`:

1. Remove `resolved_namespace` logic from `merge_with_object()` (lines 83-91, 115)
2. Remove `namespace` parameter and logic from `merge_with_params()` (lines 124, 139-147, 167)
3. Remove `merge_namespaces()` from `FieldMergeUtils`

In `src/mountainash_settings/settings_parameters/utils.py`:

1. Remove `default_namespace` class attribute
2. Remove `namespace` parameter from `merge_settings_parameters()`
3. Remove `merge_namespaces()` method

- [ ] **Step 5: Remove namespace from SettingsManager docstrings**

In `src/mountainash_settings/settings_cache/settings_manager.py`:

1. Update docstrings to remove namespace references (no code changes needed beyond docstrings since `SettingsManager` uses `SettingsParameters` as keys, not namespace strings directly)
2. Rename `is_namespace_initialised` to `is_initialised` for clarity

- [ ] **Step 6: Update ALL tests to remove namespace= arguments**

This is a bulk operation across many test files. For each file:

**`tests/test_base_settings.py`:** Remove all `namespace=` arguments from `SettingsParameters.create()` calls. Each test currently uses a unique namespace for cache isolation -- since namespace is removed, tests that need distinct cache entries must differ on other structural params (different config files, env_prefix, or settings_class). For tests that are identical except for namespace, either:
- Use the `isolated_settings_manager` fixture (which creates a fresh `SettingsManager`)
- Add a unique kwarg that doesn't affect cache identity

Remove `settings_namespace=` from `get_test_settings()` function signature and calls.

**`tests/test_base_settings_coverage.py`:**
- Remove all `namespace=` from `SettingsParameters.create()` calls
- Remove `test_hash_different_namespaces` test entirely (namespace is gone)
- Remove `settings_namespace=` from `TestSettings.get_settings()` calls
- Update `test_extract_basic_parameters` etc. to not assert on `extracted.namespace`
- Update `test_full_workflow_with_templates` to not assert `params.namespace`

**`tests/test_settings_manager.py`:**
- Remove all `namespace=` from `SettingsParameters.create()` calls
- Rename `is_namespace_initialised` to `is_initialised` in test method calls
- For `test_different_namespaces_create_different_settings`: change to use different `env_prefix` values to ensure distinct cache entries
- For `test_multiple_settings_in_cache`: use different `env_prefix` values

**`tests/test_settings_parameters/test_settings_parameters.py`:**
- Remove all `namespace=` from `SettingsParameters` and `SettingsParameters.create()` calls
- Remove `assert params.namespace` assertions
- Remove `test_init_namespace_*` tests
- Remove `'namespace'` from `to_dict` assertions
- Update `test_hash_different_for_different_params` to use different env_prefix instead

**`tests/test_settings_parameters/test_settings_parameters_coverage.py`:**
- Remove all `namespace=` from `SettingsParameters.create()` calls
- Remove `test_eq_differs_on_namespace` test
- Update integration tests to not assert on namespace
- Remove `assert settings.SETTINGS_NAMESPACE` assertions

**`tests/test_settings_parameters/test_merge_framework.py`:**
- Remove all `namespace=` from `SettingsParameters.create()` calls
- Remove all `TestSettingsParameterMergerObject` tests about namespace merging
- Remove all `TestSettingsParameterMergerParams` tests about namespace merging
- Remove `TestFieldMergeUtils.test_merge_namespaces_*` tests
- Update integration tests to not assert on namespace

**`tests/fixtures/parameters.py`:**
- Remove all `namespace=` from `SettingsParameters.create()` calls
- Remove `parametrized_namespace` fixture
- Remove `namespace` parameter from `create_settings_parameters` factory

**`tests/fixtures/instances.py`:**
- Remove `namespace=` from `settings_with_runtime_override` fixture

- [ ] **Step 7: Run the full test suite**

Run: `hatch run test:test -v`

Expected: ALL PASS. If any test fails, examine the failure -- it's likely a missed namespace reference. Fix and re-run.

- [ ] **Step 8: Commit**

```bash
git add -u
git commit -m "refactor: remove namespace field from settings architecture

Namespace was a legacy cache discriminator with no behavioral effect
on settings loading, resolution, or scoping. Cache identity is now
determined entirely by config_files, settings_class, env_prefix,
and secrets_dir -- the parameters that actually affect what values
are produced."
```

---

### Task 4: Collapse merge framework to single entry point

**Files:**
- Modify: `src/mountainash_settings/settings_parameters/merge_framework.py`
- Modify: `src/mountainash_settings/settings_parameters/utils.py`
- Modify: `src/mountainash_settings/settings_parameters/__init__.py`
- Modify: `src/mountainash_settings/__init__.py`
- Modify: `src/mountainash_settings/settings/base_settings.py`
- Modify: `src/mountainash_settings/settings_cache/settings_functions.py`
- Modify: `src/mountainash_settings/settings_cache/settings_manager.py`
- Modify: `tests/test_settings_parameters/test_merge_framework.py`

- [ ] **Step 1: Add a merge() classmethod to SettingsParameters**

In `src/mountainash_settings/settings_parameters/settings_parameters.py`, add after the `create()` method:

```python
@classmethod
def merge(cls,
          base: 'SettingsParameters',
          other: Optional['SettingsParameters'] = None,
          prioritise_base: bool = False
          ) -> 'SettingsParameters':
    """
    Merge two SettingsParameters objects.

    Per-field strategies:
    - config_files: combined and deduplicated
    - settings_class: must match if both provided (raises ValueError)
    - scalars (env_prefix, secrets_dir): last wins (or first if prioritise_base)
    - kwargs: merged dict, second takes precedence (or first if prioritise_base)

    Args:
        base: The base parameters.
        other: Parameters to merge in. If None, returns base.
        prioritise_base: If True, base values win over other values.

    Returns:
        A new SettingsParameters with merged values.

    Raises:
        ValueError: If base is None or settings_class values conflict.
    """
    if base is None:
        raise ValueError("Base SettingsParameters cannot be None")
    if other is None:
        return base

    # Config files: combine and deduplicate
    if base.config_files is None and other.config_files is None:
        merged_config_files = None
    elif prioritise_base:
        merged_config_files = base.config_files or other.config_files
    else:
        merged = set(base.config_files or ()) | set(other.config_files or ())
        merged_config_files = tuple(sorted(str(p) for p in merged)) if merged else None

    # Settings class: validate compatibility
    if base.settings_class is not None and other.settings_class is not None:
        if base.settings_class != other.settings_class:
            raise ValueError(
                f"Settings class must match for merging. "
                f"base: {base.settings_class} != other: {other.settings_class}"
            )
    if prioritise_base:
        merged_class = base.settings_class or other.settings_class
    else:
        merged_class = other.settings_class or base.settings_class

    # Scalars: simple priority
    if prioritise_base:
        merged_env_prefix = base.env_prefix or other.env_prefix
        merged_secrets_dir = base.secrets_dir or other.secrets_dir
    else:
        merged_env_prefix = other.env_prefix or base.env_prefix
        merged_secrets_dir = other.secrets_dir or base.secrets_dir

    # Kwargs: merge dicts
    if base.kwargs is None and other.kwargs is None:
        merged_kwargs = None
    elif prioritise_base:
        merged_kwargs = base.kwargs or other.kwargs
    else:
        merged_kwargs = dict(base.kwargs or {}) | dict(other.kwargs or {})
        merged_kwargs = merged_kwargs.get("kwargs", merged_kwargs)
        merged_kwargs = merged_kwargs if merged_kwargs else None

    return cls.create(
        settings_class=merged_class,
        config_files=merged_config_files,
        env_prefix=merged_env_prefix,
        secrets_dir=merged_secrets_dir,
        **(merged_kwargs or {})
    )
```

- [ ] **Step 2: Update all callers to use SettingsParameters.merge()**

In `src/mountainash_settings/settings/base_settings.py`, line ~58:

Replace:
```python
local_settings_params = SettingsUtils.merge_settings_parameter_objects(settings_parameters, local_settings_params)
```
With:
```python
local_settings_params = SettingsParameters.merge(settings_parameters, local_settings_params)
```

In `src/mountainash_settings/settings_cache/settings_functions.py`, line ~95:

Replace:
```python
final_settings_parameters = SettingsUtils.merge_settings_parameter_objects(settings_parameters, local_settings_parameters)
```
With:
```python
final_settings_parameters = SettingsParameters.merge(settings_parameters, local_settings_parameters)
```

- [ ] **Step 3: Strip merge_framework.py down to just ValidationError**

Replace `src/mountainash_settings/settings_parameters/merge_framework.py` with:

```python
"""
Validation utilities for settings parameter operations.
"""


class ValidationError(Exception):
    """Exception for validation failures in settings parameter operations."""
    pass
```

The four module-level merge functions (`_merge_simple`, `_merge_config_files`, `_merge_kwargs`, `_merge_settings_class`) are no longer needed -- their logic is now inline in `SettingsParameters.merge()`. The classes `SettingsParameterMerger`, `FieldMergeUtils`, `GenericMerger`, `MergePriority`, and `get_merger` are removed.

- [ ] **Step 4: Update __init__.py exports**

In `src/mountainash_settings/settings_parameters/__init__.py`:

```python
from .filehandler import SettingsFileHandler, SettingsFiles
from .kwargshandler import SettingsKwargsHandler
from .settings_parameters import SettingsParameters
from .merge_framework import ValidationError

__all__ = [
    "SettingsParameters",
    "SettingsFileHandler",
    "SettingsKwargsHandler",
    "SettingsFiles",
    "ValidationError",
]
```

- [ ] **Step 5: Update tests for the merge framework**

Rewrite `tests/test_settings_parameters/test_merge_framework.py` to test `SettingsParameters.merge()` directly:

```python
"""
Tests for SettingsParameters.merge() method.
"""

import pytest
from mountainash_settings import SettingsParameters
from mountainash_settings.settings_parameters.merge_framework import ValidationError
from fixtures.settings_classes import TestSettings, MockBaseSettings


class TestMerge:
    """Test SettingsParameters.merge() method."""

    @pytest.mark.unit
    def test_merge_raises_error_if_base_none(self):
        other = SettingsParameters.create(settings_class=TestSettings)
        with pytest.raises(ValueError, match="Base SettingsParameters cannot be None"):
            SettingsParameters.merge(None, other)

    @pytest.mark.unit
    def test_merge_with_none_other_returns_base(self):
        base = SettingsParameters.create(settings_class=TestSettings)
        result = SettingsParameters.merge(base, None)
        assert result is base

    @pytest.mark.unit
    def test_merge_config_files_combines_and_deduplicates(self):
        base = SettingsParameters.create(
            settings_class=TestSettings,
            config_files=["config1.yaml", "config2.yaml"]
        )
        other = SettingsParameters.create(
            settings_class=TestSettings,
            config_files=["config2.yaml", "config3.yaml"]
        )
        result = SettingsParameters.merge(base, other)
        config_files_str = tuple(str(f) for f in result.config_files)
        assert config_files_str == ("config1.yaml", "config2.yaml", "config3.yaml")

    @pytest.mark.unit
    def test_merge_kwargs_second_wins(self):
        base = SettingsParameters.create(
            settings_class=TestSettings,
            TEST_VAL_1="base_value"
        )
        other = SettingsParameters.create(
            settings_class=TestSettings,
            TEST_VAL_1="other_value"
        )
        result = SettingsParameters.merge(base, other)
        assert result.kwargs["TEST_VAL_1"] == "other_value"

    @pytest.mark.unit
    def test_merge_kwargs_combines(self):
        base = SettingsParameters.create(
            settings_class=TestSettings,
            TEST_VAL_1="base_value"
        )
        other = SettingsParameters.create(
            settings_class=TestSettings,
            TEST_VAL_2="other_value"
        )
        result = SettingsParameters.merge(base, other)
        assert result.kwargs["TEST_VAL_1"] == "base_value"
        assert result.kwargs["TEST_VAL_2"] == "other_value"

    @pytest.mark.unit
    def test_merge_env_prefix_second_wins(self):
        base = SettingsParameters.create(settings_class=TestSettings, env_prefix="BASE_")
        other = SettingsParameters.create(settings_class=TestSettings, env_prefix="OTHER_")
        result = SettingsParameters.merge(base, other)
        assert result.env_prefix == "OTHER_"

    @pytest.mark.unit
    def test_merge_secrets_dir_second_wins(self):
        base = SettingsParameters.create(settings_class=TestSettings, secrets_dir="/base")
        other = SettingsParameters.create(settings_class=TestSettings, secrets_dir="/other")
        result = SettingsParameters.merge(base, other)
        assert result.secrets_dir == "/other"

    @pytest.mark.unit
    def test_merge_incompatible_classes_raises_error(self):
        base = SettingsParameters.create(settings_class=TestSettings)
        other = SettingsParameters.create(settings_class=MockBaseSettings)
        with pytest.raises(ValueError, match="Settings class must match"):
            SettingsParameters.merge(base, other)

    @pytest.mark.unit
    def test_merge_same_class_succeeds(self):
        base = SettingsParameters.create(settings_class=TestSettings)
        other = SettingsParameters.create(settings_class=TestSettings)
        result = SettingsParameters.merge(base, other)
        assert result.settings_class is TestSettings

    @pytest.mark.unit
    def test_merge_prioritise_base(self):
        base = SettingsParameters.create(
            settings_class=TestSettings,
            env_prefix="BASE_",
            TEST_VAL_1="base_value"
        )
        other = SettingsParameters.create(
            settings_class=TestSettings,
            env_prefix="OTHER_",
            TEST_VAL_1="other_value"
        )
        result = SettingsParameters.merge(base, other, prioritise_base=True)
        assert result.env_prefix == "BASE_"
        assert result.kwargs["TEST_VAL_1"] == "base_value"

    @pytest.mark.unit
    def test_merge_both_none_kwargs(self):
        base = SettingsParameters.create(settings_class=TestSettings)
        other = SettingsParameters.create(settings_class=TestSettings)
        result = SettingsParameters.merge(base, other)
        assert result.kwargs is None

    @pytest.mark.unit
    def test_merge_both_none_config_files(self):
        base = SettingsParameters.create(settings_class=TestSettings)
        other = SettingsParameters.create(settings_class=TestSettings)
        result = SettingsParameters.merge(base, other)
        assert result.config_files is None

    @pytest.mark.integration
    def test_full_merge_workflow(self):
        base = SettingsParameters.create(
            settings_class=TestSettings,
            config_files=["config1.yaml"],
            env_prefix="BASE_",
            TEST_VAL_1="base_value"
        )
        other = SettingsParameters.create(
            settings_class=TestSettings,
            config_files=["config2.yaml"],
            TEST_VAL_2="other_value"
        )
        result = SettingsParameters.merge(base, other)

        config_files_str = set(str(f) for f in result.config_files)
        assert config_files_str == {"config1.yaml", "config2.yaml"}
        assert result.kwargs["TEST_VAL_1"] == "base_value"
        assert result.kwargs["TEST_VAL_2"] == "other_value"
        assert result.env_prefix == "BASE_"
```

- [ ] **Step 6: Run the full test suite**

Run: `hatch run test:test -v`

Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add -u
git commit -m "refactor: collapse merge framework into SettingsParameters.merge()

Replace 10 merge participants (SettingsParameterMerger, FieldMergeUtils,
GenericMerger, MergePriority, get_merger, and 4 module-level functions)
with a single SettingsParameters.merge() classmethod. Same per-field
strategies preserved: combine config files, validate class compatibility,
last-wins for scalars, merge dicts for kwargs."
```

---

### Task 5: Remove SettingsUtils facade class

**Files:**
- Modify: `src/mountainash_settings/settings_parameters/utils.py`
- Modify: `src/mountainash_settings/settings_parameters/__init__.py`
- Modify: `src/mountainash_settings/__init__.py`
- Modify: `src/mountainash_settings/settings/base_settings.py`
- Modify: `src/mountainash_settings/settings_cache/settings_functions.py`
- Modify: `src/mountainash_settings/settings_cache/settings_manager.py`
- Modify: `tests/test_settings_utils.py`

- [ ] **Step 1: Identify remaining SettingsUtils usages**

After Task 4, the remaining live `SettingsUtils` usages are:

1. `base_settings.py:252` -- `SettingsUtils.format_kwargs_dict()` -> replace with `SettingsKwargsHandler.format_kwargs_dict()`
2. `base_settings.py:305` -- `SettingsUtils.format_config_file_list()` -> replace with `SettingsFileHandler.format_config_file_list()`
3. `base_settings.py:306` -- `SettingsUtils.format_kwargs_dict()` -> replace with `SettingsKwargsHandler.format_kwargs_dict()`
4. `settings_manager.py:105` -- `SettingsUtils.format_kwargs_dict()` -> replace with `SettingsKwargsHandler.format_kwargs_dict()`

- [ ] **Step 2: Replace all SettingsUtils calls with direct handler calls**

In `src/mountainash_settings/settings/base_settings.py`:

Replace the import:
```python
from mountainash_settings.settings_parameters import SettingsFileHandler, SettingsParameters, SettingsUtils, SettingsFiles
```
With:
```python
from mountainash_settings.settings_parameters import SettingsFileHandler, SettingsParameters, SettingsKwargsHandler, SettingsFiles
```

Replace line ~252:
```python
settings_dict = SettingsUtils.format_kwargs_dict(p_kwargs=settings_dict)
```
With:
```python
settings_dict = SettingsKwargsHandler.format_kwargs_dict(p_kwargs=settings_dict)
```

Replace lines ~305-306:
```python
existing_config_files = SettingsUtils.format_config_file_list(config_files=config_files)
existing_kwargs = SettingsUtils.format_kwargs_dict(p_kwargs=self.SETTINGS_SOURCE_KWARGS)
```
With:
```python
existing_config_files = SettingsFileHandler.format_config_file_list(config_files=config_files)
existing_kwargs = SettingsKwargsHandler.format_kwargs_dict(p_kwargs=self.SETTINGS_SOURCE_KWARGS)
```

In `src/mountainash_settings/settings_cache/settings_manager.py`:

Replace the import:
```python
from ..settings_parameters import SettingsParameters, SettingsUtils
```
With:
```python
from ..settings_parameters import SettingsParameters, SettingsKwargsHandler
```

Replace line ~105:
```python
settings_kwargs: Dict[str, Any]|None = SettingsUtils.format_kwargs_dict(p_kwargs=settings_parameters.kwargs)
```
With:
```python
settings_kwargs: Dict[str, Any]|None = SettingsKwargsHandler.format_kwargs_dict(p_kwargs=settings_parameters.kwargs)
```

In `src/mountainash_settings/settings_cache/settings_functions.py`:

Replace the import:
```python
from ..settings_parameters.utils import SettingsUtils, SettingsParameters
```
With:
```python
from ..settings_parameters import SettingsParameters
```

(The `SettingsUtils.merge_settings_parameter_objects` call was already replaced in Task 4.)

- [ ] **Step 3: Delete utils.py and remove from exports**

Delete `src/mountainash_settings/settings_parameters/utils.py`.

Update `src/mountainash_settings/settings_parameters/__init__.py`:

```python
from .filehandler import SettingsFileHandler, SettingsFiles
from .kwargshandler import SettingsKwargsHandler
from .settings_parameters import SettingsParameters
from .merge_framework import ValidationError

__all__ = [
    "SettingsParameters",
    "SettingsFileHandler",
    "SettingsKwargsHandler",
    "SettingsFiles",
    "ValidationError",
]
```

Update `src/mountainash_settings/__init__.py`:

```python
from .__version__ import __version__

from .settings_parameters.settings_parameters import SettingsParameters
from .settings.base_settings import MountainAshBaseSettings
from .settings_cache.settings_functions import get_settings, get_settings_manager
from .settings_cache.settings_manager import SettingsManager

__all__ = [
    "__version__",

    "SettingsParameters",

    "MountainAshBaseSettings",
    "SettingsManager",

    "get_settings",
    "get_settings_manager",
]
```

- [ ] **Step 4: Update or remove tests/test_settings_utils.py**

Read the file first. If it only tests `SettingsUtils` delegation methods, delete it. If it has tests for behavior that moved, migrate those tests to the appropriate test file.

- [ ] **Step 5: Run the full test suite**

Run: `hatch run test:test -v`

Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add -u
git commit -m "refactor: remove SettingsUtils facade class

Replace all SettingsUtils method calls with direct calls to
SettingsFileHandler, SettingsKwargsHandler, and SettingsParameters.merge().
SettingsUtils was a facade with only one-line delegations."
```

---

### Task 6: Normalize kwargs once at boundary

**Files:**
- Modify: `src/mountainash_settings/settings_parameters/settings_parameters.py`
- Modify: `src/mountainash_settings/settings_parameters/kwargshandler.py`

- [ ] **Step 1: Remove defensive kwargs unwrapping from SettingsParameters.merge()**

In the `merge()` method added in Task 4, the line:
```python
merged_kwargs = merged_kwargs.get("kwargs", merged_kwargs)
```
is defensive re-unwrapping. Remove it. The `create()` method already normalizes via `SettingsKwargsHandler.format_kwargs_dict()`, so by the time kwargs reach `merge()`, they're already clean.

- [ ] **Step 2: Verify SettingsKwargsHandler.format_kwargs_dict() is the single normalization point**

Confirm that `format_kwargs_dict()` in `kwargshandler.py` is called in `SettingsParameters.create()` and nowhere else needs the `.get("kwargs", ...)` unwrapping. If any test passes a raw `{"kwargs": {...}}` structure directly to a `SettingsParameters` constructor (bypassing `create()`), update the test to use `create()` instead.

- [ ] **Step 3: Run the full test suite**

Run: `hatch run test:test -v`

Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add -u
git commit -m "cleanup: normalize kwargs once at SettingsParameters.create() boundary

Remove defensive re-unwrapping of nested 'kwargs' key from merge logic.
Normalization now happens exactly once in create() via
SettingsKwargsHandler.format_kwargs_dict()."
```

---

### Task 7: Remove dead code

**Files:**
- Modify: `src/mountainash_settings/settings_cache/settings_functions.py`
- Modify: `src/mountainash_settings/settings_cache/settings_manager.py`

- [ ] **Step 1: Remove unreachable build_path_template**

In `src/mountainash_settings/settings_cache/settings_functions.py`, delete lines 114-119 (the `build_path_template` function defined after the `return` statement inside `get_settings()`).

- [ ] **Step 2: Remove commented-out code from settings_manager.py**

In `src/mountainash_settings/settings_cache/settings_manager.py`, delete all the large commented-out method blocks (lines ~119-394). These are dead legacy code providing no value.

- [ ] **Step 3: Remove commented-out code from settings_functions.py**

In `src/mountainash_settings/settings_cache/settings_functions.py`, delete the commented-out `get_app_settings()` function at the bottom.

- [ ] **Step 4: Run the full test suite**

Run: `hatch run test:test -v`

Expected: ALL PASS (no behavior changed)

- [ ] **Step 5: Commit**

```bash
git add -u
git commit -m "cleanup: remove dead code from settings_cache modules

Remove unreachable build_path_template(), commented-out legacy methods
from SettingsManager, and commented-out get_app_settings()."
```
