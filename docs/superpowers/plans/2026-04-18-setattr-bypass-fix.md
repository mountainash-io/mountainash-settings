# Setattr Bypass Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore canonical pydantic v2 assignment semantics on `MountainAshBaseSettings` so declared field types (enums, `SecretStr`, `AfterValidator` transforms) are honoured on every post-construction mutation.

**Architecture:** Flip `model_config["validate_assignment"] = True`, remove the redundant `update_settings_from_dict` re-application inside `__init__`, and convert the seven meta-field writes in `__init__` to `object.__setattr__` so they stay exempt from the newly-enabled validation.

**Tech Stack:** Python 3.12 · pydantic 2.9 · pydantic-settings 2.6 · hatch · pytest · UPath

**Spec:** `docs/superpowers/specs/2026-04-18-setattr-bypass-fix-design.md`

---

## File Structure

**Modified files:**
- `src/mountainash_settings/settings/base_settings.py` — config flag + `__init__` cleanup
- `tests/test_base_settings_coverage.py` — add `TestCanonicalAssignmentSemantics` and regression-guard test

**Unchanged but relevant (do not edit):**
- `src/mountainash_settings/profiles/profile.py` — `DescriptorProfile` already wires `AfterValidator` and uses `object.__setattr__` for template writes; no edit needed.
- `src/mountainash_settings/settings_cache/settings_manager.py:47` — uses `update_settings_from_dict`; gains correctness automatically.
- `src/mountainash_settings/settings_parameters/settings_parameters.py:365` — same.

**Branch:** work continues on `feat/profiles-promotion` (current branch). Target PR base: `develop`.

---

## Task 1: Add canonical-assignment tests as xfail

**Files:**
- Modify: `tests/test_base_settings_coverage.py` — append a new test class at the end of the file (after `TestPostInitHook`, line 608-ish).

Rationale: these tests codify the contract we want. Add them as `xfail` first so they don't block commits; flip to expected-pass after Change A lands in Task 2.

- [ ] **Step 1: Read the current end of `test_base_settings_coverage.py`**

```bash
wc -l tests/test_base_settings_coverage.py
```

Expected: a line count (~610). Note the number — we'll append after the last class.

- [ ] **Step 2: Append the new test class**

Add this at the end of `tests/test_base_settings_coverage.py`:

```python


# ---------------------------------------------------------------------------
# Canonical pydantic assignment semantics
# ---------------------------------------------------------------------------
# See docs/superpowers/specs/2026-04-18-setattr-bypass-fix-design.md
# Tests codify the contract restored by enabling validate_assignment=True.
# ---------------------------------------------------------------------------

from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator, Field, SecretStr

from mountainash_settings import MountainAshBaseSettings
from mountainash_settings.auth import NoAuth
from mountainash_settings.profiles import (
    DescriptorProfile,
    ParameterSpec,
    ProfileDescriptor,
)


class _Mode(StrEnum):
    FULL = "full"
    INCREMENTAL = "incremental"


class _SecretSettings(MountainAshBaseSettings):
    PASSWORD: SecretStr = Field(default=SecretStr(""))


class _EnumSettings(MountainAshBaseSettings):
    MODE: _Mode = Field(default=_Mode.FULL)


class _TransformSettings(MountainAshBaseSettings):
    NAME: Annotated[str, AfterValidator(str.upper)] = Field(default="")


class _SampleProfile(DescriptorProfile):
    __descriptor__ = ProfileDescriptor(
        name="sample",
        provider_type="sample",
        parameters=[
            ParameterSpec(name="TOKEN", type=str, tier="core", secret=True),
            ParameterSpec(name="MODE", type=_Mode, tier="core",
                          default=_Mode.FULL),
            ParameterSpec(name="LABEL", type=str, tier="core", default="x",
                          validator=str.upper),
        ],
        auth_modes=[NoAuth],
    )


class TestCanonicalAssignmentSemantics:
    """Validate_assignment=True restores pydantic's declared-type contract."""

    @pytest.mark.unit
    @pytest.mark.xfail(reason="Enabled by Change A in Task 2", strict=True)
    def test_secretstr_wraps_on_direct_setattr(self):
        s = _SecretSettings()
        s.PASSWORD = "plain"
        assert isinstance(s.PASSWORD, SecretStr)
        assert s.PASSWORD.get_secret_value() == "plain"

    @pytest.mark.unit
    @pytest.mark.xfail(reason="Enabled by Change A in Task 2", strict=True)
    def test_enum_coerces_on_direct_setattr(self):
        s = _EnumSettings()
        s.MODE = "incremental"
        assert s.MODE is _Mode.INCREMENTAL

    @pytest.mark.unit
    @pytest.mark.xfail(reason="Enabled by Change A in Task 2", strict=True)
    def test_aftervalidator_transforms_on_direct_setattr(self):
        s = _TransformSettings()
        s.NAME = "lower"
        assert s.NAME == "LOWER"

    @pytest.mark.unit
    @pytest.mark.xfail(reason="Enabled by Change A in Task 2", strict=True)
    def test_update_settings_from_dict_wraps_secretstr(self):
        s = _SecretSettings()
        s.update_settings_from_dict({"PASSWORD": "plain"})
        assert isinstance(s.PASSWORD, SecretStr)
        assert s.PASSWORD.get_secret_value() == "plain"

    @pytest.mark.unit
    @pytest.mark.xfail(reason="Enabled by Change A in Task 2", strict=True)
    def test_update_settings_from_dict_coerces_enum(self):
        s = _EnumSettings()
        s.update_settings_from_dict({"MODE": "incremental"})
        assert s.MODE is _Mode.INCREMENTAL

    @pytest.mark.unit
    @pytest.mark.xfail(reason="Enabled by Change A in Task 2", strict=True)
    def test_update_settings_from_dict_applies_transform(self):
        s = _TransformSettings()
        s.update_settings_from_dict({"NAME": "lower"})
        assert s.NAME == "LOWER"

    @pytest.mark.unit
    @pytest.mark.xfail(reason="Enabled by Change A in Task 2", strict=True)
    def test_descriptor_profile_secret_on_setattr(self):
        p = _SampleProfile(TOKEN="raw", auth=NoAuth())
        p.TOKEN = "new"
        assert isinstance(p.TOKEN, SecretStr)
        assert p.TOKEN.get_secret_value() == "new"

    @pytest.mark.unit
    @pytest.mark.xfail(reason="Enabled by Change A in Task 2", strict=True)
    def test_descriptor_profile_enum_on_setattr(self):
        p = _SampleProfile(TOKEN="raw", auth=NoAuth())
        p.MODE = "incremental"
        assert p.MODE is _Mode.INCREMENTAL

    @pytest.mark.unit
    @pytest.mark.xfail(reason="Enabled by Change A in Task 2", strict=True)
    def test_descriptor_profile_validator_transform_on_setattr(self):
        p = _SampleProfile(TOKEN="raw", auth=NoAuth())
        p.LABEL = "lower"
        assert p.LABEL == "LOWER"
```

- [ ] **Step 3: Run the new tests to confirm they xfail (not error)**

```bash
hatch run test:test tests/test_base_settings_coverage.py::TestCanonicalAssignmentSemantics -v
```

Expected: all 9 tests reported as XFAIL (expected failure). If any errors with `ImportError` or class-definition failure, fix imports/class definitions before continuing — the tests must *run* (and fail at the assertion) for `xfail` to be meaningful. A test that errors during collection is not a valid `xfail`.

- [ ] **Step 4: Run the full existing suite to confirm no regression**

```bash
hatch run test:test
```

Expected: previous baseline green plus 9 new XFAIL lines. No new FAIL or ERROR.

- [ ] **Step 5: Commit**

```bash
git add tests/test_base_settings_coverage.py
git commit -m "$(cat <<'EOF'
test(base_settings): add canonical assignment semantics tests (xfail)

Codifies the contract to be restored by enabling
validate_assignment=True on MountainAshBaseSettings. Covers
SecretStr wrapping, StrEnum coercion, AfterValidator transform
on direct setattr, update_settings_from_dict, and the
DescriptorProfile integration path.

Marked xfail(strict=True) — will flip to expected-pass once
Change A lands.

Spec: docs/superpowers/specs/2026-04-18-setattr-bypass-fix-design.md
EOF
)"
```

