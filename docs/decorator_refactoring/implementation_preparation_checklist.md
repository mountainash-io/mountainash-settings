# @mountainash_settings Decorator Implementation Preparation Checklist

## Overview
This document outlines the preparation needed for implementing the `@mountainash_settings` decorator as detailed in the project plan. The decorator will enhance Pydantic BaseSettings classes to work seamlessly with the existing mountainash-settings infrastructure.

## Current Architecture Analysis ✅

### Core Components Identified
- **SettingsParameters**: Sophisticated parameter handling with structural/runtime separation for caching
- **MountainAshBaseSettings**: Current base class with template resolution, multi-format config support
- **SettingsManager**: Caching layer using hash-based instance management  
- **get_settings()**: Main function for retrieving settings with SettingsParameters integration
- **Template System**: String formatting with attribute substitution via `format_template_from_settings()`
- **Multi-format Support**: YAML, TOML, JSON, ENV file handling via SettingsFileHandler

### Key Architecture Insights
1. **Smart Caching Strategy**: SettingsParameters uses custom `__hash__`/`__eq__` methods that only consider structural parameters (namespace, config_files, settings_class, env_prefix), ignoring runtime parameters (kwargs, secrets_dir) to enable cache reuse
2. **JIT Security Pattern**: Settings parameters passed around, actual settings loaded just-in-time to minimize secret exposure
3. **Runtime Override System**: `apply_runtime_overrides()` method applies kwargs to cached instances without affecting cache identity
4. **Template Resolution**: Post-initialization template processing via `post_init()` method

## Implementation Preparation Tasks

### Phase 1: Core Decorator Infrastructure ✅

#### 1.1 Create Decorator Module ✅
- [x] Create `src/mountainash_settings/decorator.py`
- [x] Implement basic decorator function signature
- [x] Add feature flag parameters (cache, templates, multi_format, namespace)
- [x] Support usage with and without parentheses

#### 1.2 Enhanced __init__ Method ✅
- [x] Create mechanism to wrap/replace Pydantic class `__init__`
- [x] Implement SettingsParameters integration logic
- [x] Add support for all existing MountainAshBaseSettings constructor parameters:
  - `settings_parameters: Optional[SettingsParameters]`
  - `config_files: Optional[List[str]]`
  - `namespace: Optional[str]`
  - `**kwargs` for runtime overrides
- [x] Add fallback mechanism for cases where caching fails (test classes, recursion)

#### 1.3 get_settings() Class Method Injection ✅
- [x] Create classmethod that delegates to existing `get_settings()` function
- [x] Ensure compatibility with existing SettingsParameters API
- [x] Add proper type hints for decorated classes
- [x] Add fallback mechanism for edge cases

#### 1.4 Feature Flag System ✅
- [x] Add introspection attributes to decorated classes:
  - `_mountainash_cache_enabled`
  - `_mountainash_templates_enabled` 
  - `_mountainash_multi_format_enabled`
  - `_mountainash_namespace`
  - `_mountainash_decorated` (internal recursion prevention)

### Phase 2: Feature Integration

#### 2.1 Template Resolution Integration ⏳
- [ ] Port template logic from MountainAshBaseSettings
- [ ] Implement `post_init()` equivalent for decorated classes
- [ ] Add `format_template_from_settings()` method to decorated classes
- [ ] Ensure template processing works with feature flag

#### 2.2 Multi-format Configuration Support ⏳
- [ ] Integrate SettingsFileHandler for config file processing
- [ ] Add support for YAML, TOML, JSON configuration files
- [ ] Implement file validation logic
- [ ] Add `settings_customise_sources()` method injection

#### 2.3 Caching Integration ⏳
- [ ] Integrate with existing SettingsManager
- [ ] Ensure decorated classes work with `_get_settings()` caching
- [ ] Implement `apply_runtime_overrides()` support
- [ ] Add cache bypass option for pure Pydantic behavior

