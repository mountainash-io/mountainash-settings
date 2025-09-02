# Backward Compatibility and Deprecation Plan

## Overview

This document outlines the strategy for maintaining backward compatibility while transitioning from `MountainAshBaseSettings` to the `@mountainash_settings` decorator approach. The plan ensures zero breaking changes during the transition period and provides a clear migration path.

## Compatibility Commitment

### Current Guarantee (v25.x)
- **Full Backward Compatibility**: All existing `MountainAshBaseSettings` code continues working unchanged
- **API Preservation**: All current APIs, methods, and behaviors remain identical
- **Performance Maintenance**: No performance degradation for existing code
- **SettingsParameters Integration**: Complete compatibility with all existing SettingsParameters usage

### Future Commitment (v26.x and beyond)
- **Long-term Support**: `MountainAshBaseSettings` will be supported for minimum 18 months
- **Bug Fixes**: Critical bugs will be fixed in both implementations
- **Security Updates**: Security issues addressed in both approaches
- **Migration Tools**: Automated migration assistance will be provided

## Compatibility Strategy

### Phase 1: Introduction (v25.5+)
**Duration**: 3-6 months  
**Status**: ✅ Complete

**Deliverables:**
- [x] `@mountainash_settings` decorator fully implemented
- [x] 100% feature parity with `MountainAshBaseSettings`
- [x] Comprehensive test coverage ensuring compatibility
- [x] Documentation and migration guides
- [x] Working examples demonstrating both approaches

**Compatibility Actions:**
- [x] Keep `MountainAshBaseSettings` unchanged
- [x] Export both approaches from main package
- [x] Ensure decorator works identically with all `SettingsParameters` patterns
- [x] Maintain identical caching behavior

### Phase 2: Promotion (v26.0)
**Duration**: 6-12 months  
**Target**: Mid-2025

**Planned Deliverables:**
- [ ] Soft deprecation warnings for `MountainAshBaseSettings` in documentation
- [ ] Performance optimizations for decorator approach
- [ ] Enhanced IDE support and type hints for decorated classes
- [ ] Migration tooling and automated refactoring scripts
- [ ] Community feedback integration

**Compatibility Actions:**
- [ ] `MountainAshBaseSettings` remains fully functional
- [ ] Add soft deprecation notices in documentation (not in code)
- [ ] Promote decorator approach as preferred method in examples
- [ ] Provide migration assistance for major users

### Phase 3: Deprecation (v27.0)  
**Duration**: 6-12 months  
**Target**: Late 2025 / Early 2026

**Planned Deliverables:**
- [ ] Formal deprecation warnings in `MountainAshBaseSettings` constructor
- [ ] Automated migration tools
- [ ] Community outreach and migration support
- [ ] Performance benchmarking and optimization

**Compatibility Actions:**
- [ ] Add `DeprecationWarning` to `MountainAshBaseSettings.__init__()`
- [ ] Maintain full functionality while issuing warnings
- [ ] Provide clear migration instructions in warning messages
- [ ] Offer migration assistance for enterprise users

### Phase 4: Legacy Support (v28.0+)
**Duration**: 6-12 months  
**Target**: Mid-2026 onwards

**Planned Deliverables:**
- [ ] `MountainAshBaseSettings` moved to legacy module
- [ ] Optional legacy support package
- [ ] Complete migration documentation
- [ ] End-of-life timeline communication

**Compatibility Actions:**
- [ ] Move `MountainAshBaseSettings` to `mountainash_settings.legacy`
- [ ] Maintain import compatibility with deprecation warnings
- [ ] Provide separate legacy package for extended support
- [ ] Clear end-of-life communication

### Phase 5: Removal (v29.0+)
**Duration**: Final transition  
**Target**: Late 2026 / Early 2027

**Planned Actions:**
- [ ] Remove `MountainAshBaseSettings` from main package
- [ ] Legacy package available separately for extended support
- [ ] Migration tools remain available
- [ ] Full transition to decorator approach

## Technical Compatibility Details

### API Compatibility Matrix

| Feature | MountainAshBaseSettings | @mountainash_settings | Compatibility |
|---------|-------------------------|----------------------|---------------|
| Direct instantiation | `Settings()` | `Settings()` | ✅ Identical |
| Parameter overrides | `Settings(debug=True)` | `Settings(debug=True)` | ✅ Identical |
| SettingsParameters | `Settings(settings_parameters=p)` | `Settings(settings_parameters=p)` | ✅ Identical |
| get_settings() | `Settings.get_settings()` | `Settings.get_settings()` | ✅ Identical |
| Template resolution | `format_template_from_settings()` | `format_template_from_settings()` | ✅ Identical |
| Multi-format configs | YAML/TOML/JSON support | YAML/TOML/JSON support | ✅ Identical |
| Caching behavior | Smart structural caching | Smart structural caching | ✅ Identical |
| Metadata tracking | All SETTINGS_* attributes | All SETTINGS_* attributes | ✅ Identical |
| Runtime overrides | `apply_runtime_overrides()` | `apply_runtime_overrides()` | ✅ Identical |
| Parameter extraction | `extract_settings_parameters()` | `extract_settings_parameters()` | ✅ Identical |

