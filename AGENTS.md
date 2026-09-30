# Agent guidance for mountainash-settings

This repository contains the Python package, tests, usage documentation, examples
and docs site. Architecture contracts and planning records live in the sibling
`../mountainash-central` checkout. Keep this file focused on navigation and local
working instructions; maintain architectural rules in their owning principles.

## Finding architecture guidance

Start with the [principles index](../mountainash-central/01.principles/mountainash-settings/README.md).
The following paths are relative to
`../mountainash-central/01.principles/mountainash-settings/`:

| Topic | Where to read and what you will find |
|---|---|
| Settings declaration and retrieval | `b.usage/settings-creation-patterns.md` covers construction and retrieval patterns; `a.architecture/descriptor-based-profiles.md` and `migration-decision-criteria.md` cover declarative profiles and adoption trade-offs |
| Profile declarations and driver integration | `b.usage/declaring-descriptor-profiles.md` and `writing-sdk-adapters.md` cover specs, registration, emission and adapters |
| Cache lifecycle and ownership | `a.architecture/caching-strategy.md`, `structural-runtime-parameter-split.md` and `just-in-time-settings-resolution.md` cover source snapshots, structural identity and retrieval; `b.usage/configuration-forking.md` covers invocation-local overrides |
| Sources and merging | `a.architecture/multi-source-configuration.md`, `merge-strategy.md` and `b.usage/config-file-handling.md` cover source composition, precedence and parameter/file handling |
| Templates | `a.architecture/template-resolution.md`, `b.usage/post-init-patterns.md` and `path-templating-with-upath.md` cover derivation, initialization and path construction |
| Secrets and diagnostics | `a.architecture/secrets-resolution.md` and `configuration-observability.md` cover storage/reference ownership and diagnostic boundaries; the index links the shared filesystem trust policy |
| Development and release | `c.development/testing-philosophy.md`, `code-style.md` and `versioning-and-releases.md` cover testing, style and release conventions |

Read the relevant principles before changing behavior. Some pages still contain
pre-0.1 API names and contracts, including descriptor profiles, bundled auth,
singular adapters, provider-name selection, cached-instance reuse and CalVer.
Reconcile them with the approved
[0.1 API design](../mountainash-central/04.planning/mountainash-settings/superpowers/specs/2026-09-27-v0.1-api-reset-and-typing-design.md),
later owner decisions, current code and tests. Report contradictions rather than
restoring obsolete behavior based on a historical status label.

## Planning records

Paths below are relative to `../mountainash-central`:

| Artifact | Location |
|---|---|
| Design specs | `04.planning/mountainash-settings/superpowers/specs/` |
| Implementation plans | `04.planning/mountainash-settings/superpowers/plans/` |
| Backlog and history | `04.planning/mountainash-settings/a.backlog/INDEX.md` |

Override skills that default to local `docs/superpowers/` paths. Central planning
edits remain uncommitted for owner review unless explicitly authorized. Preserve
unrelated work in both repositories.

The [JSON Schema backlog item](../mountainash-central/04.planning/mountainash-settings/a.backlog/restore-settings-json-schema-generation.md)
records the reproduced `model_json_schema()` limitation, its cause and acceptance
criteria. Consult it before documenting schema support or changing bookkeeping.

## Source map

| Location | Responsibility |
|---|---|
| `src/mountainash_settings/settings/base_settings.py` | Construction, source ordering, templates, provenance and persistence |
| `src/mountainash_settings/settings_parameters/` | Selectors, normalization and merge semantics |
| `src/mountainash_settings/settings_cache/` | Source capture and isolated materialization |
| `src/mountainash_settings/profiles/` | Specs, field installation, emission, registry and invariants |
| `src/mountainash_settings/resolve.py` | Reference resolution in dictionaries and model trees |
| `src/mountainash_settings/secrets/` | Local records, storage protocols and native implementations |
| `tests/secrets/native/` | Filesystem and platform-native regressions |
| `tests/tools/` | Qualification and typing tooling checks |
| `tests/fixtures/` | Explicitly registered shared cache/config fixtures and reusable models |
| `examples/` | Independent configuration recipes using consistent application/database settings and shared fixtures |

## Verification

Use `pyproject.toml` and `hatch.toml` as dependency and environment authorities.

```bash
hatch run test_github:test
hatch run test_github:pytest tests/examples -q
hatch run test:test
hatch run ruff:check
hatch run mypy:check
hatch build
```

`test_github` runs the settings-only suite. `test:test` includes coverage and
expects a sibling auth-client checkout; there is no `test:cov` script. For one
test, use `hatch run test_github:pytest path/to/test.py::test_name -v`.

Keep mypy pinned to 1.10.1 with the existing rules and test exclusion; do not enable
`--strict`. `tools/check_types.py` runs common, Linux POSIX, macOS POSIX and
Windows-native passes. Ruff's configured check covers `src`.

## README and examples

The root README owns positioning, a broad capability map, one runnable quick
start and links to depth. `tests/examples/test_readme_examples.py` executes its actual
Python block with its YAML input; do not expand it into a concatenated tutorial.

`examples/` contains sibling topic directories, each with a README and
an independently runnable `example.py` (or `test_profiles.py` for invariants).
Keep the application/database vocabulary and shared fixture data coherent. Repeat small
declarations when they keep the lesson visible; never import another recipe or
require it to run first. Each README states a question, root-level command,
expected result and relevant explanation. Resolve bundled paths from `__file__`.

`tests/examples/test_examples.py` discovers scripts and executes them in fresh
processes, with isolated environments and temporary writable resources. It also
runs the generated invariant checks through pytest. Preserve explicit coverage
configuration propagation for subprocesses that change working directory.

Explain declaration and retrieval as two use cases, each with two patterns. The
suite index supplies a reading order; recipes remain independently accessible.
The threaded comparison is deferred at the owner's request. Contributor and
textbook maintenance instructions live in `CONTRIBUTING.md` and `docs-site/README.md`.

The docs sites have their own refresh workflows. Do not expand README work into
site regeneration or edit generated provenance just to advance its baseline.

## Release work

Read [RELEASE.md](RELEASE.md) and the central release records before release work.
The local `release-candidate-qualification.yml` workflow and
`tools/qualify_release_candidate.py` contain qualification execution details.
Central records own qualification evidence and authorization status; release
authorization is currently withheld during documentation work.

Use `develop` as the normal PR target; `main` is the production release branch.
Keep changes on their intended branches and respect required review.
