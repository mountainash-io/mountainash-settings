# Configuration recipes

Explore focused, independently runnable examples of configuration loading,
retrieval, templates, secrets and connection profiles. The examples use consistent
application and database settings so you can compare approaches.

Read in the order below or go straight to the feature you need. Each recipe
declares its own settings and runs independently; none imports another recipe.

## Setup

Use Python 3.12+ and install this checkout from the repository root:

```bash
python -m pip install -e .
```

The invariant-check recipe additionally uses `pytest==8.3.5`; the optional
[Dagster worker reproduction](dagster_workers/) has its own Hatch environment.
All commands in
the recipes run from the repository root. Input paths are relative to the script,
so an absolute script path also works from a different working directory.

Each script prints a small result and checks it with assertions. Run without
Python's `-O` flag. To reproduce the documented output, unset conflicting
`REPORT_*` environment variables and unprefixed variables matching declared
fields. The precedence example sets and restores its own environment input.

No recipe opens a database connection or contacts a service. The persistence
example uses a temporary local directory and closes its store before cleanup.

## Shared example data

These examples configure a Python application and its PostgreSQL connection.
The sample application is `reports_app`, its database is `reports_db`, and deployments use
`development` or `production`. Connection recipes use `prod-db.example.com`,
PostgreSQL port `5432`, `report_user` and a synthetic password. Passwords are
checked internally but never printed.

[config/base.yaml](config/base.yaml), [config/production.toml](config/production.toml),
[config/application.json](config/application.json) and [config/.env](config/.env) hold shared
deployment values. Conflicting fixtures for the precedence lesson live beside
that recipe. Small repeated declarations keep the concept visible in each file.

## Loading

| Recipe | Question |
|---|---|
| [Basic settings](basic_settings/) | How do I declare and validate fields? |
| [Configuration files](configuration_files/) | How do I load several file formats together? |
| [Source precedence](source_precedence/) | Which input wins, and how do files merge? |

## Retrieval

For the motivation behind recipe-based retrieval, start with the execution-boundary
reproduction: startup state can be absent when workers reconstruct the application.
The credential example shows why retaining a recipe on an orchestration object
also reduces accidental disclosure through ordinary printing.

| Recipe | Question |
|---|---|
| [Execution boundaries](execution_boundaries/) | Which threads/processes inherit startup settings and caches, and which must rehydrate? |
| [Dagster workers](dagster_workers/) | What happens to a warmed parent cache in real multiprocess step execution? |
| [Orchestrator credentials](orchestrator_credentials/) | What can logging an orchestrator's settings attribute disclose? |
| [Cached sources](cached_sources/) | How do I reuse deployment inputs while receiving fresh instances? |
| [Local overrides](local_overrides/) | How do I change one invocation without affecting others? |
| [Parameter merging](parameter_merging/) | How do I package recurring overrides? |

## Derivation

| Recipe | Question |
|---|---|
| [Templates](templates/) | How do I derive a path from loaded values? |
| [Recomputation](recomputation/) | How do I recompute derived values while preserving explicit inputs? |

## Secrets and persistence

| Recipe | Question |
|---|---|
| [Namespaced records](namespaced_records/) | How do applications separate records in one store? |
| [Secret references](secret_references/) | How do settings resolve a password from a selected store? |
| [Settings persistence](settings_persistence/) | How do I explicitly save and reopen a local record? |

## Connections

| Recipe | Question |
|---|---|
| [Handwritten mapping](driver_mapping/) | How do I map ordinary settings to one driver's kwargs? |
| [Profile emission](profile_emission/) | How do native fields describe reusable emission rules? |
| [Explicit specs](explicit_specs/) | How do I install fields from a data-driven declaration? |

## Profile extensions

| Recipe | Question |
|---|---|
| [Spec inspection](spec_inspection/) | How do I inspect declarations without loading values? |
| [Registry discovery](registry_discovery/) | How do callers select a profile by name? |
| [Invariant checks](invariant_checks/) | How do I check conventions across a registry? |
| [Domain metadata](domain_metadata/) | How does my domain define typed spec metadata? |
| [Target adapters](target_adapters/) | How do I map and transform fields for different clients? |

## Verification

The recipe scripts are executed independently in temporary directories, with
ambient configuration removed:

```bash
hatch run test_github:pytest tests/examples -q
```

The root README's quick start is executed separately with its documented input.
The invariant recipe is collected through pytest, and its receipt must contain
passing checks. When adding a recipe, update this index and include assertions
for the concept it demonstrates. Keep detailed contracts in the linked reference
pages rather than repeating the full suite in the README.
