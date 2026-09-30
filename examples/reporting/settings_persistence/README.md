# Explicit settings persistence

How do I save a configuration record to local storage?

[example.py](example.py) provisions a temporary directory, selects a filesystem
store, calls `persist()` and verifies the record through a newly opened store.
It closes both handles before deleting the temporary directory.

From the repository root, after the [shared setup](../README.md#setup):

```bash
python examples/reporting/settings_persistence/example.py
```

Expected output:

```text
Saved and reopened reporting configuration
```

`persist(data, key=...)` replaces one complete record through the selected writer,
then updates the current settings instance. It does not update a source snapshot,
rewrite configuration files or make future settings automatically load that record.
The transaction coordinates writers; it does not provide rollback across storage
and subsequent field validation.

The example uses no credentials. In a deployment, the application provisions the
directory and controls access to it. See [persistence semantics](../../../docs/README_SECRETS.md#settings-persistence)
and [native platform requirements](../../../docs/README_SECRETS.md#platform-support).
