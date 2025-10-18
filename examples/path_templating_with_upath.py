"""
Example: Path Templating with UPath

This example demonstrates how to use UPath for cross-platform path templating
without needing PLATFORM_SLASH or other platform-specific hacks.

Key Principles:
1. Use UPath's / operator to construct paths cross-platform
2. Convert to string for template storage (allows {placeholder} formatting)
3. Use MountainAshBaseSettings.init_setting_from_template() for resolution
4. Convert back to UPath after template formatting if needed
"""

from pydantic import Field
from upath import UPath
from mountainash_settings import MountainAshBaseSettings


# Example 1: Basic Path Templates
# ================================

class PathTemplateSettings(MountainAshBaseSettings):
    """Example showing path template patterns."""

    # Organization info (used in templates)
    ORGANISATION_NAME: str = Field(default="acme_corp")
    PORTFOLIO_NAME: str = Field(default="production")
    RUNDATE: str = Field(default="20250111")

    # Path templates using UPath - CORRECT PATTERN
    # Build the path with UPath's / operator, then convert to string for template storage
    REPORT_BASE_PATH_TEMPLATE: str = Field(
        default=str(
            UPath("~") / "data" / "mountainash" / "{ORGANISATION_NAME}" / "{PORTFOLIO_NAME}" / "{RUNDATE}" / "report"
        )
    )

    RESPONSE_BASE_PATH_TEMPLATE: str = Field(
        default=str(
            UPath("~") / "data" / "mountainash" / "{ORGANISATION_NAME}" / "{PORTFOLIO_NAME}" / "{RUNDATE}" / "response"
        )
    )

    # Resolved paths (set during post_init)
    REPORT_BASE_PATH: str = Field(default=None)
    RESPONSE_BASE_PATH: str = Field(default=None)

    # Derived path templates (reference other templates)
    REPORT_DATA_PATH_TEMPLATE: str = Field(
        default=str(UPath("{REPORT_BASE_PATH}") / "report_data")
    )

    RESPONSE_DATA_PATH_TEMPLATE: str = Field(
        default=str(UPath("{RESPONSE_BASE_PATH}") / "response_data")
    )

    # Resolved derived paths
    REPORT_DATA_PATH: str = Field(default=None)
    RESPONSE_DATA_PATH: str = Field(default=None)

    def post_init(self, reinitialise: bool = False):
        """Resolve all path templates."""
        super().post_init(reinitialise=reinitialise)

        # Resolve base paths
        self.REPORT_BASE_PATH = self.init_setting_from_template(
            template_str=self.REPORT_BASE_PATH_TEMPLATE,
            current_value=self.REPORT_BASE_PATH,
            reinitialise=reinitialise
        )

        self.RESPONSE_BASE_PATH = self.init_setting_from_template(
            template_str=self.RESPONSE_BASE_PATH_TEMPLATE,
            current_value=self.RESPONSE_BASE_PATH,
            reinitialise=reinitialise
        )

        # Resolve derived paths (depend on base paths)
        self.REPORT_DATA_PATH = self.init_setting_from_template(
            template_str=self.REPORT_DATA_PATH_TEMPLATE,
            current_value=self.REPORT_DATA_PATH,
            reinitialise=reinitialise
        )

        self.RESPONSE_DATA_PATH = self.init_setting_from_template(
            template_str=self.RESPONSE_DATA_PATH_TEMPLATE,
            current_value=self.RESPONSE_DATA_PATH,
            reinitialise=reinitialise
        )


# Example 2: Helper Function Pattern
# ===================================

def build_path_template(*parts: str) -> str:
    """
    Helper function to build path templates using UPath.

    Args:
        *parts: Path components (can include template placeholders)

    Returns:
        String path template suitable for Field(default=...)

    Example:
        >>> build_path_template("~", "data", "{ORG}", "{DATE}", "reports")
        '~/data/{ORG}/{DATE}/reports'
    """
    path = UPath(parts[0])
    for part in parts[1:]:
        path = path / part
    return str(path)


class PathTemplateSettingsWithHelper(MountainAshBaseSettings):
    """Example using helper function for cleaner code."""

    ORGANISATION_NAME: str = Field(default="acme_corp")
    PORTFOLIO_NAME: str = Field(default="production")
    RUNDATE: str = Field(default="20250111")

    # Cleaner syntax with helper
    REPORT_BASE_PATH_TEMPLATE: str = Field(
        default=build_path_template(
            "~", "data", "mountainash",
            "{ORGANISATION_NAME}", "{PORTFOLIO_NAME}", "{RUNDATE}", "report"
        )
    )

    REPORT_BASE_PATH: str = Field(default=None)

    def post_init(self, reinitialise: bool = False):
        super().post_init(reinitialise=reinitialise)
        self.REPORT_BASE_PATH = self.init_setting_from_template(
            template_str=self.REPORT_BASE_PATH_TEMPLATE,
            current_value=self.REPORT_BASE_PATH,
            reinitialise=reinitialise
        )


# Example 3: Working with UPath Objects After Resolution
# =======================================================

