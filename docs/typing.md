# Installed typing support

Built distributions include the PEP 561 `py.typed` marker. Consumers can use
the package's inline annotations without configuring a source path or stubs.
The installed-consumer gate uses mypy 1.10.1 on Python 3.12 and 3.13, with
Pydantic's standard typing support and no mypy plugin.

## Retrieval types

```python
from typing import assert_type
from mountainash_settings import MountainAshBaseSettings, SettingsParameters, get_settings

class AppSettings(MountainAshBaseSettings):
    PORT: int = 5432

assert_type(AppSettings.get_settings(), AppSettings)
assert_type(get_settings(settings_class=AppSettings), AppSettings)

params = SettingsParameters.create(settings_class=AppSettings)
assert_type(get_settings(params), MountainAshBaseSettings)
assert_type(get_settings(params, settings_class=AppSettings), AppSettings)
```

Class-method retrieval preserves the receiving class through `Self`, including
for `Profile` subclasses. An explicit subclass override on that method still
has the receiving class's static return type. The existing runtime check rejects
a result that is not an instance of the receiver.

Module-level retrieval preserves the static type of an explicit `settings_class`,
whether supplied positionally or by keyword. Conflicting classes in the explicit
selector and `SettingsParameters` still raise `ValueError`.

`SettingsParameters` is not generic. Parameter-only retrieval and manager methods
return `MountainAshBaseSettings` statically, even when a more specific class was
stored in the parameters. Supply the known class explicitly or narrow the result
with `isinstance` when application code needs its fields.

## Dynamic boundaries

- Native annotated profile fields retain their declared types. Fields installed
  solely from an explicit `ProfileSpec` are runtime-generated; static checking
  needs visible field annotations on the class to know those attributes.
- Name-based `Registry.get_settings_class()` returns `type[Profile]`. A runtime
  name does not establish a specific subclass for a type checker.
- Constructor and retrieval `**kwargs` remain dynamic inputs. Pydantic validates
  their values at runtime; the typing contract does not promise static checking
  of every input key or coercion. Typed attribute access and assignment are checked.
- Emitted driver dictionaries and other intentionally dynamic values can contain
  `Any`. The marker does not make every operation statically precise.

## Source and test checks

```sh
hatch run mypy:check-src
hatch run mypy:check-tests
hatch run mypy:check-src-untyped
hatch run mypy:check-tests-untyped
```

The source commands use the same four production passes as `mypy:check`: common
code, Linux POSIX, macOS POSIX and Windows-native code. Extra mypy flags are
forwarded to every pass. The test commands target `tests` and also accept extra
mypy flags without replacing that target. Test checks still follow source imports
and can also report source errors.

The `-untyped` variants include `--check-untyped-defs` to check bodies of
unannotated functions. This flag remains opt-in.

## Qualification

Run `hatch run mypy:check` for the four production passes and
`hatch run mypy:qualify` for installed-artifact checks. The latter builds a wheel
and sdist, rebuilds a wheel from the sdist, and checks each wheel in its own fresh
environment outside the source tree. It checks public exports, inferred types,
expected-invalid calls and runtime selector behavior.

The command prints the evidence directory. Pass `--output /path/to/new-directory`
to retain artifacts and logs at a chosen location. CI runs the gate for both
Python versions and uploads logs, artifacts and their SHA-256 receipt. This
typing qualification is separate from release authorization.