### Import Compatibility

Both approaches remain available through standard imports:

```python
# Current approach (will remain available)
from mountainash_settings import MountainAshBaseSettings

# New approach (recommended going forward)
from mountainash_settings import mountainash_settings
from pydantic_settings import BaseSettings
```

### Code Compatibility Examples

**Existing code continues working unchanged:**
```python
# This continues working identically
class AppSettings(MountainAshBaseSettings):
    debug: bool = Field(default=False)
    port: int = Field(default=8000)

settings = AppSettings.get_settings(namespace="prod", debug=True)
```

**New code benefits from decorator approach:**
```python
# This provides the same functionality with better ergonomics
@mountainash_settings()
class AppSettings(BaseSettings):
    debug: bool = Field(default=False)
    port: int = Field(default=8000)

settings = AppSettings.get_settings(namespace="prod", debug=True)
```

## Migration Support Tools

### Planned Tooling (v26.0+)

#### 1. Automated Migration Script
```bash
# Command-line tool for automated refactoring
mountainash-migrate --scan src/
mountainash-migrate --convert src/settings.py
mountainash-migrate --validate src/
```

**Features:**
- [ ] Scan codebase for `MountainAshBaseSettings` usage
- [ ] Automated conversion of class definitions
- [ ] Import statement updates
- [ ] Validation of migration success
- [ ] Rollback capabilities

#### 2. Migration Validation Tool
```bash
# Validate that migrated classes work identically
mountainash-validate --old LegacySettings --new NewSettings
```

**Features:**
- [ ] Functional equivalence testing
- [ ] Performance comparison
- [ ] API compatibility verification
- [ ] Edge case testing

#### 3. IDE Integration
**Features:**
- [ ] VSCode extension for migration assistance
- [ ] PyCharm plugin for automated refactoring
- [ ] Linting rules for migration guidance

### Manual Migration Checklist

#### Pre-Migration Assessment
```markdown
## Migration Assessment for [ClassName]

### Usage Analysis
- [ ] Class uses SettingsParameters: YES/NO
- [ ] Class uses template resolution: YES/NO
- [ ] Class uses multi-format configs: YES/NO
- [ ] Class has custom post_init(): YES/NO
- [ ] Class uses caching: YES/NO
- [ ] External dependencies on class: LIST

### Risk Assessment  
- [ ] High usage class: YES/NO
- [ ] Critical production usage: YES/NO
- [ ] Complex inheritance: YES/NO
- [ ] Custom behavior: YES/NO

### Migration Strategy
- [ ] Direct replacement: SUITABLE/NOT SUITABLE
- [ ] Side-by-side migration: SUITABLE/NOT SUITABLE
- [ ] Feature-by-feature: SUITABLE/NOT SUITABLE

### Testing Requirements
- [ ] Unit test coverage: ADEQUATE/NEEDS IMPROVEMENT
- [ ] Integration test coverage: ADEQUATE/NEEDS IMPROVEMENT
- [ ] Performance test needed: YES/NO
```

#### Migration Execution Steps
```markdown
## Migration Steps for [ClassName]

### Preparation
- [ ] Create feature branch: `migration/[ClassName]`
- [ ] Backup existing implementation
- [ ] Review usage patterns across codebase
- [ ] Identify test coverage gaps

### Implementation  
- [ ] Update imports
- [ ] Add decorator with appropriate flags
- [ ] Change base class from MountainAshBaseSettings to BaseSettings
- [ ] Remove custom __init__ if simple
- [ ] Update any custom post_init() calls
- [ ] Verify field definitions unchanged

### Testing
- [ ] Run existing unit tests
- [ ] Run integration tests
- [ ] Performance comparison
- [ ] Manual functionality verification
- [ ] Edge case testing

### Validation
- [ ] Code review with migration checklist
- [ ] Stakeholder approval for critical classes
- [ ] Documentation updates
- [ ] Rollback plan confirmed
```

## Deprecation Communication Plan

### Documentation Strategy

#### v25.5+ (Current)
- [x] Document both approaches as valid
- [x] Show decorator as "new recommended approach"
- [x] Provide clear migration paths
- [x] Maintain examples for both approaches

#### v26.0+ (Promotion Phase)
- [ ] Update main README to feature decorator approach first
- [ ] Add "Legacy" section for MountainAshBaseSettings
- [ ] Include migration benefits prominently
- [ ] Provide migration timeline

#### v27.0+ (Deprecation Phase)  
- [ ] Clear deprecation notices in documentation
- [ ] Migration urgency messaging
- [ ] End-of-life timeline communication
- [ ] Support availability information

### Code Warning Strategy

#### v26.0+ (No Warnings)
```python
# No code warnings yet - only documentation guidance
class AppSettings(MountainAshBaseSettings):
    pass  # Works silently with no warnings
```