---

## Task 2: Change A — enable `validate_assignment=True`

**Files:**
- Modify: `src/mountainash_settings/settings/base_settings.py:16-23`

- [ ] **Step 1: Flip the config flag**

Replace the `model_config` block at lines 16-23:

```python
    model_config = SettingsConfigDict(
            extra="ignore",
            validate_default=False,
            arbitrary_types_allowed=True,
            # validate_assignment=True,
            # validate_assignment=False,

        )
```

with:

```python
    model_config = SettingsConfigDict(
            extra="ignore",
            validate_default=False,
            arbitrary_types_allowed=True,
            validate_assignment=True,

        )
```

- [ ] **Step 2: Run the canonical-assignment tests — they should now fail xfail (XPASS)**

```bash
hatch run test:test tests/test_base_settings_coverage.py::TestCanonicalAssignmentSemantics -v
```

Expected: **all 9 tests FAIL** because `xfail(strict=True)` converts unexpected passes to failures. The output will show `XPASS(strict)` — that's the signal Change A worked.

- [ ] **Step 3: Run the full suite to surface existing-test impact**

```bash
hatch run test:test 2>&1 | tee /tmp/phase2-suite.log
```

Expected: a mix of outcomes:
- New `XPASS(strict)` lines (treated as failures) — fixed in Task 3 Step 1.
- Previously-passing tests may now fail if they asserted raw-string post-setattr shape.

- [ ] **Step 4: Triage failures**

For each failing test that is NOT one of our new `TestCanonicalAssignmentSemantics` cases:

1. Read the failure and the test source.
2. Classify:
   - **(a) Test asserted the broken contract** (e.g. `assert isinstance(s.PASSWORD, str) and not isinstance(s.PASSWORD, SecretStr)`) → this test codified the bypass bug. Report to user with the classification; await direction.
   - **(b) Implementation has a latent bug exposed by validation** → report to user; await direction.

Per `~/.claude/CLAUDE.md` test-integrity rule: **do not skip, xfail, or silently rewrite any existing test.** Surface each failure to the user before making changes.

If there are zero existing-test failures (the ideal case), proceed to Step 5.

- [ ] **Step 5: Remove `xfail` markers from `TestCanonicalAssignmentSemantics`**

In `tests/test_base_settings_coverage.py`, delete every line that matches:

```python
    @pytest.mark.xfail(reason="Enabled by Change A in Task 2", strict=True)
```

Nine occurrences — one per test method in `TestCanonicalAssignmentSemantics`. Leave the `@pytest.mark.unit` decorators intact.

- [ ] **Step 6: Re-run and confirm green**

```bash
hatch run test:test tests/test_base_settings_coverage.py::TestCanonicalAssignmentSemantics -v
hatch run test:test
```

