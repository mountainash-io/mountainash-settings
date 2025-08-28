# Migration Guide: From MountainAshBaseSettings to @mountainash_settings

## Overview

This guide provides a step-by-step approach for migrating from the current `MountainAshBaseSettings` inheritance model to the new `@mountainash_settings` decorator approach. The migration preserves all functionality while making classes feel like standard Pydantic.

## Migration Benefits

- **Familiar API**: Classes look and feel like standard Pydantic BaseSettings
- **SettingsParameters Preservation**: All existing SettingsParameters usage continues to work identically
- **Infrastructure Compatibility**: Full integration with SettingsManager and caching system
- **No Functionality Loss**: All current features are preserved through delegation to existing infrastructure
- **Incremental Migration**: Can migrate class by class without breaking existing usage
- **Backward Compatibility**: Existing code continues to work during transition

## Before and After Comparison

### Current Approach (MountainAshBaseSettings)
```python
from mountainash_settings import MountainAshBaseSettings
from pydantic import Field
from typing import Optional, List
from upath import UPath

class AppSettings(MountainAshBaseSettings):
    def __init__(self,
                 config_files: Optional[List[str|UPath]] = None,
                 settings_parameters: Optional[SettingsParameters] = None,
                 **kwargs) -> None:
        super().__init__(
            config_files=config_files,
            settings_parameters=settings_parameters,
            **kwargs
        )
    
    # App Settings
    app_name: str = Field(default="MyApp")
    debug: bool = Field(default=False)
    database_url: str = Field(default="sqlite:///app.db")
    log_path: str = Field(default="logs/{RUNDATE}/app.log")

# Usage
settings = AppSettings.get_settings(
    namespace="production",
    config_files=["config.yaml"]
)
```

### New Approach (@mountainash_settings)
```python
from pydantic_settings import BaseSettings
from pydantic import Field
from mountainash_settings import mountainash_settings

@mountainash_settings(cache=True, templates=True, namespace="production")
class AppSettings(BaseSettings):
    # No custom __init__ needed - pure Pydantic class
    app_name: str = Field(default="MyApp")
    debug: bool = Field(default=False)
    database_url: str = Field(default="sqlite:///app.db")
    log_path: str = Field(default="logs/{RUNDATE}/app.log")

# Usage - exactly the same API with SettingsParameters
settings_params = SettingsParameters.create(
    settings_class=AppSettings,
    namespace="production",
    config_files=["config.yaml"]
)
settings = AppSettings.get_settings(settings_parameters=settings_params)

# Individual parameters (delegates to SettingsParameters internally)
settings = AppSettings.get_settings(
    settings_namespace="production", 
    config_files=["config.yaml"]
)

# Plus standard Pydantic usage works too
settings = AppSettings()  # Simple instantiation
settings = AppSettings(debug=True, app_name="TestApp")  # Direct params
```

## Migration Strategies

### Strategy 1: Simple Decorator Replacement

**Best for**: Simple settings classes without complex customization

**Steps**:
1. Change inheritance from `MountainAshBaseSettings` to `BaseSettings`
2. Add `@mountainash_settings()` decorator
3. Remove custom `__init__` method
4. Test existing usage patterns

**Example**:
```python
# Before
class DatabaseSettings(MountainAshBaseSettings):
    def __init__(self, config_files=None, settings_parameters=None, **kwargs):
        super().__init__(config_files=config_files, 
                        settings_parameters=settings_parameters, 
                        **kwargs)
    
    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    database: str = Field(default="app")

# After
@mountainash_settings()
class DatabaseSettings(BaseSettings):
    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    database: str = Field(default="app")
```

### Strategy 2: Feature-Selective Migration

**Best for**: Classes that only need specific mountainash-settings features

**Steps**:
1. Identify which features are actually used
2. Apply decorator with only needed features enabled
3. Remove unused functionality

**Example**:
```python
# Before - using all features
class CacheHeavySettings(MountainAshBaseSettings):
    # Complex initialization with caching
    pass

# After - only enable caching
@mountainash_settings(cache=True, templates=False, multi_format=False)
class CacheHeavySettings(BaseSettings):
    # Much simpler - only caching enabled
    pass
```

### Strategy 3: Gradual Migration with Compatibility Layer

**Best for**: Large codebases with many settings classes

**Steps**:
1. Introduce decorator alongside existing classes
2. Create new classes with decorator
3. Gradually migrate usage
4. Eventually deprecate old classes

