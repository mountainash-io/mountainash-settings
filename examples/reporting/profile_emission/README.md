# Native profile fields and emission

How do I declare reusable driver mappings alongside my settings fields?

[example.py](example.py) declares native Pydantic fields on `Profile`. MountainAsh
generates a descriptive spec and uses it to emit the same PostgreSQL arguments as
the [handwritten mapping](../driver_mapping/).

From the repository root, after the [shared setup](../README.md#setup):

```bash
python examples/reporting/profile_emission/example.py
```

Expected output:

```text
Prepared PostgreSQL arguments for reports (credentials omitted)
```

`driver_keys="lower"` opts into lowercase mappings. `driver_key="dbname"`
overrides the convention, and explicit `driver_key=None` excludes `LOCAL_NOTE`.
`None` values are omitted and `SecretStr` values are unwrapped at emission.
Keep the emitted dictionary out of logs. No registry is needed to load or emit.

Untouched inherited fields keep their metadata. Redeclaring a field follows
Pydantic replacement rules: `PORT: int = 6432` discards the earlier constraints
and field options; repeat those you need. An unannotated `PORT = 6432` is rejected.

Related: [explicit specs](../explicit_specs/), [inspection](../spec_inspection/),
[target adapters](../target_adapters/) and the
[profile declaration reference](../../../docs/profile-spec-pattern.md).
