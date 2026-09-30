# Cached source snapshots

How can functions retrieve settings without rereading deployment inputs?

[example.py](example.py) captures a temporary copy of the reporting configuration
using `SettingsParameters` and `get_settings()`, then changes the file. A second
cached retrieval still sees the captured value; direct construction sees the edit.

From the repository root, after the [shared setup](../README.md#setup):

```bash
python examples/reporting/cached_sources/example.py
```

Expected output:

```text
Cached: reports; direct: changed_reports
```

Each retrieval returns an independently owned, validated instance. The cache saves
baseline source reads; it does not reuse a mutable settings object. Defaults and
default factories remain per-instance behavior.

Pass parameters to application functions and retrieve at the point of use.
Capture known configurations during startup when they should observe stable
deployment inputs. Snapshots are process-local and each structural configuration
initializes separately; they do not coordinate across processes or live-reload files.

Related: [local overrides](../local_overrides/) and
[cache contracts](../../../docs/advanced-usage.md#cache-contexts-and-runtime-materialization).