Expected: all 9 canonical-assignment tests PASS. Full suite green (or at parity with Step 4's triaged baseline).

- [ ] **Step 7: Commit**

```bash
git add src/mountainash_settings/settings/base_settings.py tests/test_base_settings_coverage.py
git commit -m "$(cat <<'EOF'
feat(base_settings): enable validate_assignment for canonical semantics

Sets model_config["validate_assignment"] = True on
MountainAshBaseSettings. Every setattr on an instance (including
via update_settings_from_dict, SettingsManager runtime overrides,
and apply_runtime_overrides) now runs the field's declared
validator pipeline — enum coercion, SecretStr wrapping,
AfterValidator transforms.

Addresses the setattr-bypass-limitation backlog item. Removes
the bypass mechanism that forced PySparkMode.__setattr__ and
ConnectionProfile SecretStr defensive code in consumer packages.

Flips the canonical-assignment test class out of xfail.

Spec: docs/superpowers/specs/2026-04-18-setattr-bypass-fix-design.md
EOF
)"
```

---

## Task 3: Change B — remove redundant re-application in `__init__`

**Files:**
- Modify: `src/mountainash_settings/settings/base_settings.py:97-107`

**Why this task is separate from Task 2:** Change A alone fixes the canonical contract. Change B is about removing dead code (the redundant re-application) and documenting intentional validation bypass for harness meta-fields. Keeping them as separate commits makes bisect clean.

- [ ] **Step 1: Write a test asserting internal bookkeeping still stashes meta-fields**

Append to `TestCanonicalAssignmentSemantics` in `tests/test_base_settings_coverage.py`:

```python

    @pytest.mark.unit
    def test_meta_field_bookkeeping_still_works(self):
        """Change B refactors __init__ meta-field writes to
        object.__setattr__. Confirm the bookkeeping values still land."""
        from fixtures.settings_classes import TestSettings
        s = TestSettings(TEST_VAL_1="x", TEST_VAL_2="y")
        assert s.SETTINGS_CLASS is TestSettings
        assert s.SETTINGS_CLASS_NAME == "TestSettings"
        assert s.SETTINGS_SOURCE_KWARGS == {"TEST_VAL_1": "x", "TEST_VAL_2": "y"}
```

- [ ] **Step 2: Run the new test — it should pass on current code (baseline)**

```bash
hatch run test:test tests/test_base_settings_coverage.py::TestCanonicalAssignmentSemantics::test_meta_field_bookkeeping_still_works -v
```

Expected: PASS. This is the guard: if Change B breaks meta-field bookkeeping, this test flips red.

- [ ] **Step 3: Apply Change B in `base_settings.py`**

Replace lines 97-107 (the section from the `#Update all vals from valid kwargs` comment through the last `setattr`):

```python
        #Update all vals from valid kwargs
        self.update_settings_from_dict(settings_dict=valid_attribute_kwargs)

        setattr(self, "SETTINGS_CLASS",                 local_settings_params.settings_class or MountainAshBaseSettings)
        setattr(self, "SETTINGS_CLASS_NAME",            local_settings_params.settings_class.__name__ if local_settings_params.settings_class else "MountainAshBaseSettings")
        setattr(self, "SETTINGS_SOURCE_ENV_PREFIX",     local_settings_params.env_prefix)
        setattr(self, "SETTINGS_SOURCE_ENV_FILES",      obj_config_files.env_files)
        setattr(self, "SETTINGS_SOURCE_YAML_FILES",     obj_config_files.yaml_files)
        setattr(self, "SETTINGS_SOURCE_TOML_FILES",     obj_config_files.toml_files)
        setattr(self, "SETTINGS_SOURCE_JSON_FILES",     obj_config_files.json_files)
        setattr(self, "SETTINGS_SOURCE_SECRETS_DIR",    local_settings_params.secrets_dir)
```

with:

```python
        # Meta-field bookkeeping only. super().__init__ above already applied
        # valid_attribute_kwargs under full validation — re-applying them via
        # update_settings_from_dict would overwrite validated values with raw
        # input (see setattr-bypass-limitation spec, 2026-04-18).
        #
        # object.__setattr__ is intentional: these fields are harness
        # bookkeeping, not user config, and with validate_assignment=True on
        # model_config we want to skip revalidation on them explicitly.
        object.__setattr__(self, "SETTINGS_SOURCE_KWARGS",    valid_attribute_kwargs)
        object.__setattr__(self, "SETTINGS_CLASS",            local_settings_params.settings_class or MountainAshBaseSettings)
        object.__setattr__(self, "SETTINGS_CLASS_NAME",       local_settings_params.settings_class.__name__ if local_settings_params.settings_class else "MountainAshBaseSettings")
        object.__setattr__(self, "SETTINGS_SOURCE_ENV_PREFIX", local_settings_params.env_prefix)
        object.__setattr__(self, "SETTINGS_SOURCE_ENV_FILES",  obj_config_files.env_files)
        object.__setattr__(self, "SETTINGS_SOURCE_YAML_FILES", obj_config_files.yaml_files)
        object.__setattr__(self, "SETTINGS_SOURCE_TOML_FILES", obj_config_files.toml_files)
        object.__setattr__(self, "SETTINGS_SOURCE_JSON_FILES", obj_config_files.json_files)
        object.__setattr__(self, "SETTINGS_SOURCE_SECRETS_DIR", local_settings_params.secrets_dir)
```

Note: `SETTINGS_SOURCE_KWARGS` is now stashed inline (first `object.__setattr__`) — previously it was set by `update_settings_from_dict` at line 258. `update_settings_from_dict` still stashes it at line 258 for callsites 2 & 3 (`SettingsManager.get_settings_object`, `apply_runtime_overrides`) — that line is **unchanged**.

- [ ] **Step 4: Run the meta-field bookkeeping test**

```bash
hatch run test:test tests/test_base_settings_coverage.py::TestCanonicalAssignmentSemantics::test_meta_field_bookkeeping_still_works -v
```

Expected: PASS.

- [ ] **Step 5: Run the full `TestUpdateSettingsFromDict` class**

```bash
hatch run test:test tests/test_base_settings_coverage.py::TestUpdateSettingsFromDict -v
```

Expected: all existing tests still PASS. `update_settings_from_dict` itself is unchanged; only the redundant call inside `__init__` was removed.

- [ ] **Step 6: Run the full suite**

```bash
hatch run test:test
```

Expected: green, at parity with end of Task 2.

- [ ] **Step 7: Commit**

```bash
git add src/mountainash_settings/settings/base_settings.py tests/test_base_settings_coverage.py
git commit -m "$(cat <<'EOF'
refactor(base_settings): remove redundant kwargs re-application in __init__

super().__init__(**valid_attribute_kwargs) already applies kwargs
under full pydantic validation. The subsequent
update_settings_from_dict(valid_attribute_kwargs) call was
overwriting the validated values with raw input — the original
source of the setattr-bypass-limitation.

Replaces the call plus seven meta-field setattrs with explicit
object.__setattr__ writes. Meta-fields are harness bookkeeping,
not user config: bypassing validation is intentional and now
explicit. SETTINGS_SOURCE_KWARGS is stashed inline here;
update_settings_from_dict still stashes it for the
SettingsManager and apply_runtime_overrides callsites.

Adds a guard test for meta-field bookkeeping.

Spec: docs/superpowers/specs/2026-04-18-setattr-bypass-fix-design.md
EOF
)"
```

---

## Task 4: Regression guard

**Files:**
- Modify: `tests/test_base_settings_coverage.py`

- [ ] **Step 1: Add a regression guard test**

Append to `TestCanonicalAssignmentSemantics` in `tests/test_base_settings_coverage.py`:

```python

    @pytest.mark.unit
    def test_validate_assignment_is_enabled(self):
        """Regression guard — canonical assignment validation must stay on.

        If this assertion fires, someone disabled validate_assignment on
        MountainAshBaseSettings. Do not 'fix' by deleting this test.
        See docs/superpowers/specs/2026-04-18-setattr-bypass-fix-design.md
        """
        assert MountainAshBaseSettings.model_config.get("validate_assignment") is True
```

- [ ] **Step 2: Run the guard**

```bash
hatch run test:test tests/test_base_settings_coverage.py::TestCanonicalAssignmentSemantics::test_validate_assignment_is_enabled -v
```

Expected: PASS.

- [ ] **Step 3: Run the full suite one last time**

```bash
hatch run test:test
```

Expected: green.

- [ ] **Step 4: Lint the modified files**

```bash
hatch run ruff:check src/mountainash_settings/settings/base_settings.py tests/test_base_settings_coverage.py
```

Expected: no complaints, or run `hatch run ruff:fix` on the same paths and re-run.

- [ ] **Step 5: Commit**

```bash
git add tests/test_base_settings_coverage.py
git commit -m "$(cat <<'EOF'
test(base_settings): add regression guard for validate_assignment

Explicit assertion that model_config["validate_assignment"] is True
on MountainAshBaseSettings. Fails loudly if a future change turns
off the canonical assignment contract.

Spec: docs/superpowers/specs/2026-04-18-setattr-bypass-fix-design.md
EOF
)"
```

---

## Task 5: Final verification + PR

- [ ] **Step 1: Confirm the full test suite is green**

```bash
hatch run test:test
```

Expected: all tests pass, including the 11 new ones in `TestCanonicalAssignmentSemantics` (9 canonical + 1 bookkeeping guard + 1 regression guard).

- [ ] **Step 2: Confirm ruff is clean for the whole project**

```bash
hatch run ruff:check
```

Expected: clean. Fix any complaints or run `hatch run ruff:fix`, then re-run and recommit with `style:` prefix.

- [ ] **Step 3: Confirm mypy is clean**

```bash
hatch run mypy:check
```

Expected: clean (or at parity with pre-change baseline). Triage any new errors with the user before proceeding.

- [ ] **Step 4: Verify the commits look right**

```bash
git log --oneline feat/profiles-promotion ^origin/develop
```

Expected: four new commits on top of the spec commit — `test: xfail tests`, `feat: validate_assignment`, `refactor: __init__`, `test: regression guard`. Plus the design-doc commit.

- [ ] **Step 5: Push the branch**

```bash
git push -u origin feat/profiles-promotion
```

- [ ] **Step 6: Open the PR targeting `develop`**

Per the mountainash-io three-tier flow, feature branches PR into `develop`, not `main`.

```bash
gh pr create --base develop --title "fix(base_settings): restore canonical pydantic assignment semantics" --body "$(cat <<'EOF'
## Summary

- Enables `validate_assignment=True` on `MountainAshBaseSettings` so declared field types (enums, `SecretStr`, `AfterValidator` transforms) are honoured on every post-construction mutation.
- Removes the redundant `update_settings_from_dict` re-application in `__init__` that was overwriting validated fields with raw kwargs.
- Converts seven meta-field writes in `__init__` to explicit `object.__setattr__` to document intentional bypass for harness bookkeeping.

## Why

Addresses the `setattr-bypass-limitation` backlog item:
`mountainash-central/01.principles/mountainash-data/f.backlog/setattr-bypass-limitation.md`

Root cause was `__init__` applying kwargs twice: once via `super().__init__(**kwargs)` (with validation) and then again via `update_settings_from_dict` (raw setattr, no validation) — discarding the validated values. Combined with `validate_assignment` being disabled, this forced per-class `__setattr__` overrides (e.g. `PySparkMode`) and defensive unwrap guards (e.g. `ConnectionProfile._default_driver_kwargs`) across consumer packages.

## Test plan

- [ ] `hatch run test:test` green
- [ ] `hatch run ruff:check` clean
- [ ] `hatch run mypy:check` clean
- [ ] New `TestCanonicalAssignmentSemantics` class (11 tests) passes
- [ ] Existing `TestUpdateSettingsFromDict` still passes
- [ ] Downstream packages (`mountainash-data`) still build against this branch

## Spec & Design

`docs/superpowers/specs/2026-04-18-setattr-bypass-fix-design.md`

## Follow-up (separate PRs)

After this is released and consumers bump:

- Remove `PySparkMode.__setattr__` override in `mountainash-data`
- Remove `ConnectionProfile._default_driver_kwargs` SecretStr unwrap guard
- Simplify adapter `str(enum_value)` defensive code
- Close the backlog item

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-Review

**Spec coverage:**
- Change A (`validate_assignment=True`) → Task 2.
- Change B (remove redundant call + convert meta-field setattrs) → Task 3.
- Change C (leave `update_settings_from_dict` as-is) → confirmed unchanged in Task 3 Step 5.
- Test strategy items (SecretStr / enum / AfterValidator / update_settings_from_dict / DescriptorProfile / meta-field bookkeeping / regression guard) → Tasks 1, 3, 4.
- Release-notes entry → captured in the PR body in Task 5 Step 6.
- Risk category 2 triage (existing-test failures) → Task 2 Step 4.

**Placeholder scan:** no TBD/TODO; every step has concrete code or commands. Triage step in Task 2 Step 4 references specific classification rules, not a vague "handle failures."

**Type consistency:** `_Mode`, `_SecretSettings`, `_EnumSettings`, `_TransformSettings`, `_SampleProfile` are referenced consistently across Task 1 tests. `ParameterSpec`, `ProfileDescriptor`, `NoAuth`, `DescriptorProfile` import paths match the current package exports (`src/mountainash_settings/__init__.py` and `src/mountainash_settings/profiles/__init__.py`, verified against `feat/profiles-promotion` HEAD).

**Gap found & fixed:** original draft had no explicit ruff/mypy verification; added to Task 5 Steps 2–3.
