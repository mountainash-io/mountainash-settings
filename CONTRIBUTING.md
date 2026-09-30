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

Start with the settings-only suite and production checks:

```bash
hatch run test_github:test
hatch run ruff:check
hatch run mypy:check
hatch build
```

See [TESTING.md](TESTING.md) for focused checks, coverage, native-platform testing
and CI scope. The optional `test` environment requires a sibling auth-client
checkout. Keep mypy pinned to 1.10.1 with its existing rules and test exclusion.

## Documentation

- Keep the README concise: purpose, capability map, one runnable quick start and links.
- Put detailed usage contracts in [docs/](docs/) and keep public docstrings current.
- Add independent, single-concept [configuration recipes](examples/) with a question,
  root-level command, expected result and explanation. Use consistent sample data.
- Verify README and recipe changes with
  `hatch run test_github:pytest tests/test_readme_examples.py tests/test_examples.py -q`.
- Keep designs, plans and historical delivery evidence in
  [mountainash-central](https://github.com/mountainash-io/mountainash-central/blob/main/04.planning/mountainash-settings/superpowers/INDEX.md).
- Follow [the textbook workflow](docs-site/README.md) for generated-site refreshes.
  A source-document edit does not by itself advance generated provenance.
