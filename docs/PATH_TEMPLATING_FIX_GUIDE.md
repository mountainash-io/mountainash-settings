# Path Templating Fix Guide

## Problem Summary

The PLATFORM_SLASH approach for cross-platform path templates is a hack that creates brittle, hard-to-read code. The attempt to use backslash operators `\` with UPath results in syntax errors.

## Solution

Use UPath's `/` operator for path joining, then convert to string for template storage.

## Fixing acrds_settings_templates.py

### Current Code (Line 26 - BROKEN)

```python
# This has a SYNTAX ERROR - backslash is not a path operator
REPORT_BASE_PATH_TEMPLATE: str = Field(
    default= UPath("~" \ "data" \ "mountainash" \ "{{ORGANISATION_NAME}}" \ "{{PORTFOLIO_NAME}}" \ "{{RUNDATE}}" \ "report")
)
```

### Fixed Code

```python
# Option 1: Direct conversion
REPORT_BASE_PATH_TEMPLATE: str = Field(
    default=str(
        UPath("~") / "data" / "mountainash" / "{ORGANISATION_NAME}" / "{PORTFOLIO_NAME}" / "{RUNDATE}" / "report"
    )
)

# Option 2: With intermediate variable (more readable for long paths)
_report_base = (
    UPath("~") / "data" / "mountainash" /
    "{ORGANISATION_NAME}" / "{PORTFOLIO_NAME}" / "{RUNDATE}" / "report"
)
REPORT_BASE_PATH_TEMPLATE: str = Field(default=str(_report_base))

# Option 3: Using helper function (cleanest for many paths)
def build_path_template(*parts: str) -> str:
    """Build cross-platform path template from parts."""
    path = UPath(parts[0])
    for part in parts[1:]:
        path = path / part
    return str(path)

REPORT_BASE_PATH_TEMPLATE: str = Field(
    default=build_path_template(
        "~", "data", "mountainash",
        "{ORGANISATION_NAME}", "{PORTFOLIO_NAME}", "{RUNDATE}", "report"
    )
)
```

## Step-by-Step Migration

### Step 1: Remove PLATFORM_SLASH dependency

**OLD:**
```python
from mountainash_utils_os import get_platform_slash
PLATFORM_SLASH = get_platform_slash()
```

**NEW:**
```python
from upath import UPath
# No need for PLATFORM_SLASH at all!
```

### Step 2: Convert path templates

**OLD:**
```python
REPORT_BASE_PATH_TEMPLATE: str = Field(
    default=f"~{PLATFORM_SLASH}data{PLATFORM_SLASH}mountainash{PLATFORM_SLASH}{{ORGANISATION_NAME}}{PLATFORM_SLASH}{{PORTFOLIO_NAME}}{PLATFORM_SLASH}{{RUNDATE}}{PLATFORM_SLASH}report"
)
```

**NEW:**
```python
REPORT_BASE_PATH_TEMPLATE: str = Field(
    default=str(
        UPath("~") / "data" / "mountainash" / "{ORGANISATION_NAME}" / "{PORTFOLIO_NAME}" / "{RUNDATE}" / "report"
    )
)
```

### Step 3: Convert derived path templates

**OLD:**
```python
REPORT_DATA_PATH_TEMPLATE: str = Field(
    default=f"{{REPORT_BASE_PATH}}{PLATFORM_SLASH}report_data"
)
```

**NEW:**
```python
REPORT_DATA_PATH_TEMPLATE: str = Field(
    default=str(UPath("{REPORT_BASE_PATH}") / "report_data")
)
```

### Step 4: Test cross-platform

```python
# Test that templates work correctly
settings = AcrdsSettingsTemplates()
print(settings.REPORT_BASE_PATH_TEMPLATE)
# Output on Linux: ~/data/mountainash/{ORGANISATION_NAME}/{PORTFOLIO_NAME}/{RUNDATE}/report
# Output on Windows: ~\data\mountainash\{ORGANISATION_NAME}\{PORTFOLIO_NAME}\{RUNDATE}\report
```

## Complete Example for acrds_settings_templates.py

```python
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from upath import UPath


def build_path_template(*parts: str) -> str:
    """Helper to build cross-platform path templates."""
    path = UPath(parts[0])
    for part in parts[1:]:
        path = path / part
    return str(path)


