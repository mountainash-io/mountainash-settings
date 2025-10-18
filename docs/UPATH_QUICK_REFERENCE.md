# UPath Quick Reference for Path Templating

## The Problem You're Solving

**OLD (BROKEN):**
```python
# Line 26 in acrds_settings_templates.py - SYNTAX ERROR
REPORT_BASE_PATH_TEMPLATE: str = Field(
    default= UPath("~" \ "data" \ "mountainash" \ "{{ORGANISATION_NAME}}" \ "{{PORTFOLIO_NAME}}" \ "{{RUNDATE}}" \ "report")
)
```

**Why it's broken:**
- `\` is NOT a path joining operator in Python
- You're thinking of using `/` which is UPath's path joining operator

## The Solution (3 Variations)

### Option 1: Inline (Simple)

```python
from upath import UPath
from pydantic import Field

REPORT_BASE_PATH_TEMPLATE: str = Field(
    default=str(UPath("~") / "data" / "mountainash" / "{ORGANISATION_NAME}" / "{PORTFOLIO_NAME}" / "{RUNDATE}" / "report")
)
```

### Option 2: Multi-line (More Readable)

```python
REPORT_BASE_PATH_TEMPLATE: str = Field(
    default=str(
        UPath("~") / "data" / "mountainash" /
        "{ORGANISATION_NAME}" / "{PORTFOLIO_NAME}" / "{RUNDATE}" / "report"
    )
)
```

### Option 3: Helper Function (Best for Many Paths)

```python
def build_path_template(*parts: str) -> str:
    path = UPath(parts[0])
    for part in parts[1:]:
        path = path / part
    return str(path)

REPORT_BASE_PATH_TEMPLATE: str = Field(
    default=build_path_template("~", "data", "mountainash", "{ORGANISATION_NAME}", "{PORTFOLIO_NAME}", "{RUNDATE}", "report")
)
```

## Cheat Sheet

| Task | OLD (Don't Use) | NEW (Use This) |
|------|----------------|----------------|
| Join paths | `f"~{PLATFORM_SLASH}data"` | `str(UPath("~") / "data")` |
| With template | `f"~{PLATFORM_SLASH}{{ORG}}"` | `str(UPath("~") / "{ORG}")` |
| Derived path | `f"{{BASE}}{PLATFORM_SLASH}sub"` | `str(UPath("{BASE}") / "sub")` |
| Wrong operator | `UPath("~" \ "data")` ❌ | `UPath("~") / "data"` ✅ |

## Common Mistakes

### Mistake 1: Using backslash `\`
```python
# ❌ WRONG - Syntax error
UPath("~" \ "data")

# ✅ CORRECT - Use forward slash
UPath("~") / "data"
```

### Mistake 2: Forgetting to convert to string
```python
# ❌ WRONG - Field expects str, not UPath
TEMPLATE: str = Field(default=UPath("~") / "data")

# ✅ CORRECT - Convert to string
TEMPLATE: str = Field(default=str(UPath("~") / "data"))
```

### Mistake 3: Double braces in non-f-strings
```python
# ❌ WRONG - Double braces only needed in f-strings
TEMPLATE = str(UPath("~") / "{{ORG}}")  # Results in literal {{ORG}}

# ✅ CORRECT - Single braces for templates
TEMPLATE = str(UPath("~") / "{ORG}")
```

## How Template Resolution Works

```python
# 1. Define template (at class level)
DATA_PATH_TEMPLATE: str = Field(
    default=str(UPath("~") / "data" / "{ORG_NAME}")
)

# 2. Define resolved field (starts as None)
DATA_PATH: str = Field(default=None)

# 3. Resolve in post_init()
def post_init(self, reinitialise: bool = False):
    super().post_init(reinitialise=reinitialise)
    self.DATA_PATH = self.init_setting_from_template(
        template_str=self.DATA_PATH_TEMPLATE,
        current_value=self.DATA_PATH,
        reinitialise=reinitialise
    )

