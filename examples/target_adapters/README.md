# Target mappings and adapters

How does one profile prepare arguments for different clients?

[example.py](example.py) maps fields to `driver` or `url` targets. A transform
converts the URL port to a string; the driver adapter adds a timeout from an
excluded settings field after base kwargs and mapped values have been merged.

From the repository root, after the [shared setup](../README.md#setup):

```bash
python examples/target_adapters/example.py
```

Expected output:

```text
Driver timeout: 5; URL port: 5432 (string)
```

`driver_key={target: "name"}` scopes a mapping; a bare string applies to every
target. Target-scoped profiles require `emit(target)` and reject unknown targets.
Adapters use plural `__adapters__` and receive `(profile, merged_kwargs)`. They
return the final dictionary. Emitted values override same-named base values.

This adapter copies the outer mapping. If an adapter changes nested caller-owned
containers, copy those too. The assertion checks that the supplied base stays
unchanged. Real driver compatibility is the consuming application's responsibility.

Related: [basic emission](../profile_emission/) and
[emission reference](../../docs/profile-spec-pattern.md#extending-emission).
