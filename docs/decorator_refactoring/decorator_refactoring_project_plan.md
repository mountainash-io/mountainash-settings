# @mountainash_settings Decorator Implementation Project Plan

## Executive Summary

Create a `@mountainash_settings` decorator that makes Pydantic classes feel like standard `BaseSettings` while preserving all existing mountainash-settings infrastructure (SettingsParameters, caching, templates, multi-format configs).

## Core Architecture

### The Decorator Pattern
```python
@mountainash_settings(cache=True, templates=True, multi_format=True)
class AppSettings(BaseSettings):  # Standard Pydantic class
    debug: bool = Field(default=False)
    log_path: str = Field(default="logs/{RUNDATE}/app.log")
```

**Key Principle**: Enhance Pydantic classes to work with SettingsParameters infrastructure, don't replace it.

## Critical Requirements

### 1. Preserve SettingsParameters API
All existing usage must work identically:
```python
# Must continue working exactly as before
settings_params = SettingsParameters.create(...)
settings = AppSettings.get_settings(settings_parameters=settings_params)
```

### 2. Maintain JIT Security Pattern
```python
# Safe: Parameters passed around, settings loaded JIT
class Service:
    def __init__(self, settings_params: SettingsParameters):
        self.settings_params = settings_params  # No secrets stored
    
    def method(self):
        settings = AppSettings.get_settings(settings_parameters=self.settings_params)
        # Use settings, secrets go out of scope
```

### 3. Preserve Smart Caching
- Structural parameters (namespace, config_files) affect cache
- Runtime parameters (kwargs) don't affect cache
- Runtime overrides applied to cached instances

## Implementation Plan

### Phase 1: Core Decorator (Week 1)
```python
def mountainash_settings(
    cache: bool = True,
    templates: bool = True, 
    multi_format: bool = True,
    namespace: Optional[str] = None
):
    def decorator(cls):
        # Enhance __init__ to work with SettingsParameters
        # Inject get_settings() classmethod
        # Add template resolution if enabled
        return enhanced_class
    return decorator
```

**Deliverables**:
- [ ] Basic decorator function
- [ ] Enhanced `__init__` method with SettingsParameters integration
- [ ] Injected `get_settings()` classmethod that delegates to existing infrastructure
- [ ] Feature flag introspection (`_mountainash_cache_enabled`, etc.)

### Phase 2: Feature Integration (Week 2)
**Deliverables**:
- [ ] Template resolution system integration
- [ ] Multi-format configuration support
- [ ] SettingsParameters processing pipeline integration
- [ ] Runtime override behavior preservation

### Phase 3: Testing & Validation (Week 3)
**Deliverables**:
- [ ] Unit tests for decorator functionality
- [ ] Integration tests with SettingsParameters
- [ ] Compatibility tests with existing usage patterns
- [ ] Performance benchmarks vs MountainAshBaseSettings

### Phase 4: Documentation & Migration (Week 4)
**Deliverables**:
- [ ] Usage documentation and examples
- [ ] Migration guide from MountainAshBaseSettings
- [ ] Backward compatibility strategy
- [ ] Deprecation timeline

## Key Implementation Details

### Enhanced __init__ Method
```python
def enhanced_init(self, 
                 settings_parameters: Optional[SettingsParameters] = None,
                 config_files: Optional[List[str]] = None,
                 namespace: Optional[str] = None,
                 **kwargs):
    # 1. Create/use SettingsParameters
    # 2. Check cache if enabled
    # 3. Process configuration through existing pipeline
    # 4. Call original Pydantic __init__
    # 5. Apply template resolution
    # 6. Cache instance
```

### Injected get_settings Method
```python
@classmethod
def get_settings(cls, settings_parameters=None, **kwargs):
    # Delegate to existing mountainash-settings infrastructure
    from mountainash_settings import get_settings
    return get_settings(settings_parameters=..., settings_class=cls, ...)
```

## Success Criteria

### Functional Requirements
- [ ] All existing SettingsParameters usage works identically
- [ ] Template resolution works with decorator-enhanced classes
- [ ] Multi-format configuration loading preserved
- [ ] Smart caching behavior maintained
- [ ] Runtime override system functions correctly

### Non-Functional Requirements
- [ ] Performance equivalent to MountainAshBaseSettings
- [ ] Memory usage comparable or better
- [ ] Zero secret leakage in logs/debug output
- [ ] Serialization safety maintained

### User Experience Requirements
- [ ] Classes look like standard Pydantic BaseSettings
- [ ] No learning curve for existing Pydantic users
- [ ] Optional features can be disabled for pure Pydantic behavior
- [ ] Clear error messages and validation

## Risk Mitigation

### Technical Risks
- **SettingsParameters compatibility**: Extensive integration testing
- **Performance degradation**: Benchmark against current implementation
- **Feature regressions**: Comprehensive test coverage

### Migration Risks
- **Backward compatibility**: Maintain MountainAshBaseSettings during transition
- **User adoption**: Provide clear migration path and tooling
- **Production stability**: Gradual rollout with feature flags

## Definition of Done

A decorated class must:
1. Work identically to MountainAshBaseSettings for all SettingsParameters usage
2. Feel like standard Pydantic BaseSettings for direct usage
3. Preserve all security, performance, and reliability characteristics
4. Pass all existing tests plus new decorator-specific tests
5. Have complete documentation and migration guidance

## Timeline: 4 Weeks Total

This focused approach preserves the sophisticated SettingsParameters infrastructure while giving users the familiar Pydantic experience they expect.