**Example**:
```python
# Phase 1: Keep existing class, add new decorator-based version
class LegacyAppSettings(MountainAshBaseSettings):
    # Existing implementation
    pass

@mountainash_settings()
class AppSettings(BaseSettings):
    # New implementation with same fields
    pass

# Phase 2: Use compatibility helper during transition
def get_app_settings(**kwargs):
    """Transition helper - can switch implementation easily"""
    return AppSettings.get_settings(**kwargs)  # New implementation
    # return LegacyAppSettings.get_settings(**kwargs)  # Old implementation

# Phase 3: Direct usage of new class
settings = AppSettings.get_settings(config_files=["config.yaml"])
```

## Step-by-Step Migration Process

### Step 1: Analyze Current Usage

First, identify what features each settings class actually uses and how SettingsParameters is being used:

```bash
# Search for SettingsParameters usage (core infrastructure)
grep -r "SettingsParameters\|get_settings" src/

# Search for template usage
grep -r "post_init\|{.*}" src/

# Search for caching patterns
grep -r "get_settings_manager\|settings_object_cache" src/

# Search for multi-format configs
grep -r "\.yaml\|\.toml\|\.json" src/
```

**Common Patterns to Look For**:
- **SettingsParameters.create()** calls → Preserve this usage pattern exactly
- **settings.get_settings(settings_parameters=...)** → Must work identically
- **Runtime override patterns** → `apply_runtime_overrides()` behavior must be preserved
- Template strings with `{VARIABLE}` placeholders → Need `templates=True`
- Loading from YAML/TOML/JSON files → Need `multi_format=True`
- Custom `post_init()` methods → Need `templates=True` and custom logic

### Step 2: Create Migration Checklist

For each settings class, create a checklist:

```markdown
## AppSettings Migration Checklist

- [ ] SettingsParameters usage: YES (calls with settings_parameters argument)
- [ ] Runtime override patterns: YES (uses kwargs with cached instances)
- [ ] Uses template resolution: YES (log_path field)
- [ ] Uses caching: YES (calls get_settings with namespace)
- [ ] Uses multi-format configs: YES (loads YAML files)
- [ ] Has custom post_init: NO
- [ ] Has complex initialization: NO
- [ ] External dependencies on class structure: CHECK
- [ ] SettingsManager integration: YES (uses get_settings_manager)

**Decorator Configuration**: `@mountainash_settings(cache=True, templates=True, multi_format=True)`
**Critical**: Must preserve all SettingsParameters usage patterns
```

### Step 3: Implement Migration

**Basic Migration Template**:
```python
# 1. Change imports
from pydantic_settings import BaseSettings  # Instead of MountainAshBaseSettings
from mountainash_settings import mountainash_settings

# 2. Apply decorator with needed features
@mountainash_settings(
    cache=True,        # If using get_settings() or SettingsParameters
    templates=True,    # If using {VARIABLE} templates or post_init
    multi_format=True, # If loading YAML/TOML/JSON files
    namespace="app"    # Optional: set default namespace
)
# 3. Change inheritance
class AppSettings(BaseSettings):  # Instead of MountainAshBaseSettings
    
    # 4. Remove custom __init__ (decorator handles this)
    # def __init__(self, ...): 
    #     super().__init__(...)
    
    # 5. Keep all field definitions unchanged
    app_name: str = Field(default="MyApp")
    debug: bool = Field(default=False)
    
    # 6. Template fields work the same
    log_path: str = Field(default="logs/{RUNDATE}/app.log")
    
    # 7. Custom post_init still works if needed
    # def post_init(self, reinitialise: bool = False):
    #     # Custom logic here
    #     super().post_init(reinitialise)  # Call template resolution
```

### Step 4: Test Migration

