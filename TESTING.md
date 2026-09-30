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
hatch run test_github:pytest tests/settings/test_base_settings.py -v
hatch run test_github:pytest tests/examples -q
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

## Suite organisation and fixtures

Tests follow the package's module ownership: `settings/` (including `app/`),
`settings_cache/`, `settings_parameters/`, `profiles/` and `secrets/` (including
`native/`). Root `test_resolve.py` and `test_public_api.py` cover root-module
contracts. `tests/examples/` executes documentation; `tests/tools/` covers repository
tooling. Select an owner directory to run its tests. Markers describe test types
without duplicating this tree under unit/integration directories.

- `tests/conftest.py` explicitly registers shared modules from `tests/fixtures/`.
  Request fixtures by argument; import reusable models from their support module.
- Use `isolated_settings_manager` for public retrieval and direct manager tests
  that need the same fresh owner. Mutable settings, stores and managers are
  function-scoped. A test exercising manager construction may construct its own.
- Keep domain setup in the nearest `conftest.py`: the AppSettings clock under
  `settings/app/`, subprocess environments under `examples/`, and the filesystem
  `store` fixture under `secrets/`. Keep scenario-specific models and helpers close
  to their tests when their declarations are part of the scenario.
- Use `tmp_path` for writable resources and the shared configuration fixtures for
  repeated inputs. Static inputs live in `tests/data/`, reached via `test_data_dir`
  rather than a working-directory-relative string. Keep raw malformed inputs
  visible in the tests that exercise them.
- Declare markers in `pytest.ini`. Support models named `Test*` use
  `__test__ = False` so pytest does not mistake them for test containers.

The native qualification runner copies `tests/secrets/native/`, the secrets
conftest and selected portable tests into an independent directory. Keep that
subset self-contained when adding fixture/helper dependencies. Root fixtures
are deliberately outside its `--confcutdir` boundary.

`tests/test_config_files.py` contains historical commented code and `tests/test.ipynb`
is a historical notebook. Neither contributes collected pytest cases.

## Optional sibling-checkout environment

The `test` environment installs `mountainash-auth-client` from the sibling
`../mountainash-auth-client` checkout and includes extra pytest plugins. Use it
when that dependency is available and relevant; it is not required for the
settings-only suite.

| Command | Purpose |
|---|---|
| `hatch run test:test` | Suite with coverage, JUnit and JSON/XML/HTML coverage reports |
| `hatch run test:test-quick` | Suite without coverage |
| `hatch run test:test-target-quick tests/settings/test_base_settings.py` | Focused tests without coverage |
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

Native store tests live in `tests/secrets/native/`. Linux needs `libacl.so.1` and
ACL fixture tools (`acl` on Ubuntu); macOS and Windows use their native APIs.
Platform-specific tests may be unselected on other platforms. A local Linux
pass does not replace the installed three-platform qualification.

## GitHub Actions

| Workflow | Trigger and scope |
|---|---|
| [Pytest](.github/workflows/python-run-pytest.yml) | Pushes to `develop`/`main`, PRs changing source/tests/examples/README/test configuration or this workflow, and manual dispatch; Ubuntu 24.04 / Python 3.12, `test_github:test-cov`, Codecov coverage and test-result uploads |
| [Production typing](.github/workflows/python-run-mypy.yml) | All PRs and pushes to `develop`; four mypy passes |
| [Local Store Candidate](.github/workflows/native-store-candidate.yml) | PRs targeting `develop`, or manual dispatch; installed native-store checks on Linux/macOS/Windows, Python 3.12 |
| [Release Candidate Qualification](.github/workflows/release-candidate-qualification.yml) | Manual dispatch; full installed suite and two-process lifecycle on all three OSes, Python 3.12/3.13, wheel and sdist-rebuilt wheel |
| [Build, Verify, and Publish](.github/workflows/build-and-release-package.yml) | PRs targeting `main`/`develop`, or manual dispatch; package build/install verification, separately gated publication |

Codecov coverage and test-result uploads authenticate with GitHub OIDC using
job-scoped `id-token: write`. Upload failures fail the job. Push runs keep the
`develop` and `main` coverage baselines current after merges.

Documentation-only PRs outside the README/examples do not trigger Pytest.
Run relevant local checks or dispatch it manually. Its retained
`fallback_branch` input sets an environment variable; the current workflow does
not check out dependency repositories or select matching dependency branches.

For exact-artifact qualification and publication, follow [RELEASE.md](RELEASE.md).