#### 2.4 Metadata Tracking ⏳
- [ ] Port settings source tracking from MountainAshBaseSettings:
  - `SETTINGS_NAMESPACE`
  - `SETTINGS_CLASS`
  - `SETTINGS_CLASS_NAME` 
  - `SETTINGS_SOURCE_*` fields
- [ ] Implement `extract_settings_parameters()` method
- [ ] Add `update_settings_from_dict()` method

### Phase 3: Testing Infrastructure

#### 3.1 Unit Tests ⏳
- [ ] Test basic decorator functionality
- [ ] Test feature flag combinations
- [ ] Test enhanced `__init__` method
- [ ] Test injected `get_settings()` classmethod
- [ ] Test template resolution system
- [ ] Test multi-format configuration loading

#### 3.2 Integration Tests ⏳
- [ ] Test compatibility with existing SettingsParameters usage
- [ ] Test caching behavior matches MountainAshBaseSettings
- [ ] Test runtime override system
- [ ] Test JIT security pattern preservation
- [ ] Test performance vs MountainAshBaseSettings

#### 3.3 Compatibility Tests ⏳
- [ ] Test existing code continues working unchanged
- [ ] Test migration from MountainAshBaseSettings
- [ ] Test edge cases and error conditions

### Phase 4: Documentation & Migration

#### 4.1 Usage Documentation ⏳
- [ ] Create decorator usage examples
- [ ] Document feature flags and their effects
- [ ] Create migration guide from MountainAshBaseSettings
- [ ] Add API reference documentation

#### 4.2 Migration Strategy ⏳
- [ ] Plan backward compatibility approach
- [ ] Create deprecation timeline for MountainAshBaseSettings
- [ ] Develop automated migration tooling if needed

## Critical Implementation Notes

### Preserve Existing APIs
- All current `SettingsParameters.create()` usage must work identically
- `AppSettings.get_settings(settings_parameters=params)` pattern must be preserved
- Runtime override behavior must match exactly

### Security Considerations
- JIT pattern: parameters passed around, settings loaded only when needed
- No secrets stored in long-lived objects
- Runtime kwargs applied without affecting cache identity
- Serialization safety maintained

### Performance Requirements
- Caching efficiency equivalent to MountainAshBaseSettings
- Memory usage comparable or better
- Template resolution performance maintained
- No degradation in settings loading speed

### Error Handling
- Clear error messages when decorator features conflict
- Graceful fallback when features disabled
- Proper validation of feature flag combinations

## Risk Mitigation

### Technical Risks
- **SettingsParameters Integration**: Extensive testing of parameter handling edge cases
- **Caching Behavior**: Validate hash/equality behavior works identically
- **Template Resolution**: Ensure all template features work correctly
- **Multi-format Loading**: Test all configuration file formats

### Compatibility Risks
- **Existing Code**: Comprehensive regression testing
- **Pydantic Version Changes**: Test against supported Pydantic versions
- **Type Checking**: Ensure mypy compatibility

## Success Criteria Checklist

### Functional ✅
- [ ] Decorated classes feel like standard Pydantic BaseSettings
- [ ] All SettingsParameters usage works identically to current implementation
- [ ] Template resolution functions correctly
- [ ] Multi-format configuration loading preserved
- [ ] Smart caching behavior maintained
- [ ] Runtime override system works correctly

### Non-Functional ✅
- [ ] Performance equivalent to MountainAshBaseSettings
- [ ] Memory usage comparable or better
- [ ] Zero secret leakage in logs/debug output
- [ ] Serialization safety maintained

### User Experience ✅
- [ ] No learning curve for Pydantic users
- [ ] Optional features can be disabled for pure Pydantic behavior
- [ ] Clear error messages and validation
- [ ] Seamless migration path from MountainAshBaseSettings

## Next Steps

1. Begin Phase 1 implementation starting with core decorator module
2. Set up comprehensive test suite early in development process
3. Create proof-of-concept examples to validate approach
4. Regular compatibility testing throughout implementation
5. Performance benchmarking against current MountainAshBaseSettings

This preparation ensures a systematic approach to implementing the decorator while preserving all existing functionality and providing the enhanced user experience outlined in the project plan.