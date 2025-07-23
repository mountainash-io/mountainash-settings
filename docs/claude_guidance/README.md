# Claude Guidance Files for mountainash-settings

This directory contains guidance files for generating high-quality documentation using Claude Code or other LLMs.

## Available Guidance Files

### [Package Overview](PACKAGE_OVERVIEW_GUIDE.md)
Guide for creating detailed package documentation

## Usage Instructions

1. **Review the guidance file** for the documentation type you want to create
2. **Navigate to the package root directory**: `cd /home/nathanielramm/git/mountainash/mountainash-settings`
3. **Run Claude Code** with the guidance file:
   ```bash
   claude-code "Please create [DOCUMENT_TYPE] based on docs/claude_guidance/[GUIDANCE_FILE]"
   ```

## Examples

```bash
# Generate README.md
claude-code "Please create a README.md based on docs/claude_guidance/README_GENERATION_GUIDE.md"

# Generate examples
claude-code "Please create usage examples based on docs/claude_guidance/EXAMPLES_GENERATION_GUIDE.md"

# Generate package overview
claude-code "Please create docs/PACKAGE_OVERVIEW.md based on docs/claude_guidance/PACKAGE_OVERVIEW_GUIDE.md"
```

## Regenerating These Files

To regenerate these guidance files from the central mountainash-docs package:

```bash
# Regenerate all guidance files
mountainash-docs create-claude-guidance --package mountainash-settings

# Regenerate specific guidance types
mountainash-docs create-claude-guidance --package mountainash-settings --types readme,examples
```

---
*Generated on 2025-07-22 16:59:48 by Mountain Ash Documentation Generator*
