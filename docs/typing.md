# Installed typing support

Built distributions include the PEP 561 `py.typed` marker. Consumers can use
the package's inline annotations without configuring a source path or stubs.
The installed-consumer gate uses mypy 1.10.1 on Python 3.12 and 3.13, with
Pydantic's standard typing support and no mypy plugin.

## Direct construction

Ordinary subclasses accept MountainAsh's source controls and dynamic field inputs
without a forwarding constructor or a required mypy plugin:

```python
from typing import assert_type
from mountainash_settings import MountainAshBaseSettings

class AppSettings(MountainAshBaseSettings):
    PORT: int = 5432

settings = AppSettings(config_files=[], env_prefix="REPORT_", PORT="6000")
assert_type(settings, AppSettings)
assert_type(settings.PORT, int)
assert settings.PORT == 6000
```

Pydantic validates and coerces constructor inputs at runtime; the resulting
object and its declared fields retain their static types. Required model fields
can come from configured sources rather than explicit constructor arguments.
This also applies through settings inheritance and native class-declared profiles.

A private metaclass preserves the library's constructor signature under the
supported mypy baseline. It is an implementation detail, not a new public
metaclass extension API. Typed attribute assignment remains checked; dynamic
constructor inputs do not make the resulting model `Any`.

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
- `Registry.get_settings_class()` returns the registry's selected profile class
  interface, defaulting to `type[Profile]` when no profile selector is supplied.
  A name alone does not establish the exact registered concrete subclass type.
- Constructor and retrieval `**kwargs` remain dynamic inputs. Pydantic validates
  their values at runtime; the typing contract does not promise static checking
  of every input key or coercion. Typed attribute access and assignment are checked.
- Emitted driver dictionaries and other intentionally dynamic values can contain
  `Any`. The marker does not make every operation statically precise.

## Registry types

`Registry` infers spec/profile types from `spec_type` and `profile_type`.
`get_spec()` and `specs` retain the selected spec type; `get_settings_class()`
returns the selected profile class type. Omitted or `None` selectors default to
`ProfileSpec` and `Profile`. Optional selectors retain those default possibilities.
Explicit generic arguments do not configure runtime selectors.

Registry is statically final: use selectors and composition instead of
subclassing it. Profile subclasses remain supported.

Profile selectors are class objects, including runtime-checkable method-only
Protocols usable with `issubclass`. Functions and callable instances are not
selectors. Registered classes must still inherit Profile and meet the selected
domain constraints. Data-member and non-runtime-checkable Protocols gain no support.

Direct registration checks the selected argument types statically. Decorators
preserve the exact input Profile subclass; their domain checks happen at runtime.
A structural match alone does not establish nominal Profile inheritance.

Protocol selector typing uses a documented class-only bottom-type union
workaround for mypy 1.10.1. Installed positive and negative controls protect it
when the checker changes; no plugin is required.

## Source and test checks

```sh
hatch run mypy:check-src
hatch run mypy:check-tests
hatch run mypy:check-src-untyped
hatch run mypy:check-tests-untyped
```

The source commands use the same four production passes as `mypy:check`: common
code, Linux POSIX, macOS POSIX and Windows-native code. Extra mypy flags are
forwarded to every pass. `tools/check_test_types.py` owns a separate four-pass
test check, also forwarding extra flags:

| Pass | Targets |
|---|---|
| Common (Linux typeshed) | `tests`, excluding the four native files routed below |
| Linux POSIX | `tests/secrets/native/test_posix.py` and `posix_helpers.py` |
| macOS POSIX | The same two POSIX files |
| Windows | `tests/secrets/native/test_windows.py` and `_windows_fixtures.py` |

`tests/secrets/native/test_filesystem.py` remains in the common pass. That pass
follows source imports normally and can report source errors; native passes use
`--follow-imports=silent`. Discovery exclusions do not suppress imported modules,
so keep native helpers confined to their platform's tests. Selecting a typeshed
platform does not execute tests on that operating system.

The `-untyped` variants include `--check-untyped-defs` to check bodies of
unannotated functions. This flag remains opt-in; the test variant can still report
outstanding annotation and intentional-invalid-input diagnostics. A clean default
test check does not establish that all untyped test bodies are checked.

Current typing CI runs the production and installed-consumer gates. The separate
test commands are developer checks, not yet additional CI jobs.

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
