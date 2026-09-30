# Handwritten driver mapping

How do I configure one database with an ordinary settings class?

[example.py](example.py) declares database fields and maps them in a short
`driver_kwargs()` method. It unwraps the synthetic password only at that boundary.

From the repository root, after the [shared setup](../README.md#setup):

```bash
python examples/reporting/driver_mapping/example.py
```

Expected output:

```text
Prepared PostgreSQL arguments for reports (credentials omitted)
```

The resulting dictionary is ready to pass to a compatible driver; the example
does not import a driver or connect. The dictionary contains an unwrapped password
and should not be logged.

Ordinary classes already support sources, caching, templates, selected stores,
Pydantic inheritance, aliases and validators. A profile is optional. See the same
connection expressed with [native profile fields](../profile_emission/) or
[an explicit spec](../explicit_specs/).
