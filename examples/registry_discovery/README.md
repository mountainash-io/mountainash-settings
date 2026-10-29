# Registry discovery

How do I select a profile when configuration gives me its name?

[example.py](example.py) registers a completed profile once, then looks up
`postgresql` and constructs the selected class.

From the repository root, after the [shared setup](../README.md#setup):

```bash
python examples/registry_discovery/example.py
```

Expected output:

```text
Selected PostgreSQLSettings for reports_db
```

A registry adds discovery and duplicate-name protection. It does not construct
instances, open connections or create a separate settings cache. The returned
class supports direct construction or cached retrieval like any other profile.

For immediate registration, use `register = databases.decorator()` and bare
`@register` on the declaration. Register each name only once.

Related: [registry invariant checks](../invariant_checks/) and
[profiles without registration](../profile_emission/).
