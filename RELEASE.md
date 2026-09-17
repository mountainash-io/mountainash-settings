# Release Procedure

mountainash-settings requires Python 3.12+. Source changes and candidate builds do not establish public publication. Its declared third-party dependencies must resolve from public PyPI.

## Unpublished compatibility note — MAS-SEC-001

The next release removes the public `SETTINGS_SOURCE_KWARGS` model field.
Diagnostic consumers must use the value-free
`SETTINGS_SOURCE_KWARG_NAMES` tuple; trusted reconstruction consumers must use
`extract_settings_parameters()` and explicitly access its `kwargs` when
needed. There is no compatibility alias or raw-provenance replacement.

Extracted kwargs are intentionally accessible reconstruction inputs, not a
safe serialization format. Normal `SettingsParameters` representation omits
kwargs, while explicit serialization, pickle, debugger inspection, and direct
access remain trusted operations. Local candidate verification is recorded below;
merge and publication remain separately authorized.

### Local candidate verification — 2026-09-17

- Branch: `bugfix/mas-sec-001-secret-safe-provenance`, based on `05612f3f68d91828bf09cdd9b7fd70b91f0607bf`; uncommitted implementation, not a released fix.
- Focused provenance/resolver/parameter suite: 196 passed. Full suite: 503 passed, 18 collection/deprecation warnings. Production Ruff check passed.
- Installed public-package smoke passed on Python 3.12.14 and 3.13.15 outside the checkout with asserted venv imports, no PYTHONPATH and `-I`.
- Exact wheel SHA-256 on both runtimes: `a57fde543333a798d35b723fd193d9f884e0399054d1d58a24f1bfc43d6fb5b4`. Candidate version remains 26.5.0; this does not approve reusing a published version.
- Smoke exercised private reference preservation, zero extraction reads, partial update/persist, uncached reconstruction, nested ownership, diagnostics and unsupported extraction. Dependencies: Pydantic 2.13.5, pydantic-settings 2.15.0, universal_pathlib 0.3.10, PyYAML 6.0.3.
- Scoped security review found no remaining MAS-SEC-001 blocker after corrections. Cache/fork isolation (002), common safe errors (006) and the other programme items are not certified by this fix.
- Open gates: `hatch run mypy:check` reports 60 errors in 13 files; documented `textbook-refresh` tooling was unavailable, so descriptions were updated without advancing generation baselines. No all-checks-green, generated-site, merge or publication claim.

## Prepare and verify

1. Prepare the final unused version in `src/mountainash_settings/__version__.py` under this repository's version policy. Use reviewed `release/*` or `hotfix/*` changes and existing branch/CI rules; do not push directly to protected branches.
2. `build-and-release-package.yml` builds candidates for PRs targeting `main`/`develop` and for manual dispatch. Default manual input is `publish=false`.
3. The workflow builds exactly one wheel and one sdist with public build requirements, checks metadata and records hashes/source/run identity. It installs the wheel and an independently sdist-derived wheel in fresh external Python 3.12 environments, using only public PyPI dependencies.
4. Installation reports, `pip check`, imported-module origins and wheel/sdist metadata agreement must pass. A sibling checkout or private wheelhouse is not final release evidence.

## Publishing setup requires separate authorization

- Establish PyPI ownership or a pending publisher for `mountainash-settings`. Pending publishers do not reserve names.
- Configure the GitHub environment **`pypi`** with required human reviewers and exactly one custom deployment policy allowing the **`main` branch**.
- Configure PyPI Trusted Publishing for this repository's exact owner/name, workflow filename **`build-and-release-package.yml`**, and environment **`pypi`**.
- No token, unprotected environment, fallback branch or alternate index substitutes for missing setup. Preflight fails closed if protection is missing or cannot be verified.

## Approve, publish, confirm

After authorization, dispatch on `main` with `publish=true`. Review the exact source/version, wheel/sdist hashes and verification evidence before approving the `pypi` environment.

The publisher downloads the exact same-run distribution/evidence artifact IDs, checks identity and hashes, and uploads with short-lived OIDC authority. It never rebuilds, rewrites the version or uses `skip-existing`. It then checks the public PyPI file set/hashes and performs a fresh public-index install/import.

Evidence artifacts are named `release-dist-<run>-<attempt>`, `release-evidence-<run>-<attempt>` and, after successful confirmation, `publication-evidence-<run>-<attempt>`. The old automatic GitHub/SBOM/wheels-repository release path is replaced; historical releases remain untouched.

## Failure handling

Missing public dependencies, incompatible metadata, install/import failures, changed hashes or missing environment protection block publication. Collisions, partial uploads and unexpected public files require explicit reconciliation before a new attempt; upload success alone is not confirmation.

Do not relax safe sdist extraction to accept repository-local tooling links. Source archives contain portable package/build inputs rather than the development checkout. Source/version changes require a new candidate and approval.

See [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/adding-a-publisher/) and [first-publication setup](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/).
