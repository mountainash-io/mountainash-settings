# Basic settings

How do I declare application settings and validate an input?

[example.py](example.py) declares the reporting application's fields directly on
`MountainAshBaseSettings`. Defaults allow it to run without configuration files.
Pydantic converts the string `"true"` to a boolean for one diagnostic invocation.

From the repository root, after the [shared setup](../README.md#setup):

```bash
python examples/reporting/basic_settings/example.py
```

Expected output:

```text
reports: ordinary debug=False, diagnostic debug=True
```

Direct construction reads sources for each instance; it does not populate the
source cache. `env_prefix="REPORT_"` permits environment inputs such as
`REPORT_DEBUG`. Run without conflicting environment values to reproduce the output.

MountainAsh ignores unknown inputs, does not validate field defaults by default,
and validates assignments. Set `model_config` deliberately when you need different
behavior; upstream Pydantic Settings defaults differ.

Next: [configuration files](../configuration_files/).
