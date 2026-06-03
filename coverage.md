# Package Profile Coverage Report

Generated: 2026-05-13T00:00:00Z
Source hash: b09b31cf2867ac909f50975ed1d4e79090c8d359
Branch: develop

## Summary

| Category | Count |
|---|---|
| Source files discovered | 37 |
| Modules profiled | 29 |
| Profiles ignored (with reason) | 8 |
| Missing profiles | 0 |
| Stale profiles | 0 |
| Orphaned profiles | 0 |
| Coverage gaps | 3 (open questions, not blockers) |

## Ignored Paths

| Path | Reason |
|---|---|
| `src/mountainash_settings/__init__.py` | Package root aggregator — covered by all module profiles via "exported from __all__" evidence |
| `src/mountainash_settings/auth/__init__.py` | Auth sub-package aggregator — covered by individual auth module profiles |
| `src/mountainash_settings/profiles/__init__.py` | Profiles sub-package aggregator — covered by individual profiles module profiles |
| `src/mountainash_settings/secrets/__init__.py` | Secrets sub-package aggregator — covered by secrets.registry profile |
| `src/mountainash_settings/settings/__init__.py` | Settings sub-package aggregator — covered by base_settings profile |
| `src/mountainash_settings/settings/app/__init__.py` | App sub-package aggregator — covered by app_settings profile |
| `src/mountainash_settings/settings_cache/__init__.py` | Settings cache sub-package aggregator — covered by settings_functions and settings_manager profiles |
| `src/mountainash_settings/settings_parameters/__init__.py` | Settings parameters sub-package aggregator — covered by individual settings_parameters profiles |

## Public Modules Without User Facet Coverage

All public modules with `doc_priority: essential` appear in the users facet.

## Internal Modules Without Maintainer Facet Coverage

All internal architecture modules appear in the maintainers facet.

## Open Questions (Coverage Gaps)

1. **AppSettings public status** — `mountainash_settings.settings.app.app_settings` is not in package `__all__` but is a non-trivial convenience class. Should it be part of the primary public API?

2. **DescriptorProfile.__adapter__ contract** — The `__adapter__` extension point is declared but its callable signature is not documented in the codebase. Extension authors need a specification.

3. **Thread-safety of model_config mutation** — `MountainAshBaseSettings.__init__` mutates the class-level `model_config` dict before calling `super().__init__()`. Under concurrent construction of different subclasses sharing the same `model_config`, this could race. Needs audit before recommending for multi-threaded applications.

## Low-Confidence Profiles

| Module | Confidence | Reason |
|---|---|---|
| `mountainash_settings.settings_parameters.merge_framework` | medium | Module name implies more planned content; currently only ValidationError |

## Facets Written

- users
- maintainers
- extension-authors
- broader-hype

## Not Yet Written

- contributors (not requested in this run — overlaps with maintainers + extension-authors; low priority)
- backend-architecture (low priority for initial profile — maintainers facet covers the key architecture points)
- executives-marketing (deferred — broader-hype facet covers the key claims)
