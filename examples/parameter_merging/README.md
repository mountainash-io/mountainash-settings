# Reusable parameter merging

How can several application functions share the same diagnostic override?

[example.py](example.py) merges `DEBUG=True` into reusable `SettingsParameters`.
The result retains the deployment selectors while carrying different runtime values.

From the repository root, after the [shared setup](../README.md#setup):

```bash
python examples/parameter_merging/example.py
```

Expected output:

```text
Same source key: True; ordinary debug=False; diagnostic debug=True
```

Structural identity consists of `config_files`, `settings_class`, `env_prefix`,
`secrets_dir` and the selected `secret_store` object's identity. Runtime kwargs
are excluded from equality and hashing; equal parameters can yield different values.

`merge()` combines file paths in stable order, appending unseen paths. Other
selectors and runtime kwargs follow their [per-field merge rules](../../docs/advanced-usage.md#field-by-field-merge-rules).
Parameters are trusted application wiring and can contain literal credentials;
do not assume they are safe to serialize or log.

Related: [one-call overrides](../local_overrides/) and
[source-file merging](../source_precedence/), which is a separate operation.
