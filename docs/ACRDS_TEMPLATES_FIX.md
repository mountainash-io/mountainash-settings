# Exact Fixes for acrds_settings_templates.py

## Current Issues (Lines 26-38)

You've correctly switched from backslash to forward slash, but there are two remaining issues:

1. **Missing `str()` conversion** - Field expects str, not UPath
2. **Double braces** - Use `{VAR}` not `{{VAR}}` (double braces only in f-strings)

## Line-by-Line Fixes

### Line 26 - REPORT_BASE_PATH_TEMPLATE

**CURRENT (has issues):**
```python
REPORT_BASE_PATH_TEMPLATE: str = Field(
    default= UPath("~") / "data" / "mountainash" / "{{ORGANISATION_NAME}}" / "{{PORTFOLIO_NAME}}" / "{{RUNDATE}}" / "report"
)
```

**FIXED:**
```python
REPORT_BASE_PATH_TEMPLATE: str = Field(
    default=str(UPath("~") / "data" / "mountainash" / "{ORGANISATION_NAME}" / "{PORTFOLIO_NAME}" / "{RUNDATE}" / "report")
)
```

**Changes:**
- Added `str()` wrapper around the entire UPath expression
- Changed `{{ORGANISATION_NAME}}` to `{ORGANISATION_NAME}`
- Changed `{{PORTFOLIO_NAME}}` to `{PORTFOLIO_NAME}`
- Changed `{{RUNDATE}}` to `{RUNDATE}`

### Line 27 - RESPONSE_BASE_PATH_TEMPLATE

**CURRENT:**
```python
RESPONSE_BASE_PATH_TEMPLATE: str = Field(
    default=UPath("~") / "data" / "mountainash" / "{{ORGANISATION_NAME}}" / "{{PORTFOLIO_NAME}}" / "{{RUNDATE}}" / "response"
)
```

**FIXED:**
```python
RESPONSE_BASE_PATH_TEMPLATE: str = Field(
    default=str(UPath("~") / "data" / "mountainash" / "{ORGANISATION_NAME}" / "{PORTFOLIO_NAME}" / "{RUNDATE}" / "response")
)
```

### Lines 30-31 - Derived Paths

**CURRENT:**
```python
REPORT_DATA_PATH_TEMPLATE: str = Field(
    default=UPath("{REPORT_BASE_PATH}") / "report_data"
)
RESPONSE_DATA_PATH_TEMPLATE: str = Field(
    default=UPath("{RESPONSE_BASE_PATH}") / "response_data"
)
```

**FIXED:**
```python
REPORT_DATA_PATH_TEMPLATE: str = Field(
    default=str(UPath("{REPORT_BASE_PATH}") / "report_data")
)
RESPONSE_DATA_PATH_TEMPLATE: str = Field(
    default=str(UPath("{RESPONSE_BASE_PATH}") / "response_data")
)
```

### Lines 33-34 - Flattened Paths

**CURRENT:**
```python
REPORT_FLATTENED_DATA_PATH_TEMPLATE: str = Field(
    default=UPath("{REPORT_BASE_PATH}") / "flattened_report_data"
)
RESPONSE_FLATTENED_DATA_PATH_TEMPLATE: str = Field(
    default=UPath("{RESPONSE_BASE_PATH}") / "flattened_response_data"
)
```

**FIXED:**
```python
REPORT_FLATTENED_DATA_PATH_TEMPLATE: str = Field(
    default=str(UPath("{REPORT_BASE_PATH}") / "flattened_report_data")
)
RESPONSE_FLATTENED_DATA_PATH_TEMPLATE: str = Field(
    default=str(UPath("{RESPONSE_BASE_PATH}") / "flattened_response_data")
)
```

### Lines 37-38 - Validation Paths

**CURRENT:**
```python
REPORT_VALIDATION_DATA_PATH_TEMPLATE: str = Field(
    default=UPath("{REPORT_BASE_PATH}") / "report_validation_data"
)
RESPONSE_VALIDATION_DATA_PATH_TEMPLATE: str = Field(
    default=UPath("{RESPONSE_BASE_PATH}") / "response_validation_data"
)
```