**Test Checklist**:
```python
def test_migrated_settings():
    # Test 1: Direct instantiation works
    settings = AppSettings()
    assert settings.app_name == "MyApp"
    
    # Test 2: Parameter override works  
    settings = AppSettings(debug=True)
    assert settings.debug == True
    
    # Test 3: SettingsParameters usage works identically
    settings_params = SettingsParameters.create(
        settings_class=AppSettings,
        namespace="test",
        config_files=["test.yaml"],
        kwargs={"debug": True}
    )
    settings = AppSettings.get_settings(settings_parameters=settings_params)
    assert settings is not None
    assert settings.debug == True
    
    # Test 4: Individual parameter delegation works
    settings = AppSettings.get_settings(
        settings_namespace="test",
        config_files=["test.yaml"],
        debug=True
    )
    assert settings is not None
    
    # Test 5: Template resolution works
    settings = AppSettings()
    assert "{" not in settings.log_path  # Templates resolved
    
    # Test 6: SettingsParameters caching works
    params1 = SettingsParameters.create(
        settings_class=AppSettings,
        namespace="cache_test",
        config_files=["config.yaml"]
    )
    params2 = SettingsParameters.create(
        settings_class=AppSettings, 
        namespace="cache_test",
        config_files=["config.yaml"]
    )
    
    settings1 = AppSettings.get_settings(settings_parameters=params1)
    settings2 = AppSettings.get_settings(settings_parameters=params2)
    assert settings1 is settings2  # Same cached instance
    
    # Test 7: Runtime overrides work
    params_with_override = SettingsParameters.create(
        settings_class=AppSettings,
        namespace="cache_test", 
        config_files=["config.yaml"],
        kwargs={"debug": True}  # Runtime override
    )
    
    settings_override = AppSettings.get_settings(settings_parameters=params_with_override)
    assert settings_override.debug == True
    # Should share same base cache as settings1/settings2
```

## Common Migration Scenarios

### Scenario 1: Simple Settings Class

**Before**:
```python
class SimpleSettings(MountainAshBaseSettings):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    api_key: str = Field(default="dev-key")
    timeout: int = Field(default=30)
```

**After**:
```python
@mountainash_settings()  # All features enabled by default
class SimpleSettings(BaseSettings):
    api_key: str = Field(default="dev-key")
    timeout: int = Field(default=30)
```

### Scenario 2: Template-Heavy Class

**Before**:
```python
class BatchSettings(MountainAshBaseSettings):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    batch_id: str = Field(default="B001")
    run_date: str = Field(default="20241201")
    input_path: str = Field(default="data/input/{run_date}/batch_{batch_id}/")
    output_path: str = Field(default="data/output/{run_date}/{batch_id}/")
    
    def post_init(self, reinitialise=False):
        super().post_init(reinitialise)
        # Custom logic after template resolution
        self.working_dir = f"tmp/{self.batch_id}_{self.run_date}"
```

**After**:
```python
@mountainash_settings(templates=True)
class BatchSettings(BaseSettings):
    batch_id: str = Field(default="B001")
    run_date: str = Field(default="20241201")
    input_path: str = Field(default="data/input/{run_date}/batch_{batch_id}/")
    output_path: str = Field(default="data/output/{run_date}/{batch_id}/")
    
    # Custom post_init still works
    def post_init(self, reinitialise=False):
        super().post_init(reinitialise)  # Calls template resolution
        self.working_dir = f"tmp/{self.batch_id}_{self.run_date}"
```

### Scenario 3: Performance-Critical Caching

**Before**:
```python
class CachedSettings(MountainAshBaseSettings):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    expensive_computation: str = Field(default="default")
    
    @classmethod
    def get_production_settings(cls):
        return cls.get_settings(
            namespace="production",
            config_files=["production.yaml", "secrets.env"]
        )
```

**After**:
```python
@mountainash_settings(cache=True, namespace="production")
class CachedSettings(BaseSettings):
    expensive_computation: str = Field(default="default")
    
    @classmethod
    def get_production_settings(cls):
        # Same API, enhanced caching
        return cls.get_settings(
            config_files=["production.yaml", "secrets.env"]
        )
```

### Scenario 4: Minimal Feature Usage

**Before**:
```python
class MinimalSettings(MountainAshBaseSettings):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    # Only uses basic Pydantic features
    service_name: str = Field(default="my-service")
    port: int = Field(default=8000)
```

**After**:
```python
# Disable all mountainash features for pure Pydantic behavior
@mountainash_settings(cache=False, templates=False, multi_format=False)
class MinimalSettings(BaseSettings):
    service_name: str = Field(default="my-service")
    port: int = Field(default=8000)
```

## Troubleshooting Common Issues

### Issue 1: Template Resolution Not Working

**Symptom**: Template strings like `{VARIABLE}` not being resolved

**Solution**: Ensure `templates=True` in decorator:
```python
@mountainash_settings(templates=True)  # Enable template resolution
class SettingsWithTemplates(BaseSettings):
    path: str = Field(default="data/{run_id}/output")
```

### Issue 2: Configuration Files Not Loading

**Symptom**: YAML/TOML/JSON files not being loaded

**Solution**: Ensure `multi_format=True` and proper file paths:
```python
@mountainash_settings(multi_format=True)
class SettingsWithFiles(BaseSettings):
    pass

# Usage
settings = SettingsWithFiles(config_files=["config.yaml"])
```

