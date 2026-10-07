# Reconstructing settings in Dagster workers

**Question:** Does initializing settings and warming the cache in the parent
make them available to Dagster's multiprocess step workers?

Run from the repository root:

```bash
hatch run examples_dagster:run
```

The optional Hatch environment uses Python 3.12, Dagster 1.13.25 and this checkout.
Dagster is not a package runtime dependency. To use an existing environment:

```bash
python -m pip install -e . 'dagster==1.13.25'
python examples/dagster_workers/example.py
```

## Reproduction

`definitions.py` contains importable settings classes, resources and four
two-step jobs. `example.py` loads the parent-only Pydantic object and explicitly
warms the MountainAsh cache. It first executes in-process controls, then calls
Dagster's real `execute_job(reconstructable(...))` with its default multiprocess
executor. This is not `execute_in_process()` presented as a multiprocess test.

The file contains only `DATABASE: reports_db` and remains unchanged throughout.
All instance/event/output storage lives in a temporary directory. Neither step
connects to a database or remote service.

| Resource strategy | In-process | Multiprocess |
|---|---|---|
| Parent-only eager object | Works | First step fails: object absent |
| Parent-warmed cache, cache-only lookup | Works | Resource initialization fails: capture absent |
| Plain Pydantic factory in each worker | — | Both steps work |
| Recipe resolved in each worker | — | Both steps work; one read per worker |

For the recipe, the absolute file selector travels through Dagster's resource
configuration. Each worker constructs a `SettingsParameters` and resolves it
inside resource initialization. Dagster does not transport the parent's cache.
This example does not depend on pickling the recipe; the
[execution-boundary example](../execution_boundaries/) covers direct transfer.

## Expected output

Alongside Dagster's event logs:

```text
In-process: parent object and warmed cache both work
Multiprocess eager: expected failure
Multiprocess cache_only: expected failure
Multiprocess factory: succeeds
Multiprocess recipe: succeeds
Recipe: each step worker rehydrates once; second retrieval reads no file
```

The two failing jobs are deliberate. The script verifies their specific causes
and exits successfully only if all comparisons match expectations:

* Eager object: `AttributeError`, from accessing the absent parent-only object.
* Cache-only resource: `Cached settings context is not initialised`.

For the successful recipe, the script checks two distinct worker PIDs, both
initially uncached. Each reads the source once; a second retrieval with a local
database override reads zero times and leaves the first result unchanged.
Audit events count actual fixture opens.

Entering Dagster's execution-result context can also initialize resources in
the parent. The comparison excludes parent-PID observations, so parent cache
hits cannot masquerade as successful worker cache sharing.

## The useful application pattern

Treat source selectors as resource configuration. Resolve settings at worker
resource initialization or the task boundary. This lets the same retrieval API
use existing captured inputs or rehydrate when the worker starts fresh.

A plain Pydantic factory solves worker reconstruction too. MountainAsh adds
packaged recipe parameters, local source reuse and independently owned results.
There is no claim that every eager Dagster resource fails: explicitly transported
configuration and worker-side initialization are valid approaches.

Workers must still have the package, importable declarations and access to the
configured file. This is a local multiprocess reproduction, not a Kubernetes or
remote-executor deployment test.

## Automated verification

```bash
hatch run examples_dagster:test
```

The existing example runner copies the suite and launches this script from an
unrelated working directory with isolated environment inputs. Environments
without Dagster skip this optional recipe; the dedicated command executes it.
