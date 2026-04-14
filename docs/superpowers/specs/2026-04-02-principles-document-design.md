# Principles Document Design for mountainash-settings

**Date:** 2026-04-02
**Location:** `/home/nathanielramm/git/mountainash-io/mountainash/mountainash-central/01.principles/mountainash-settings/`
**Scope:** Create a principles directory following the established mountainash-expresions pattern

## Goal

Consolidate the validated architecture decisions, usage patterns, and development conventions for mountainash-settings into a browsable, authoritative reference. Primary audience: LLM coding agents who need to understand patterns and guardrails without analyzing the entire package. Secondary audiences: the maintainer returning after time away, and future contributors.

## Structure

```
mountainash-settings/
  PRINCIPLES.md              # Governance document
  README.md                  # Index with status tables
  a.architecture/            # 5 documents
    structural-runtime-parameter-split.md
    caching-strategy.md
    template-resolution.md
    multi-source-configuration.md
    merge-strategy.md
  b.usage/                   # 4 documents
    settings-creation-patterns.md
    path-templating-with-upath.md
    config-file-handling.md
    post-init-patterns.md
  c.development/             # 3 documents
    testing-philosophy.md
    code-style.md
    versioning-and-releases.md
```

## Governance (PRINCIPLES.md)

Adapted from mountainash-expresions governance with:
- Same document template (Status, The Principle, Rationale, Examples, Anti-Patterns, Technical Reference, Future Considerations)
- Same status markers (ENFORCED, ADOPTED, PROPOSED, EXPLORATORY)
- Three categories instead of seven (simpler package)
- Category precedence: a > b > c
- Added "Reading Order for Agents" section that directs agents to the right 2-3 documents based on their task

## Category Mapping

| Category | Concern | Role |
|----------|---------|------|
| **a** | Architecture | Structural foundations -- caching, parameters, merge, templates |
| **b** | Usage | Consumer-facing patterns -- how to create, configure, and use settings correctly |
| **c** | Development | Conventions for contributing -- testing, style, releases |

## Document Inventory

### a. Architecture (5 documents)

| Document | Status | Summary |
|----------|--------|---------|
| `structural-runtime-parameter-split.md` | ENFORCED | Cache identity determined by structural params (config_files, settings_class, env_prefix, secrets_dir); kwargs are runtime overrides applied on retrieval |
| `caching-strategy.md` | ENFORCED | Two-tier caching (lru_cache + SettingsManager dict); cached instances never mutated; runtime overrides produce copies via model_copy() |
| `template-resolution.md` | ENFORCED | {placeholder} fields resolved in post_init() after all config sources loaded; resolution order is caller-controlled |
| `multi-source-configuration.md` | ENFORCED | Settings load from env vars, .env, YAML, TOML, JSON, secrets dirs; pydantic-settings field value priority governs precedence |
| `merge-strategy.md` | ENFORCED | SettingsParameters.merge() combines two parameter sets: config files deduplicated, classes validated compatible, scalars last-wins, kwargs merged dicts |

### b. Usage (4 documents)

| Document | Status | Summary |
|----------|--------|---------|
| `settings-creation-patterns.md` | ENFORCED | Three creation patterns: direct construction, SettingsParameters.create() + get_settings(), ClassMethod.get_settings(); when to use each |
| `path-templating-with-upath.md` | ENFORCED | Use UPath / operator for cross-platform path templates; never use PLATFORM_SLASH or f-strings with separators |
| `config-file-handling.md` | ENFORCED | FileTypeRegistry identifies by extension; dotfiles supported; files validated for existence at construction |
| `post-init-patterns.md` | ADOPTED | Override post_init() for template resolution and computed fields; resolve dependencies in topological order; use reinitialise flag |

### c. Development (3 documents)

| Document | Status | Summary |
|----------|--------|---------|
| `testing-philosophy.md` | ENFORCED | isolated_settings_manager fixture for cache isolation; never disable/skip tests; present failures to user |
| `code-style.md` | ENFORCED | Ruff formatting, Google-style docstrings, typing annotations, hatch environments, uv installer |
| `versioning-and-releases.md` | ADOPTED | CalVer YYYY.MM.MICRO; main for production, develop for RC; protected branches require code owner approval |

## Document Content Summary

### a.1 structural-runtime-parameter-split.md

**The Principle:** SettingsParameters separates fields into structural (affect cache identity) and runtime (applied on retrieval). Structural: config_files, settings_class, env_prefix, secrets_dir. Runtime: kwargs only. Two parameter sets with identical structural params but different kwargs hash to the same value.

