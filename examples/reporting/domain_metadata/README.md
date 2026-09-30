# Typed domain metadata

How does a domain add its own metadata to generated specs?

[example.py](example.py) defines a `BackendSpec` dataclass, selects it on an
intermediate `SQLProfile`, and supplies metadata on a concrete PostgreSQL class.

From the repository root, after the [shared setup](../README.md#setup):

```bash
python examples/reporting/domain_metadata/example.py
```

Expected output:

```text
PostgreSQL domain default port: 5432
```

Header metadata is validated strictly; `default_port="5432"` is not an integer
and fails at declaration time. Metadata inherits by key; supplied dictionaries
replace rather than deep-merge inherited dictionaries. Metadata describes the
domain: `default_port` does not automatically set the separate `PORT` field.

Concrete generated subclasses declare their own `name` and `provider_type`.
Intermediate classes expose `__spec__ = None` and cannot construct or register.
Put Pydantic options in `model_config`, not in class headers.

Related: [spec inspection](../spec_inspection/) and
[profile lifecycle and inheritance](../../../docs/profile-spec-pattern.md#inheritance-and-completion).
