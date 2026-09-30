# Explicit recomputation

When a host changes for one invocation, how do I recompute a derived address?

[example.py](example.py) uses `ProfileField(template=...)` to derive an address.
It compares a host-only override with `reinitialise=True`, and shows that an
explicit address takes precedence over derivation.

From the repository root, after the [shared setup](../README.md#setup):

```bash
python examples/reporting/recomputation/example.py
```

Expected output:

```text
Baseline: prod-db.example.com:5432
Recomputed: diagnostic.example.com:5432; explicit: explicit
```

Without the flag, an already-derived value remains as captured even when an
input changes. With the flag, the profile recomputes eligible derived values from
the invocation's effective inputs; explicitly supplied values remain authoritative.
There is no automatic dependency synchronization. `reinitialise` does not reload
files, refresh the source cache or change structural identity.

Related: [ordinary template helpers](../templates/), [profile declarations](../profile_emission/)
and [cached source snapshots](../cached_sources/).
