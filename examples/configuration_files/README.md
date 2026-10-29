# Configuration files

How do I load YAML, TOML, JSON and dotenv values together?

[example.py](example.py) loads an application deployment from:

| Input | Supplies |
|---|---|
| [base.yaml](../config/base.yaml) | Application and database names |
| [production.toml](../config/production.toml) | Deployment environment |
| [application.json](../config/application.json) | Batch size |
| [.env](../config/.env) | Debug flag |

From the repository root, after the [shared setup](../README.md#setup):

```bash
python examples/configuration_files/example.py
```

Expected output:

```text
reports_app: database=reports_db, production, batch=100, debug=False
```

The `REPORT_` prefix applies to environment and dotenv inputs; structured files
use field names such as `APP_NAME`. Each format supplies a different field here.
The script resolves bundled paths relative to its own location, so it can also
be launched by absolute path from another directory.

Pass source selectors as `config_files`, `env_prefix` and `secrets_dir`.
Underscore-prefixed controls such as `_env_file` are rejected.

Next: [source precedence and merging](../source_precedence/).
