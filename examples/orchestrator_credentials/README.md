# Credentials on an orchestration object's attributes

**Question:** What can an innocent debug log reveal when an orchestration class
stores a settings object as an attribute?

Run from the repository root:

```bash
python examples/orchestrator_credentials/example.py
```

The example uses only synthetic credentials. It checks rendered strings in
memory and prints disclosure booleans, never the password itself.

## A common ownership pattern

```python
@dataclass
class EagerOrchestrator:
    settings: EagerSettings

    def run_task(self):
        return self.settings.DATABASE
```

With `PASSWORD: str`, the loaded settings object's representation contains the
password. The dataclass-generated orchestrator representation includes its
settings attribute. Logging either of these can therefore disclose it:

```python
logger.debug("Orchestrator: %r", orchestrator)
logger.debug("Attributes: %s", vars(orchestrator))
```

A normal class's default object representation does not automatically list its
attributes. This example deliberately uses a dataclass to make the representation
behavior explicit; attribute logging can expose the nested object in either case.

## Store the recipe instead

```python
@dataclass
class RecipeOrchestrator:
    settings_parameters: SettingsParameters

    def run_task(self):
        settings = self.settings_parameters.get_settings()
        return settings.DATABASE
```

The orchestrator retains reconstruction inputs. Resolved settings are local to
the task, and ordinary orchestrator printing includes only the recipe's default
representation. `SettingsParameters` excludes `kwargs` and `secret_store` from
that representation.

The example exercises two forms:

1. A recipe containing a caller-supplied password in `kwargs`: the literal is
   accessible to trusted code, but absent from ordinary `repr`/attribute printing.
2. A file-selector recipe: its fields hold source selectors rather than the
   resolved file password, before and after task execution.

Cached source values can still live in process memory. Keeping resolved settings
off `self` reduces accidental attribute disclosure; it does not erase credentials
from the process or make the recipe a security boundary against explicit access.

## Fair comparison: Pydantic SecretStr

The third orchestrator holds eager settings with `PASSWORD: SecretStr`.
Pydantic masks that field in normal representations, so it also prevents the
demonstrated accidental printing. Recipe-based retrieval and secret field types
are complementary: use suitable field types on resolved settings too.

## Expected output

```text
Eager string: credential in orchestrator repr/attributes = True
Recipe: credential in orchestrator repr/attributes = False
Eager SecretStr: credential in orchestrator repr/attributes = False
File recipe: resolved credentials stay off orchestrator attributes
Explicit kwargs/resolved-value access still exposes credentials
```

Assertions check the representations before and after running each task, so the
demo also verifies that task execution has not replaced the stored recipe with
resolved settings.

## What remains value-bearing

Explicitly inspecting `params.kwargs`, serializing those inputs, or logging a
resolved model with a plain string password can expose credentials. In particular,
recursive dataclass serialization is not the same operation as the safe default
representation. `SecretStr.get_secret_value()` explicitly returns its value too.
Paths and other visible selectors must not themselves contain literal credentials
if they are to be logged.

The benefit demonstrated here is protection against a common accidental logging
path, not automatic credential classification or universal safe serialization.
For explicit references and storage, see [secret references](../secret_references/).