# Result: If ORG_NAME="acme"
# DATA_PATH_TEMPLATE = "~/data/{ORG_NAME}"
# DATA_PATH          = "~/data/acme"
```

## Resolution Order Matters

```python
# ✅ CORRECT - Base paths resolved first
def post_init(self, reinitialise: bool = False):
    super().post_init(reinitialise=reinitialise)

    # 1. Resolve base paths
    self.BASE_PATH = self.init_setting_from_template(
        template_str=self.BASE_PATH_TEMPLATE,
        current_value=self.BASE_PATH,
        reinitialise=reinitialise
    )

    # 2. Then resolve derived paths (that reference BASE_PATH)
    self.DERIVED_PATH = self.init_setting_from_template(
        template_str=self.DERIVED_PATH_TEMPLATE,  # Contains {BASE_PATH}
        current_value=self.DERIVED_PATH,
        reinitialise=reinitialise
    )
```

## Converting from PLATFORM_SLASH

### Step 1: Remove import
```python
# ❌ REMOVE THIS
from mountainash_utils_os import get_platform_slash
PLATFORM_SLASH = get_platform_slash()

# ✅ ADD THIS
from upath import UPath
```

### Step 2: Convert each path template
```python
# ❌ OLD
REPORT_BASE_PATH_TEMPLATE: str = Field(
    default=f"~{PLATFORM_SLASH}data{PLATFORM_SLASH}mountainash{PLATFORM_SLASH}{{ORGANISATION_NAME}}{PLATFORM_SLASH}{{PORTFOLIO_NAME}}{PLATFORM_SLASH}{{RUNDATE}}{PLATFORM_SLASH}report"
)

# ✅ NEW
REPORT_BASE_PATH_TEMPLATE: str = Field(
    default=str(UPath("~") / "data" / "mountainash" / "{ORGANISATION_NAME}" / "{PORTFOLIO_NAME}" / "{RUNDATE}" / "report")
)
```

### Step 3: Convert derived templates
```python
# ❌ OLD
REPORT_DATA_PATH_TEMPLATE: str = Field(
    default=f"{{REPORT_BASE_PATH}}{PLATFORM_SLASH}report_data"
)

# ✅ NEW
REPORT_DATA_PATH_TEMPLATE: str = Field(
    default=str(UPath("{REPORT_BASE_PATH}") / "report_data")
)
```

## Why This Is Better

| Aspect | PLATFORM_SLASH | UPath |
|--------|---------------|-------|
| **Readability** | `f"~{PS}data{PS}{{ORG}}"` 😵 | `str(UPath("~") / "data" / "{ORG}")` ✨ |
| **Maintainability** | Hard to modify | Easy to change |
| **Cross-platform** | Manual platform detection | Automatic |
| **Error-prone** | Easy to miss a slash | Type-safe |
| **Cloud paths** | Doesn't work | Works (s3://, gs://) |
| **Code cleanliness** | Ugly concatenation | Clean operators |

## Testing Your Changes

```python
# Test template creation
settings = AcrdsSettingsTemplates()
print(settings.REPORT_BASE_PATH_TEMPLATE)
# Linux: ~/data/mountainash/{ORGANISATION_NAME}/{PORTFOLIO_NAME}/{RUNDATE}/report
# Windows: ~\data\mountainash\{ORGANISATION_NAME}\{PORTFOLIO_NAME}\{RUNDATE}\report

# Test template resolution (assuming you have a settings class that uses these)
app_settings = YourAppSettings(ORGANISATION_NAME="acme", PORTFOLIO_NAME="prod", RUNDATE="20250111")
print(app_settings.REPORT_BASE_PATH)
# Linux: ~/data/mountainash/acme/prod/20250111/report
# Windows: ~\data\mountainash\acme\prod\20250111\report
```

## Complete Examples

See these files for full working examples:
- `examples/path_templating_with_upath.py` - Comprehensive examples with 4 patterns
- `docs/PATH_TEMPLATING_FIX_GUIDE.md` - Detailed migration guide
- `CLAUDE.md` - Project-specific guidance

## One-Liner Reminder

**Use `/` to join UPath components, then convert to string for Field defaults.**

```python
# This is the pattern:
Field(default=str(UPath("part1") / "part2" / "{TEMPLATE_VAR}"))
```
