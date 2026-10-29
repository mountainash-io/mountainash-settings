# Contributing

Use Python 3.12+ and Hatch. Fork or clone the repository, create a topic branch
from current `develop`, and install the package if you need an editable environment:

```bash
python -m pip install hatch
python -m pip install -e .
```

[pyproject.toml](pyproject.toml) and [hatch.toml](hatch.toml) define dependencies
and development environments. Hatch creates its own environments for checks.

## Branches and pull requests

- Target `develop` for ordinary code, tests, documentation and dependency changes.
- Use descriptive topic names such as `feature/*`, `bugfix/*`, `chore/*` or `docs/*`.
- `main` is the production branch. Its PR validator accepts only `release/*` or
  `hotfix/*` source branches; coordinate that work through [RELEASE.md](RELEASE.md).
- Keep commits focused, explain observable changes and list the checks run in
  the PR description. Link related issues and planning records.
- Request code-owner review, address feedback and let a maintainer merge after
  the repository's required checks and approvals. Ownership is declared in
  [.github/CODEOWNERS](.github/CODEOWNERS).

## Code and verification

Follow the surrounding Python style, use type hints and keep functions focused.
Add tests for observable contracts and credible regressions; avoid checks that
duplicate stronger coverage or assert implementation details.
Place tests under their package-module owner and reuse shared fixtures according
to [the suite organisation rules](TESTING.md#suite-organisation-and-fixtures).

Start with the settings-only suite and production checks:

```bash
hatch run test_github:test
hatch run ruff:check
hatch run mypy:check
hatch run mypy:qualify
hatch build
```

See [TESTING.md](TESTING.md) for focused checks, coverage, native-platform testing
and CI scope. The optional `test` environment requires a sibling auth-client
checkout. Keep mypy pinned to 1.10.1 with its existing rules and test exclusion.
The separate installed-consumer gate checks `tests/typing/consumer.py` against
built wheels; see [typing support](docs/typing.md#qualification) for its evidence.

For source and test typing work, use the separate targets:

```bash
hatch run mypy:check-src
hatch run mypy:check-tests
hatch run mypy:check-tests-untyped
```

The test checker routes native modules to Linux, macOS and Windows typeshed
passes. The `-untyped` mode is opt-in and can still report outstanding test-body
typing debt. These developer targets do not add CI enforcement: current typing
CI checks production source and installed consumers.

## Documentation

- Keep the README concise: purpose, capability map, one runnable quick start and links.
- Put detailed usage contracts in [docs/](docs/) and keep public docstrings current.
- Add independent, single-concept [configuration recipes](examples/) with a question,
  root-level command, expected result and explanation. Use consistent sample data.
- Verify README and recipe changes with
  `hatch run test_github:pytest tests/examples -q`.
- Keep designs, plans and historical delivery evidence in
  [mountainash-central](https://github.com/mountainash-io/mountainash-central/blob/main/04.planning/mountainash-settings/superpowers/INDEX.md).
- Follow [the textbook workflow](docs-site/README.md) for generated-site refreshes.
  A source-document edit does not by itself advance generated provenance.