class PathTemplateSettingsWithUPathObjects(MountainAshBaseSettings):
    """Example showing how to work with UPath objects after template resolution."""

    ORGANISATION_NAME: str = Field(default="acme_corp")
    RUNDATE: str = Field(default="20250111")

    DATA_PATH_TEMPLATE: str = Field(
        default=str(UPath("~") / "data" / "{ORGANISATION_NAME}" / "{RUNDATE}")
    )

    DATA_PATH: str = Field(default=None)

    def post_init(self, reinitialise: bool = False):
        super().post_init(reinitialise=reinitialise)
        self.DATA_PATH = self.init_setting_from_template(
            template_str=self.DATA_PATH_TEMPLATE,
            current_value=self.DATA_PATH,
            reinitialise=reinitialise
        )

    def get_data_path_as_upath(self) -> UPath:
        """
        Get the resolved data path as a UPath object.

        Returns:
            UPath object with expanduser() applied
        """
        return UPath(self.DATA_PATH).expanduser()

    def ensure_data_path_exists(self) -> None:
        """Ensure the data path exists, creating it if necessary."""
        path = self.get_data_path_as_upath()
        path.mkdir(parents=True, exist_ok=True)


# Example 4: Migration from PLATFORM_SLASH
# =========================================

class LegacySettings(MountainAshBaseSettings):
    """OLD WAY - Using PLATFORM_SLASH (DO NOT USE)"""

    from mountainash_utils_os import get_platform_slash
    PLATFORM_SLASH: str = Field(default=get_platform_slash())

    ORG_NAME: str = Field(default="acme")

    # OLD: Brittle, platform-dependent, hard to read
    LEGACY_PATH_TEMPLATE: str = Field(
        default=f"~{{PLATFORM_SLASH}}data{{PLATFORM_SLASH}}{{ORG_NAME}}{{PLATFORM_SLASH}}reports"
    )


class ModernSettings(MountainAshBaseSettings):
    """NEW WAY - Using UPath (USE THIS)"""

    ORG_NAME: str = Field(default="acme")

    # NEW: Clean, cross-platform, readable
    MODERN_PATH_TEMPLATE: str = Field(
        default=str(UPath("~") / "data" / "{ORG_NAME}" / "reports")
    )


# Example Usage
# =============

if __name__ == "__main__":
    print("Example 1: Basic Path Templates")
    print("=" * 50)
    settings1 = PathTemplateSettings()
    print(f"REPORT_BASE_PATH_TEMPLATE: {settings1.REPORT_BASE_PATH_TEMPLATE}")
    print(f"REPORT_BASE_PATH (resolved): {settings1.REPORT_BASE_PATH}")
    print(f"REPORT_DATA_PATH (resolved): {settings1.REPORT_DATA_PATH}")

    print("\n\nExample 2: Helper Function Pattern")
    print("=" * 50)
    settings2 = PathTemplateSettingsWithHelper()
    print(f"REPORT_BASE_PATH_TEMPLATE: {settings2.REPORT_BASE_PATH_TEMPLATE}")
    print(f"REPORT_BASE_PATH (resolved): {settings2.REPORT_BASE_PATH}")

    print("\n\nExample 3: UPath Objects After Resolution")
    print("=" * 50)
    settings3 = PathTemplateSettingsWithUPathObjects()
    print(f"DATA_PATH_TEMPLATE: {settings3.DATA_PATH_TEMPLATE}")
    print(f"DATA_PATH (resolved): {settings3.DATA_PATH}")
    print(f"As UPath object: {settings3.get_data_path_as_upath()}")

    print("\n\nExample 4: Migration Comparison")
    print("=" * 50)
    legacy = LegacySettings()
    modern = ModernSettings()
    print(f"Legacy template: {legacy.LEGACY_PATH_TEMPLATE}")
    print(f"Modern template: {modern.MODERN_PATH_TEMPLATE}")
    print("\nNotice: Modern version is cleaner and cross-platform!")


# Common Patterns and Best Practices
# ===================================

"""
BEST PRACTICES:

1. ALWAYS use UPath's / operator for path construction
   ✓ GOOD: str(UPath("~") / "data" / "{ORG}")
   ✗ BAD:  f"~{PLATFORM_SLASH}data{PLATFORM_SLASH}{{ORG}}"

2. Convert to string for template storage
   ✓ GOOD: Field(default=str(UPath(...)))
   ✗ BAD:  Field(default=UPath(...))  # Can't format UPath directly

3. Use double braces for template placeholders
   ✓ GOOD: "{ORGANISATION_NAME}"
   ✗ BAD:  "{{ORGANISATION_NAME}}"  # Only use double braces in f-strings

4. Resolve templates in post_init()
   ✓ GOOD: Use init_setting_from_template() in post_init()
   ✗ BAD:  Try to resolve during field definition

5. Order matters for dependent templates
   ✓ GOOD: Resolve base paths before derived paths
   ✗ BAD:  Reference unresolved template values

6. Convert back to UPath for path operations
   ✓ GOOD: UPath(resolved_path).mkdir(parents=True)
   ✗ BAD:  os.makedirs(resolved_path)  # Use UPath for consistency


MIGRATION CHECKLIST:

□ Replace PLATFORM_SLASH imports with UPath
□ Convert f"~{PLATFORM_SLASH}..." to str(UPath("~") / ...)
□ Remove get_platform_slash() dependency
□ Update template resolution order in post_init()
□ Test on both Windows and POSIX systems
□ Update tests to verify cross-platform behavior
"""
