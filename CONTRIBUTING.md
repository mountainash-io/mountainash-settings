# Contributing to mountainash-settings

This document outlines the process for contributing to the project and provides guidelines to ensure a smooth collaboration.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Branching Strategy](#branching-strategy)
3. [Making Changes](#making-changes)
4. [Submitting a Pull Request](#submitting-a-pull-request)
5. [Code Review Process](#code-review-process)
6. [Coding Standards](#coding-standards)
7. [Testing](#testing)
8. [Documentation](#documentation)

## Getting Started

1. Fork the repository on GitHub.
2. Clone your fork locally: `git clone https://github.com/your-username/mountainash-settings.git`
3. Add the original repository as a remote: `git remote add upstream https://github.com/mountainash-io/mountainash-settings.git`
4. Create a new branch for your contribution (see [Branching Strategy](#branching-strategy)).

Use Python 3.12+ and Hatch. `pyproject.toml` and `hatch.toml` own dependency and
environment configuration. For an editable installation:

```bash
python -m pip install -e .
```

## Branching Strategy

We follow a git-flow branching methodology. The following branch naming conventions are allowed:

- `main`: The main production branch
- `develop`: The main development branch
- `feature/*`: For new features
- `chore/*`: For maintenance tasks
- `docs/*`: For documentation and examples
- `release/*`: For release preparation
- `hotfix/*`: For critical bug fixes in production
- `bugfix/*`: For non-critical bug fixes
- `renovate/*`: For dependency updates (automated)

### Protected Branches

The following branches are strictly protected and require code owner review and repository owner approval for pull requests:

- `main`
- `develop`
- `release/*`

## Making Changes

1. Ensure you're working on the correct branch (e.g., `feature/new-feature` for a new feature).
2. Make your changes in small, logical commits.
3. Follow the [Coding Standards](#coding-standards) of the project.
4. Add or update tests as necessary (see [Testing](#testing)).
5. Update documentation if required (see [Documentation](#documentation)).

## Submitting a Pull Request

1. Push your changes to your fork on GitHub.
2. Open a pull request against the appropriate branch:
   - For features, chores, and bugfixes, target the `develop` branch.
   - For hotfixes, target the `main` branch.
3. Provide a clear title and description for your pull request.
4. Reference any related issues in the pull request description.
5. Ensure all checks (tests, linting, etc.) pass successfully.

## Code Review Process

1. All pull requests require at least one review from a code owner.
2. For protected branches (`main`, `develop`, `release/*`), additional approval from a repository owner is required.
3. Address any feedback or comments provided during the review process.
4. Once approved, a maintainer will merge your pull request.

## Coding Standards

- Follow PEP 8 style guide for Python code.
- Use type hints where appropriate.
- Write clear, self-documenting code with meaningful variable and function names.
- Keep functions and methods focused and concise.
- Use comments sparingly, only when necessary to explain complex logic.

## Testing

Use the settings-only environment without a sibling checkout:

```bash
hatch run test_github:test
hatch run test_github:test-cov
hatch run test_github:pytest tests/test_readme_examples.py tests/test_reporting_examples.py -q
hatch run test_github:pytest tests/test_base_settings.py -v
```

`hatch run test:test` includes coverage and expects a sibling
`mountainash-auth-client` checkout. There is no `test:cov` script. Add tests for
observable contracts and credible regressions; avoid duplicating stronger
integration coverage or asserting implementation details.

## Linting, typing and build

```bash
hatch run ruff:check
hatch run ruff:fix
hatch run mypy:check
hatch build
```

Ruff's configured check covers `src`. Mypy remains pinned to 1.10.1 with existing
rules and test exclusions; do not enable `--strict`. The typing tool runs common,
Linux POSIX, macOS POSIX and Windows-native passes.

## Documentation

- Keep the README concise: purpose, capability map, one working quick start and navigation.
- Add focused recipes to [examples/reporting](examples/reporting/) with a question,
  run command, expected result and short explanation. Use the same reporting data;
  each recipe must run independently and teach one primary concept.
- Verify the actual README snippet and example scripts with the commands above.
  The README is not a concatenation of the examples.
- Put detailed contracts in `docs/`, and keep public docstrings current.
- Follow [the textbook workflow](docs-site/README.md) for site refreshes and publishing.

See [RELEASE.md](RELEASE.md) for qualification and release work.
