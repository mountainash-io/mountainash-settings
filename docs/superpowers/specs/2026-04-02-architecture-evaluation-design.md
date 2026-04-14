# Architecture Evaluation: mountainash-settings

**Date:** 2026-04-02
**Scope:** Validate core design decisions across four architectural layers
**Method:** Design principles audit (correctness, predictability, simplicity)

## Executive Summary

mountainash-settings extends pydantic-settings with caching, multi-format config file support, parameter merging, and template resolution. The core architectural idea -- separating structural configuration identity from runtime overrides -- is genuinely well-conceived. The template system is clean and intuitive. However, the caching layer has a mutation bug, the merge framework is over-layered, the `namespace` field is dead weight, and `secrets_dir` is misclassified.

## Layer-by-Layer Findings

### Layer 1: Two-Tier Caching System

**Components:** `@lru_cache` on `_get_settings()` + `SettingsManager.settings_object_cache` dict

**Context:** Originally developed for multi-process systems (Dagster) where singleton preservation across process boundaries was unreliable. The redundancy was a rational defensive choice in that environment.

#### Bug: Mutation of cached objects

`SettingsManager.get_settings_object()` (`settings_manager.py:50`) calls `update_settings_from_dict()` directly on the cached instance when override kwargs are present. This mutates the shared cached object in-place, meaning subsequent callers receive an object polluted by a previous caller's runtime kwargs.

The `apply_runtime_overrides()` path in `settings_functions.py:111` correctly calls `model_copy()` first. The two paths are inconsistent.

**Impact:** Silent data corruption. Caller B gets Caller A's runtime overrides baked into their "cached" base settings.

#### Redundancy

`lru_cache` wraps the function that populates `settings_object_cache`. The `lru_cache` will always hit first on subsequent calls, making the dict lookup in `SettingsManager` unreachable after the first call per key. The two layers are keyed identically and serve the same purpose.

**Note:** In the original Dagster context, `lru_cache` doesn't survive process forks (each worker gets its own), so both layers may have been doing real work in different processes. If multi-process support is still a requirement, this should be explicitly designed for rather than accidentally supported.

#### Recommendations

1. **P0 (Bug):** Fix the mutation in `SettingsManager.get_settings_object()` -- either copy before mutating, or remove the override logic from this path entirely and let `apply_runtime_overrides()` handle it exclusively
2. **P1:** Decide whether multi-process caching is a requirement. If yes, design explicitly (e.g., shared-memory cache, or accept per-process caches). If no, collapse to a single `lru_cache`-based approach and remove `SettingsManager` as a class
3. **P2:** If `SettingsManager` is retained, make the singleton pattern explicit rather than hidden behind `@lru_cache` on `get_settings_manager()`

---

### Layer 2: Structural vs Runtime Parameter Split

**Components:** `SettingsParameters` frozen dataclass with custom `__hash__`/`__eq__`

#### Verdict: Strongest layer in the architecture

The separation of structural parameters (cache identity) from runtime parameters (applied on retrieval) is a genuinely useful pattern that solves a real problem. The documentation on `__hash__` and `__eq__` is excellent.

#### Bug: `secrets_dir` misclassified as runtime

`secrets_dir` is excluded from the hash, but pydantic-settings reads configuration values from files in this directory during construction. Two parameter sets with the same structural params but different `secrets_dir` values would produce different field values, yet hash to the same cache key. The second caller's `secrets_dir` is silently ignored.

#### Recommendations

1. **P0 (Bug):** Move `secrets_dir` from runtime to structural -- include it in `__hash__` and `__eq__`
2. **P2:** Consider documenting the structural/runtime split as a first-class concept in the README, since it's the most distinctive architectural contribution of this package

---

### Layer 3: The Merge Framework

**Components:** `SettingsParameterMerger`, `FieldMergeUtils`, `SettingsUtils` (facade), `SettingsKwargsHandler`, `GenericMerger` (legacy), `MergePriority` (legacy), plus four module-level merge functions

#### Over-layered

10 participants for what is fundamentally: "given two `SettingsParameters`, produce a third by combining fields with a priority flag." The four module-level functions (`_merge_simple`, `_merge_config_files`, `_merge_kwargs`, `_merge_settings_class`) are clean and correct. Everything above them is indirection without added behavior.

#### Duplicated kwargs unwrapping

The `p_kwargs.get("kwargs", p_kwargs)` unwrapping pattern appears in both `_merge_kwargs` (`merge_framework.py:50`) and `SettingsKwargsHandler.format_kwargs_dict()` (`kwargshandler.py:26`). It's idempotent so it doesn't break, but it signals that the boundary between raw user input and normalized internal format isn't clearly drawn.

#### Per-field strategies are well-chosen

