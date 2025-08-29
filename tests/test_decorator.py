import pytest
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings

from mountainash_settings.decorator import mountainash_settings
from mountainash_settings.settings_parameters import SettingsParameters


class TestMountainAshSettingsDecorator:
    """Test suite for the @mountainash_settings decorator."""
    
    def test_decorator_basic_functionality(self):
        """Test that decorator enhances BaseSettings class with mountainash features."""
        
        @mountainash_settings()
        class TestSettings(BaseSettings):
            debug: bool = Field(default=False)
            name: str = Field(default="test")
        
        # Test feature flags are set
        assert hasattr(TestSettings, '_mountainash_cache_enabled')
        assert hasattr(TestSettings, '_mountainash_templates_enabled')
        assert hasattr(TestSettings, '_mountainash_multi_format_enabled')
        assert hasattr(TestSettings, '_mountainash_namespace')
        
        # Test default feature flags
        assert TestSettings._mountainash_cache_enabled is True
        assert TestSettings._mountainash_templates_enabled is True
        assert TestSettings._mountainash_multi_format_enabled is True
        assert TestSettings._mountainash_namespace is None
    
    def test_decorator_custom_feature_flags(self):
        """Test decorator with custom feature flag settings."""
        
        @mountainash_settings(
            cache=False, 
            templates=False, 
            multi_format=False,
            namespace="custom"
        )
        class TestSettings(BaseSettings):
            debug: bool = Field(default=False)
        
        assert TestSettings._mountainash_cache_enabled is False
        assert TestSettings._mountainash_templates_enabled is False
        assert TestSettings._mountainash_multi_format_enabled is False
        assert TestSettings._mountainash_namespace == "custom"
    
    def test_enhanced_init_basic(self):
        """Test that enhanced __init__ method works with basic parameters."""
        
        @mountainash_settings(cache=False)  # Disable cache for simpler testing
        class TestSettings(BaseSettings):
            debug: bool = Field(default=False)
            name: str = Field(default="test")
        
        # Test basic initialization
        settings = TestSettings()
        assert settings.debug is False
        assert settings.name == "test"
        
        # Test initialization with kwargs
        settings = TestSettings(debug=True, name="custom")
        assert settings.debug is True
        assert settings.name == "custom"
    
    def test_enhanced_init_with_settings_parameters(self):
        """Test enhanced __init__ with SettingsParameters object."""
        
        @mountainash_settings(cache=False)
        class TestSettings(BaseSettings):
            debug: bool = Field(default=False)
            name: str = Field(default="test")
        
        # Create SettingsParameters
        params = SettingsParameters.create(
            namespace="test_namespace",
            settings_class=TestSettings,
            debug=True,
            name="from_params"
        )
        
        # Initialize with settings_parameters
        settings = TestSettings(settings_parameters=params)
        assert settings.debug is True
        assert settings.name == "from_params"
    
    def test_enhanced_init_with_config_files_and_namespace(self):
        """Test enhanced __init__ with config_files and namespace parameters."""
        
        @mountainash_settings(cache=False)
        class TestSettings(BaseSettings):
            debug: bool = Field(default=False)
            name: str = Field(default="test")
        
        # Test with namespace and kwargs
        settings = TestSettings(
            namespace="test_ns",
            debug=True,
            name="namespace_test"
        )
        assert settings.debug is True
        assert settings.name == "namespace_test"
    
    def test_get_settings_classmethod_injection(self):
        """Test that get_settings classmethod is properly injected."""
        
        @mountainash_settings()
        class TestSettings(BaseSettings):
            debug: bool = Field(default=False)
            name: str = Field(default="test")
        
        # Test that get_settings method exists
        assert hasattr(TestSettings, 'get_settings')
        assert callable(TestSettings.get_settings)
        
        # Test basic get_settings usage
        settings = TestSettings.get_settings(debug=True, name="get_settings_test")
        assert isinstance(settings, TestSettings)
        assert settings.debug is True
        assert settings.name == "get_settings_test"
    
    def test_get_settings_with_settings_parameters(self):
        """Test get_settings classmethod with SettingsParameters."""
        
        @mountainash_settings()
        class TestSettings(BaseSettings):
            debug: bool = Field(default=False)
            name: str = Field(default="test")
        
        # Create SettingsParameters
        params = SettingsParameters.create(
            namespace="get_settings_test",
            settings_class=TestSettings,
            debug=True,
            name="params_test"
        )
        
        # Use get_settings with parameters
        settings = TestSettings.get_settings(settings_parameters=params)
        assert isinstance(settings, TestSettings)
        assert settings.debug is True
        assert settings.name == "params_test"
    
    def test_get_settings_type_safety(self):
        """Test that get_settings ensures type safety."""
        
        @mountainash_settings()
        class TestSettings(BaseSettings):
            debug: bool = Field(default=False)
        
        # This should work and return correct type
        settings = TestSettings.get_settings()
        assert isinstance(settings, TestSettings)
        assert type(settings) is TestSettings
    
    def test_decorator_preserves_pydantic_functionality(self):
        """Test that decorated class still works as standard Pydantic BaseSettings."""
        
        @mountainash_settings()
        class TestSettings(BaseSettings):
            debug: bool = Field(default=False)
            count: int = Field(default=10, gt=0)
            name: str = Field(default="test")
        
        # Test model validation still works
        settings = TestSettings(count=5)
        assert settings.count == 5
        
        # Test validation errors still work
        with pytest.raises(ValueError):
            TestSettings(count=-1)  # Should fail gt=0 validation
        
        # Test model_dump works
        data = settings.model_dump()
        assert isinstance(data, dict)
        assert 'debug' in data
        assert 'count' in data
        assert 'name' in data
    
    def test_multiple_decorated_classes(self):
        """Test that multiple decorated classes work independently."""
        
        @mountainash_settings(namespace="class1")
        class Settings1(BaseSettings):
            value1: str = Field(default="default1")
        
        @mountainash_settings(namespace="class2")
        class Settings2(BaseSettings):
            value2: str = Field(default="default2")
        
        # Test they have different namespaces
        assert Settings1._mountainash_namespace == "class1"
        assert Settings2._mountainash_namespace == "class2"
        
        # Test they work independently
        s1 = Settings1(value1="custom1")
        s2 = Settings2(value2="custom2")
        
        assert s1.value1 == "custom1"
        assert s2.value2 == "custom2"
        assert type(s1) is Settings1
        assert type(s2) is Settings2


class TestDecoratorEdgeCases:
    """Test edge cases and error conditions for the decorator."""
    
    def test_decorator_without_parentheses(self):
        """Test using decorator without parentheses (default parameters)."""
        
        @mountainash_settings
        class TestSettings(BaseSettings):
            debug: bool = Field(default=False)
        
        # Should use default parameters
        assert TestSettings._mountainash_cache_enabled is True
        assert TestSettings._mountainash_templates_enabled is True
        assert TestSettings._mountainash_multi_format_enabled is True
        assert TestSettings._mountainash_namespace is None
    
    def test_decorator_with_non_basesettings_class(self):
        """Test that decorator works with classes that inherit from BaseSettings."""
        
        class CustomBaseSettings(BaseSettings):
            custom_field: str = Field(default="custom")
        
        @mountainash_settings()
        class TestSettings(CustomBaseSettings):
            debug: bool = Field(default=False)
        
        settings = TestSettings()
        assert settings.debug is False
        assert settings.custom_field == "custom"
        
        # Feature flags should still be set
        assert hasattr(TestSettings, '_mountainash_cache_enabled')