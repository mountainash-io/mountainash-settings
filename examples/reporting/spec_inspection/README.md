# Spec inspection

How can tooling inspect fields and mappings without loading values?

[example.py](example.py) reads the class's generated `__spec__`. Required host and
password inputs are never supplied, and no settings instance is constructed.

From the repository root, after the [shared setup](../README.md#setup):

```bash
python examples/reporting/spec_inspection/example.py
```

Expected output:

```text
DATABASE maps to dbname; PASSWORD is secret; TAGS has a factory
```

`default is MISSING` identifies a required field; `FACTORY_DEFAULT` identifies a
native factory without evaluating it. Inspect `model_fields` for the factory
itself. Ordinary Pydantic models also support field metadata and introspection.

Generated specs describe emission and field metadata, but cannot reconstruct
all aliases, factories or decorator validators. `ProfileSpec` is a frozen
dataclass whose list/dictionary contents remain mutable; treat a declared spec
as fixed. This inspection is separate from `model_json_schema()`, which currently
has a known inherited-bookkeeping limitation.

Related: [native fields](../profile_emission/) and [domain metadata](../domain_metadata/).