- Config files: combine and deduplicate (correct -- you want all files loaded)
- Settings class: validate compatibility, raise if different (correct -- mixing classes is a bug)
- Scalars (namespace, env_prefix): last-wins (correct -- override semantics)
- Kwargs: merge with second taking precedence (correct -- caller overrides base)

#### Recommendations

1. **P1:** Collapse to a single merge entry point. The four module-level functions are the right core. Wrap them in one `merge()` function or a single class method on `SettingsParameters` itself. Remove `SettingsParameterMerger`, `FieldMergeUtils`, `GenericMerger`, `MergePriority`
2. **P1:** Remove `SettingsUtils` as a facade class -- its methods are all one-line delegations. Move the merge entry point to `SettingsParameters.merge()` or a standalone function
3. **P2:** Normalize kwargs exactly once, at the boundary (`SettingsParameters.create()`), and trust internal code to receive clean data. Remove defensive re-unwrapping in merge functions

---

### Layer 4: Template Resolution via `post_init`

**Components:** `_build_template_mapping()`, `init_setting_from_template()`, `format_template_from_settings()` on `MountainAshBaseSettings`

#### Verdict: Cleanest layer, no changes recommended

Simple, predictable, well-proportioned. The `{placeholder}` syntax is immediately intuitive. The UPath integration for cross-platform path templates is a nice touch. Three methods, no unnecessary abstractions.

#### Known constraint: ordering dependency

Template resolution order depends on the order the subclass calls `init_setting_from_template()` in `post_init()`. If field A references field B which references field C, the author must resolve C -> B -> A. This is a reasonable trade-off -- automatic topological sorting would add complexity for a scenario that rarely arises. Worth documenting.

#### Recommendations

1. **P3:** Document the ordering constraint in the docstring of `post_init()` or in the README's template section
2. **No structural changes needed**

---

### Cross-Cutting: The `namespace` Field

**Components:** `SettingsParameters.namespace`, `MountainAshBaseSettings.SETTINGS_NAMESPACE`, `_init_namespace()`, merge logic in `FieldMergeUtils.merge_namespaces()`

#### Dead weight with false affordance

`namespace` participates in cache identity and is stored on the settings instance, but has zero behavioral effect. It doesn't influence config file selection, environment variable scoping, secret lookup, or any resolution logic. It's purely a cache discriminator.

A user seeing `namespace="production"` would reasonably expect it to influence behavior. It doesn't. In the test suite, namespace values like `"test_init_file_prefix2"` reveal the actual use case: ensuring unique cache entries for test isolation.

With the structural caching strategy working correctly, the difference between two settings instances should come from different config files, env_prefix, settings_class, or secrets_dir -- not an arbitrary label.

#### Recommendations

1. **P1:** Remove `namespace` from `SettingsParameters`, `MountainAshBaseSettings`, hash/eq logic, merge framework, and all related helpers (`_init_namespace`, `merge_namespaces`, `"DEFAULT"` fallback)
2. **P1:** Update tests to not rely on unique namespace strings for cache isolation. Tests should either use unique structural parameters or clear the cache between tests

---

## Prioritized Recommendation Summary

| Priority | Item | Layer | Type |
|----------|------|-------|------|
| **P0** | Fix cached object mutation in `SettingsManager.get_settings_object()` | Caching | Bug |
| **P0** | Move `secrets_dir` to structural parameters (include in hash/eq) | Parameters | Bug |
| **P1** | Remove `namespace` field entirely | Cross-cutting | Simplification |
| **P1** | Collapse merge framework to single entry point | Merge | Simplification |
| **P1** | Remove `SettingsUtils` facade class | Merge | Simplification |
| **P1** | Decide on single-process vs multi-process caching strategy | Caching | Architecture |
| **P2** | Normalize kwargs once at boundary, remove defensive re-unwrapping | Merge | Cleanup |
| **P2** | Document structural/runtime split as first-class concept | Parameters | Documentation |
| **P2** | Make singleton pattern explicit if `SettingsManager` is retained | Caching | Clarity |
| **P3** | Document template ordering constraint | Templates | Documentation |

## Minor: Dead Code

`build_path_template()` at `settings_functions.py:114` is defined inside `get_settings()` after the `return` statement. It's unreachable. Should be removed or moved to a utility module.

## What to Preserve

These are genuine strengths that should survive any refactoring:

- **Structural vs runtime parameter split** -- the core caching insight
- **`SettingsParameters` as a frozen dataclass** -- immutable, hashable, well-documented
- **Per-field merge strategies** -- combine files, validate classes, last-wins for scalars
- **Template resolution via `post_init`** -- simple, intuitive, right-sized
- **Multi-format config file support** with `FileTypeRegistry` -- extensible, clean
- **The `create()` classmethod pattern** -- normalizes inputs before construction
- **UPath integration** for cross-platform path templates
