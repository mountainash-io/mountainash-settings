# Release procedure

This guide covers candidate verification and PyPI publication. Historical receipts
and authorization decisions live in the
[central release records](https://github.com/mountainash-io/mountainash-central/blob/main/04.planning/mountainash-settings/superpowers/specs/2026-09-18-authorized-release-deployment-design.md).
Use [TESTING.md](TESTING.md) for local checks and
[the migration guide](docs/migration-0.1.md) for API changes.

## Current candidate — 0.1.0

The development version is **0.1.0**, using SemVer and requiring Python 3.12+.
Publication remains subject to explicit owner authorization and renewed
qualification of the final candidate. Earlier receipts qualify only their
recorded source and artifact hashes.

For this release, downstream migrations must pass ecosystem rehearsal against
identified candidate artifacts before source freeze. Downstream merges/releases
follow settings publication. Legacy-artifact deletion, GitHub release/tag work
and retirement of `mountainash-secrets` follow their separately authorized central
steps; the PyPI workflow does not perform them.

## Prepare and qualify

1. Finalize an unused version in `src/mountainash_settings/__version__.py` and run
   the checks in [TESTING.md](TESTING.md). Dependencies must resolve from public
   PyPI; sibling checkouts are not installed-release evidence.
2. Freeze the reviewed source revision after ecosystem rehearsal. Dispatch
   [Settings Release Candidate Qualification](.github/workflows/release-candidate-qualification.yml)
   on its branch/ref and verify the run's source SHA.
3. Inspect the full-suite and two-process lifecycle receipts for Linux, macOS and
   Windows, Python 3.12 and 3.13, using both wheel and sdist-rebuilt wheel installs.
   The workflow runs `tools/qualify_release_candidate.py` and
   `tools/qualify_lifecycle_receipt.py`; it retains
   `settings-release-candidate-<OS>` artifacts for 30 days.
4. Record the source revision, selected wheel/sdist hashes, receipt identities and
   rehearsal mapping in central release records. Preserve evidence before expiry.
   Source, version, dependency or build-input changes require a new candidate and
   full qualification.
5. Prepare a reviewed `release/*` PR into `main` from the qualified revision.
   The main-branch validator permits only `release/*` and `hotfix/*` source
   branches. Confirm that the release merge preserves the qualified inputs.

## Build and publication workflow

[Build, Verify, and Publish Package](.github/workflows/build-and-release-package.yml)
runs on PRs targeting `main` or `develop`, and on manual dispatch. Manual
`publish` defaults to `false`.

Its build job creates one wheel and one sdist, checks metadata, records hashes,
and verifies fresh external Python 3.12 installs of the wheel and an independently
sdist-rebuilt wheel using public dependencies. This is an installation check;
the separate qualification workflow runs the full cross-platform suite.

A publication dispatch builds a new same-run artifact pair; it does not download
the qualification run's distributions. Before approving publication, reconcile
that pair's hashes with the qualified release unit and central rehearsal evidence.
Different bytes require resolution under the central exact-artifact gate.
The workflow itself does not enforce this cross-run comparison.

### Publishing setup

- Establish PyPI ownership or a pending publisher for `mountainash-settings`.
- Configure the GitHub `pypi` environment with required human reviewers and
  exactly one custom deployment policy allowing the `main` branch.
- Configure PyPI Trusted Publishing for the exact repository, workflow
  `build-and-release-package.yml` and environment `pypi`.

The workflow preflight blocks publication when that environment protection is
missing or cannot be verified. See [PyPI Trusted Publishing setup](https://docs.pypi.org/trusted-publishers/adding-a-publisher/).

### Publish and confirm

After owner authorization, dispatch on `main` with `publish=true`. Review the
source/version, exact hashes and qualification evidence before approving `pypi`.

The publish job downloads its build job's exact artifact IDs, verifies hashes and
uploads through OIDC. It does not rebuild or use `skip-existing`. It then compares
the public PyPI file set/hashes and performs a clean public-index install/import.

Retain the run's evidence:

- `release-dist-<run>-<attempt>`: wheel and sdist.
- `release-evidence-<run>-<attempt>`: identity, hashes and installation checks.
- `publication-evidence-<run>-<attempt>`: public confirmation, after success.

Record publication links and hashes centrally. Complete the separately authorized
release/tag and branch-synchronization steps from the central contract.

## Failure handling

Metadata, dependency, install/import, hash or environment-protection failures
block publication. Version collisions, partial uploads and unexpected public
files require reconciliation before another attempt. Upload success alone is
not confirmation; retain failure evidence and resolve the discrepancy first.
