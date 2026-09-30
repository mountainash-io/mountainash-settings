# Testing

Use Python 3.12+ and [Hatch](https://hatch.pypa.io/). Run commands from the repository
root. [hatch.toml](hatch.toml) owns environments and scripts;
[pyproject.toml](pyproject.toml) owns package dependencies and coverage settings.
Both test environments currently select Python 3.12.

## Everyday checks

The `test_github` environment runs the settings-only suite without sibling checkouts:

```bash
python -m pip install hatch
hatch run test_github:test
hatch run test_github:test-cov
```

For focused work:

```bash
hatch run test_github:pytest tests/test_base_settings.py -v
hatch run test_github:pytest tests/test_readme_examples.py tests/test_examples.py -q
```

Append `::test_name` to a test path to select a specific test. The README/example
checks execute the documented code, independent recipe scripts and generated
profile invariants.

Run lint, production typing and package builds as appropriate:

```bash
hatch run ruff:check
hatch run mypy:check
hatch build
```

Ruff checks `src`; `hatch run ruff:fix` applies fixes. Mypy is pinned to 1.10.1
with the existing rules and test exclusion. `tools/check_types.py` runs common,
Linux POSIX, macOS POSIX and Windows-native passes; do not add `--strict`.

## Optional sibling-checkout environment

The `test` environment installs `mountainash-auth-client` from the sibling
`../mountainash-auth-client` checkout and includes extra pytest plugins. Use it
when that dependency is available and relevant; it is not required for the
settings-only suite.

| Command | Purpose |
|---|---|
| `hatch run test:test` | Suite with coverage, JUnit and JSON/XML/HTML coverage reports |
| `hatch run test:test-quick` | Suite without coverage |
| `hatch run test:test-target-quick tests/test_base_settings.py` | Focused tests without coverage |
| `hatch run test:test-changed-quick` | Selection through pytest-picked; not a substitute for the suite |
| `hatch run test:test-ci` | Structured pytest JSON, JUnit and coverage reports |

Additional marker, benchmark and targeted-coverage scripts are defined in
`hatch.toml`. There is no `test:cov` script.

## Coverage and native-platform checks

`test_github:test-cov` writes `coverage.xml` and `junit.xml`. `test:test` also
writes `coverage.json` and `htmlcov/index.html`; `test:test-ci` adds
`pytest_report.json`. Report formats depend on the selected script.

The main coverage commands pass `--cov-config={root}/pyproject.toml` explicitly.
Keep that configuration propagation when changing subprocess commands: the
examples run from temporary working directories and must retain the same
branch-coverage settings as their parent.

Native store tests live in `tests/native_store/`. Linux needs `libacl.so.1` and
ACL fixture tools (`acl` on Ubuntu); macOS and Windows use their native APIs.
Platform-specific tests may be unselected on other platforms. A local Linux
pass does not replace the installed three-platform qualification.

## GitHub Actions

| Workflow | Trigger and scope |
|---|---|
| [Pytest](.github/workflows/python-run-pytest.yml) | PRs changing `src/mountainash_settings/**`, or manual dispatch; Ubuntu 24.04 / Python 3.12, `test_github:test-cov`, Codecov coverage and test-result uploads |
| [Production typing](.github/workflows/python-run-mypy.yml) | All PRs and pushes to `develop`; four mypy passes |
| [Local Store Candidate](.github/workflows/native-store-candidate.yml) | PRs targeting `develop`, or manual dispatch; installed native-store checks on Linux/macOS/Windows, Python 3.12 |
| [Release Candidate Qualification](.github/workflows/release-candidate-qualification.yml) | Manual dispatch; full installed suite and two-process lifecycle on all three OSes, Python 3.12/3.13, wheel and sdist-rebuilt wheel |
| [Build, Verify, and Publish](.github/workflows/build-and-release-package.yml) | PRs targeting `main`/`develop`, or manual dispatch; package build/install verification, separately gated publication |

The Pytest workflow does not run automatically for test-only or documentation-only
changes. Run the relevant local checks or dispatch it manually. Its retained
`fallback_branch` input sets an environment variable; the current workflow does
not check out dependency repositories or select matching dependency branches.

For exact-artifact qualification and publication, follow [RELEASE.md](RELEASE.md).