### Issue 3: Caching Not Working

**Symptom**: New instances created instead of cached ones

**Solution**: Use `get_settings()` method with consistent parameters:
```python
@mountainash_settings(cache=True)
class CachedSettings(BaseSettings):
    pass

# Correct - uses caching
settings = CachedSettings.get_settings(namespace="prod")

# Incorrect - bypasses caching  
settings = CachedSettings()
```

### Issue 4: Custom post_init Not Called

**Symptom**: Custom initialization logic not executing

**Solution**: Call `super().post_init()` for template resolution:
```python
@mountainash_settings(templates=True)
class CustomInitSettings(BaseSettings):
    def post_init(self, reinitialise=False):
        super().post_init(reinitialise)  # Enable template resolution
        # Custom logic here
```

## Migration Testing Strategy

### Unit Tests for Migrated Classes
```python
import pytest
from your_module import AppSettings  # Migrated class

class TestMigratedAppSettings:
    
    def test_basic_instantiation(self):
        """Test that basic Pydantic behavior is preserved."""
        settings = AppSettings()
        assert isinstance(settings, BaseSettings)
        assert settings.app_name == "MyApp"
    
    def test_parameter_override(self):
        """Test parameter overrides work."""
        settings = AppSettings(debug=True, app_name="Test")
        assert settings.debug == True
        assert settings.app_name == "Test"
    
    def test_get_settings_compatibility(self):
        """Test that get_settings method works like before."""
        settings = AppSettings.get_settings(
            namespace="test",
            debug=True
        )
        assert settings.debug == True
    
    def test_template_resolution(self):
        """Test template resolution if enabled."""
        settings = AppSettings()
        # Verify templates are resolved (no { } remaining)
        assert "{" not in settings.log_path
    
    def test_config_file_loading(self):
        """Test configuration file loading."""
        settings = AppSettings(config_files=["test_config.yaml"])
        # Verify values loaded from config file
        
    def test_caching_behavior(self):
        """Test caching works if enabled."""
        settings1 = AppSettings.get_settings(namespace="cache_test")
        settings2 = AppSettings.get_settings(namespace="cache_test")
        
        if AppSettings._mountainash_cache_enabled:
            assert settings1 is settings2
        else:
            # If caching disabled, should be different instances
            assert settings1 is not settings2
```

### Integration Tests
```python
def test_migration_compatibility():
    """Test that migrated class works with existing code."""
    
    # Test with existing usage patterns
    settings = AppSettings.get_settings(
        namespace="integration_test",
        config_files=["integration_config.yaml"],
        debug=True
    )
    
    # Verify all expected behavior
    assert settings is not None
    assert hasattr(settings, 'get_settings')
    
    # Test template resolution if used
    if hasattr(settings, 'post_init'):
        settings.post_init()
        # Verify post_init worked correctly
```

## Rollback Strategy

If migration issues occur, you can easily rollback:

### Temporary Rollback
```python
# Temporarily switch back to old implementation
# @mountainash_settings()  # Comment out decorator
class AppSettings(MountainAshBaseSettings):  # Switch back to old inheritance
    # Same field definitions
    pass
```

### Gradual Rollback with Feature Flags
```python
# Use feature flag to switch implementations
USE_NEW_SETTINGS = False  # Set to False to rollback

if USE_NEW_SETTINGS:
    @mountainash_settings()
    class AppSettings(BaseSettings):
        pass
else:
    class AppSettings(MountainAshBaseSettings):
        pass
```

## Migration Timeline Recommendation

### Phase 1 (Weeks 1-2): Preparation
- [ ] Analyze all existing settings classes
- [ ] Identify feature usage patterns
- [ ] Create migration checklists
- [ ] Set up testing framework

### Phase 2 (Weeks 3-4): Pilot Migration
- [ ] Migrate 1-2 simple settings classes
- [ ] Thorough testing of migrated classes
- [ ] Validate all usage patterns work
- [ ] Document any issues and solutions

### Phase 3 (Weeks 5-8): Bulk Migration
- [ ] Migrate remaining settings classes
- [ ] Update all usage sites
- [ ] Run comprehensive integration tests
- [ ] Performance testing

### Phase 4 (Weeks 9-10): Deprecation
- [ ] Mark MountainAshBaseSettings as deprecated
- [ ] Update documentation
- [ ] Plan removal timeline
- [ ] Monitor for any remaining issues

This migration approach ensures a smooth transition while preserving all the valuable functionality that makes mountainash-settings useful.