# Template-derived values

How do I build a log path from the loaded application and environment names?

[example.py](example.py) resolves a brace template in `post_init()`. The field
declarations and derivation remain visible in an ordinary settings class.

From the repository root, after the [shared setup](../README.md#setup):

```bash
python examples/reporting/templates/example.py
```

Expected output on POSIX (path separators follow the platform):

```text
Log path: ~/logs/reports/production.log
```

Use UPath's `/` operator to construct portable path templates. This recipe only
derives a string; it does not expand the home directory, create directories or
open a log file. When several derived fields depend on each other, resolve them
in dependency order in `post_init()`.

The helper uses an existing value unless recomputation is requested. For a
profile's explicit-versus-derived value handling, see
[recomputation](../recomputation/).