**FIXED:**
```python
REPORT_VALIDATION_DATA_PATH_TEMPLATE: str = Field(
    default=str(UPath("{REPORT_BASE_PATH}") / "report_validation_data")
)
RESPONSE_VALIDATION_DATA_PATH_TEMPLATE: str = Field(
    default=str(UPath("{RESPONSE_BASE_PATH}") / "response_validation_data")
)
```

## Why These Changes Matter

### Issue 1: Missing str() Conversion

```python
# ❌ WRONG - Type mismatch
TEMPLATE: str = Field(default=UPath("~") / "data")
# Result: UPath object assigned to str field - may cause validation errors

# ✅ CORRECT - Proper type
TEMPLATE: str = Field(default=str(UPath("~") / "data"))
# Result: String "~/data" assigned to str field
```

### Issue 2: Double Braces vs Single Braces

```python
# ❌ WRONG - Double braces produce literal braces in output
template = UPath("~") / "{{ORG}}"
str(template)  # Results in: "~/{ORG}" - wrong!

# ✅ CORRECT - Single braces for template placeholders
template = UPath("~") / "{ORG}"
str(template)  # Results in: "~/{ORG}" - correct!

# Note: Double braces are ONLY needed in f-strings to escape them
f_string_template = f"~{{ORG}}"  # Results in: "~{ORG}" - correct in f-strings
```

## Complete Fixed File Section

Here's the complete fixed section (lines 22-38):

```python
# File and Path Templates
# Legacy commented out
# REPORT_BASE_PATH_TEMPLATE: str = Field(default=f"~{PLATFORM_SLASH}data{PLATFORM_SLASH}mountainash...")

# New UPath-based templates
REPORT_BASE_PATH_TEMPLATE: str = Field(
    default=str(UPath("~") / "data" / "mountainash" / "{ORGANISATION_NAME}" / "{PORTFOLIO_NAME}" / "{RUNDATE}" / "report")
)

RESPONSE_BASE_PATH_TEMPLATE: str = Field(
    default=str(UPath("~") / "data" / "mountainash" / "{ORGANISATION_NAME}" / "{PORTFOLIO_NAME}" / "{RUNDATE}" / "response")
)

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

# Filename templates (no path components, correct as-is)
REPORT_FILENAME_TEMPLATE: str = Field(
    default="{ORGANISATION_NAME}_{PORTFOLIO_NAME}_{RUNDATETIME}_{ORGANISATION_TLA}_{RUNDATE}{BATCH_ITERATION}.xml"
)

RESPONSE_FILENAME_TEMPLATE: str = Field(
    default="{ORGANISATION_NAME}_{PORTFOLIO_NAME}_{RUNDATETIME}_{ORGANISATION_TLA}_{RUNDATE}{BATCH_ITERATION}{BUREAU_RESPONSE_SUFFIX}.xml"
)
```

## Quick Verification

After making these changes, verify with:

```python
from mountainash_acrds_core.settings.acrds_settings_templates import get_acrds_settings_templates

templates = get_acrds_settings_templates()

# Check that templates are strings
assert isinstance(templates.REPORT_BASE_PATH_TEMPLATE, str)

# Check that single braces are preserved
assert "{ORGANISATION_NAME}" in templates.REPORT_BASE_PATH_TEMPLATE
assert "{{ORGANISATION_NAME}}" not in templates.REPORT_BASE_PATH_TEMPLATE

print("✅ All checks passed!")
print(f"Template: {templates.REPORT_BASE_PATH_TEMPLATE}")
```

## Summary

**Two-step fix for each path template:**

1. Wrap the entire UPath expression in `str(...)`
2. Change double braces `{{VAR}}` to single braces `{VAR}`

**Pattern:**
```python
# Before: UPath(...) / "{{VAR}}"
# After:  str(UPath(...) / "{VAR}")
```
