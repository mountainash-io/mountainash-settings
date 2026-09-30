# Invocation-local overrides

How do I enable debugging for one report without changing other callers?

[example.py](example.py) retrieves a diagnostic instance with `DEBUG=True`, then
mutates its database name. Both changes stay local to that instance.

From the repository root, after the [shared setup](../README.md#setup):

```bash
python examples/reporting/local_overrides/example.py
```

Expected output:

```text
Diagnostic debug=True; ordinary debug=False; later database=reports
```

Runtime field overrides are excluded from structural cache identity. Retrieval
validates them against the captured sources without writing them back to the
shared baseline. The application owns actual client connections and their lifetimes;
settings should describe them rather than contain live resources.

Related: [cached sources](../cached_sources/), [reusable parameter sets](../parameter_merging/)
and [derived-value recomputation](../recomputation/).