#### v27.0+ (Soft Warnings)
```python
# Soft deprecation warning on first usage
import warnings

class MountainAshBaseSettings(BaseSettings):
    def __init__(self, **kwargs):
        warnings.warn(
            "MountainAshBaseSettings is deprecated and will be removed in v29.0. "
            "Please migrate to @mountainash_settings decorator. "
            "See migration guide: https://docs.mountainash-settings.com/migration",
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__(**kwargs)
```

#### v28.0+ (Strong Warnings)
```python
# Stronger warnings with migration assistance
warnings.warn(
    "MountainAshBaseSettings will be removed in v29.0 (6 months). "
    "Migration tool available: pip install mountainash-settings[migration]. "
    "Run: mountainash-migrate --help",
    FutureWarning,
    stacklevel=2
)
```

### Community Communication

#### Channels
- [ ] GitHub Discussions for migration questions
- [ ] Documentation with prominent migration guides
- [ ] Release notes with migration emphasis
- [ ] Community examples and tutorials

#### Timeline Communication
```markdown
## MountainAshBaseSettings Deprecation Timeline

| Version | Timeline | Status | Action Required |
|---------|----------|--------|-----------------|
| v25.5+ | Now | New decorator available | Optional migration |
| v26.0 | Mid-2025 | Soft deprecation in docs | Plan migration |
| v27.0 | Late 2025 | Deprecation warnings | Begin migration |
| v28.0 | Mid-2026 | Legacy module | Complete migration |
| v29.0 | Late 2026 | Removal | Must be migrated |
```

## Support During Transition

### Enterprise Support

#### Dedicated Migration Assistance
- [ ] Migration planning consultations
- [ ] Custom tooling for large codebases  
- [ ] Priority support during transition
- [ ] Extended legacy support contracts

#### SLA Commitments
- [ ] Bug fixes in both implementations
- [ ] Security updates for legacy approach
- [ ] Performance maintenance
- [ ] API stability guarantees

### Community Support

#### Resources
- [ ] Migration guides and tutorials
- [ ] Community Q&A sessions
- [ ] Example repositories
- [ ] Best practices documentation

#### Tooling
- [ ] Open-source migration tools
- [ ] Validation utilities
- [ ] Performance comparison tools
- [ ] Community-contributed extensions

## Risk Mitigation

### Breaking Change Prevention

#### Compatibility Testing
```python
# Automated compatibility tests run in CI
def test_migration_compatibility():
    """Ensure migrated classes behave identically."""
    
    # Test with same parameters
    legacy = LegacySettings.get_settings(namespace="test", debug=True)
    decorator = DecoratorSettings.get_settings(namespace="test", debug=True)
    
    # Verify identical behavior
    assert legacy.debug == decorator.debug
    assert type(legacy.debug) == type(decorator.debug)
    assert legacy.extract_settings_parameters().namespace == decorator.extract_settings_parameters().namespace
```

#### Version Compatibility Matrix
| Feature | v25.x | v26.x | v27.x | v28.x | v29.x |
|---------|-------|-------|-------|-------|-------|
| MountainAshBaseSettings | ✅ Full | ✅ Full | ⚠️ Deprecated | 🏗️ Legacy | ❌ Removed |
| @mountainash_settings | ✅ Full | ✅ Enhanced | ✅ Preferred | ✅ Standard | ✅ Only |
| Migration Tools | ❌ None | 🏗️ Basic | ✅ Full | ✅ Advanced | ✅ Maintained |
| Legacy Support | N/A | N/A | ✅ Full | ✅ Separate | 💰 Commercial |

### Rollback Strategies

#### Per-Class Rollback
```python
# Easy rollback by commenting decorator
# @mountainash_settings()  # Comment out
class AppSettings(MountainAshBaseSettings):  # Switch back
    pass
```

#### Feature Flag Rollback
```python
# Environment-based rollback capability
USE_DECORATOR = os.getenv("USE_DECORATOR_SETTINGS", "true").lower() == "true"

if USE_DECORATOR:
    @mountainash_settings()
    class AppSettings(BaseSettings):
        pass
else:
    class AppSettings(MountainAshBaseSettings):
        pass
```

#### Package-Level Rollback
```bash
# Rollback to earlier package version if needed
pip install mountainash-settings==25.12.0  # Last pre-deprecation version
```

## Success Metrics

### Migration Tracking

#### Quantitative Metrics
- [ ] % of classes migrated to decorator approach
- [ ] Reduction in MountainAshBaseSettings usage
- [ ] Migration tool usage statistics
- [ ] Community feedback scores

#### Qualitative Metrics  
- [ ] Developer experience improvements
- [ ] Reduced support requests
- [ ] Community adoption feedback
- [ ] Performance improvements achieved

### Compatibility Monitoring

#### Automated Monitoring
- [ ] CI/CD tests ensuring both approaches work identically
- [ ] Performance regression detection
- [ ] API compatibility validation
- [ ] Breaking change detection

#### Community Feedback
- [ ] Migration success stories
- [ ] Issue tracking and resolution
- [ ] Documentation effectiveness
- [ ] Tooling satisfaction surveys

This backward compatibility plan ensures a smooth, low-risk transition from `MountainAshBaseSettings` to the decorator approach while maintaining full support for existing code throughout the transition period.