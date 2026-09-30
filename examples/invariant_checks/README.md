# Generated invariant checks

How do I check conventions across every profile in a registry?

[test_profiles.py](test_profiles.py) declares and registers a profile, then turns
the registry into a pytest test class with `spec_invariants_for(DATABASES)`.

From the repository root, after the [shared setup](../README.md#setup):

```bash
python -m pip install pytest==8.3.5
python -m pytest examples/invariant_checks/test_profiles.py -q
```

Expected result: **7 passed** (timing varies). These checks verify registry/name
agreement, lowercase nonempty names, unique uppercase parameter names, unique
output keys per target, valid tiers and a non-None provider type.

Generate the class after registering the profiles you want checked. In an
application test module, import its existing registry before generating the
class. These checks verify spec conventions; they do not test connectivity or
whether the emitted arguments work with a real driver.

Related: [registry discovery](../registry_discovery/).
