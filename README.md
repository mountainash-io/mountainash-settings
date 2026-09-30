# mountainash-settings

![Python](https://img.shields.io/badge/python-3.12%2B-blue)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

Typed configuration for Python applications: combine deployment sources, derive
values, retrieve isolated settings where they are needed, and turn connection
profiles into driver arguments. Built on **Pydantic Settings**, with native
Pydantic field types, validation, aliases and inheritance.

[Examples](examples/) · [Getting started](docs/quickstart.md) ·
[Reference](docs/advanced-usage.md) · [Migrating to 0.1](docs/migration-0.1.md)

## What MountainAsh adds to Pydantic Settings

Pydantic supplies validation and model behavior; Pydantic Settings supplies source
primitives. MountainAsh composes them with per-invocation source selection and
adds retrieval, derivation, storage and profile conventions:

| Area | Capabilities | Explore |
|---|---|---|
| Configuration loading | YAML, TOML, JSON, dotenv and environment inputs; source precedence and recursive file merging | [Loading](examples/#loading) |
| Derived configuration | Brace templates, portable path construction and explicit recomputation | [Derivation](examples/#derivation) |
| Settings retrieval | Direct loading or cached source snapshots; independently owned instances, local overrides and reusable parameter sets | [Retrieval](examples/#retrieval) |
| Secrets and persistence | Selected stores, namespaced records, secret-reference resolution and explicit local persistence | [Secrets](examples/#secrets-and-persistence) |
| Connection profiles | Native fields or explicit specs; driver-key mappings, value transformations and target adapters | [Connections](examples/#connections) |
| Inspection and extension | Inspectable specs, typed domain metadata, registry discovery and generated invariant checks | [Profile extensions](examples/#profile-extensions) |

## Installation

Requires **Python 3.12+** and **Pydantic 2.10+**.

This README describes the **unpublished 0.1.0 candidate**. To try this API,
install the development checkout:

```bash
git clone --branch develop https://github.com/mountainash-io/mountainash-settings.git
cd mountainash-settings
python -m pip install -e .
```

## Quick start

Configure a Python application. Save this as `report.yaml`:

```yaml
APP_NAME: reports_app
DATABASE: reports_db
```

Save this as `quickstart.py` alongside it:

```python
from mountainash_settings import MountainAshBaseSettings

class ReportSettings(MountainAshBaseSettings):
    APP_NAME: str
    DATABASE: str
    DEBUG: bool = False

settings = ReportSettings(
    config_files=["report.yaml"], env_prefix="REPORT_", DEBUG=True,
)
print(f"{settings.APP_NAME}: {settings.DATABASE}, debug={settings.DEBUG}")
```

Run `python quickstart.py` from that directory:

```text
reports_app: reports_db, debug=True
```

The file supplies the application values; `DEBUG=True` overrides the default for
this invocation. Environment variables such as `REPORT_DATABASE` can override
file values. Run without conflicting variables to reproduce this output.

## Learn more

Explore [configuration recipes](examples/) for loading, retrieval, templates,
secrets and connection profiles. Each runs independently, using consistent
application and database settings so you can compare approaches.

| Guide | Contents |
|---|---|
| [Getting started](docs/quickstart.md) | Suggested route through the examples and Pydantic defaults |
| [Advanced usage](docs/advanced-usage.md) | Parameter merging, cache lifecycle, reconstruction and custom sources |
| [Profiles](docs/profile-spec-pattern.md) | Declaration choices, inheritance, emission, inspection and typing |
| [Secrets and local records](docs/README_SECRETS.md) | Reference syntax, persistence, store lifetime and platform requirements |
| [Migration to 0.1](docs/migration-0.1.md) | Breaking API changes |

Textbook: [production](https://docs.mountainash.io/mountainash-settings/) ·
[development](https://docs.mountainash.io/mountainash-settings/dev/).
Generated material has its own [refresh and provenance workflow](docs-site/README.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, checks and PRs targeting `develop`.
Release procedure: [RELEASE.md](RELEASE.md).

Part of the [Mountain Ash ecosystem](https://github.com/mountainash-io), alongside
`mountainash-auth-client`, `mountainash-transport`, `mountainash-files`,
`mountainash-data` and `mountainash`. Authentication models and OAuth flows belong
to `mountainash-auth-client`.

## License

[MIT](LICENSE).
