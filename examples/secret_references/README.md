# Secret references

How do I load a password without embedding it in application configuration?

[example.py](example.py) owns a small in-memory record store, then loads
`secret:database.password` into a `SecretStr` field through `secret_store=records`.
The example's synthetic password is checked internally and never printed.

From the repository root, after the [shared setup](../README.md#setup):

```bash
python examples/secret_references/example.py
```

Expected output:

```text
Password reference resolved
```

The last dot separates the record key from its field. Here the namespace view
selects `reports`, the record is `database`, and the field is `password`.
Pass the store object directly to settings or `SettingsParameters`; there is no
named provider registry. Ordinary environment/file inputs need no record store.

With cached retrieval, baseline resolved values remain pinned. An explicit runtime
secret-reference override resolves afresh for that invocation. See
[cache contracts](../../docs/advanced-usage.md#cache-contexts-and-runtime-materialization).

Related: [namespaced records](../namespaced_records/) and
[reference syntax and errors](../../docs/README_SECRETS.md#secret-references).
