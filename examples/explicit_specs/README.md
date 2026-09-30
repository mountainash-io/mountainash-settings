# Explicit profile specs

How do I declare a profile when its field list is assembled as data?

[example.py](example.py) assigns an authored `ProfileSpec` to `__spec__`.
The spec installs the fields, including a secret field and driver mappings.

From the repository root, after the [shared setup](../README.md#setup):

```bash
python examples/explicit_specs/example.py
```

Expected output:

```text
Prepared PostgreSQL arguments for reports_db (credentials omitted)
```

This emits the same dictionary as the [native declaration](../profile_emission/)
and [ordinary class](../driver_mapping/). Fields installed from data are less
visible to static tooling than annotated class attributes.

Choose one declaration authority per class. Do not combine an own `__spec__`
with generated-mode headers, or feed a generated spec back into this installer:
generated specs do not fully describe aliases, factories and decorator validators.
See the [profile reference](../../docs/profile-spec-pattern.md).
