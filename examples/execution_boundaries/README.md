# Why carry a recipe across execution boundaries?

**Question:** If startup loads settings and populates a cache, can every thread
and process use them? What happens when a worker must reconstruct the application?

Run from the repository root:

```bash
python examples/execution_boundaries/example.py
```

Requires the normal example installation, with no extra dependencies. The script
uses a fixed, bundled JSON file with `DATABASE: reports_db` and an empty `TAGS`
list. It never changes the configuration file. Paths are resolved from `__file__`.

## The recipe

```python
params = SettingsParameters(
    settings_class=AppSettings,
    config_files=[absolute_config_path],
    env_prefix="REPORT_",
)

# At startup, capture this process's source inputs.
params.get_settings()

# At the execution boundary, retrieve independently owned settings.
settings = params.get_settings()
```

The recipe retains the instructions for obtaining settings. If this execution
context has the captured inputs, retrieval reuses them. Otherwise it captures
them locally. A parent process's initialized state is not a portable deployment
mechanism by itself.

## Expected results

The script asserts each observation before printing its result. On Linux with
all three multiprocessing start methods available:

```text
Warm parent cache: available to both threads; no file reads
Threads shared: isolated=False, file reads=1
Threads deepcopy: isolated=True, file reads=1
Threads factory: isolated=True, file reads=2
Threads recipe: isolated=True, file reads=0
spawn: parent cache=False, recipe reads=1/0; explicit object transfer works
fork: parent cache=True, recipe reads=0/0; explicit object transfer works
forkserver: parent cache=False, recipe reads=1/0; explicit object transfer works
Worker environment: local factory/recipe sees worker input; passed object retains parent values
Worker cwd: relative source fails; absolute source succeeds
```

Unavailable start methods are explicitly reported instead of run. For example,
Windows provides spawn, but not fork or forkserver. This repro selects each
available method explicitly rather than relying on Python's platform/version
default. It uses an ordinary forkserver without module preloading.

## 1. Startup cache availability

The parent explicitly warms MountainAsh's cache before launching workers. Two
distinct threads synchronize at a barrier, then retrieve settings. Both can use
the parent cache, with zero new reads.

Each process probe runs in a fresh one-worker process pool. The comparison uses:

* `get_settings_manager().get_settings_object(params)`: intentionally requires
  an already initialized source capture. This exposes the failure of assuming
  the parent's cache is present everywhere.
* `params.get_settings()`: the normal retrieval route, which captures inputs if
  needed and then materializes settings.

| Boundary | Cache-only retrieval | Recipe retrieval |
|---|---|---|
| Threads | Works | Reuses captured inputs |
| Fork | Works with inherited capture | Reuses inherited inputs |
| Spawn | Fails: cache uninitialized | Reads the file once in the worker |
| Forkserver | Fails: cache uninitialized | Reads the file once in the worker |

A second recipe retrieval sets `DATABASE="task_database"`; it performs no new
file read and leaves the first result's database unchanged. This demonstrates
worker-local reuse and invocation-local overrides together.

Read counts come from Python audit `open` events filtered to the exact fixture
path. The single parent warm-up read is checked separately. Counts describe
source access, not performance timings. The inherited fork capture is suitable
for this stable deployment; it is not a cache shared between processes.
Forking during concurrent cache initialization is outside this example.

## 2. Parent-only objects versus explicitly transferred objects

A module global populated only in the parent is absent when spawn/forkserver
imports the module afresh. Fork inherits it. The lost state is application
initialization, not Pydantic mysteriously losing fields.

Explicitly passing the loaded Pydantic object through the process pool preserves
its values under all tested methods and needs no worker source reads. This is a
valid alternative when transporting an eager snapshot is what the application
wants. This simple model has picklable fields and module-level classes; arbitrary
custom objects, clients or stores do not acquire a serialization guarantee.

The plain Pydantic factory also succeeds in every process, using upstream
`JsonConfigSettingsSource`. Its file selector is provided via a `ContextVar` to
the custom source hook. Source priority is initializer, environment, then JSON.
MountainAsh packages explicit selectors and cached reconstruction into its API.

## 3. Shared mutable settings in threads

Threads do not lose ordinary object state. Instead, sharing a settings object
can unintentionally share mutations. One task appends to `TAGS`; after a barrier,
the other task sees the mutation when both use the same eager object.

Both fresh factory calls and MountainAsh retrieval isolate the nested lists.
The plain factory reads twice; the warmed MountainAsh recipe reads zero times.
Pydantic `model_copy(deep=True)` also isolates this simple nested-list example
using one eager read. These are useful alternatives, with different ownership
and construction responsibilities for the application.

## 4. Worker-local environment

A spawned worker receives `REPORT_DATABASE=worker_database` before loading its
settings. Both the plain factory and recipe read that worker input. A transferred
eager object retains the parent's `reports_db`. This compares initialization in
different execution contexts; it is not an environment-refresh scenario.

## 5. Worker working directory

The worker starts in a temporary directory containing no settings file. A
relative `settings.json` selector fails for both factories and recipes. An
absolute path to the bundled fixture succeeds. A recipe cannot distribute files
or turn a parent-relative location into a worker-accessible one automatically.

## What this establishes

Keep a recipe when work may reconstruct the application in another process:
resolve at the execution boundary, rehydrate when necessary, and reuse local
source captures while keeping task results independently owned.

Continue with [real Dagster workers](../dagster_workers/) and
[orchestrator credential printing](../orchestrator_credentials/).
For API details, see [cached sources](../cached_sources/),
[local overrides](../local_overrides/) and [advanced usage](../../docs/advanced-usage.md).
