# AppSettings run timestamps

`AppSettings` supplies `RUNDATE`, `RUNTIME` and the template-derived `RUNDATETIME`.
Declare the timestamp lifetime on the settings class:

```python
from typing import ClassVar, Literal
from mountainash_settings.settings.app.app_settings import AppSettings

class ReportingSettings(AppSettings):
    RUN_TIMESTAMP_SCOPE: ClassVar[Literal["context", "process"]] = "context"

settings = ReportingSettings()
```

`context` is the inherited default. Direct construction captures a fresh instant
on each call. Cached retrieval captures once for each manager-owned structural
context (class, configuration files, environment prefix, secrets directory and
store identity). Further retrievals, including `reinitialise=True`, retain that
instant. Separate contexts and managers initialize independently.

Set the class policy to `"process"` to share one instant across process-scoped
AppSettings classes, contexts and managers. Capture is lazy: the first
process-scoped construction or context initialization samples the clock. A new
process, including a forked child, captures its own instant on first use.

The policy is class configuration, not a settings field or invocation override.
Declare it before initialization; changing it on an already initialized class
or context is unsupported. Invalid policies raise `ValueError`.

## Values and precedence

One local-time instant supplies both generated defaults: `RUNDATE` uses
`YYYYMMDD`, and `RUNTIME` uses `HHMMSS`. `LOCALE_TIMEZONE` does not convert them.
Equal strings can come from independent constructions within the same second.

Normal source precedence applies. Configuration, environment and explicit field
inputs override generated defaults; overriding one component keeps the generated
other component. A first cached call's overrides never replace the context's
retained defaults. Subclass field declarations can replace the default factories.

`RUNDATETIME` normally formats the effective fields as `{RUNDATE}T{RUNTIME}`.
Existing template rules apply: cached retrieval without reinitialization can
retain a previously derived string; `reinitialise=True` recomputes it using
effective fields and preserves an explicit current invocation value. Custom
template parameters can be supplied to direct construction.

## Migration

Earlier versions sampled the clock when the AppSettings class was imported.
Initialization now owns capture. Use process scope when several configurations
should share a run timestamp, or supply explicit values when the application
already owns its run identity.