**Key Anti-Patterns:**
- Adding new fields without deciding structural vs runtime
- Using arbitrary discriminator fields to force separate cache entries
- Treating secrets_dir as runtime (it's a config source)

### a.2 caching-strategy.md

**The Principle:** Two-tier caching (lru_cache + SettingsManager dict). Cached instances never mutated. model_copy() before update_settings_from_dict() when override kwargs present. No-override callers get original cached instance directly.

**Key Anti-Patterns:**
- Calling update_settings_from_dict() on cached instance without copying
- Assuming object identity when kwargs differ
- Manipulating lru_cache directly in tests

### a.3 template-resolution.md

**The Principle:** {placeholder} fields resolved in post_init() via init_setting_from_template(). Formatter().parse() extracts referenced field names. Resolution order controlled by subclass call sequence.

**Key Anti-Patterns:**
- Resolving templates in __init__ before config sources loaded
- Assuming automatic dependency ordering
- Using f-strings for templates (evaluate at definition time)

### a.4 multi-source-configuration.md

**The Principle:** Extends pydantic-settings with env, YAML, TOML, JSON, secrets simultaneously. Precedence: init > env > dotenv > YAML > TOML > JSON > file secrets. FileTypeRegistry identifies by extension including dotfiles.

**Key Anti-Patterns:**
- Passing extensionless files
- Assuming YAML overrides env vars (env has higher priority)
- Relative paths without understanding expanduser() behavior

### a.5 merge-strategy.md

**The Principle:** SettingsParameters.merge(base, other) with per-field strategies: combine config files (deduplicate+sort), validate class compatibility, last-wins for scalars, merge dicts for kwargs. prioritise_base=True inverts.

**Key Anti-Patterns:**
- Merging different settings_class values
- Expecting config file order preserved across merges
- Relying on merge to normalize kwargs format

### b.1 settings-creation-patterns.md

**The Principle:** Three patterns: (1) Direct construction for one-off/test, (2) SettingsParameters.create() + get_settings() for cached application use, (3) ClassMethod.get_settings() for subclass entry points.

**Key Anti-Patterns:**
- get_settings() without settings_class
- SettingsParameters() constructor instead of create() (bypasses normalization)
- Re-creating settings in a loop instead of using cache

### b.2 path-templating-with-upath.md

**The Principle:** str(UPath("~") / "data" / "{ORG}" / "reports"). UPath handles platform separators. Placeholders survive string conversion. Resolved in post_init().

**Key Anti-Patterns:**
- PLATFORM_SLASH or os.sep (deprecated/removed)
- f-strings with path separators
- Backslash as UPath operator

### b.3 config-file-handling.md

**The Principle:** FileTypeRegistry identifies by extension (.env, .yaml/.yml, .toml, .json). Dotfiles supported. Files validated at construction (FileNotFoundError). Multiple same-type files deduplicated; later overrides earlier per pydantic-settings.

**Key Anti-Patterns:**
- Files without recognized extensions (silently ignored)
- Assuming file order preserved across merges
- Relative paths without understanding expanduser()

### b.4 post-init-patterns.md

**The Principle:** Override post_init() for templates and computed fields. Call init_setting_from_template(template_str, current_value, reinitialise) per field. current_value prevents double-resolution. Canonical pattern: define TEMPLATE field, define target field defaulting to None, resolve in post_init().

**Key Anti-Patterns:**
- Forgetting super().post_init()
- Resolving dependent templates out of order
- Setting computed fields in __init__ instead of post_init()

### c.1 testing-philosophy.md

**The Principle:** isolated_settings_manager fixture for cache isolation. Distinct cache entries via different structural params (env_prefix, config_files), not arbitrary labels. Never disable/skip tests. Present failures, ask what to fix.

**Key Anti-Patterns:**
- Unique string labels for cache isolation (old namespace pattern, removed)
- Global singleton in tests (cross-test pollution)
- Asserting object identity with kwargs present
- Auto-fixing tests without understanding

### c.2 code-style.md

**The Principle:** Ruff formatting/linting. Google docstrings. typing annotations. CamelCase classes, snake_case functions, UPPER_CASE constants. Hatch environments. uv installer.

**Key Anti-Patterns:**
- pip instead of uv
- Adding docstrings/annotations to untouched code
- Error handling for impossible internal scenarios

### c.3 versioning-and-releases.md

**The Principle:** CalVer YYYY.MM.MICRO. develop for RC, main for production. feature/bugfix/hotfix branch strategy. Protected branches, code owner approval. CI: pytest, ruff, radon. SBOMs generated.

**Key Anti-Patterns:**
- Pushing directly to main/develop
- Using semver
- Skipping CI checks

## Agent Reading Order

Included in PRINCIPLES.md governance doc:

| Task | Read first |
|------|-----------|
| Modifying settings loading or caching | a.1 structural-runtime-parameter-split, a.2 caching-strategy |
| Adding a new settings class | b.1 settings-creation-patterns, b.4 post-init-patterns |
| Adding config file support | a.4 multi-source-configuration, b.3 config-file-handling |
| Working on path templates | b.2 path-templating-with-upath, a.3 template-resolution |
| Writing or fixing tests | c.1 testing-philosophy |
| Merging or combining parameters | a.5 merge-strategy, a.1 structural-runtime-parameter-split |
| General contribution | c.2 code-style, c.3 versioning-and-releases |

## Source Material

These principles are derived from:
- Architecture evaluation: `docs/superpowers/specs/2026-04-02-architecture-evaluation-design.md`
- Refactoring implementation: 7 commits on develop (ce4feb2..38eef0d)
- Existing CLAUDE.md project instructions
- Package README and existing documentation
