# Source precedence and merging

Which value wins when several inputs configure the same field?

[example.py](example.py) deliberately conflicts YAML, TOML, an environment
variable and an invocation value. The local [base](base.yaml) and
[production](production.yaml) fixtures also demonstrate recursive mapping merge
and list replacement. These conflicting inputs belong to this recipe; the
shared deployment fixtures stay simple.

From the repository root, after the [shared setup](../README.md#setup):

```bash
python examples/reporting/source_precedence/example.py
```

Expected output:

```text
Files: production_reports; environment: environment_reports; invocation: diagnostic_reports
Merged export: csv, batch=250; recipients: monthly
```

Priority, highest first:

1. Constructor values
2. OS environment
3. Prefixed dotenv
4. Unprefixed dotenv fallback
5. YAML
6. TOML
7. JSON
8. Pydantic secret files
9. Field defaults

Cross-format order is fixed. Within one structured format, later files recursively
merge mappings and replace lists or scalars. Reversing the formats in the path
list does not make TOML beat YAML. The example restores its deliberate
`REPORT_DATABASE` environment change before exiting.

Related: [configuration files](../configuration_files/) and the separate
[parameter-set merging](../../../docs/advanced-usage.md#merging-settings-parameters) rules.
