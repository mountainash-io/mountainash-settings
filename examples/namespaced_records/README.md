# Namespaced records

How do two applications use the same store without sharing record names?

[example.py](example.py) creates two namespace views over an in-memory store.
Both can use the key `database`; the sample application's record is visible only through
the `reports` view. Namespaces separate keys, not access permissions.

From the repository root, after the [shared setup](../README.md#setup):

```bash
python examples/namespaced_records/example.py
```

Expected output:

```text
Database record: present in reports; absent in other_application
```

Records are JSON-native mappings. `set()` replaces a complete record; `get()`
returns an owned copy or `None` for absence. Use an explicit transaction for
coordinated writes. A namespace view borrows the underlying store; its owner
controls the store's lifetime. This example makes no disk writes.

Next: [resolve secret references](../secret_references/).
Reference: [records, keys and storage contracts](../../docs/README_SECRETS.md).