class AcrdsSettingsTemplates(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=(
            "~/.mountainash_acdrs/mountainash_acdrs_file_templates.env",
            "mountainash_acdrs_file_templates.env",
        ),
        extra="ignore",
    )

    # Base path templates - using UPath
    REPORT_BASE_PATH_TEMPLATE: str = Field(
        default=build_path_template(
            "~", "data", "mountainash",
            "{ORGANISATION_NAME}", "{PORTFOLIO_NAME}", "{RUNDATE}", "report"
        )
    )

    RESPONSE_BASE_PATH_TEMPLATE: str = Field(
        default=build_path_template(
            "~", "data", "mountainash",
            "{ORGANISATION_NAME}", "{PORTFOLIO_NAME}", "{RUNDATE}", "response"
        )
    )

    # Derived path templates - reference other templates
    REPORT_DATA_PATH_TEMPLATE: str = Field(
        default=str(UPath("{REPORT_BASE_PATH}") / "report_data")
    )

    RESPONSE_DATA_PATH_TEMPLATE: str = Field(
        default=str(UPath("{RESPONSE_BASE_PATH}") / "response_data")
    )

    REPORT_FLATTENED_DATA_PATH_TEMPLATE: str = Field(
        default=str(UPath("{REPORT_BASE_PATH}") / "flattened_report_data")
    )

    RESPONSE_FLATTENED_DATA_PATH_TEMPLATE: str = Field(
        default=str(UPath("{RESPONSE_BASE_PATH}") / "flattened_response_data")
    )

    REPORT_VALIDATION_DATA_PATH_TEMPLATE: str = Field(
        default=str(UPath("{REPORT_BASE_PATH}") / "report_validation_data")
    )

    RESPONSE_VALIDATION_DATA_PATH_TEMPLATE: str = Field(
        default=str(UPath("{RESPONSE_BASE_PATH}") / "response_validation_data")
    )

    # Filename templates (no path components, just strings)
    REPORT_FILENAME_TEMPLATE: str = Field(
        default="{ORGANISATION_NAME}_{PORTFOLIO_NAME}_{RUNDATETIME}_{ORGANISATION_TLA}_{RUNDATE}{BATCH_ITERATION}.xml"
    )

    RESPONSE_FILENAME_TEMPLATE: str = Field(
        default="{ORGANISATION_NAME}_{PORTFOLIO_NAME}_{RUNDATETIME}_{ORGANISATION_TLA}_{RUNDATE}{BATCH_ITERATION}{BUREAU_RESPONSE_SUFFIX}.xml"
    )

    # Module paths (use dots, not filesystem paths)
    APP_METADATA_PATH_TEMPLATE: str = Field(
        default="mountainash_acrds_core.config.app_metadata"
    )

    APP_BUILD_REPORT_FIELDMAPPINGS_PATH_TEMPLATE: str = Field(
        default="mountainash_acrds_core.config.fieldmappings.report.build.{BATCH_VERSION}"
    )

    # ... rest of the templates ...

    BATCH_ID_TEMPLATE: str = Field(
        default="BATCH_{ORGANISATION_NAME}_{PORTFOLIO_NAME}_{RUNDATE}{BATCH_ITERATION}"
    )

    RUNDATETIME_TEMPLATE: str = Field(
        default="{RUNDATE}T{RUNTIME}"
    )


@lru_cache(maxsize=None)
def get_acrds_settings_templates() -> AcrdsSettingsTemplates:
    """Retrieve the AcrdsSettingsTemplates object."""
    return AcrdsSettingsTemplates()
```

## Key Takeaways

1. **Use `/` operator, not `\` operator** - UPath's `/` is the path joining operator
2. **Convert to string** - Use `str(UPath(...))` for template storage
3. **Single braces for templates** - Use `{FIELD}` not `{{FIELD}}` (double braces only in f-strings)
4. **Helper function for readability** - `build_path_template()` makes code cleaner
5. **No PLATFORM_SLASH needed** - UPath handles cross-platform automatically
6. **Test on both platforms** - Verify templates work on Linux and Windows

## Benefits

- **Cleaner code**: No ugly f-string concatenation
- **More readable**: Clear path structure with `/` operator
- **Type safe**: UPath provides better type hints
- **Less error-prone**: No manual slash management
- **Future-proof**: Works with cloud paths (s3://, gs://, etc.) via UPath
- **Maintainable**: Easy to understand and modify

## Reference

- See `examples/path_templating_with_upath.py` for comprehensive examples
- See `CLAUDE.md` section "Path Templating with UPath" for quick reference
- See `MountainAshBaseSettings.init_setting_from_template()` for template resolution
