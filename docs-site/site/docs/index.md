---
title: 'Mountainash Settings'
description: 'Documentation for mountainash-settings: typed configuration for Python applications built on Pydantic v2'
---


[← Back to Ecosystem](https://docs.mountainash.io/)
# Mountainash Settings

**Typed configuration for Python, from a single script to a fleet of services.**

!!! warning "Experimental"
    mountainash-settings 0.1.0 is experimental and not yet ready for production use. Its APIs can change between versions, and it is not yet published on PyPI.

Configuration always starts small: a dictionary loaded from a YAML file. Then staging needs a different host. The deployment overrides a port through an environment variable. A database password turns up that must never be committed. Before long, three services parse the same file three different ways, and nobody is sure which value actually wins.

mountainash-settings is the one place all of that comes together. You describe your settings once, as a typed Pydantic class. Files, environment variables and your secret store all feed into it, in an order you can predict, and every part of your code gets the same validated answer.

## Who it's for

<div class="grid cards" markdown>

-   **Application developers**

    ---

    Replace hand-merged YAML, `os.environ` lookups and vault calls with one class that loads YAML, TOML, JSON and `.env` files and validates the result.

    [Define a settings class](chapters/02-mountainash-base-settings/index.md)

-   **Data and platform engineers**

    ---

    Run the same class in dev, staging and production; only the files and the environment change. Secret references are safe to commit, because the real values are fetched when the settings load.

    [Resolve secrets](chapters/05-secrets-resolution/index.md)

-   **Teams connecting to many systems**

    ---

    Declare a database's or SDK's parameters once as a connection profile, then render the exact keyword arguments its driver expects. Every registered profile gets a ready-made pytest suite.

    [Build connection profiles](chapters/06-connection-profiles/index.md)

-   **Package and integration authors**

    ---

    Plug in Vault, AWS SSM or Azure Key Vault by implementing a small store protocol, or build your own profile registry for a family of backends.

    [Implement a secret store](chapters/05-secrets-resolution/index.md#record-store-protocols)

</div>

## See it work

`app.yaml` holds an environment's defaults. The password is a reference, not a value:

```yaml
DB_HOST: db.internal
DB_PORT: 5432
DB_PASSWORD: secret:db.prod.password
```

The deployment sets `APP_DB_PORT=6543`, and the application asks for its settings:

```python
from pydantic import SecretStr
from mountainash_settings import MountainAshBaseSettings, get_settings
from mountainash_settings.secrets import MemorySecretStore

class AppConfig(MountainAshBaseSettings):
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_PASSWORD: SecretStr

store = MemorySecretStore()
with store.transaction("db.prod"):
    store.set("db.prod", {"password": "s3cret"})

settings = get_settings(
    settings_class=AppConfig,
    config_files="app.yaml",
    env_prefix="APP_",
    secret_store=store,
)

print(settings.DB_HOST, settings.DB_PORT)       # db.internal 6543
print(settings.DB_PASSWORD)                     # **********
print(settings.DB_PASSWORD.get_secret_value())  # s3cret
```

The host came from the file, the port from the environment and the password from the secret store, and all three were validated. In production you swap `MemorySecretStore` for the filesystem store or your own adapter; `AppConfig` does not change.

## Where to go next

- New to the package? Start with [Chapter 2](chapters/02-mountainash-base-settings/index.md). The chapters assume you are comfortable with Python type annotations, Pydantic v2 models and validators, and at least one of YAML, TOML, JSON or `.env`; [Chapter 1](chapters/01-pydantic-and-configuration-foundations/index.md) covers the Pydantic background.
- The [chapter list](chapters/index.md) shows everything the documentation covers.
- [About](about.md) has authorship, the license and the link to the code repository.

!!! note "Upgrading from 0.x"
    0.1.0 reset the public API. The [migration guide](https://github.com/mountainash-io/mountainash-settings/blob/develop/docs/migration-0.1.md) lists the supported names, target adapters and the new cached retrieval. This documentation describes 0.1.
