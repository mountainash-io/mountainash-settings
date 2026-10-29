---
title: 'Mountainash Settings'
description: 'Documentation for mountainash-settings: typed configuration for Python applications built on Pydantic v2'
---


[← Back to Ecosystem](https://docs.mountainash.io/)
# Mountainash Settings

!!! note "0.1.0 API reset"
    Read the [migration guide](https://github.com/mountainash-io/mountainash-settings/blob/develop/docs/migration-0.1.md)
    for supported names, target adapters and cached retrieval. This documentation describes 0.1.

Most applications read configuration from several places at once: a YAML file checked into the repo, environment variables set by the deployment, and passwords that must never sit in either. mountainash-settings puts all of that behind one typed class. You declare the fields once with Pydantic, point the class at your files, and get back a validated object with secrets already filled in.

## A first example

`app.yaml` holds the defaults for an environment. The password is a reference, not a value:

```yaml
DB_HOST: db.internal
DB_PORT: 5432
DB_PASSWORD: secret:db.prod.password
```

The deployment sets `APP_DB_PORT=6543`. The application declares its settings and asks for them:

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

The host comes from the file, the port from the environment, and the password from the secret store. Pydantic validated all three, so `DB_PORT` is an `int`. In production you swap `MemorySecretStore` for the filesystem store or your own adapter; the settings class does not change.

## Why use it

If you write applications, you stop hand-merging dictionaries from `yaml.safe_load`, `os.environ` and a vault client. YAML, TOML, JSON, `.env` files and environment variables all feed the same class, with a documented rule for which value wins. `get_settings()` reads your files once and hands every caller a freshly validated copy, so one module mutating its settings never leaks into another.

If you run data platforms, the same class works in dev, staging and production; only the files and the environment change. Secret references live safely in version control because they resolve at construction time, before validation, and the resolved values stay masked as `SecretStr`.

If you connect to many systems, a connection profile declares a database's or SDK's parameters once, with types, defaults and validators, and `emit()` renders the exact keyword arguments the driver expects. Register your profiles and `spec_invariants_for()` gives you a pytest suite that checks every one of them, without writing the tests yourself.

If you build on top of it, secret stores are plain protocols. A read-only store for Vault, AWS SSM or Azure Key Vault implements one method, `get()`, and a writable one adds `set()`, `delete()` and `transaction()`.

## Where to go next

- [Chapters](chapters/index.md): start with [MountainAsh base settings](chapters/02-mountainash-base-settings/index.md) to define your own class, or read [Chapter 1](chapters/01-pydantic-and-configuration-foundations/index.md) first for the Pydantic background.
- [Package overview](course-description.md): scope, capabilities and ecosystem context.
- [About](about.md): authorship, license and the relationship to the code repository.
